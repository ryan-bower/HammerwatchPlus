// Vanilla Tuning: skill edits exported from the Dev Arena tuner (tools/devarena/export.py).
//
// tweak/hwp/vanilla_tuning.sval holds one version's edits, rows of
// [skill id, level index, dotted path, value text] (level 0 = the "skill" dict, k = upgrades[k-1]).
// Each frame with a local player, every skill def the edits name that is not patched yet gets
// copy-on-write patches (Patch.as, a generated copy of the Dev Arena's) and the player's skills
// are rebuilt once (PlayerBase.LoadSkills). Defs are patched once each, so a class picked later
// is patched when it first shows up. No base file is shadowed.
namespace HWP
{
namespace VanillaTuning
{
	const string FILE = "tweak/hwp/vanilla_tuning.sval";
	const int SCHEMA = 1;

	class Edit
	{
		string skill;
		int level;
		string path;
		string value;
	}

	array<Edit@> g_edits;
	array<PlayerSkillDef@> g_patched;
	int g_applied;
	int g_failed;

	void Load()
	{
		auto root = Resources::GetSValue(FILE);
		if (root is null || root.GetType() != SValueType::Dictionary)
		{
			HWP::Log("vanilla-tuning", "no " + FILE);
			return;
		}
		auto schema = root.GetDictionaryEntry("schema");
		if (schema is null || schema.GetType() != SValueType::Integer || schema.GetInteger() != SCHEMA)
		{
			HWP::Log("vanilla-tuning", FILE + ": schema is not " + SCHEMA + ", ignored");
			return;
		}
		auto edits = root.GetDictionaryEntry("edits");
		array<SValue@>@ ea = edits is null ? null : edits.GetArray();
		for (uint i = 0; ea !is null && i < ea.length(); i++)
		{
			auto row = ea[i].GetArray();
			if (row is null || row.length() != 4)
				continue;
			Edit e;
			e.skill = row[0].GetString();
			e.level = row[1].GetInteger();
			e.path = row[2].GetString();
			e.value = row[3].GetString();
			g_edits.insertLast(e);
		}
		auto note = root.GetDictionaryEntry("note");
		HWP::Log("vanilla-tuning", "loaded " + g_edits.length() + " edits" + (note is null ? "" : " (" + note.GetString() + ")"));
	}

	PlayerSkillDef@ FindDef(PlayerBase@ plr, const string &in id)
	{
		if (plr.m_record !is null && plr.m_record.playerClass !is null)
		{
			auto def = plr.m_record.playerClass.GetSkillDef(HashString(id));
			if (def !is null)
				return def;
		}
		return PlayerSkillDef::Get(HashString(id));
	}

	// the type a key new at an upgrade takes: the base dict's leaf type
	SValueType HintType(PlayerSkillDef@ def, int level, const string &in path)
	{
		if (level <= 0 || def.m_levelParams.length() == 0)
			return SValueType::Null;
		auto base = Lookup(def.m_levelParams[0], path);
		return base is null ? SValueType::Null : base.GetType();
	}

	void PatchDef(PlayerSkillDef@ def, const string &in skill)
	{
		for (uint i = 0; i < g_edits.length(); i++)
		{
			auto e = g_edits[i];
			if (e.skill != skill)
				continue;
			string err;
			SValue@ copy = null;
			if (e.level >= 0 && uint(e.level) < def.m_levelParams.length())
				@copy = PatchCopy(def.m_levelParams[e.level], e.path, e.value, err, HintType(def, e.level, e.path));
			else
				err = "level index " + e.level + " out of range";
			if (copy is null)
			{
				g_failed++;
				HWP::Log("vanilla-tuning", "failed " + skill + "[" + e.level + "]." + e.path + ": " + err);
				continue;
			}
			@def.m_levelParams[e.level] = copy;
			g_applied++;
		}
	}

	void Tick()
	{
		if (g_edits.length() == 0)
			return;
		auto plr = cast<PlayerBase>(GetLocalPlayer());
		if (plr is null)
			return;
		int fresh = 0;
		array<string> done;
		for (uint i = 0; i < g_edits.length(); i++)
		{
			auto skill = g_edits[i].skill;
			if (done.find(skill) >= 0)
				continue;
			done.insertLast(skill);
			auto def = FindDef(plr, skill);
			if (def is null || g_patched.findByRef(def) >= 0)
				continue;
			g_patched.insertLast(def);
			PatchDef(def, skill);
			fresh++;
		}
		if (fresh == 0)
			return;
		plr.LoadSkills();
		HWP::Log("vanilla-tuning", "patched " + fresh + " skill defs (" + g_applied + " edits applied, " + g_failed + " failed)");
	}
}
}

namespace Modules
{
	class HWPVanillaTuningModule : Module
	{
		HWPVanillaTuningModule()
		{
			super("vanilla-tuning");
			HWP::VanillaTuning::Load();
		}

		void UpdateFrame(int ms, GameInput& gameInput, MenuInput& menuInput, bool paused) override
		{
			HWP::VanillaTuning::Tick();
		}
	}
}
