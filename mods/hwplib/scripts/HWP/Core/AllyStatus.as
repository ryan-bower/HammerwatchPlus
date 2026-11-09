// HWP::AllyStatus - what one player knows about themselves and the rest of the party has to be
// told: their shield, and their potion count (a drink syncs through PlayerSyncPotion, a refill
// does not: PlayerPotionCharged carries no count, and RefillPotion only refills the local
// Player). A display channel, so it never touches gameplay state.
//
//   HWP::AllyStatus::ReportShield(pool / maxPool); // any shield provider, on the shielded machine
//   float s = HWP::AllyStatus::Shield(record);     // fraction of the bar `record.hp` measures
//   int left = HWP::AllyStatus::PotionsLeft(record);
//
// The owner sends {s, l, m} to the host, which relays it with the owner's peer (HWPEvent carries
// no sender). A shield fraction is not clamped: Bannerlord shields scale from the caster's max
// HP, so an ally's can pass 1. Reporting runs whatever the local party frames setting is, as it
// feeds the other players' screens. A heartbeat covers late joiners and level loads. A peer on
// an older library sends nothing, so its shield reads 0 and its potions use the vanilla sync.
namespace HWP
{
	namespace AllyStatus
	{
		const string REPORT = "allystatus.report"; // client -> host
		const string STATE = "allystatus.state";   // host -> all
		const int THROTTLE_MS = 250;
		const float MIN_CHANGE = 0.005f;
		const int HEARTBEAT_MS = 3000;
		const int CLEANUP_MS = 1000;
		const float MAX_SHIELD = 100.0f;           // sanity bound on a received fraction

		class Entry
		{
			int peer;
			float shield = 0;
			int left = 0;
			int total = 0;
		}

		array<Entry@> g_entries;

		float g_shield = 0;      // this machine's own, as last reported by a provider
		float g_sentShield = 0;
		int g_sentLeft = -1;
		int g_sentTotal = -1;
		int g_throttleC = 0;
		int g_heartbeatC = 0;
		int g_cleanupC = CLEANUP_MS;

		void ReportShield(float fraction)
		{
			g_shield = max(0.0f, fraction);
		}

		Entry@ Find(int peer)
		{
			for (uint i = 0; i < g_entries.length(); i++)
				if (g_entries[i].peer == peer)
					return g_entries[i];
			return null;
		}

		// a local record reads its own live state, not the echo of its last report
		Entry@ Remote(PlayerRecord@ record)
		{
			if (record.local)
				return null;
			return Find(record.peer);
		}

		bool HasReport(PlayerRecord@ record)
		{
			return record !is null && (record.local || Find(record.peer) !is null);
		}

		float Shield(PlayerRecord@ record)
		{
			if (record is null || record.IsDead())
				return 0;
			if (record.local)
				return g_shield;
			auto e = Find(record.peer);
			return e !is null ? e.shield : 0;
		}

		int PotionsMax(PlayerRecord@ record)
		{
			if (record is null)
				return 0;
			Entry@ e = Remote(record);
			return e !is null ? e.total : int(record.currStats.PotionCharges);
		}

		int PotionsLeft(PlayerRecord@ record)
		{
			if (record is null)
				return 0;
			Entry@ e = Remote(record);
			return e !is null ? e.left : max(0, int(record.currStats.PotionCharges) - int(record.potionChargesUsed));
		}

		SValue@ Payload(int peer, float shield, int left, int total)
		{
			SValueBuilder b;
			b.PushDictionary();
			b.PushInteger("p", peer);
			b.PushFloat("s", shield);
			b.PushInteger("l", left);
			b.PushInteger("m", total);
			b.PopDictionary();
			return b.Build();
		}

		// the host: a fresh payload, as Broadcast frees what it is handed and so does Request
		void OnReport(uint8 peer, SValue@ data)
		{
			if (!Network::IsServer())
				return;
			float shield = clamp(HWP::SV::Float(data, "s", 0), 0.0f, MAX_SHIELD);
			HWP::Net::Broadcast(STATE, Payload(peer, shield, max(0, HWP::SV::Int(data, "l", 0)), max(0, HWP::SV::Int(data, "m", 0))));
		}

		void OnState(SValue@ data)
		{
			int peer = HWP::SV::Int(data, "p", -1);
			if (peer < 0)
				return;
			auto e = Find(peer);
			if (e is null)
			{
				@e = Entry();
				e.peer = peer;
				g_entries.insertLast(e);
			}
			e.shield = clamp(HWP::SV::Float(data, "s", 0), 0.0f, MAX_SHIELD);
			e.left = HWP::SV::Int(data, "l", 0);
			e.total = HWP::SV::Int(data, "m", 0);
		}

		bool InParty(int peer)
		{
			for (uint i = 0; i < g_players.length(); i++)
				if (g_players[i].peer == peer)
					return true;
			return false;
		}

		// no leave event: RemovePlayer only sets the record's peer to 255
		void Cleanup()
		{
			for (int i = int(g_entries.length()) - 1; i >= 0; i--)
				if (!InParty(g_entries[i].peer))
					g_entries.removeAt(i);
		}

		void Update(int ms)
		{
			g_cleanupC -= ms;
			if (g_cleanupC <= 0)
			{
				g_cleanupC = CLEANUP_MS;
				Cleanup();
			}

			auto record = GetLocalPlayerRecord();
			if (record is null || record.peer == 255)
				return;
			g_throttleC -= ms;
			g_heartbeatC -= ms;

			int total = record.currStats.PotionCharges;
			int left = max(0, total - int(record.potionChargesUsed));
			bool potions = left != g_sentLeft || total != g_sentTotal;
			bool edge = (g_shield > 0) != (g_sentShield > 0);
			bool moved = abs(g_shield - g_sentShield) > MIN_CHANGE && g_throttleC <= 0;
			if (!potions && !edge && !moved && g_heartbeatC > 0)
				return;

			g_sentShield = g_shield;
			g_sentLeft = left;
			g_sentTotal = total;
			g_throttleC = THROTTLE_MS;
			g_heartbeatC = HEARTBEAT_MS;
			HWP::Net::Request(REPORT, Payload(-1, g_shield, left, total));
		}
	}
}

namespace Modules
{
	// its own module, not a line in CoreModule.as: an older library copy can win that file
	// (docs/modules.md), and this one has to register either way
	class HWPAllyStatusModule : Module
	{
		HWPAllyStatusModule()
		{
			super("hwp-allystatus");
			HWP::Net::OnRequest(HWP::AllyStatus::REPORT, HWP::Net::RequestHandler(HWP::AllyStatus::OnReport));
			HWP::Net::OnEvent(HWP::AllyStatus::STATE, HWP::Net::EventHandler(HWP::AllyStatus::OnState));
		}

		HWP::Guard m_guardUpdateFrame;
		void UpdateFrame(int ms, GameInput& gameInput, MenuInput& menuInput, bool paused) override
		{
			if (m_guardUpdateFrame.Skip("allystatus", "HWPAllyStatusModule.UpdateFrame"))
				return;
			if (m_guardUpdateFrame.Raw())
			{
				GuardedUpdateFrame(ms, gameInput, menuInput, paused);
				m_guardUpdateFrame.Ok();
				return;
			}
			try { GuardedUpdateFrame(ms, gameInput, menuInput, paused); m_guardUpdateFrame.Ok(); }
			catch { m_guardUpdateFrame.Failed(); }
		}

		void GuardedUpdateFrame(int ms, GameInput& gameInput, MenuInput& menuInput, bool paused)
		{
			HWP::AllyStatus::Update(ms);
		}
	}
}
