// HWP::Luck - the Luck stat (docs/design/luck.md).
//
// Luck is a vanilla custom stat ("hwp-luck", Modifiers::CustomStat, read from
// PlayerStats.m_customStats the way the Firearms class reads hwp-ele-chance), so
// anything that carries modifiers can give it: the rolled gear affixes in
// tweak/hwp/modifiers_luck.sval ("of Fortune": +5 / +10 / +20 on armour), the Rabbit's
// Foot trinket (tweak/hwp/trinkets_luck.sval), and any buff whose modifiers list holds
//
//   <dict>
//     <string name="class">Modifiers::CustomStat</string>
//     <string name="name">hwp-luck</string>
//     <float name="add">25</float>
//   </dict>
//
// (herbs, food, fish: an ActorBuffDef or a MissionBuff, both go through
// PlayerRecord.RefreshModifiers). Factor(plr) = 1 + luck / 100 is what drop code
// multiplies the weight of its rarer outcomes by: SpawnLoot rolls a loot table with
// every entry lighter than the pool's heaviest one scaled by the factor (a pool pays
// nothing at its vanilla odds first, so Luck shifts what drops, it never makes more
// things drop); Chance(base, factor) scales a plain drop chance, capped at 1;
// TierUpChance(factor) is the abyss' chance of paying the next reward tier.
// Shared host-rolled drops roll once and everyone gets what that roll picked. A drop
// someone opens (a chest, a strongbox) rolls at the opener's Luck (OpenerFactor), so the
// luckiest player should open them; one nobody opens (an abyss crack, the keys budget's
// accept roll) at the lobby's average (PartyFactor). Each peer reports its own Luck to the
// host (REPORT), since the host's copy of a client's record may lack the client's buffs.
//
// Cheats (e_cheats 1): `hwp luck <n>` sets a cheat luck value (an exact modifier added
// in the PlayerRecordRefreshModifiers hook), `hwp luck buff [n] [ms]` applies the Luck buff
// (tweak/hwp/buffs_luck.sval:hwp_luck_charm, +n for 10 min or ms, n up to 100; GiveBuff() is
// what herbs, food and fish call for the same buff), `hwp luck item
// <tier>` equips a chest piece carrying only the tier's affix, `hwp luck roll <table|
// chance <pct>|tier> <n> [luck]` rolls n times without spawning and counts the outcomes.
// `hwp luck` alone prints the status line: "Luck: N (factor F) ..." ([HWP:luck] too).
namespace HWP
{
	namespace Luck
	{
		const string STAT = "hwp-luck";
		const string BUFF = "tweak/hwp/buffs_luck.sval:hwp_luck_charm";
		const string MOD_PREFIX = "hwp_mod_luck_";   // + 1..3 (uncommon, rare, epic)
		const string TRINKET = "hwp_trinket_rabbit_foot";
		const int TIERS = 3;
		const float TIER_UP_PER_FACTOR = 0.25f;      // abyss: next tier chance per +1.0 factor
		const float TIER_UP_CAP = 0.75f;

		float g_cheat = 0;                           // hwp luck <n>
		array<Modifiers::IModifier@> g_cheatMods;    // the modifier carrying g_cheat
		ModifierProvider@ g_provider;

		// ---- reading ---------------------------------------------------------

		float OfRecord(PlayerRecord@ rec) { return HWP::CustomStat(rec, STAT); }

		// total luck points of a player (gear + trinkets + buffs + cheat); 0 for null
		float Of(PlayerBase@ plr)
		{
			if (plr is null)
				return 0;
			return OfRecord(plr.m_record);
		}

		float FactorOf(float luck) { return max(0.0f, 1.0f + luck / 100.0f); }

		// 1.0 + luck / 100 (1.0 for null or no luck): what rarer outcomes are weighted by
		float Factor(PlayerBase@ plr) { return FactorOf(Of(plr)); }
		float FactorRecord(PlayerRecord@ rec) { return FactorOf(OfRecord(rec)); }

		// The average luck of everyone in the lobby (each as their own machine reported
		// it, OpenerLuck), for the shared drops nobody opens.
		float PartyLuck()
		{
			float sum = 0;
			int n = 0;
			for (uint i = 0; i < g_players.length(); i++)
			{
				if (g_players[i] is null || g_players[i].peer == 255)
					continue;
				sum += OpenerLuck(g_players[i]);
				n++;
			}
			if (n == 0)
			{
				auto me = GetLocalPlayerRecord();
				return me is null ? 0.0f : OfRecord(me);
			}
			return sum / float(n);
		}

		float PartyFactor() { return FactorOf(PartyLuck()); }

		// ---- the opener's Luck (shared drops) ----------------------------------

		// Each player's own machine is the authority on its Luck: the host's copy of a
		// client's record may lack the client's buffs and cheat value. Every peer reports
		// its Luck to the host on a change and every REPORT_EVERY_MS; the host keeps the
		// last value per peer.
		const string REPORT = "hwp.luck.report";
		const int REPORT_EVERY_MS = 5000;
		array<float> g_reported(256, 0.0f);
		array<bool> g_hasReport(256, false);
		int g_reportTimer = 0;
		float g_lastSent = -999999;

		void OnReport(uint8 peer, SValue@ data)
		{
			g_reported[peer] = HWP::SV::Float(data, "luck");
			g_hasReport[peer] = true;
		}

		// every peer, from the module's UpdateFrame
		void ReportTick(int ms)
		{
			auto rec = GetLocalPlayerRecord();
			if (rec is null)
				return;
			float luck = OfRecord(rec);
			KeepPartyScalar();
			g_reportTimer += ms;
			if (luck == g_lastSent && g_reportTimer < REPORT_EVERY_MS)
				return;
			g_reportTimer = 0;
			g_lastSent = luck;
			SValueBuilder b;
			b.PushDictionary();
			b.PushFloat("luck", luck);
			b.PopDictionary();
			HWP::Net::Request(REPORT, b.Build());
		}

		// host: the party's average Luck as a run scalar, for floor generation (LuckFloors.as)
		void KeepPartyScalar()
		{
			if (!Network::IsServer())
				return;
			float party = float(int(PartyLuck() * 10.0f + 0.5f)) / 10.0f;
			if (g_scalars.Get(PARTY_SCALAR) != party)
				g_scalars.Set(PARTY_SCALAR, party);
		}

		// a player's Luck as the host should count it: the value their own machine
		// reported, or their record here until a report came (the local player's own)
		float OpenerLuck(PlayerRecord@ rec)
		{
			if (rec is null)
				return 0;
			if (!rec.local && g_hasReport[rec.peer])
				return g_reported[rec.peer];
			return OfRecord(rec);
		}

		float OpenerFactor(PlayerRecord@ rec) { return FactorOf(OpenerLuck(rec)); }

		// " (opener <name>, Luck <n>)" for the drop sites' log lines
		string OpenerNote(PlayerRecord@ rec)
		{
			if (rec is null)
				return " (no opener)";
			float luck = OpenerLuck(rec);
			return " (opener " + rec.GetName() + ", Luck " + int(luck + (luck < 0 ? -0.5f : 0.5f)) + ")";
		}

		// ---- the formulas ----------------------------------------------------

		// a plain drop chance (0..1) scaled by luck, capped at 1
		float Chance(float base, float factor) { return clamp(base * factor, 0.0f, 1.0f); }
		bool Roll(float base, float factor) { return randf() < Chance(base, factor); }

		// abyss: the chance the reward goes up one tier: 25 % per +1.0 of factor, at most 75 %
		float TierUpChance(float factor) { return clamp((factor - 1.0f) * TIER_UP_PER_FACTOR, 0.0f, TIER_UP_CAP); }

		// The luck-weighted pick of one loot pool: the index into pool.m_items, or -1 for
		// nothing. Vanilla rolls randi(1000) against the entries' chances (a pool whose
		// chances sum below 1000 pays nothing the rest of the time). Here the pool pays
		// nothing at its vanilla odds first; when it does pay, every entry lighter than the
		// pool's heaviest one has its chance multiplied by factor for the pick between them,
		// so Luck changes which entry drops, never how often one does. The exception is a
		// pool of dye buckets only (the chests' dye pool, tweak/loot/chests.sval): it pays at
		// its vanilla share times the factor (Chance), so Luck finds more dyes.
		int RollPool(Item::LootTablePool@ pool, float factor)
		{
			if (pool is null || pool.m_items.length() == 0)
				return -1;
			int top = 0;
			int sum = 0;
			for (uint i = 0; i < pool.m_items.length(); i++)
			{
				top = max(top, pool.m_items[i].m_chance);
				sum += pool.m_items[i].m_chance;
			}
			float pays = float(sum) / float(max(1000, sum));
			if (DyePool(pool))
				pays = Chance(pays, factor);
			if (sum <= 0 || randf() >= pays)
				return -1;
			array<float> w;
			float total = 0;
			for (uint i = 0; i < pool.m_items.length(); i++)
			{
				float c = float(pool.m_items[i].m_chance);
				if (pool.m_items[i].m_chance < top)
					c *= factor;
				w.insertLast(c);
				total += c;
			}
			float r = randf() * total;
			for (uint i = 0; i < w.length(); i++)
			{
				r -= w[i];
				if (r < 0)
					return int(i);
			}
			// float rounding past the last entry: the pool still pays
			for (int i = int(w.length()) - 1; i >= 0; i--)
				if (w[i] > 0)
					return i;
			return -1;
		}

		// every entry a unit under items/dyes/ (the dye buckets)
		bool DyePool(Item::LootTablePool@ pool)
		{
			for (uint i = 0; i < pool.m_items.length(); i++)
			{
				auto unit = cast<Item::LootUnit>(pool.m_items[i]);
				if (unit is null || unit.m_unitProducerID.findFirst("items/dyes/") != 0)
					return false;
			}
			return pool.m_items.length() > 0;
		}

		// Item::LootTable::SpawnLoot with RollPool in place of the vanilla pick: the
		// rest (conditionals, spread, the raycast, one spawn per player for instanced
		// entries, shared entries once) is the vanilla LootTablePool::SpawnLoot. Server
		// only, like the vanilla call. Logs the picks as "[HWP:luck] loot <table> ...".
		int SpawnLoot(Item::LootTable@ table, PlayerBase@ looter, vec3 pos, float factor, const string &in what = "")
		{
			PlayerRecord@ rec;
			if (looter !is null)
				@rec = looter.m_record;
			return SpawnLootFor(table, rec, pos, factor, what, false);
		}

		// SpawnLoot for a record; personal: the instanced entries (gear, trinkets) spawn
		// for that player alone instead of once per player in the lobby (a catch, not a
		// chest). Shared entries (gold, valuables, quest items) still spawn once, through
		// the host's own record: vanilla LootItem.SpawnLoot drops a shared item only for
		// a local looter on the server, so a client looter would get none.
		int SpawnLootFor(Item::LootTable@ table, PlayerRecord@ rec, vec3 pos, float factor, const string &in what = "", bool personal = false)
		{
			if (table is null || table.m_pools.length() == 0)
				return 0;
			if (rec is null)
				@rec = GetLocalPlayerRecord();
			if (rec is null)
				return 0;
			int numSpawned = 0;
			string picks;
			for (uint p = 0; p < table.m_pools.length(); p++)
			{
				auto pool = table.m_pools[p];
				if (!CheckConditionals(pool.m_conditionals, rec.actor))
				{
					picks += " -";
					continue;
				}
				vec3 spawnPos = pos + pool.m_offset;
				spawnPos.x += (randf() - 0.5f) * pool.m_spread.x;
				spawnPos.y += (randf() - 0.5f) * pool.m_spread.y;
				spawnPos.z += randf() * pool.m_spread.z;
				int pick = RollPool(pool, factor);
				picks += " " + pick;
				if (pick < 0)
					continue;
				auto entry = pool.m_items[pick];
				auto rayRes = g_scene.RaycastClosest(xy(pos), xy(spawnPos), ~0, RaycastType::Any);
				vec3 at = vec3(rayRes.point.x, rayRes.point.y, spawnPos.z);
				if (personal)
				{
					// counted per rolled entry: a LootUnit (gold, pickups) returns -1
					auto who = rec;
					if (!entry.CanBeInstanced())
						@who = GetLocalPlayerRecord();
					if (who !is null)
					{
						entry.SpawnLoot(who, at);
						numSpawned++;
					}
					continue;
				}
				for (uint i = 0; i < g_players.length(); i++)
				{
					auto plr = g_players[i];
					if (plr is null || plr.peer == 255)
						continue;
					if (!entry.CanBeInstanced() && !plr.local)
						continue;
					int spawned = entry.SpawnLoot(plr, at);
					if (plr.local)
						numSpawned += spawned;
				}
			}
			HWP::Log("luck", "loot " + what + " factor " + Fmt(factor) + " picks" + picks);
			return numSpawned;
		}

		// n rolls of a pool at a factor, without spawning: counts per entry, the last
		// count the empty outcome
		array<int>@ Simulate(Item::LootTablePool@ pool, float factor, int n)
		{
			array<int> counts(pool.m_items.length() + 1, 0);
			for (int k = 0; k < n; k++)
			{
				int pick = RollPool(pool, factor);
				counts[pick < 0 ? pool.m_items.length() : uint(pick)]++;
			}
			return counts;
		}

		string Fmt(float f) { return "" + (float(int(f * 100.0f + 0.5f)) / 100.0f); }

		// The one line every drop site logs before it rolls, so a test can read the
		// factor it used: "[HWP:<module>] luck x1.5 <what>"
		void LogRoll(const string &in module, const string &in what, float factor)
		{
			HWP::Log(module, "luck x" + Fmt(factor) + " " + what);
		}

		// The timed Luck buff (BUFF, +points for durationMs, the def's 10 minutes when
		// -1), for herbs, food and fish: the buff's add lerps 0..100 by intensity, so
		// points is capped at 100. Applying it again refreshes the one already running
		// to the longer duration and the stronger of the two, so a weaker source never
		// lowers it. ActorBuffList.Add (same def) calls ActorBuff.Refresh, which averages
		// the intensities on every peer the buff is sent to, so the new application
		// carries 2 * stronger - running: the average is the stronger one. Server or
		// local, as the caller's ApplyBuff would be. False when the player or the buff
		// def is missing.
		// the Luck buff already on the player, or null
		ActorBuff@ RunningBuff(PlayerBase@ plr, ActorBuffDef@ def)
		{
			auto list = plr.GetBuffList();
			if (list is null)
				return null;
			for (uint i = 0; i < list.m_buffs.length(); i++)
				if (list.m_buffs[i].m_def is def)
					return list.m_buffs[i];
			return null;
		}

		bool GiveBuff(PlayerBase@ plr, float points, int durationMs = -1, const string &in why = "")
		{
			if (plr is null || plr.m_record is null)
				return false;
			auto def = LoadActorBuff(BUFF);
			if (def is null)
			{
				HWP::LogError("luck", "missing buff " + BUFF);
				return false;
			}
			float n = clamp(points, 0.0f, 100.0f);
			float intensity = n / 100.0f;
			auto running = RunningBuff(plr, def);
			if (running !is null)
			{
				float keep = max(running.m_intensity, intensity);
				intensity = 2.0f * keep - running.m_intensity;
				n = keep * 100.0f;
			}
			plr.ApplyBuff(ActorBuff(plr, def, intensity, false, 0, durationMs));
			if (plr.m_record.local)
			{
				plr.m_record.RefreshModifiers();
				plr.m_record.RefreshStats();
			}
			HWP::Log("luck", "buff +" + int(n + 0.5f) + (running is null ? "" : " (refreshed)") + " for " + (durationMs < 0 ? def.m_duration : durationMs) + " ms" + (why.isEmpty() ? "" : " (" + why + ")"));
			return true;
		}

		// ---- the cheat modifier (hwp luck <n>) --------------------------------

		array<Modifiers::IModifier@>@ CheatModifiers()
		{
			g_cheatMods.removeRange(0, g_cheatMods.length());
			SValueBuilder b;
			b.PushDictionary();
			b.PushString("name", STAT);
			b.PushFloat("add", g_cheat);
			b.PopDictionary();
			auto data = b.Build();
			g_cheatMods.insertLast(Modifiers::CustomStat(UnitPtr(), data));
			return g_cheatMods;
		}

		void RefreshLocal()
		{
			auto rec = GetLocalPlayerRecord();
			if (rec is null)
				return;
			rec.RefreshModifiers();
			rec.RefreshStats();
		}

		// ---- commands ---------------------------------------------------------

		void Reply(const string &in text) { HWP::Commands::Reply(text); }

		bool CheatsOn()
		{
			if (GetVarBool("e_cheats"))
				return true;
			Reply("cheats are off - type e_cheats 1 in the console first");
			return false;
		}

		float NumArg(array<string>@ args, uint i, float def)
		{
			if (i >= args.length())
				return def;
			if (HWP::Commands::IsInteger(args[i]))
				return float(parseInt(args[i]));
			if (HWP::Commands::IsDecimal(args[i]))
				return parseFloat(args[i]);
			return def;
		}

		// the stat's tooltip text (the character tab's bar, the Mods tab's row)
		string TooltipText(float luck)
		{
			return Resources::GetString(".hwp.luck.stat.tip", {
				{ "luck", int(luck + (luck < 0 ? -0.5f : 0.5f)) }, { "factor", Fmt(FactorOf(luck)) },
				{ "party", Fmt(PartyFactor()) } });
		}

		string Status(PlayerRecord@ rec)
		{
			float luck = OfRecord(rec);
			return Resources::GetString(".hwp.luck.status", {
				{ "luck", int(luck + (luck < 0 ? -0.5f : 0.5f)) }, { "factor", Fmt(FactorOf(luck)) },
				{ "party", Fmt(PartyFactor()) }, { "cheat", int(g_cheat + 0.5f) } });
		}

		void CmdStatus()
		{
			auto rec = GetLocalPlayerRecord();
			if (rec is null)
			{
				Reply("no character in the world - load one first");
				return;
			}
			rec.RefreshStats();
			string line = Status(rec);
			Reply(line);
			HWP::Log("luck", HWP::Commands::Plain(line));
		}

		void CmdBuff(array<string>@ args)
		{
			if (!CheatsOn())
				return;
			auto rec = GetLocalPlayerRecord();
			PlayerBase@ plr;
			if (rec !is null)
				@plr = cast<PlayerBase>(rec.actor);
			if (plr is null)
			{
				Reply("no character in the world - load one first");
				return;
			}
			float n = clamp(NumArg(args, 1, 25), 0.0f, 100.0f);
			int ms = int(NumArg(args, 2, -1));
			if (!GiveBuff(plr, n, ms, "hwp luck buff"))
			{
				Reply("missing buff " + BUFF);
				return;
			}
			Reply(Resources::GetString(".hwp.luck.buffed", { { "n", int(n + 0.5f) } }));
			HWP::Log("luck", "buff applied; " + HWP::Commands::Plain(Status(rec)));
		}

		void CmdItem(array<string>@ args)
		{
			if (!CheatsOn())
				return;
			auto rec = GetLocalPlayerRecord();
			if (rec is null || rec.actor is null)
			{
				Reply("no character in the world - load one first");
				return;
			}
			int tier = clamp(int(NumArg(args, 1, 1)), 1, TIERS);
			auto mod = Equipment::ItemModifier::Get(HashString(MOD_PREFIX + tier));
			if (mod is null)
			{
				Reply("missing item modifier " + MOD_PREFIX + tier);
				return;
			}
			Equipment::Generator gen;
			gen.m_slots = Equipment::Slot::Chest;
			gen.m_ilvl = 1;
			gen.m_qualities = Item::Quality::Common;
			// a base whose requirement the character fails (chest_dex_t1a on a paladin) adds no
			// modifiers (PlayerRecord.RefreshModifiers skips gear that fails MayEquip), so
			// generate until the base is one the character can wear
			Equipment::Item@ item = null;
			for (int i = 0; i < 64 && item is null; i++)
			{
				@item = gen.GenerateItem();
				if (item !is null && !rec.equipped.MayEquip(item))
					@item = null;
			}
			if (item is null)
			{
				Reply("no chest armour this character can wear");
				return;
			}
			item.quality = Item::Quality::Uncommon;
			item.mods.removeRange(0, item.mods.length());
			item.mods.insertLast(mod);
			item.Finalize(item.intensity, int(item.itemLevel), int(item.upgradeLevel), item.colorA, item.colorB);
			auto unequipped = rec.equipped.Equip(item);
			if (unequipped is item)
			{
				Reply("could not equip " + item.baseItem.m_id);
				return;
			}
			if (unequipped !is null)
				rec.equipInventory.Add(unequipped);
			RefreshLocal();
			Reply(Resources::GetString(".hwp.luck.item", { { "item", item.GetName() }, { "tier", tier } }));
			HWP::Log("luck", "item tier " + tier + " equipped (" + item.baseItem.m_id + "); " + HWP::Commands::Plain(Status(rec)));
		}

		// hwp luck roll <table|chance <pct>|tier> <n> [luck]
		void CmdRoll(array<string>@ args)
		{
			if (!CheatsOn())
				return;
			if (args.length() < 3)
			{
				Reply("usage: hwp luck roll <loot table | chance <pct> | tier | quality | secret | count> <n> [luck]");
				return;
			}
			auto rec = GetLocalPlayerRecord();
			string what = args[1];
			uint at = 2;
			float base = 0;
			if (what == "chance")
			{
				base = NumArg(args, 2, 10) / 100.0f;
				at = 3;
			}
			int n = clamp(int(NumArg(args, at, 1000)), 1, 100000);
			float luck = at + 1 < args.length() ? NumArg(args, at + 1, 0) : (rec is null ? 0.0f : OfRecord(rec));
			float factor = FactorOf(luck);
			string head = "luck roll " + what + (what == "chance" ? " " + int(base * 100 + 0.5f) : "") + " luck " + int(luck + 0.5f) + " factor " + Fmt(factor) + " n " + n;
			if (what == "chance")
			{
				int hits = 0;
				for (int k = 0; k < n; k++)
					if (Roll(base, factor))
						hits++;
				Reply(head + ": hits " + hits);
				return;
			}
			if (what == "tier")
			{
				int ups = 0;
				for (int k = 0; k < n; k++)
					if (randf() < TierUpChance(factor))
						ups++;
				Reply(head + ": ups " + ups);
				return;
			}
			// floors (LuckFloors.as): a blueprint pick among two commons, an uncommon and a
			// rare; the extra secret room; a reward count's lean (LuckyRandf, mean per mille)
			if (what == "quality")
			{
				array<int> quals = { 1, 1, 2, 3 };
				array<int> got(4, 0);
				for (int k = 0; k < n; k++)
					got[quals[PickByQuality(quals, factor)]]++;
				Reply(head + ": common " + got[1] + " uncommon " + got[2] + " rare " + got[3]);
				return;
			}
			if (what == "secret")
			{
				int extra = 0;
				for (int k = 0; k < n; k++)
					if (randf() < SecretRoomChance(factor))
						extra++;
				Reply(head + ": extra rooms " + extra);
				return;
			}
			if (what == "count")
			{
				float sum = 0;
				for (int k = 0; k < n; k++)
					sum += LuckyRandf(factor);
				Reply(head + ": mean " + int(sum / float(n) * 1000.0f + 0.5f) + "/1000");
				return;
			}
			auto table = Item::GetLootTable(what);
			if (table is null)
			{
				Reply("no loot table '" + what + "'");
				return;
			}
			for (uint p = 0; p < table.m_pools.length(); p++)
			{
				auto counts = Simulate(table.m_pools[p], factor, n);
				string line = head + " pool " + p + ":";
				for (uint i = 0; i + 1 < counts.length(); i++)
					line += " e" + i + " " + counts[i];
				line += " none " + counts[counts.length() - 1];
				Reply(line);
			}
		}

		void CmdLuck(array<string>@ args)
		{
			if (args.length() == 0)
			{
				CmdStatus();
				return;
			}
			if (args[0] == "buff")
			{
				CmdBuff(args);
				return;
			}
			if (args[0] == "item")
			{
				CmdItem(args);
				return;
			}
			if (args[0] == "roll")
			{
				CmdRoll(args);
				return;
			}
			if (HWP::Commands::IsInteger(args[0]) || HWP::Commands::IsDecimal(args[0]))
			{
				if (!CheatsOn())
					return;
				g_cheat = NumArg(args, 0, 0);
				RefreshLocal();
				CmdStatus();
				return;
			}
			Reply("usage: hwp luck [<n> | buff [n] [ms] | item <tier> | roll <table|chance <pct>|tier> <n> [luck]]");
		}

		void SelfCheck()
		{
			for (int t = 1; t <= TIERS; t++)
				if (Equipment::ItemModifier::Get(HashString(MOD_PREFIX + t)) is null)
					HWP::LogError("luck", "missing item modifier " + MOD_PREFIX + t + " (tweak/hwp/modifiers_luck.sval)");
			if (LoadActorBuff(BUFF) is null)
				HWP::LogError("luck", "missing buff " + BUFF);
			if (Item::Get(TRINKET) is null)
				HWP::LogError("luck", "missing trinket " + TRINKET + " (tweak/hwp/trinkets_luck.sval)");
			HWP::Log("luck", "self-check done");
		}
	}
}

// The Luck value on the character tab's stat bar (core gui/playermenu/character.gui, beside
// movement speed): a text that reads the local player's Luck each frame, and the hover tooltip
// of the button it sits in (tooltip-enabled) with the factor it gives.
class HWPLuckStatWidget : TextWidget
{
	int m_shown = -999999;
	string m_shownParty;

	HWPLuckStatWidget()
	{
		super();
	}

	Widget@ Clone() override
	{
		HWPLuckStatWidget@ w = HWPLuckStatWidget();
		CloneInto(w);
		return w;
	}

	void Update(int dt) override
	{
		auto rec = GetLocalPlayerRecord();
		float luck = HWP::Luck::OfRecord(rec);
		int n = int(luck + (luck < 0 ? -0.5f : 0.5f));
		string party = HWP::Luck::Fmt(HWP::Luck::PartyFactor());
		if (n != m_shown || party != m_shownParty)
		{
			m_shown = n;
			m_shownParty = party;
			SetText("" + n);
			if (m_parent !is null && m_parent.m_tooltip !is null)
				m_parent.m_tooltip.m_tooltipText = HWP::Luck::TooltipText(luck);
		}
		TextWidget::Update(dt);
	}
}

ref@ LoadHWPLuckStatWidget(WidgetLoadingContext &ctx)
{
	HWPLuckStatWidget@ w = HWPLuckStatWidget();
	w.Load(ctx);
	return w;
}

namespace HWPLuck
{
	[Hook]
	void LoadWidgetProducers(GUIBuilder@ builder)
	{
		builder.AddWidgetProducer("hwp-luck-stat", LoadHWPLuckStatWidget);
	}

	// the cheat value (hwp luck <n>), on the local record only
	[Hook]
	void PlayerRecordRefreshModifiers(PlayerRecord@ record)
	{
		if (record is null || !record.local || HWP::Luck::g_cheat == 0)
			return;
		if (HWP::Luck::g_provider is null)
			@HWP::Luck::g_provider = ModifierProvider(Resources::GetString(".hwp.luck.provider"));
		record.modifiers.AddModifiers(HWP::Luck::CheatModifiers(), 1.0f, HWP::Luck::g_provider);
	}
}

namespace Modules
{
	class HWPLuckModule : Module
	{
		HWPLuckModule()
		{
			super("hwp-luck");
			HWP::Commands::Register("luck", " [<n> | buff [n] [ms] | item <tier> | roll <table|chance <pct>|tier> <n> [luck]]  the Luck stat; the rest are cheats", HWP::Commands::Handler(HWP::Luck::CmdLuck));
			HWP::Net::OnRequest(HWP::Luck::REPORT, HWP::Net::RequestHandler(HWP::Luck::OnReport));
			HWP::Net::OnEvent(HWP::Luck::FLOOR_EVENT, HWP::Net::EventHandler(HWP::Luck::OnFloorEvent));
			int imps = 0;
			int secrets = HWP::Luck::InstallSecrets(imps);
			if (imps > 0)
				HWP::Log("luck", "imp sets on " + imps + " floor generator(s)");
			if (secrets > 0)
				HWP::Log("luck", "secret room sets on " + secrets + " floor generator(s)");
			HWP::Luck::SelfCheck();
		}

		void UpdateFrame(int ms, GameInput& gameInput, MenuInput& menuInput, bool paused) override
		{
			HWP::Luck::FloorTick(ms);
			HWP::Luck::ReportTick(ms);
		}
	}
}
