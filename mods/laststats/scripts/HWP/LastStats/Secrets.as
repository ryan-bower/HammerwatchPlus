// Secrets found count for the player who opened the secret (issue #98).
//
// Vanilla's WorldScript/Player/SecretFound.as runs on every machine (ServerExecute on the
// host, ClientExecute on each client) and adds secrets-found to that machine's local player,
// so every member of a party was credited. The secret rooms (prefabs/<theme>/secret_small_*)
// open when their breakable wall (doodads/walls/<theme>/_secret_dst_*.unit, class Breakable)
// is destroyed: a UnitDestroyedTrigger, registered on the host only, runs SecretFound.
// The opener is the player whose hit broke that wall. The host's Breakable.DamageEffects
// knows the attacker (its own player's hit, or a client's through UnitDamagedByMe /
// UnitDamagedByPlayer), so the Breakable.as override notes it right before the wall is
// destroyed (NoteBreak), and the SecretFound.as override reads it (SecretOpener) and sends the
// opener's peer to every client. A hit with no player behind it (a summon's, a trap's) goes
// to the living player nearest the wall.
//
// On every machine: the opener's machine books Stats::Add(secrets-found, 1, its record) as
// vanilla did; the others book Stats::Add(secrets-found, 1, null), which counts only the
// town's total (the guild's Secrets Found accomplishment keeps counting every secret, as
// in vanilla) and not the character or run stats. GlobalCache SECRETS_OPENED counts every
// secret the party opened on each machine, for mods/mmhmm's party moment.
namespace HWP
{
	namespace LastStats
	{
		const string SECRETS_OPENED = "hwp_secrets_opened"; // GlobalCache, a count as text (mods/mmhmm)
		const int BREAK_MS = 2000; // a SecretFound this soon after a secret wall broke is that wall's

		int g_breakPeer = -1;   // the player who broke the last secret wall, -1 none
		vec2 g_breakPos;
		int g_breakTime = -1;

		bool IsSecretWall(UnitPtr u)
		{
			if (!u.IsValid())
				return false;
			auto prod = u.GetUnitProducer();
			if (prod is null)
				return false;
			string p = prod.GetResourceName();
			return p.findFirst("_secret_dst_") >= 0 && p.findFirst("_corpse") < 0;
		}

		// Breakable.as override, every breakable that breaks, before it is destroyed
		void NoteBreak(UnitPtr unit, Actor@ attacker)
		{
			if (!Network::IsServer() || !IsSecretWall(unit))
				return;
			g_breakPeer = -1;
			auto player = cast<PlayerBase>(attacker);
			if (player !is null && player.m_record !is null)
				g_breakPeer = int(player.m_record.peer);
			g_breakPos = xy(unit.GetPosition());
			g_breakTime = g_scene.GetTime();
		}

		int NearestPeer(vec2 pos)
		{
			int best = -1;
			float bestSq = 0;
			for (uint i = 0; i < g_players.length(); i++)
			{
				auto rec = g_players[i];
				if (rec is null || rec.peer == 255 || rec.IsDead() || rec.actor is null)
					continue;
				float d = distsq(xy(rec.actor.m_unit.GetPosition()), pos);
				if (best < 0 || d < bestSq)
				{
					best = int(rec.peer);
					bestSq = d;
				}
			}
			return best;
		}

		// host: the peer of the player who opened the secret, -1 when nobody can be named
		int SecretOpener(vec3 scriptPos)
		{
			bool recent = g_breakTime >= 0 && g_scene.GetTime() - g_breakTime <= BREAK_MS;
			int peer = -1;
			string how;
			if (recent && g_breakPeer >= 0)
			{
				peer = g_breakPeer;
				how = "broke the wall";
			}
			else
			{
				peer = NearestPeer(recent ? g_breakPos : xy(scriptPos));
				how = recent ? "nearest the wall" : "nearest the secret";
			}
			g_breakTime = -1;
			HWP::Log("laststats", "secret found: peer " + peer + " (" + how + ")");
			return peer;
		}

		// every machine: the host's opener (-1: unknown, everyone counts it as vanilla did)
		void CreditSecret(int peer)
		{
			GlobalCache::Set(SECRETS_OPENED, "" + (parseInt(GlobalCache::Get(SECRETS_OPENED)) + 1));
			auto local = GetLocalPlayerRecord();
			if (local is null)
				return;
			if (peer < 0 || int(local.peer) == peer)
				Stats::Add(HashString("secrets-found"), 1, local);
			else
				Stats::Add(HashString("secrets-found"), 1, null); // the town's total only
		}
	}
}
