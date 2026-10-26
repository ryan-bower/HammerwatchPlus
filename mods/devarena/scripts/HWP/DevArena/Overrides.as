// The override file (docs/devarena/SPEC.md, "Decided during build" 2): the tuner's versions,
// A/B pins, the live version and the curve pins. It is the source of truth from the first edit.
//
// The game reads it once, at boot: tweak/hwp/devarena_overrides.sval inside this mod, through
// Resources::GetSValue, which caches resource files at boot. The game cannot write files, so
// it logs the whole state as one JSON line on every change:
//   [HWP:devarena] override {"schema":1,"live":2,"a":0,"b":2,"slot":"B","pins":[...],
//                            "versions":[{"note":"...","edits":[[skill,level,path,value],...]},...]}
// and tools/devarena/overrides.py writes the .sval from the last such line (v0, vanilla, is
// implied and not stored).
namespace HWP
{
namespace DevArena
{
	const string OVERRIDE_FILE = "tweak/hwp/devarena_overrides.sval";
	const int OVERRIDE_SCHEMA = 1;
	int g_overrideLoaded = -1;     // versions read from the file at boot, -1 not read
	uint g_fileHash;               // HashString(OverrideJson()) just after the boot file was read
	int g_overrideEmits;

	string OverrideJson()
	{
		EnsureVersions();
		array<string> vs;
		for (uint i = 1; i < g_versions.length(); i++)
		{
			auto v = g_versions[i];
			array<string> es;
			for (uint j = 0; j < v.edits.length(); j++)
			{
				auto e = v.edits[j];
				es.insertLast("[" + GameLab::Quote(e.skill) + "," + e.level + "," + GameLab::Quote(e.path) + ","
					+ GameLab::Quote(e.value) + "]");
			}
			vs.insertLast("{\"note\":" + GameLab::Quote(v.note) + ",\"edits\":[" + join(es, ",") + "]}");
		}
		array<string> pins;
		auto keys = g_pins.getKeys();
		keys.sortAsc();
		for (uint i = 0; i < keys.length(); i++)
			pins.insertLast(GameLab::Quote(keys[i]));
		return "{\"schema\":" + OVERRIDE_SCHEMA + ",\"live\":" + g_want + ",\"a\":" + g_slotA + ",\"b\":" + g_slotB
			+ ",\"slot\":\"" + (g_onB ? "B" : "A") + "\",\"pins\":[" + join(pins, ",") + "],\"versions\":["
			+ join(vs, ",") + "]}";
	}

	void EmitOverride()
	{
		g_overrideEmits++;
		HWP::Log("devarena", "override " + OverrideJson());
	}

	int IntEntry(SValue@ d, const string &in key, int def)
	{
		auto v = d.GetDictionaryEntry(key);
		return (v is null || v.GetType() != SValueType::Integer) ? def : v.GetInteger();
	}

	// read the file into the versions; the live version is applied by Tick once a player exists
	void LoadOverrides()
	{
		if (g_overrideLoaded >= 0)
			return;
		g_overrideLoaded = 0;
		EnsureVersions();
		auto root = Resources::GetSValue(OVERRIDE_FILE);
		if (root is null || root.GetType() != SValueType::Dictionary)
			HWP::Log("devarena", "override file: none");
		else if (IntEntry(root, "schema", 0) != OVERRIDE_SCHEMA)
			HWP::Log("devarena", "override file: schema " + IntEntry(root, "schema", 0) + " is not " + OVERRIDE_SCHEMA + ", ignored");
		else
			g_overrideLoaded = ReadTuner(root, "override file");
		g_fileHash = HashString(OverrideJson());
	}

	// the versions, slots and pins from an override-shaped dict (the file, or the town save);
	// returns the version count, v0 not counted
	int ReadTuner(SValue@ root, const string &in from)
	{
		g_versions.resize(0);
		EnsureVersions();
		g_pins.deleteAll();
		auto versions = root.GetDictionaryEntry("versions");
		array<SValue@>@ arr = versions is null ? null : versions.GetArray();
		for (uint i = 0; arr !is null && i < arr.length(); i++)
		{
			Version v;
			auto note = arr[i].GetDictionaryEntry("note");
			if (note !is null)
				v.note = note.GetString();
			auto edits = arr[i].GetDictionaryEntry("edits");
			array<SValue@>@ ea = edits is null ? null : edits.GetArray();
			for (uint j = 0; ea !is null && j < ea.length(); j++)
			{
				auto row = ea[j].GetArray();
				if (row is null || row.length() != 4)
					continue;
				v.edits.insertLast(MakeEdit(row[0].GetString(), row[1].GetInteger(), row[2].GetString(), row[3].GetString()));
			}
			g_versions.insertLast(v);
		}
		int n = g_versions.length();
		g_slotA = clamp(IntEntry(root, "a", 0), 0, n - 1);
		g_slotB = IntEntry(root, "b", -1);
		if (g_slotB >= n)
			g_slotB = -1;
		auto slot = root.GetDictionaryEntry("slot");
		g_onB = slot !is null && slot.GetString() == "B" && g_slotB >= 0;
		g_want = clamp(IntEntry(root, "live", LiveSlotVersion()), 0, n - 1);
		auto pins = root.GetDictionaryEntry("pins");
		array<SValue@>@ pa = pins is null ? null : pins.GetArray();
		for (uint i = 0; pa !is null && i < pa.length(); i++)
			g_pins.set(pa[i].GetString(), true);
		HWP::Log("devarena", from + ": " + (n - 1) + " versions, live v" + g_want + ", A v" + g_slotA
			+ ", B " + (g_slotB < 0 ? "-" : "v" + g_slotB) + ", slot " + (g_onB ? "B" : "A"));
		return n - 1;
	}

	// Script globals do not survive a level change, and the boot file is cached at boot, so
	// Reload floor or a stairway would put the tuner back to the boot file (review 6: v1 lost,
	// and the next edit's override line no longer held it). The state rides in the town save
	// (ArenaSave.as) with the boot file's fingerprint: it is taken back only while the process
	// still sees that file, so a relaunch after overrides.py sync (or an emptied file) reads it.
	void SaveTuner(SValueBuilder& b)
	{
		EnsureVersions();
		b.PushDictionary("tuner");
		b.PushInteger("boot", int(g_fileHash));
		b.PushInteger("live", g_want);
		b.PushInteger("a", g_slotA);
		b.PushInteger("b", g_slotB);
		b.PushString("slot", g_onB ? "B" : "A");
		b.PushBoolean("relaunch", g_needsRelaunch);
		b.PushArray("pins");
		auto keys = g_pins.getKeys();
		keys.sortAsc();
		for (uint i = 0; i < keys.length(); i++)
			b.PushString(keys[i]);
		b.PopArray();
		b.PushArray("versions");
		for (uint i = 1; i < g_versions.length(); i++)
		{
			auto v = g_versions[i];
			b.PushDictionary();
			b.PushString("note", v.note);
			b.PushArray("edits");
			for (uint j = 0; j < v.edits.length(); j++)
			{
				auto e = v.edits[j];
				b.PushArray();
				b.PushString(e.skill);
				b.PushInteger(e.level);
				b.PushString(e.path);
				b.PushString(e.value);
				b.PopArray();
			}
			b.PopArray();
			b.PopDictionary();
		}
		b.PopArray();
		b.PopDictionary();
	}

	void LoadTuner(SValue@ d)
	{
		auto t = d.GetDictionaryEntry("tuner");
		if (t is null || t.GetType() != SValueType::Dictionary)
			return;
		LoadOverrides();
		if (IntEntry(t, "boot", 0) != int(g_fileHash))
		{
			HWP::Log("devarena", "tuner in the town save is from another override file: the file wins");
			return;
		}
		ReadTuner(t, "tuner from the town save");
		auto r = t.GetDictionaryEntry("relaunch");
		g_needsRelaunch = r !is null && r.GetType() == SValueType::Boolean && r.GetBoolean();
		g_live = -1;   // the defs are this level's, vanilla: Tick puts g_want on them
	}
}
}
