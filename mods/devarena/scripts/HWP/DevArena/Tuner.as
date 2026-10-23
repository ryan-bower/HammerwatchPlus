// Dev Arena tuner core: versions of skill edits, applied between casts.
//
// An Edit sets one leaf of one level dict of a skill def (Patch.as). A Version is the full,
// cumulative list of edits on top of vanilla; v0 is vanilla and has none. Every apply
// (dock Enter, a growth step, da-set) makes a new version from the current one, so a version
// never changes once made, and A/B pins and undo/redo are just version indices.
//
// Activating a version restores the vanilla level dicts of every skill ever touched, replays
// the version's edits on copies, then rebuilds the local player's skills once
// (PlayerBase.LoadSkills). It waits for the first frame no class skill is casting, so a cast in
// flight keeps the values it started with (spike-deferred 20261020-222134).
//
// A and B. Slot A starts on v0. The first apply while B is empty makes B and switches to it,
// so A stays the champion and edits go into the challenger. After that an apply, undo or redo
// moves the live slot's pin. F2 swaps to the other slot; "Keep B -> A" pins A to B and empties B.
// Versions are append-only: an apply after an undo adds a new version at the end, so no pin
// ever points at a version that was thrown away.
namespace HWP
{
namespace DevArena
{
	class Edit
	{
		string skill;
		int level;   // index into m_levelParams: 0 = base "skill" dict, k = upgrades[k-1]
		string path;
		string value;

		string Key() const { return skill + "|" + level + "|" + path; }
	}

	Edit@ MakeEdit(const string &in skill, int level, const string &in path, const string &in value)
	{
		Edit e;
		e.skill = skill;
		e.level = level;
		e.path = path;
		e.value = value;
		return e;
	}

	class Version
	{
		array<Edit@> edits;
		string note;
	}

	class VanillaParams
	{
		array<SValue@> params;
		string name;   // def.m_name (a composed skill renames its slot)
	}

	array<Version@> g_versions;   // [0] = vanilla
	int g_live;                   // the version on the live skills
	int g_want;                   // the version to put there (waits for a cast to end)
	int g_slotA;                  // version pinned in A (always set)
	int g_slotB = -1;             // version pinned in B, -1 empty
	bool g_onB;                   // the live slot is B
	dictionary g_vanilla;         // skill id -> VanillaParams@, snapshot before the first edit
	dictionary g_pins;            // "skill|path|L" -> true: curve cells growth leaves alone

	int g_applied;        // versions activated
	int g_rebuilds;       // LoadSkills calls
	int g_deferredFrames; // frames an activation waited for a cast to end
	string g_lastError;
	string g_lastAction;

	void EnsureVersions()
	{
		if (g_versions.length() == 0)
			g_versions.insertLast(Version());
	}

	// cast counting, keyed by skill id, for the life of the script module. Handles, not ints:
	// dictionary.get into an int returned the last value the caller wrote to a Json
	// (spike-rebuild 20261020-221715 / -221955: "casts" = castpoint, then cooldown)
	class CastStat
	{
		bool was;
		bool now;
		int casts;
		int lastStart = -1; // g_clock at the last cast start
		int lastGap = -1;   // ms between the last two starts
	}
	dictionary g_castStats;   // id -> CastStat@

	CastStat@ Stat(const string &in id)
	{
		CastStat@ st;
		if (!g_castStats.get(id, @st))
		{
			@st = CastStat();
			g_castStats.set(id, @st);
		}
		return st;
	}

	int g_clock;              // gameplay ms seen by UpdateFrame, unpaused only

	PlayerBase@ LocalPlayer()
	{
		return cast<PlayerBase>(GetLocalPlayer());
	}

	// the def by id, sub-skills (modifier-skills) included (PlayerClass.GetSkillDef)
	PlayerSkillDef@ FindDef(const string &in id)
	{
		auto plr = LocalPlayer();
		if (plr !is null && plr.m_record !is null && plr.m_record.playerClass !is null)
		{
			auto def = plr.m_record.playerClass.GetSkillDef(HashString(id));
			if (def !is null)
				return def;
		}
		return PlayerSkillDef::Get(HashString(id));
	}

	Skills::Skill@ FindLive(const string &in id)
	{
		auto plr = LocalPlayer();
		if (plr is null)
			return null;
		for (uint i = 0; i < plr.m_skills.length(); i++)
			if (plr.m_skills[i].m_id == id)
				return plr.m_skills[i];
		return null;
	}

	bool IsCasting(Skills::Skill@ s)
	{
		auto ps = cast<Skills::PlayerSkill>(s);
		if (ps !is null)
			return ps.m_castingT >= 0;
		return s.IsActive();
	}

	bool AnyCasting()
	{
		auto plr = LocalPlayer();
		if (plr is null)
			return false;
		for (uint i = 0; i < plr.m_skillsClass.length(); i++)
			if (IsCasting(plr.m_skillsClass[i]))
				return true;
		return false;
	}

	// the type a new key at level dict k takes: the base dict's leaf type, so a float field
	// written as "25" at an upgrade stays a float
	SValueType HintType(PlayerSkillDef@ def, int level, const string &in path)
	{
		if (level <= 0 || def.m_levelParams.length() == 0)
			return SValueType::Null;
		auto base = Lookup(def.m_levelParams[0], path);
		return base is null ? SValueType::Null : base.GetType();
	}

	// check the edit against the def as it is now, without applying it
	bool Validate(Edit@ e, string &out err)
	{
		if (e.path == COMPOSE_PATH)
			return ComposeValidate(e, err);
		auto def = FindDef(e.skill);
		if (def is null)
		{
			err = "no skill '" + e.skill + "'";
			return false;
		}
		if (e.level < 0 || uint(e.level) >= def.m_levelParams.length())
		{
			err = "level index " + e.level + " out of range (" + def.m_levelParams.length() + ")";
			return false;
		}
		// times can't run backwards (the reviewer's castpoint -100)
		string leaf = e.path.substr(e.path.findLast(".") + 1);
		if ((leaf == "castpoint" || leaf == "cooldown") && e.value.findFirst("-") == 0)
		{
			err = leaf + " can't be negative";
			return false;
		}
		return PatchCopy(def.m_levelParams[e.level], e.path, e.value, err, HintType(def, e.level, e.path)) !is null;
	}

	void Snapshot(const string &in skill, PlayerSkillDef@ def)
	{
		if (g_vanilla.exists(skill))
			return;
		VanillaParams v;
		for (uint i = 0; i < def.m_levelParams.length(); i++)
			v.params.insertLast(def.m_levelParams[i]);
		v.name = def.m_name;
		g_vanilla.set(skill, @v);
	}

	bool ApplyOne(Edit@ e, string &out err)
	{
		if (e.path == COMPOSE_PATH)
			return ComposeApply(e, err);
		auto def = FindDef(e.skill);
		if (def is null)
		{
			err = "no skill '" + e.skill + "'";
			return false;
		}
		if (e.level < 0 || uint(e.level) >= def.m_levelParams.length())
		{
			err = "level index " + e.level + " out of range";
			return false;
		}
		Snapshot(e.skill, def);
		auto copy = PatchCopy(def.m_levelParams[e.level], e.path, e.value, err, HintType(def, e.level, e.path));
		if (copy is null)
			return false;
		@def.m_levelParams[e.level] = copy;
		return true;
	}

	void RestoreVanilla()
	{
		auto keys = g_vanilla.getKeys();
		for (uint i = 0; i < keys.length(); i++)
		{
			VanillaParams@ v;
			g_vanilla.get(keys[i], @v);
			auto def = FindDef(keys[i]);
			if (def is null || v is null)
				continue;
			for (uint j = 0; j < v.params.length() && j < def.m_levelParams.length(); j++)
				@def.m_levelParams[j] = v.params[j];
			def.m_name = v.name;
		}
	}

	int LiveSlotVersion()
	{
		return g_onB ? g_slotB : g_slotA;
	}

	void PinLive(int v)
	{
		if (g_onB)
			g_slotB = v;
		else
			g_slotA = v;
	}

	// a new version: the wanted one plus `edits` (each replaces an edit of the same leaf).
	// Validated first; nothing changes when one fails. Returns the new index, -1 on error.
	int Commit(array<Edit@>@ edits, const string &in note, string &out err)
	{
		EnsureVersions();
		for (uint i = 0; i < edits.length(); i++)
		{
			if (!Validate(edits[i], err))
			{
				g_lastError = err;
				HWP::Log("devarena", "rejected " + edits[i].skill + "[" + edits[i].level + "]." + edits[i].path
					+ "=" + edits[i].value + ": " + err);
				return -1;
			}
		}
		Version v;
		v.note = note;
		auto base = g_versions[g_want];
		for (uint i = 0; i < base.edits.length(); i++)
			v.edits.insertLast(base.edits[i]);
		for (uint i = 0; i < edits.length(); i++)
		{
			if (edits[i].path == COMPOSE_PATH)
			{
				// a draft replaces the slot's dicts, so the slot's earlier edits go; "" reverts it
				for (int j = int(v.edits.length()) - 1; j >= 0; j--)
					if (v.edits[j].skill == edits[i].skill)
						v.edits.removeAt(j);
				if (edits[i].value != "")
					v.edits.insertLast(edits[i]);
				continue;
			}
			bool replaced = false;
			for (uint j = 0; j < v.edits.length() && !replaced; j++)
			{
				if (v.edits[j].Key() == edits[i].Key())
				{
					@v.edits[j] = edits[i];
					replaced = true;
				}
			}
			if (!replaced)
				v.edits.insertLast(edits[i]);
		}
		g_versions.insertLast(v);
		int idx = g_versions.length() - 1;
		if (!g_onB && g_slotB < 0)
		{
			g_slotB = idx;          // the first edit makes the challenger
			g_onB = true;
		}
		else
			PinLive(idx);
		g_want = idx;
		g_lastAction = "v" + idx + ": " + note;
		g_lastError = "";
		HWP::Log("devarena", "version v" + idx + " (" + v.edits.length() + " edits): " + note);
		EmitOverride();
		return idx;
	}

	int Commit1(const string &in skill, int level, const string &in path, const string &in value, string &out err)
	{
		array<Edit@> one = { MakeEdit(skill, level, path, value) };
		return Commit(one, skill + "[" + level + "]." + path + "=" + value, err);
	}

	// Ctrl+Z / Ctrl+Y: the live slot steps to the previous / next version
	bool StepVersion(int d)
	{
		EnsureVersions();
		int v = g_want + d;
		if (v < 0 || v >= int(g_versions.length()))
			return false;
		g_want = v;
		PinLive(v);
		g_lastAction = (d < 0 ? "undo to v" : "redo to v") + v;
		EmitOverride();
		return true;
	}

	// F2
	bool SwapAB()
	{
		if (g_slotB < 0)
		{
			g_lastError = "B is empty";
			return false;
		}
		g_onB = !g_onB;
		g_want = LiveSlotVersion();
		g_lastAction = "slot " + (g_onB ? "B" : "A") + " (v" + g_want + ")";
		EmitOverride();
		return true;
	}

	bool KeepB()
	{
		if (g_slotB < 0)
		{
			g_lastError = "B is empty";
			return false;
		}
		g_slotA = g_slotB;
		g_slotB = -1;
		g_onB = false;
		g_want = g_slotA;
		g_lastAction = "kept B -> A (v" + g_slotA + ")";
		EmitOverride();
		return true;
	}

	// pin the live version into the other slot too (makes B from A, or re-pins A)
	void PinOther()
	{
		if (g_onB)
			g_slotA = g_want;
		else
			g_slotB = g_want;
		g_lastAction = "pinned v" + g_want + " to " + (g_onB ? "A" : "B");
		EmitOverride();
	}

	bool Pending()
	{
		return g_want != g_live;
	}

	// put the wanted version on the live skills; false while a cast runs or there is no player
	bool Flush()
	{
		EnsureVersions();
		if (!Pending())
			return true;
		auto plr = LocalPlayer();
		if (plr is null || AnyCasting())
			return false;

		RestoreVanilla();
		auto v = g_versions[g_want];
		for (uint i = 0; i < v.edits.length(); i++)
		{
			auto e = v.edits[i];
			string err;
			// the override file outlives the class: a ranger_nature edit while playing a spec is a skip
			if (FindDef(e.skill) is null)
				HWP::Log("devarena", "apply skipped " + e.skill + "[" + e.level + "]." + e.path + ": not on this class");
			else if (ApplyOne(e, err))
				HWP::Log("devarena", "applied " + e.skill + "[" + e.level + "]." + e.path + "=" + e.value);
			else
			{
				g_lastError = err;
				HWP::Log("devarena", "apply failed " + e.skill + "[" + e.level + "]." + e.path + ": " + err);
			}
		}
		g_live = g_want;
		g_applied++;
		plr.LoadSkills();
		g_rebuilds++;
		HWP::Log("devarena", "live v" + g_live + " (" + v.edits.length() + " edits)");
		return true;
	}

	void TrackCasts()
	{
		auto plr = LocalPlayer();
		if (plr is null)
			return;
		array<CastStat@> seen;
		for (uint i = 0; i < plr.m_skillsClass.length(); i++)
		{
			auto s = plr.m_skillsClass[i];
			auto st = Stat(s.m_id);
			if (seen.findByRef(st) < 0)
			{
				seen.insertLast(st);
				st.now = false;
			}
			st.now = st.now || IsCasting(s);
		}
		for (uint i = 0; i < seen.length(); i++)
		{
			auto st = seen[i];
			if (st.now && !st.was)
			{
				st.casts++;
				if (st.lastStart >= 0)
					st.lastGap = g_clock - st.lastStart;
				st.lastStart = g_clock;
			}
			st.was = st.now;
		}
	}

	void Tick(int ms, bool paused)
	{
		if (!paused)
			g_clock += ms;
		if (Pending() && LocalPlayer() !is null && !Flush())
			g_deferredFrames++;
		TrackCasts();
	}
}
}
