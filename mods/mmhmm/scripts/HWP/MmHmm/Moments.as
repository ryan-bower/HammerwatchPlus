// The other Mm-hmm! moments besides the crit (that one is the modifier's own trigger,
// modifiers_mmhmm.sval). None of them has a vanilla hook, so the local character is polled
// with the hat check (every CHECK_MS) and its counters compared with the last poll:
// - a well or fountain drunk from: run stat wells-used (WorldScript/Well.as Use);
// - an Ace chest opened (mods/keys: its OnUnlocked counts the local player's in GlobalCache
//   hwp_keys_aces_opened; vanilla's chest-unlocked-<key> stat is not defined for "ace");
// - a secret room opened: run stat secrets-found (WorldScript/Player/SecretFound.as runs on
//   every peer: a party moment, so it says it for whoever in the party wears the hat; the
//   few secret prefabs without SecretFound are missed);
// - a trinket set completed: the trinkets owned per set reaching the set's m_totItems
//   (owning a trinket counts, as PlayerRecord.RefreshModifiers counts them);
// - the last orb of an orb tree: a pickedTempSkills entry going up to the tree's size,
//   only for trees of more than one orb.
// The first poll on a level only takes the counts, so nothing fires for what the
// character already had. The revive is HWPMmHmmCorpse (Corpse.as).
namespace HWP
{
	namespace MmHmm
	{
		class Seen
		{
			bool seeded = false;
			int wells = 0, aces = 0, secrets = 0;
			array<Item::TrinketSet@> sets;
			array<int> setCounts;
			dictionary orbs; // pickedTempSkills id -> level
		}
		Seen g_seen;

		int RunStat(PlayerRecord@ rec, const string &in id)
		{
			return rec.statsRun is null ? 0 : int(rec.statsRun.GetStatCurr(HashString(id)));
		}


		// sets whose owned count reached their size since the last poll
		int SetsCompleted(PlayerRecord@ rec, bool seeding)
		{
			array<Item::TrinketSet@> sets;
			array<int> counts;
			if (rec.trinketInventory !is null)
			{
				for (uint i = 0; i < rec.trinketInventory.m_items.length(); i++)
				{
					auto set = rec.trinketInventory.m_items[i].m_set;
					if (set is null)
						continue;
					int k = sets.findByRef(set);
					if (k < 0)
					{
						sets.insertLast(set);
						counts.insertLast(1);
					}
					else
						counts[k]++;
				}
			}
			int done = 0;
			for (uint i = 0; i < sets.length() && !seeding; i++)
			{
				int k = g_seen.sets.findByRef(sets[i]);
				int before = k < 0 ? 0 : g_seen.setCounts[k];
				if (counts[i] >= sets[i].m_totItems && before < sets[i].m_totItems)
					done++;
			}
			g_seen.sets = sets;
			g_seen.setCounts = counts;
			return done;
		}

		// orb trees of more than one orb taken to their last orb since the last poll
		int TreesFinished(PlayerRecord@ rec, bool seeding)
		{
			int done = 0;
			auto keys = rec.pickedTempSkills.getKeys();
			for (uint i = 0; i < keys.length(); i++)
			{
				int lvl = 0, before = 0;
				rec.pickedTempSkills.get(keys[i], lvl);
				if (!g_seen.orbs.get(keys[i], before))
					before = 0;
				g_seen.orbs.set(keys[i], lvl);
				if (seeding || lvl <= before || rec.playerClass is null)
					continue;
				auto def = rec.playerClass.GetSkillDef(HashString(keys[i]));
				if (def is null || def.m_parentSkill is null || def.m_levelParams.length() <= 1)
					continue;
				if (rec.GetSkillLevel(def) >= int(def.m_levelParams.length()))
					done++;
			}
			// a new run clears the picks
			if (keys.length() == 0)
				g_seen.orbs.deleteAll();
			return done;
		}

		void Moments(PlayerRecord@ rec)
		{
			if (rec is null)
				return;
			bool seeding = !g_seen.seeded;
			g_seen.seeded = true;
			// a counter that went up since the last poll (a new run resets the run stats: re-taken)
			int wells = RunStat(rec, "wells-used"), aces = parseInt(GlobalCache::Get("hwp_keys_aces_opened")), secrets = RunStat(rec, "secrets-found");
			bool well = wells > g_seen.wells, ace = aces > g_seen.aces, secret = secrets > g_seen.secrets;
			g_seen.wells = wells;
			g_seen.aces = aces;
			g_seen.secrets = secrets;
			int sets = SetsCompleted(rec, seeding);
			int trees = TreesFinished(rec, seeding);
			if (seeding || !Wearing(rec))
				return;
			if (well)
				Say("well");
			if (ace)
				Say("ace chest");
			if (secret)
				Say("secret room", "secret"); // one voice for the party, however many wear it
			if (sets > 0)
				Say("trinket set");
			if (trees > 0)
				Say("last orb");
		}
	}
}
