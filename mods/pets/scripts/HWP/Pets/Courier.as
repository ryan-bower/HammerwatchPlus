// Pet courier (issue #13): in a run, hand bag items to your pet and it takes them home to
// your town stash. The bag's "Send home" hint (hwplib ItemActions, key H by default,
// rebound on the Plus tab: courierkey) puts the hovered item in the pet's satchel; when
// the player menu closes the pet leaves with it (a puff of smoke) and comes back after
// the trip. The items go into the stash the moment they are handed over and the player
// and town are saved together (AGameplayGameMode.SavePlayerAndTown, one SetCharacter),
// so a death, an abort or a lost connection on the way can't lose or copy them.
//
// - Satchel: 1 item, +1 every 5 pet levels (5 at level 20) per trip.
// - Trip: pets.courier_secs (host, default 60 s), 10 % shorter per Fetch rank.
// - The pet must be out and near you (not waiting outside a puzzle room); none in town
//   (the stash is right there). A new floor brings the pet back early.
// - Items land in the stash tab "Pet deliveries" (made on the first delivery; with all
//   10 tabs taken, the last tab).
// - Co-op: the stash and the bag are the owner's own (their own town record); the others
//   only see the pet leave: the owner asks the host (pets.away), which tells everyone
//   (pets.gone) to take down their copy; the return is the owner's ResetPet, whose
//   SetPetType message re-makes it everywhere.
namespace HWP
{
	namespace PetCourier
	{
		const string AWAY = "pets.away"; // owner -> host: {}
		const string GONE = "pets.gone"; // host -> all: { peer }
		const string SMOKE_FX = "effects/generic/other/spawn_smoke_puff.effect";
		const int KEY_DEFAULT = 11; // SDL scancode for H ("home")
		const int RANGE = 300;      // the pet must be this close to take an item

		bool g_on = true;
		int g_tripMs = 60000;   // pets.courier_secs, before Fetch
		int g_handed = 0;       // items in the satchel this trip, not yet gone
		int g_awayMs = 0;       // > 0 while the pet is on its way
		bool g_wasOpen = false; // the player menu was open last frame

		void RefreshSettings()
		{
			g_on = HWP::Settings::GetBool("pets.courier", true);
			g_tripMs = 1000 * clamp(HWP::Settings::GetInt("pets.courier_secs", 60), 1, 3600);
		}

		void Reset()
		{
			g_handed = 0;
			g_awayMs = 0;
			g_wasOpen = false;
		}

		PlayerBase@ Owner(PlayerRecord@ rec)
		{
			return rec is null ? null : cast<PlayerBase>(rec.actor);
		}

		bool PetOut(PlayerBase@ pb)
		{
			return pb !is null && pb.m_pet !is null && pb.m_pet.m_unit.IsValid();
		}

		int Capacity(PlayerRecord@ rec)
		{
			return 1 + HWP::Pets::Level(rec, HWP::Pets::ActivePetId(rec)) / 5;
		}

		int TripMs(PlayerRecord@ rec)
		{
			int fetch = HWP::Pets::Rank(rec, HWP::Pets::ActivePetId(rec), HWP::Pets::Skill::Fetch);
			return g_tripMs * (10 - min(fetch, 5)) / 10;
		}

		// the hint shows: courier on, a run, your pet out and with room in its satchel
		bool CanHand(PlayerRecord@ rec)
		{
			return g_on && HWP::Pets::g_enabled && !g_inTown && rec !is null && rec.local
				&& g_awayMs <= 0 && PetOut(Owner(rec)) && g_handed < Capacity(rec);
		}

		// the stash tab deliveries go to
		TownStashTab@ DeliveryTab()
		{
			if (g_myTownRecord is null || g_myTownRecord.m_townStash is null)
				return null;
			auto stash = g_myTownRecord.m_townStash;
			string name = Resources::GetString(".hwp.pets.courier.tab");
			for (uint i = 0; i < stash.m_tabs.length(); i++)
				if (stash.m_tabs[i].m_name == name)
					return stash.m_tabs[i];
			if (stash.m_tabs.length() < 10) // the stash window's own tab limit
				return stash.CreateTab(name);
			return stash.m_tabs[stash.m_tabs.length() - 1];
		}

		class SendHomeAction : HWP::ItemActions::KeyedAction
		{
			SendHomeAction() { super("pets.courier_key", KEY_DEFAULT); }

			string Id() override { return "courier"; }
			int Order() override { return 30; }

			string Label(Equipment::Equipment@ item) override
			{
				return CanHand(GetLocalPlayerRecord()) ? Resources::GetString(".hwp.pets.courier.send") : "";
			}

			void Do(PlayerRecord@ record, Equipment::Equipment@ item) override
			{
				Hand(record, item);
			}
		}

		void Hand(PlayerRecord@ rec, Equipment::Equipment@ item)
		{
			auto pb = Owner(rec);
			if (!CanHand(rec) || item is null)
				return;
			if (dist(xy(pb.m_pet.m_unit.GetPosition()), xy(pb.m_unit.GetPosition())) > RANGE)
			{
				HWP::Commands::Reply(Resources::GetString(".hwp.pets.courier.far"));
				return;
			}
			auto tab = DeliveryTab();
			if (tab is null || !rec.equipInventory.Remove(item))
				return;
			tab.Add(item);
			g_handed++;
			auto gm = cast<AGameplayGameMode>(g_gameMode);
			if (gm !is null)
				gm.SavePlayerAndTown();
			HWP::Log("pets", "courier: " + item.GetName() + " to the stash tab '" + tab.m_name + "' ("
				+ g_handed + "/" + Capacity(rec) + ")");
			HWP::Commands::Reply(Resources::GetString(".hwp.pets.courier.handed", {
				{ "item", item.GetName() }, { "n", g_handed }, { "max", Capacity(rec) } }));
		}

		bool MenuOpen()
		{
			auto gm = cast<BaseGameMode>(g_gameMode);
			return gm !is null && gm.m_windowManager !is null && gm.m_windowManager.m_objects.length() > 0;
		}

		void Smoke(UnitPtr unit)
		{
			if (unit.IsValid())
				PlayEffect(SMOKE_FX, xy(unit.GetPosition()));
		}

		void TakeDown(PlayerBase@ pb)
		{
			if (!PetOut(pb))
				return;
			Smoke(pb.m_pet.m_unit);
			pb.m_pet.m_unit.Destroy();
			@pb.m_pet = null;
		}

		void Depart(PlayerRecord@ rec)
		{
			auto pb = Owner(rec);
			int n = g_handed;
			g_handed = 0;
			if (!PetOut(pb))
				return;
			g_awayMs = TripMs(rec);
			TakeDown(pb);
			HWP::Net::Request(AWAY, HWP::Net::Empty());
			HWP::Log("pets", "courier: the pet leaves with " + n + " item(s), back in " + (g_awayMs / 1000) + " s");
			HWP::Commands::Reply(Resources::GetString(".hwp.pets.courier.left", { { "n", n }, { "secs", g_awayMs / 1000 } }));
		}

		void Return(PlayerRecord@ rec)
		{
			auto pb = Owner(rec);
			if (pb is null || rec.pet is null)
				return;
			pb.ResetPet(); // SetPetType: the others re-make their copy too
			if (PetOut(pb))
				Smoke(pb.m_pet.m_unit);
			HWP::Log("pets", "courier: the pet is back");
			HWP::Commands::Reply(Resources::GetString(".hwp.pets.courier.back"));
		}

		// every frame, paused or not (the menu pauses a solo game)
		void Tick(int ms, bool paused)
		{
			auto rec = GetLocalPlayerRecord();
			bool open = MenuOpen();
			if (g_handed > 0 && !open && rec !is null)
				Depart(rec);
			g_wasOpen = open;
			if (g_awayMs > 0 && !paused)
			{
				g_awayMs -= ms;
				if (g_awayMs <= 0 && rec !is null)
					Return(rec);
			}
		}

		// host: an owner's pet left; everyone else takes their copy down
		void OnAway(uint8 peer, SValue@ data)
		{
			SValueBuilder b;
			b.PushDictionary();
			b.PushInteger("peer", peer);
			b.PopDictionary();
			HWP::Net::Broadcast(GONE, b.Build());
		}

		void OnGone(SValue@ data)
		{
			int peer = HWP::SV::Int(data, "peer", -1);
			if (peer < 0 || peer == int(Lobby::GetLocalPeer()))
				return;
			auto rec = GetPlayerRecordByPeer(uint8(peer));
			TakeDown(Owner(rec));
		}

		string Status()
		{
			auto rec = GetLocalPlayerRecord();
			if (g_awayMs > 0)
				return Resources::GetString(".hwp.pets.courier.status_away", { { "secs", (g_awayMs + 999) / 1000 } });
			return Resources::GetString(".hwp.pets.courier.status", { { "n", g_handed }, { "max", Capacity(rec) } });
		}

		void Init()
		{
			HWP::Settings::LocalOnly("pets.courier_key");
			auto send = SendHomeAction();
			HWP::ItemActions::Register(send);
			HWP::Options::Register("courierkey", HWP::ItemActions::ActionKeyOption(send, ".hwp.pets.courier.key"));
			HWP::Net::OnRequest(AWAY, HWP::Net::RequestHandler(OnAway));
			HWP::Net::OnEvent(GONE, HWP::Net::EventHandler(OnGone));
		}
	}
}
