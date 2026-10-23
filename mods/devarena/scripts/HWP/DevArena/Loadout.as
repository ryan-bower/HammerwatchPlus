// Loadouts (docs/devarena/SPEC.md, "Loadout"): put the local player on a preset build in one
// step: class, level, attribute points, skill and combo picks, gear and trinkets.
//
// The presets come from tools/make_presets.py, which writes tweak/hwp/devarena_presets.sval and
// checks each one against the game tables (star and stat budgets, slots, sub-skill parents).
// The file is read once, at boot. Rows are all strings:
//   ["stat", attr, n]  ["skill", id, picks]  ["combo", id, picks]  ["equip", baseId]  ["trinket", id]
//
// Apply order. Reset what the record owns (picks, combos, stats, masteries, attuned trinkets,
// gear, trinkets). Then ChangeClass when the class differs (PlayerRecord.as:387, re-initialises
// the PlayerBase, so the player is re-skinned in place). Then level and experience, stats, one
// SkillUp per pick (PlayerRecord.SkillUp: pays stars, refunds combo blockers), gear and trinkets.
// Gear is built at the header's ilvl and quality. The affixes are random, so the RNG is seeded
// from the preset id for gear and trinkets and given back a fresh seed afterwards: the same
// preset rolls the same affixes every time.
//
// An apply waits for a frame where no class skill is casting, like the tuner's patches. Every
// apply ends with CheckPreset reading the record back, logging
//   [HWP:devarena] loadout <id> ok | mismatch <what>,<what>...
namespace HWP
{
namespace DevArena
{
	const string PRESET_FILE = "tweak/hwp/devarena_presets.sval";
	const int PRESET_SCHEMA = 1;

	class Preset
	{
		string id;
		string cls;
		string tier;
		int level;
		int ilvl;
		string quality;
		string note;
		array<array<string>> rows;
	}

	array<Preset@> g_presets;
	int g_presetsLoaded = -1;      // presets read at boot, -1 not read
	string g_preset;               // the last preset applied, "" none
	bool g_sheetEdited;            // an edit landed since g_preset was applied
	array<string> g_presetQueue;   // waiting for a frame with no cast
	int g_loadoutApplied;
	int g_loadoutOk;
	int g_loadoutBad;
	string g_loadoutLastBad;       // "<id>: <what>,..." of the last mismatch

	void LoadPresets()
	{
		if (g_presetsLoaded >= 0)
			return;
		g_presetsLoaded = 0;
		auto root = Resources::GetSValue(PRESET_FILE);
		if (root is null || root.GetType() != SValueType::Dictionary || IntEntry(root, "schema", 0) != PRESET_SCHEMA)
		{
			HWP::Log("devarena", "presets: none or wrong schema");
			return;
		}
		auto list = root.GetDictionaryEntry("presets");
		array<SValue@>@ arr = list is null ? null : list.GetArray();
		for (uint i = 0; arr !is null && i < arr.length(); i++)
		{
			auto d = arr[i];
			Preset p;
			p.id = StrEntry(d, "id");
			p.cls = StrEntry(d, "class");
			p.tier = StrEntry(d, "tier");
			p.level = IntEntry(d, "level", 1);
			p.ilvl = IntEntry(d, "ilvl", 1);
			p.quality = StrEntry(d, "quality");
			p.note = StrEntry(d, "note");
			auto rs = d.GetDictionaryEntry("rows");
			array<SValue@>@ ra = rs is null ? null : rs.GetArray();
			for (uint j = 0; ra !is null && j < ra.length(); j++)
			{
				array<string> row;
				auto cells = ra[j].GetArray();
				for (uint k = 0; cells !is null && k < cells.length(); k++)
					row.insertLast(cells[k].GetString());
				p.rows.insertLast(row);
			}
			g_presets.insertLast(p);
		}
		auto favs = root.GetDictionaryEntry("favorites");
		array<SValue@>@ fa = favs is null ? null : favs.GetArray();
		for (uint i = 0; fa !is null && i < fa.length(); i++)
			if (FindPreset(fa[i].GetString()) !is null)
				g_favorites.insertLast(fa[i].GetString());
		g_presetsLoaded = g_presets.length();
		HWP::Log("devarena", "presets: " + g_presetsLoaded + ", favorites " + g_favorites.length());
	}

	string StrEntry(SValue@ d, const string &in key)
	{
		auto v = d.GetDictionaryEntry(key);
		return (v is null || v.GetType() != SValueType::String) ? "" : v.GetString();
	}

	Preset@ FindPreset(const string &in id)
	{
		for (uint i = 0; i < g_presets.length(); i++)
			if (g_presets[i].id == id)
				return g_presets[i];
		return null;
	}

	// queue one preset, or every preset for "all"; false when the id is unknown
	bool QueuePreset(const string &in id)
	{
		if (id == "all")
		{
			for (uint i = 0; i < g_presets.length(); i++)
				g_presetQueue.insertLast(g_presets[i].id);
			return g_presets.length() > 0;
		}
		if (FindPreset(id) is null)
			return false;
		g_presetQueue.insertLast(id);
		return true;
	}

	// a sheet edit (LoadoutTab.as), queued like an apply: "op|<verb>|<id>|<+1/-1>"
	void QueueOp(const string &in verb, const string &in id, int d)
	{
		g_presetQueue.insertLast("op|" + verb + "|" + id + "|" + d);
	}

	// one apply or edit per frame, on a frame where no class skill is casting
	void TickLoadout()
	{
		if (g_presetQueue.length() == 0 || LocalPlayer() is null || AnyCasting())
			return;
		string next = g_presetQueue[0];
		g_presetQueue.removeAt(0);
		if (next.findFirst("op|") == 0)
		{
			auto parts = next.split("|");
			ApplyOp(parts[1], parts[2], parseInt(parts[3]));
			return;
		}
		auto p = FindPreset(next);
		if (p !is null)
			ApplyPreset(p);
	}

	void ApplyOp(const string &in verb, const string &in id, int d)
	{
		auto plr = LocalPlayer();
		auto rec = plr.m_record;
		string err;
		if (verb == "level")
		{
			int L = clamp(rec.level + d, 1, 99);
			rec.NetSyncExperience(L, int(rec.LevelExperience(L - 1)));
		}
		else if (verb == "stat")
		{
			if (d < 0 && GetStat(rec, id) <= 0)
				err = id + " is 0";
			else if (d > 0 && rec.GetPlaceableStatPoints() <= 0)
				err = "no stat points";
			else
			{
				AddStat(rec, id, d);
				rec.SyncStatPoints();
			}
		}
		else if (d > 0)
		{
			if (!rec.SkillUp(id, verb == "combo"))
				err = "cannot raise " + id;
		}
		else
		{
			auto picked = Picked(rec, verb == "combo");
			int n = 0;
			picked.get(id, n);
			if (n <= 0)
				err = id + " is 0";
			else if (n == 1)
				picked.delete(id);
			else
				picked.set(id, n - 1);
		}
		rec.RefreshStats();
		rec.RefreshModifiers();
		plr.LoadSkills();
		GetHUD().RefreshSkillList(rec);
		g_lastAction = verb + " " + id + (d > 0 ? " +1" : " -1");
		g_lastError = err;
		if (err == "")
			g_sheetEdited = true;
		HWP::Log("devarena", "loadout-edit " + verb + " " + id + " " + d + (err == "" ? "" : " refused: " + err));
	}

	void ResetRecord(PlayerRecord@ rec)
	{
		rec.pickedSkills.deleteAll();
		rec.pickedComboSkills.deleteAll();
		rec.pickedStr = 0;
		rec.pickedDex = 0;
		rec.pickedInt = 0;
		rec.pickedFoc = 0;
		rec.pickedVit = 0;
		rec.weaponMasteries.removeRange(0, rec.weaponMasteries.length());
		rec.attunedTrinkets.removeRange(0, rec.attunedTrinkets.length());
		rec.equipped.Clear();
		rec.trinketInventory.Clear();
	}

	void AddStat(PlayerRecord@ rec, const string &in attr, int n)
	{
		if (attr == "str") rec.pickedStr += n;
		else if (attr == "dex") rec.pickedDex += n;
		else if (attr == "int") rec.pickedInt += n;
		else if (attr == "foc") rec.pickedFoc += n;
		else if (attr == "vit") rec.pickedVit += n;
	}

	int GetStat(PlayerRecord@ rec, const string &in attr)
	{
		if (attr == "str") return rec.pickedStr;
		if (attr == "dex") return rec.pickedDex;
		if (attr == "int") return rec.pickedInt;
		if (attr == "foc") return rec.pickedFoc;
		if (attr == "vit") return rec.pickedVit;
		return -1;
	}

	Equipment::Item@ MakeGear(const string &in baseId, int ilvl, const string &in quality)
	{
		auto base = Equipment::BaseItem::Get(baseId);
		if (base is null)
			return null;
		Equipment::Generator gen;
		gen.m_ilvl = ilvl;
		Equipment::Item item;
		item.quality = Item::ParseQuality(quality);
		@item.baseItem = base;
		gen.GenerateItemMods(item, ilvl, null);
		item.Finalize(randf(), ilvl, 0, null, null);
		return item;
	}

	void ApplyPreset(Preset@ p)
	{
		g_sheetEdited = false;
		auto plr = LocalPlayer();
		auto rec = plr.m_record;
		auto cls = PlayerClass::Get(p.cls);
		if (cls is null)
		{
			g_lastError = "preset " + p.id + ": no class " + p.cls;
			return;
		}
		ResetRecord(rec);
		bool changed = rec.playerClass is null || rec.playerClass.m_id != p.cls;
		if (changed)
		{
			// every class builds its own skill defs (PlayerClass.as:452) and the tuner edits the
			// current class's: put this class's back to vanilla before leaving, and re-apply the
			// live version onto the new class below (review 5: a ranger_beasts preset kept vanilla
			// ran_trap under "live v1", and going back to nature showed a stale v1)
			RestoreVanilla();
			g_vanilla.deleteAll();
			rec.ChangeClass(cls);
		}
		rec.NetSyncExperience(p.level, int(rec.LevelExperience(p.level - 1)));

		for (uint i = 0; i < p.rows.length(); i++)
			if (p.rows[i][0] == "stat")
				AddStat(rec, p.rows[i][1], parseInt(p.rows[i][2]));
		rec.SyncStatPoints();
		rec.RefreshStats();

		array<string> failed;
		for (uint i = 0; i < p.rows.length(); i++)
		{
			auto row = p.rows[i];
			if (row[0] != "skill" && row[0] != "combo")
				continue;
			int n = parseInt(row[2]);
			for (int k = 0; k < n; k++)
				if (!rec.SkillUp(row[1], row[0] == "combo"))
				{
					failed.insertLast(row[1]);
					break;
				}
		}

		int keep = randi(0x7fffffff);
		srand(int(HashString(p.id) & 0x7fffffff));
		bool ignore = g_dbg_ignore_equipment_requirements;
		g_dbg_ignore_equipment_requirements = true;
		for (uint i = 0; i < p.rows.length(); i++)
		{
			auto row = p.rows[i];
			if (row[0] == "equip")
			{
				auto item = MakeGear(row[1], p.ilvl, p.quality);
				if (item is null)
					failed.insertLast(row[1]);
				else
					rec.equipped.Equip(item);
			}
			else if (row[0] == "trinket")
			{
				auto t = Item::Trinket::Get(row[1]);
				if (t is null)
					failed.insertLast(row[1]);
				else
					rec.trinketInventory.Add(t);
			}
		}
		g_dbg_ignore_equipment_requirements = ignore;
		srand(keep);

		rec.RefreshStats();
		rec.RefreshModifiers();
		plr.LoadSkills();
		// a new item's skill starts on its full cooldown (PlayerBase.as:153, no save entry), so a
		// fresh preset's right click was dead for 3-4.5 s (class-clicks 20261021-200827: shield
		// bash, shortbow and greataxe secondaries "can 0" with full mana); a loadout starts ready
		for (uint i = 0; i < plr.m_skills.length(); i++)
			plr.m_skills[i].ResetCooldown();
		if (changed)
		{
			g_live = -1;
			HWP::Log("devarena", "class " + p.cls + ": re-applying v" + g_want);
			Flush();
		}
		rec.ResetPlayerHealthMana();
		GetHUD().RefreshSkillList(rec);

		g_preset = p.id;
		g_loadoutApplied++;
		g_lastAction = "preset " + p.id;
		g_lastError = failed.length() > 0 ? "preset " + p.id + ": failed " + join(failed, ",") : "";
		CheckPreset(p, failed);
	}

	// "foc 10<21" for each attribute an item asks for and the record lacks
	string ReqShort(PlayerRecord@ rec, Equipment::EquipmentRequirements@ r)
	{
		array<string> lack;
		auto s = rec.currStats;
		if (r.m_str > s.Str) lack.insertLast("str " + s.Str + "<" + r.m_str);
		if (r.m_dex > s.Dex) lack.insertLast("dex " + s.Dex + "<" + r.m_dex);
		if (r.m_int > s.Int) lack.insertLast("int " + s.Int + "<" + r.m_int);
		if (r.m_foc > s.Foc) lack.insertLast("foc " + s.Foc + "<" + r.m_foc);
		if (r.m_vit > s.Vit) lack.insertLast("vit " + s.Vit + "<" + r.m_vit);
		return join(lack, " ");
	}

	// read the record back against the preset and log the verdict
	void CheckPreset(Preset@ p, array<string>@ bad)
	{
		auto rec = LocalPlayer().m_record;
		if (rec.playerClass.m_id != p.cls)
			bad.insertLast("class=" + rec.playerClass.m_id);
		if (rec.level != p.level)
			bad.insertLast("level=" + rec.level);
		array<string> slots;
		array<string> trinkets;
		dictionary want;      // "skill|id" / "combo|id" / "stat|attr" -> n
		for (uint i = 0; i < p.rows.length(); i++)
		{
			auto row = p.rows[i];
			if (row[0] == "equip")
				slots.insertLast(row[1]);
			else if (row[0] == "trinket")
				trinkets.insertLast(row[1]);
			else if (row.length() >= 3)
				want.set(row[0] + "|" + row[1], parseInt(row[2]));
		}
		auto keys = want.getKeys();
		for (uint i = 0; i < keys.length(); i++)
		{
			int n = int(want[keys[i]]);
			int got = -1;
			string id = keys[i].substr(keys[i].findFirst("|") + 1);
			if (keys[i].findFirst("stat|") == 0)
				got = GetStat(rec, id);
			else if (!Picked(rec, keys[i].findFirst("combo|") == 0).get(id, got))
				got = 0;
			if (got != n)
				bad.insertLast(id + "=" + got);
		}
		auto picked = rec.pickedSkills.getKeys();
		for (uint i = 0; i < picked.length(); i++)
		{
			int lvl = 0;
			rec.pickedSkills.get(picked[i], lvl);
			if (lvl > 0 && !want.exists("skill|" + picked[i]))
				bad.insertLast("extra " + picked[i]);
		}
		auto quality = Item::ParseQuality(p.quality);
		for (uint i = 0; i < rec.equipped.m_items.length(); i++)
		{
			auto it = cast<Equipment::Item>(rec.equipped.m_items[i]);
			if (it is null)
				continue;
			int at = slots.find(it.baseItem.m_id);
			if (at < 0)
				bad.insertLast("gear " + it.baseItem.m_id);
			else
				slots.removeAt(at);
			if (it.quality != quality || int(it.itemLevel) != p.ilvl)
				bad.insertLast("gear " + it.baseItem.m_id + " q/ilvl");
			// gear goes on with the requirements ignored (ApplyPreset), but the game re-checks
			// MayEquip every frame and blocks the item's weapon skill when it fails
			// (PlayerTargetingHelper.as CheckSkillBlocked): priest/mid's scepter never fired
			if (!rec.equipped.MayEquip(it))
				bad.insertLast("unusable " + it.baseItem.m_id + " (" + ReqShort(rec, it.GetRequirements()) + ")");
		}
		for (uint i = 0; i < slots.length(); i++)
			bad.insertLast("missing " + slots[i]);
		auto inv = rec.trinketInventory.m_items;
		for (uint i = 0; i < inv.length(); i++)
		{
			int at = trinkets.find(inv[i].m_id);
			if (at < 0)
				bad.insertLast("trinket " + inv[i].m_id);
			else
				trinkets.removeAt(at);
		}
		for (uint i = 0; i < trinkets.length(); i++)
			bad.insertLast("missing " + trinkets[i]);
		if (rec.GetFreeSkillPoints() < 0)
			bad.insertLast("stars " + rec.GetFreeSkillPoints());
		if (rec.GetPlaceableStatPoints() < 0)
			bad.insertLast("statpts " + rec.GetPlaceableStatPoints());

		if (bad.length() == 0)
		{
			g_loadoutOk++;
			HWP::Log("devarena", "loadout " + p.id + " ok");
		}
		else
		{
			g_loadoutBad++;
			g_loadoutLastBad = p.id + ": " + join(bad, ",");
			HWP::Log("devarena", "loadout " + p.id + " mismatch " + join(bad, ","));
		}
	}
}
}
