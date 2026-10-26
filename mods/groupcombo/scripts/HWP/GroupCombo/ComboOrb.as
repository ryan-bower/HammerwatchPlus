// Combo orb: a rare drop from boxes, barrels, sacks and vases that puts whoever
// picks it up into combo at once. The art is the purple orb of the vanilla skill
// point pickup (items/misc/upgrade_skill.unit, base.png 0 96 16 16), which no
// level spawns.
//
// The hook: a pool of one ComboOrbLoot entry (chance groupcombo.orb.permille,
// default 10 = 1 %) appended to the container loot tables. Breakable.DamageEffects
// rolls its table on the host only; the entry is not instanced (CanBeInstanced
// false), so LootTablePool.SpawnLoot runs it once, for the host's record, with the
// break position. It broadcasts ORB_EVENT, and every machine (the host too) gives
// its own player a local orb there when that player has combo unlocked
// (currStats.ComboCountMax > 0, the test GiveCombo makes). So each player gets one
// orb, sees only their own, and nobody can take another's.
//
// The orb unit is netsync none with a plain Pickup: player-only, so only the
// local Player picks it up (husks and pets are not Player), and no pickup-trigger,
// so MiniPet.IsPickupOkay never fetches it (pets take only health, mana and
// experience triggers among plain pickups). While its player is already in combo
// HWPComboOrb.CanApply is false and the orb waits on the floor, like a health
// pickup at full health.

// global namespace: the unit names the effect class as "HWPComboOrb"
class HWPComboOrb : IEffect
{
	HWPComboOrb(UnitPtr unit, SValue& params) {}

	void SetWeaponInformation(uint weapon) {}
	CanEvade IsEvadable(Actor@ attacker) { return CanEvade::Neither; }

	bool Apply(Actor@ owner, UnitPtr target, vec2 pos, vec2 dir, float intensity, bool husk)
	{
		if (!CanApply(owner, target, pos, dir, intensity))
			return false;

		auto plr = cast<Player>(target.GetScriptBehavior());
		plr.GiveCombo();
		HWP::Log("groupcombo", "combo orb picked up: combo " + (plr.m_comboActive ? "on" : "off"));
		return true;
	}

	bool CanApply(Actor@ owner, UnitPtr target, vec2 pos, vec2 dir, float intensity) override
	{
		if (!target.IsValid())
			return false;
		auto plr = cast<Player>(target.GetScriptBehavior());
		return plr !is null && plr.m_record.currStats.ComboCountMax > 0 && !plr.m_comboActive;
	}
}

namespace HWP
{
	namespace GroupCombo
	{
		const string ORB_EVENT = "groupcombo.orb";
		const string ORB_UNIT = "items/hwp/combo_orb.unit";
		// tweak/loot/containers.sval: boxes, crates and barrels (normal and poor),
		// sacks, big vases and urns, small vases
		const array<string> ORB_TABLES = { "barrel_wood_normal", "barrel_wood_poor", "sack", "vase", "vase_small" };

		int g_orbPermille = 10;
		array<ComboOrbLoot@> g_orbEntries;

		class ComboOrbLoot : Item::LootEntry
		{
			ComboOrbLoot(int chance)
			{
				super(chance);
			}

			// once per break, on the host, whoever broke it
			bool CanBeInstanced() override { return false; }

			int SpawnLoot(PlayerRecord@ looter, vec3 pos) override
			{
				DropOrb(pos);
				return 0;
			}
		}

		void SetOrbChance(int permille)
		{
			g_orbPermille = clamp(permille, 0, 1000);
			for (uint i = 0; i < g_orbEntries.length(); i++)
				g_orbEntries[i].m_chance = g_orbPermille;
		}

		// the table's own orb pool when it has one: the tables can outlive a module
		ComboOrbLoot@ FindOrbEntry(Item::LootTable@ table)
		{
			for (uint i = 0; i < table.m_pools.length(); i++)
			{
				auto pool = table.m_pools[i];
				if (pool.m_items.length() == 1)
				{
					auto entry = cast<ComboOrbLoot>(pool.m_items[0]);
					if (entry !is null)
						return entry;
				}
			}
			return null;
		}

		void InstallOrbLoot()
		{
			g_orbEntries.removeRange(0, g_orbEntries.length());
			int added = 0;
			for (uint i = 0; i < ORB_TABLES.length(); i++)
			{
				auto table = Item::GetLootTable(ORB_TABLES[i]);
				if (table is null)
				{
					HWP::LogError("groupcombo", "no loot table " + ORB_TABLES[i] + " for the combo orb");
					continue;
				}

				auto entry = FindOrbEntry(table);
				if (entry is null)
				{
					SValueBuilder b;
					b.PushDictionary();
					b.PushArray("drops");
					b.PopArray();
					b.PopDictionary();
					auto pool = Item::LootTablePool(b.Build());
					@entry = ComboOrbLoot(g_orbPermille);
					pool.m_items.insertLast(entry);
					table.m_pools.insertLast(pool);
					added++;
				}
				g_orbEntries.insertLast(entry);
			}
			SetOrbChance(g_orbPermille);
			HWP::Log("groupcombo", "combo orb in " + g_orbEntries.length() + " breakable loot tables (" + added + " new), " + g_orbPermille + " per mille");
		}

		// host: one orb for every player, at pos
		void DropOrb(vec3 pos)
		{
			SValueBuilder b;
			b.PushDictionary();
			b.PushFloat("x", pos.x);
			b.PushFloat("y", pos.y);
			b.PopDictionary();
			HWP::Net::Broadcast(ORB_EVENT, b.Build());
		}

		// every machine: the local player's own orb, when combo is unlocked
		void OnOrb(SValue@ data)
		{
			float x = HWP::SV::Float(data, "x", 0);
			float y = HWP::SV::Float(data, "y", 0);
			string at = int(x) + "," + int(y);

			auto rec = GetLocalPlayerRecord();
			if (rec is null || g_inTown)
				return;
			if (rec.currStats.ComboCountMax <= 0)
			{
				HWP::Log("groupcombo", "combo orb at " + at + ": none for us, combo is locked");
				return;
			}

			auto prod = Resources::GetUnitProducer(ORB_UNIT);
			if (prod is null)
			{
				HWP::LogError("groupcombo", "cannot load " + ORB_UNIT);
				return;
			}
			prod.Produce(g_scene, vec3(x, y, 0));
			HWP::Log("groupcombo", "combo orb at " + at);
		}

		// the nearest breakable with a loot table within radius of the player
		Breakable@ NearestBreakable(vec3 from, float radius)
		{
			Breakable@ best = null;
			float bestD = radius * radius;
			auto units = g_scene.FetchUnitsWithBehavior("Breakable", xy(from), int(radius), true);
			for (uint i = 0; i < units.length(); i++)
			{
				auto b = cast<Breakable>(units[i].GetScriptBehavior());
				if (b is null || b.m_lootTable is null)
					continue;
				float d = distsq(xy(units[i].GetPosition()), xy(from));
				if (d < bestD)
				{
					bestD = d;
					@best = b;
				}
			}
			return best;
		}

		// hwp comboorb                 the chance and whether you can get one
		//                              (hwp set groupcombo.orb.permille <0-1000> changes it)
		// hwp comboorb drop            (cheat, host) an orb for everyone, 40 px right of you
		// hwp comboorb break [radius]  (cheat, host) break the nearest breakable that has loot
		void CmdOrb(array<string>@ args)
		{
			string sub = args.length() > 0 ? args[0] : "";
			auto rec = GetLocalPlayerRecord();

			if (sub == "drop" || sub == "break")
			{
				if (!HWP::Cheats::On())
					return;
				if (!Network::IsServer())
				{
					HWP::Commands::Reply("only the host can drop combo orbs");
					return;
				}
				if (rec is null || rec.actor is null)
				{
					HWP::Commands::Reply("no character in the world");
					return;
				}
				vec3 me = rec.actor.m_unit.GetPosition();
				if (sub == "drop")
				{
					DropOrb(me + vec3(40, 0, 0));
					HWP::Commands::Reply("combo orb dropped at " + int(me.x + 40) + "," + int(me.y));
					return;
				}

				float radius = args.length() > 1 && HWP::Commands::IsInteger(args[1]) ? float(parseInt(args[1])) : 200.0f;
				auto b = NearestBreakable(me, radius);
				if (b is null)
				{
					HWP::Commands::Reply("no breakable with loot within " + int(radius));
					return;
				}
				vec3 at = b.m_unit.GetPosition();
				string name = b.m_unit.GetDebugName();
				DamageInfo dmg;
				dmg.PureDamage = 100000;
				@dmg.Attacker = cast<Actor>(rec.actor);
				b.Damage(dmg, xy(at), vec2(1, 0));
				HWP::Commands::Reply("broke " + name + " at " + int(at.x) + "," + int(at.y));
				return;
			}

			bool unlocked = rec !is null && rec.currStats.ComboCountMax > 0;
			HWP::Commands::Reply(Resources::GetString(".hwp.groupcombo.orb.status", {
				{ "permille", "" + g_orbPermille }, { "tables", "" + g_orbEntries.length() },
				{ "unlocked", unlocked ? "yes" : "no" } }));
		}
	}
}
