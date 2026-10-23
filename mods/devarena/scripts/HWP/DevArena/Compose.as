// Dev Arena skill composer (docs/devarena/SPEC.md, "Decided during build" 25).
//
// A composed skill replaces one learned spell slot (its def keeps its id, icon, level and
// hotkey). It is built from a draft, a short text such as
//   t=projectile;p=marked_arrow;c=fan,burst;s=;dt=fire;st=marked;n=Thorn Volley;src=;cp=;cd=;mc=;dmg=
// and the parts in tweak/hwp/devarena_compose.sval (tools/devarena/make_compose.py):
//   t    the start: a catalog template ("projectile", "nova") or "clone" (src = a skill id,
//        whose vanilla base dict is the start)
//   p    a catalog projectile (its unit and the binds the unit reads; bound as proj-unit)
//   c, s snippets added to the cast / start actions
//   dt   the damage type of our own Explode effects (template and snippets: physical-bind ->
//        <dt>-bind). A projectile's on-hit lives in its unit file and is left alone.
//   st   a status (status_effects.sval) our Explode effects also apply, "none" for none
//   n    the name the HUD and the Tune tab show
//   cp, cd, mc, dmg   castpoint, cooldown, mana-cost, the main damage bind ("" = the start's)
//
// The draft is one tuner edit, {skill = slot, level 0, path "@compose", value = draft}, so the
// override file, versions, A/B, Tune and Bench treat it like any other edit. Applying it
// (Tuner.ApplyOne) puts the built dict in the slot's level 0, cuts levels 1.. down to their
// skill-cost (so an upgrade adds nothing on top) and cuts the slot's modifier sub-skills'
// level dicts to their skill-cost too (AddPlayerSkill stacks them on the base, PlayerBase.as:189-215). RestoreVanilla puts
// all of it, and the def's name, back. A "" value reverts the slot.
//
// The template takes anim, blocking, move-speed and friends from the slot's own vanilla base
// ("inherit"), so the class has the anim and nothing typed by hand is an ivec2.
namespace HWP
{
namespace DevArena
{
	const string COMPOSE_FILE = "tweak/hwp/devarena_compose.sval";
	const string COMPOSE_PATH = "@compose";
	const array<string> COMPOSE_STARTS = { "projectile", "nova", "clone" };

	SValue@ g_cat;
	bool g_catTried;

	SValue@ Catalog()
	{
		if (!g_catTried)
		{
			g_catTried = true;
			@g_cat = Resources::GetSValue(COMPOSE_FILE);
			if (g_cat is null)
				HWP::Log("devarena", "compose catalog missing: " + COMPOSE_FILE);
		}
		return g_cat;
	}

	string StrOf(SValue@ d, const string &in key)
	{
		if (d is null || d.GetType() != SValueType::Dictionary)
			return "";
		auto v = d.GetDictionaryEntry(key);
		return (v is null || v.GetType() != SValueType::String) ? "" : v.GetString();
	}

	// ids of a catalog section: an array of strings, an array of dicts with "id", or a dict's keys
	array<string> CatIds(const string &in section)
	{
		array<string> ids;
		auto cat = Catalog();
		auto v = cat is null ? null : cat.GetDictionaryEntry(section);
		if (v is null)
			return ids;
		if (v.GetType() == SValueType::Dictionary)
			return v.GetDictionaryKeys();
		if (v.GetType() != SValueType::Array)
			return ids;
		auto arr = v.GetArray();
		for (uint i = 0; i < arr.length(); i++)
			ids.insertLast(arr[i].GetType() == SValueType::String ? arr[i].GetString() : StrOf(arr[i], "id"));
		return ids;
	}

	SValue@ CatEntry(const string &in section, const string &in id)
	{
		auto cat = Catalog();
		auto v = cat is null ? null : cat.GetDictionaryEntry(section);
		if (v is null || id == "")
			return null;
		if (v.GetType() == SValueType::Dictionary)
			return v.GetDictionaryEntry(id);
		if (v.GetType() != SValueType::Array)
			return null;
		auto arr = v.GetArray();
		for (uint i = 0; i < arr.length(); i++)
			if (StrOf(arr[i], "id") == id)
				return arr[i];
		return null;
	}

	// ---- draft ------------------------------------------------------------------------
	class Draft
	{
		string t = "projectile";
		string p;
		array<string> c;
		array<string> s;
		string dt = "physical";
		string st = "none";
		string n = "Composed";
		string src;
		string cp;
		string cd;
		string mc;
		string dmg;
		string bad;          // a parse error, "" none

		string Text() const
		{
			return "t=" + t + ";p=" + p + ";c=" + join(c, ",") + ";s=" + join(s, ",") + ";dt=" + dt + ";st=" + st
				+ ";n=" + n + ";src=" + src + ";cp=" + cp + ";cd=" + cd + ";mc=" + mc + ";dmg=" + dmg;
		}

		bool Has(const array<string> &in list, const string &in id) const
		{
			return list.find(id) >= 0;
		}
	}

	array<string> SplitList(const string &in v)
	{
		array<string> ids;
		auto parts = v.split(",");
		for (uint i = 0; i < parts.length(); i++)
			if (parts[i] != "" && ids.find(parts[i]) < 0)
				ids.insertLast(parts[i]);
		return ids;
	}

	Draft@ ParseDraft(const string &in text)
	{
		Draft d;
		auto parts = text.split(";");
		for (uint i = 0; i < parts.length(); i++)
		{
			if (parts[i] == "")
				continue;
			int eq = parts[i].findFirst("=");
			if (eq < 0)
			{
				d.bad = "'" + parts[i] + "' is not key=value";
				continue;
			}
			string k = parts[i].substr(0, eq), v = parts[i].substr(eq + 1);
			if (k == "t") d.t = v;
			else if (k == "p") d.p = v;
			else if (k == "c") d.c = SplitList(v);
			else if (k == "s") d.s = SplitList(v);
			else if (k == "dt") d.dt = v;
			else if (k == "st") d.st = v;
			else if (k == "n") d.n = v;
			else if (k == "src") d.src = v;
			else if (k == "cp") d.cp = v;
			else if (k == "cd") d.cd = v;
			else if (k == "mc") d.mc = v;
			else if (k == "dmg") d.dmg = v;
			else d.bad = "unknown draft key '" + k + "'";
		}
		return d;
	}

	string NameError(const string &in n)
	{
		if (n == "")
			return "the name is empty";
		if (n.length() > 32)
			return "the name is over 32 characters";
		if (n.findFirst(";") >= 0 || n.findFirst("=") >= 0 || n.findFirst("|") >= 0)
			return "the name cannot hold ; = or |";
		return "";
	}

	// ---- build ------------------------------------------------------------------------
	// level k of a skill as vanilla had it (the tuner's snapshot, else the def now)
	SValue@ VanillaLevel(const string &in id, uint k)
	{
		VanillaParams@ v;
		if (g_vanilla.get(id, @v) && v !is null && k < v.params.length())
			return v.params[k];
		auto def = FindDef(id);
		return (def is null || k >= def.m_levelParams.length()) ? null : def.m_levelParams[k];
	}

	string VanillaName(const string &in id)
	{
		VanillaParams@ v;
		if (g_vanilla.get(id, @v) && v !is null)
			return v.name;
		auto def = FindDef(id);
		return def is null ? "" : def.m_name;
	}

	// a copy; Damage's physical-bind becomes <dt>-bind and Explode effects gain the status
	void CopyRw(SValueBuilder& b, const string &in name, bool named, SValue@ v, const string &in dt, const string &in st,
		const string &in statusFile)
	{
		auto t = v.GetType();
		if (t == SValueType::Array)
		{
			if (named) b.PushArray(name); else b.PushArray();
			auto arr = v.GetArray();
			for (uint i = 0; i < arr.length(); i++)
				CopyRw(b, "", false, arr[i], dt, st, statusFile);
			b.PopArray();
			return;
		}
		if (t != SValueType::Dictionary)
		{
			if (named) b.PushSimple(name, v.Copy()); else b.PushSimple(v.Copy());
			return;
		}
		string cls = StrOf(v, "class");
		if (named) b.PushDictionary(name); else b.PushDictionary();
		auto keys = v.GetDictionaryKeys();
		for (uint i = 0; i < keys.length(); i++)
		{
			auto e = v.GetDictionaryEntry(keys[i]);
			string k = keys[i];
			if (cls == "Damage" && k == "physical-bind" && dt != "" && dt != "physical")
				k = dt + "-bind";
			if (cls == "Explode" && k == "effects" && e.GetType() == SValueType::Array)
			{
				b.PushArray(k);
				auto arr = e.GetArray();
				for (uint j = 0; j < arr.length(); j++)
					CopyRw(b, "", false, arr[j], dt, st, statusFile);
				if (st != "" && st != "none")
				{
					b.PushDictionary();
					b.PushString("class", "ApplyBuff");
					b.PushString("buff", statusFile + ":" + st);
					b.PopDictionary();
				}
				b.PopArray();
				continue;
			}
			CopyRw(b, k, true, e, dt, st, statusFile);
		}
		b.PopDictionary();
	}

	bool HasExplode(SValue@ v)
	{
		if (v is null)
			return false;
		auto t = v.GetType();
		if (t == SValueType::Array)
		{
			auto arr = v.GetArray();
			for (uint i = 0; i < arr.length(); i++)
				if (HasExplode(arr[i]))
					return true;
			return false;
		}
		if (t != SValueType::Dictionary)
			return false;
		if (StrOf(v, "class") == "Explode")
			return true;
		auto keys = v.GetDictionaryKeys();
		for (uint i = 0; i < keys.length(); i++)
			if (HasExplode(v.GetDictionaryEntry(keys[i])))
				return true;
		return false;
	}

	// the draft's on-hit (dt, st) reaches something: the template or a snippet explodes
	bool DraftExplodes(Draft@ d)
	{
		if (d.t != "clone")
		{
			auto tm = CatEntry("templates", d.t);
			if (tm !is null && HasExplode(tm.GetDictionaryEntry("skill")))
				return true;
		}
		for (uint i = 0; i < d.c.length(); i++)
			if (HasExplode(CatEntry("snippets", d.c[i])))
				return true;
		for (uint i = 0; i < d.s.length(); i++)
			if (HasExplode(CatEntry("snippets", d.s[i])))
				return true;
		return false;
	}

	// the main damage bind of a dict's binds: the first numeric "*dmg*" key that is not a multiplier
	string FirstDmgBind(SValue@ binds)
	{
		if (binds is null || binds.GetType() != SValueType::Dictionary)
			return "";
		auto keys = binds.GetDictionaryKeys();
		for (uint i = 0; i < keys.length(); i++)
		{
			auto t = binds.GetDictionaryEntry(keys[i]).GetType();
			if (keys[i].findFirst("dmg") >= 0 && keys[i].findFirst("mul") < 0
				&& (t == SValueType::Integer || t == SValueType::Float))
				return keys[i];
		}
		return "";
	}

	class BindList
	{
		array<string> keys;
		array<SValue@> vals;   // null: the string in strs
		array<string> strs;

		void Set(const string &in k, SValue@ v, const string &in s = "")
		{
			int i = keys.find(k);
			if (i < 0)
			{
				keys.insertLast(k);
				vals.insertLast(v);
				strs.insertLast(s);
				return;
			}
			@vals[i] = v;
			strs[i] = s;
		}

		void AddAll(SValue@ d)
		{
			if (d is null || d.GetType() != SValueType::Dictionary)
				return;
			auto ks = d.GetDictionaryKeys();
			for (uint i = 0; i < ks.length(); i++)
				Set(ks[i], d.GetDictionaryEntry(ks[i]));
		}

		string Str(const string &in k)
		{
			int i = keys.find(k);
			if (i < 0)
				return "";
			if (vals[i] is null)
				return strs[i];
			return vals[i].GetType() == SValueType::String ? vals[i].GetString() : "";
		}
	}

	void PushSnippets(SValueBuilder& b, array<SValue@>@ sns, const string &in dt, const string &in st,
		const string &in statusFile)
	{
		for (uint j = 0; j < sns.length(); j++)
		{
			auto sa = sns[j].GetDictionaryEntry("actions").GetArray();
			for (uint k = 0; k < sa.length(); k++)
				CopyRw(b, "", false, sa[k], dt, st, statusFile);
		}
	}

	bool PushIntField(SValueBuilder& b, const string &in key, const string &in text, SValue@ base, array<string>@ errs)
	{
		if (text != "")
		{
			if (!IsIntText(text) || !InInt32(text) || parseInt(text) < 0)
			{
				errs.insertLast(key + " '" + text + "' is not a whole number >= 0");
				return false;
			}
			b.PushInteger(key, parseInt(text));
			return true;
		}
		auto v = base.GetDictionaryEntry(key);
		if (v !is null)
			b.PushSimple(key, v.Copy());
		return v !is null;
	}

	int IntOf(SValue@ d, const string &in key, int def)
	{
		auto v = d is null ? null : d.GetDictionaryEntry(key);
		return (v is null || v.GetType() != SValueType::Integer) ? def : v.GetInteger();
	}

	// the built "skill" dict for `slot`, or null with the reasons in errs
	SValue@ ComposeBuild(Draft@ d, const string &in slot, array<string>@ errs)
	{
		auto cat = Catalog();
		if (cat is null)
		{
			errs.insertLast("no catalog " + COMPOSE_FILE);
			return null;
		}
		if (d.bad != "")
			errs.insertLast(d.bad);
		string statusFile = StrOf(cat, "status-file");
		auto def = FindDef(slot);
		auto slotBase = VanillaLevel(slot, 0);
		if (def is null || slotBase is null)
		{
			errs.insertLast("no skill '" + slot + "'");
			return null;
		}

		bool clone = d.t == "clone";
		SValue@ base;
		array<string> inherit;
		string needs;
		if (clone)
		{
			if (d.src == "")
				errs.insertLast("clone: pick a source skill");
			else if (FindDef(d.src) is null)
				errs.insertLast("clone: no skill '" + d.src + "'");
			else
			{
				@base = VanillaLevel(d.src, 0);
				string cls = StrOf(base, "class");
				if (cls.findFirst("Skills::") != 0)
				{
					errs.insertLast("clone: '" + d.src + "' has class '" + cls + "', not a Skills:: class");
					@base = null;
				}
			}
			inherit.insertLast("skill-cost");
		}
		else
		{
			auto tm = CatEntry("templates", d.t);
			if (tm is null)
				errs.insertLast("unknown start '" + d.t + "'");
			else
			{
				@base = tm.GetDictionaryEntry("skill");
				needs = StrOf(tm, "needs");
				auto inh = tm.GetDictionaryEntry("inherit");
				if (inh !is null)
				{
					auto arr = inh.GetArray();
					for (uint i = 0; i < arr.length(); i++)
						inherit.insertLast(arr[i].GetString());
				}
			}
		}
		if (base is null)
			return null;

		SValue@ proj;
		if (d.p != "")
		{
			@proj = CatEntry("projectiles", d.p);
			if (proj is null)
				errs.insertLast("unknown projectile '" + d.p + "'");
		}
		array<SValue@> castSn, startSn;
		for (uint i = 0; i < d.c.length(); i++)
		{
			auto sn = CatEntry("snippets", d.c[i]);
			if (sn is null) errs.insertLast("unknown snippet '" + d.c[i] + "'"); else castSn.insertLast(sn);
			if (StrOf(sn, "needs") == "proj-unit") needs = "proj-unit";
		}
		for (uint i = 0; i < d.s.length(); i++)
		{
			auto sn = CatEntry("snippets", d.s[i]);
			if (sn is null) errs.insertLast("unknown snippet '" + d.s[i] + "'"); else startSn.insertLast(sn);
			if (StrOf(sn, "needs") == "proj-unit") needs = "proj-unit";
		}
		if (d.dt != "physical" && CatIds("damage-types").find(d.dt) < 0)
			errs.insertLast("unknown damage type '" + d.dt + "'");
		if (d.st != "none" && CatIds("statuses").find(d.st) < 0)
			errs.insertLast("unknown status '" + d.st + "'");
		string nerr = NameError(d.n);
		if (nerr != "")
			errs.insertLast(nerr);

		// binds: the start's, then the projectile's, then the snippets'
		BindList binds;
		binds.AddAll(base.GetDictionaryEntry("binds"));
		if (proj !is null)
		{
			binds.AddAll(proj.GetDictionaryEntry("binds"));
			binds.Set("proj-unit", null, StrOf(proj, "unit"));
		}
		for (uint i = 0; i < castSn.length(); i++)
			binds.AddAll(castSn[i].GetDictionaryEntry("binds"));
		for (uint i = 0; i < startSn.length(); i++)
			binds.AddAll(startSn[i].GetDictionaryEntry("binds"));
		if (needs == "proj-unit" && binds.Str("proj-unit") == "")
			errs.insertLast("pick a projectile");
		string dmgKey = d.t == "nova" ? "nova-dmg" : proj !is null ? StrOf(proj, "dmg-bind") : FirstDmgBind(base.GetDictionaryEntry("binds"));
		if (d.dmg != "" && (dmgKey == "" || binds.keys.find(dmgKey) < 0))
			errs.insertLast("dmg: this skill has no damage bind to set");
		if (errs.length() > 0)
			return null;

		int oldCp = IntOf(base, "castpoint", -1);
		int newCp = (d.cp != "" && IsIntText(d.cp)) ? parseInt(d.cp) : oldCp;

		SValueBuilder b;
		b.PushDictionary();
		array<string> done = { "binds", "actions", "timeline", "castpoint", "cooldown", "mana-cost", "skill-cost", "name" };
		for (uint i = 0; i < inherit.length(); i++)
		{
			auto v = slotBase.GetDictionaryEntry(inherit[i]);
			if (v !is null && (clone ? true : base.GetDictionaryEntry(inherit[i]) is null))
			{
				b.PushSimple(inherit[i], v.Copy());
				done.insertLast(inherit[i]);
			}
		}
		auto keys = base.GetDictionaryKeys();
		for (uint i = 0; i < keys.length(); i++)
			if (done.find(keys[i]) < 0)
				b.PushSimple(keys[i], base.GetDictionaryEntry(keys[i]).Copy());
		PushIntField(b, "castpoint", d.cp, base, errs);
		PushIntField(b, "cooldown", d.cd, base, errs);
		PushIntField(b, "mana-cost", d.mc, base, errs);

		b.PushDictionary("binds");
		for (uint i = 0; i < binds.keys.length(); i++)
		{
			string k = binds.keys[i];
			if (k == dmgKey && d.dmg != "")
			{
				string e;
				if (!PushLeaf(b, k, true, binds.vals[i].GetType(), false, d.dmg, e))
					errs.insertLast("dmg: " + e);
			}
			else if (binds.vals[i] is null)
				b.PushString(k, binds.strs[i]);
			else
				b.PushSimple(k, binds.vals[i].Copy());
		}
		b.PopDictionary();

		string dt = d.dt, st = d.st;
		string ownDt = clone ? "physical" : dt, ownSt = clone ? "none" : st;
		auto acts = base.GetDictionaryEntry("actions");
		array<string> actKeys;
		bool addStart = false;
		b.PushDictionary("actions");
		if (acts !is null && acts.GetType() == SValueType::Dictionary)
		{
			auto aks = acts.GetDictionaryKeys();
			for (uint i = 0; i < aks.length(); i++)
			{
				actKeys.insertLast(aks[i]);
				b.PushArray(aks[i]);
				auto arr = acts.GetDictionaryEntry(aks[i]).GetArray();
				for (uint j = 0; j < arr.length(); j++)
					CopyRw(b, "", false, arr[j], ownDt, ownSt, statusFile);
				if (aks[i] == "cast")
					PushSnippets(b, castSn, dt, st, statusFile);
				else if (aks[i] == "start")
					PushSnippets(b, startSn, dt, st, statusFile);
				b.PopArray();
			}
		}
		if (castSn.length() > 0 && actKeys.find("cast") < 0)
			errs.insertLast("clone: '" + d.src + "' has no cast action for the on-cast snippets");
		if (startSn.length() > 0 && actKeys.find("start") < 0)
		{
			if (clone)
				errs.insertLast("clone: '" + d.src + "' has no start action for the on-start snippets");
			else
			{
				addStart = true;
				actKeys.insertLast("start");
				b.PushArray("start");
				PushSnippets(b, startSn, dt, st, statusFile);
				b.PopArray();
			}
		}
		b.PopDictionary();

		auto tl = base.GetDictionaryEntry("timeline");
		if (tl !is null || addStart)
		{
			b.PushArray("timeline");
			if (addStart)
			{
				b.PushInteger(0);
				b.PushString("start");
			}
			if (tl !is null)
			{
				auto arr = tl.GetArray();
				for (uint i = 0; i < arr.length(); i++)
				{
					auto t = arr[i].GetType();
					if (t == SValueType::Integer && arr[i].GetInteger() == oldCp && !IsStartEntry(arr, i))
						b.PushInteger(newCp);
					else
						b.PushSimple(arr[i].Copy());
					if (t == SValueType::String && actKeys.find(arr[i].GetString()) < 0)
						errs.insertLast("the timeline names action '" + arr[i].GetString() + "', which is missing");
				}
			}
			b.PopArray();
		}
		else if (clone && startSn.length() > 0)
			errs.insertLast("clone: '" + d.src + "' has no timeline");
		b.PopDictionary();

		// what the engine will load: the units must resolve (ShootProjectile, PlayerSkill ctor)
		for (uint i = 0; i < binds.keys.length(); i++)
		{
			string u = binds.Str(binds.keys[i]);
			if (u.length() > 5 && u.substr(u.length() - 5) == ".unit" && Resources::GetUnitProducer(u) is null)
				errs.insertLast("unit '" + u + "' (" + binds.keys[i] + ") does not load");
		}
		if (errs.length() > 0)
			return null;
		return b.Build();
	}

	// everything the Apply button and Validate refuse on
	SValue@ ComposeCheck(const string &in slot, const string &in text, array<string>@ errs)
	{
		auto live = FindLive(slot);
		if (live is null)
			errs.insertLast("'" + slot + "' is not a learned skill");
		else if (live.m_type != PlayerSkillType::Spell)
			errs.insertLast("'" + slot + "' is not a spell slot");
		else if (live.GetTargetingMode() == Skills::TargetingMode::Passive && !IsComposed(slot))
			errs.insertLast("'" + slot + "' is a passive");
		if (errs.length() > 0)
			return null;
		return ComposeBuild(ParseDraft(text), slot, errs);
	}

	bool ComposeValidate(Edit@ e, string &out err)
	{
		if (e.level != 0)
		{
			err = COMPOSE_PATH + " is level 0 only";
			return false;
		}
		if (e.value == "")
		{
			if (FindDef(e.skill) !is null)
				return true;
			err = "no skill '" + e.skill + "'";
			return false;
		}
		array<string> errs;
		ComposeCheck(e.skill, e.value, errs);
		if (errs.length() == 0)
			return true;
		err = errs[0];
		return false;
	}

	SValue@ EmptyDict(SValue@ keepCostOf = null)
	{
		SValueBuilder b;
		b.PushDictionary();
		auto c = keepCostOf is null ? null : keepCostOf.GetDictionaryEntry("skill-cost");
		if (c !is null)
			b.PushSimple("skill-cost", c.Copy());
		b.PopDictionary();
		return b.Build();
	}

	int g_composeApplied;
	string g_composeLast;     // "slot: name" of the last applied draft

	bool ComposeApply(Edit@ e, string &out err)
	{
		auto def = FindDef(e.skill);
		if (def is null)
		{
			err = "no skill '" + e.skill + "'";
			return false;
		}
		Snapshot(e.skill, def);
		for (uint i = 0; i < def.m_modSkills.length(); i++)
			Snapshot(def.m_modSkills[i].m_id, def.m_modSkills[i]);
		if (e.value == "")
			return true;   // RestoreVanilla already put it back
		auto d = ParseDraft(e.value);
		array<string> errs;
		auto built = ComposeBuild(d, e.skill, errs);
		if (built is null)
		{
			err = errs.length() > 0 ? errs[0] : "build failed";
			return false;
		}
		VanillaParams@ v;
		g_vanilla.get(e.skill, @v);
		@def.m_levelParams[0] = built;
		for (uint k = 1; k < def.m_levelParams.length(); k++)
			@def.m_levelParams[k] = EmptyDict(k < v.params.length() ? v.params[k] : null);
		for (uint i = 0; i < def.m_modSkills.length(); i++)
		{
			auto m = def.m_modSkills[i];
			VanillaParams@ mv;
			g_vanilla.get(m.m_id, @mv);
			for (uint k = 0; k < m.m_levelParams.length(); k++)
				@m.m_levelParams[k] = EmptyDict(mv !is null && k < mv.params.length() ? mv.params[k] : null);
		}
		def.m_name = d.n;
		g_composeApplied++;
		g_composeLast = e.skill + ": " + d.n;
		HWP::Log("devarena", "compose-dict " + e.skill + " " + SvJson(built));
		return true;
	}

	// the draft on a slot in the wanted version, "" none
	string DraftOn(const string &in slot)
	{
		EnsureVersions();
		auto v = g_versions[g_want];
		for (uint i = 0; i < v.edits.length(); i++)
			if (v.edits[i].skill == slot && v.edits[i].path == COMPOSE_PATH)
				return v.edits[i].value;
		return "";
	}

	bool IsComposed(const string &in slot)
	{
		return DraftOn(slot) != "";
	}

	// ---- typed JSON of an SValue, for tools that turn a built skill back into .sval --------
	// int -> number, float -> {"f":x}, ivec2 -> {"ivec2":[x,y]}, vec2 -> {"vec2":[x,y]}
	string SvJson(SValue@ v)
	{
		if (v is null)
			return "null";
		auto t = v.GetType();
		if (t == SValueType::Integer) return "" + v.GetInteger();
		if (t == SValueType::Float) return "{\"f\":" + formatFloat(v.GetFloat(), "", 0, 4) + "}";
		if (t == SValueType::Boolean) return v.GetBoolean() ? "true" : "false";
		if (t == SValueType::String) return GameLab::Quote(v.GetString());
		if (t == SValueType::IVector2) { auto i = v.GetIVector2(); return "{\"ivec2\":[" + i.x + "," + i.y + "]}"; }
		if (t == SValueType::Vector2)
		{
			auto f = v.GetVector2();
			return "{\"vec2\":[" + formatFloat(f.x, "", 0, 4) + "," + formatFloat(f.y, "", 0, 4) + "]}";
		}
		if (t == SValueType::Array)
		{
			array<string> parts;
			auto arr = v.GetArray();
			for (uint i = 0; i < arr.length(); i++)
				parts.insertLast(SvJson(arr[i]));
			return "[" + join(parts, ",") + "]";
		}
		if (t == SValueType::Dictionary)
		{
			array<string> parts;
			auto keys = v.GetDictionaryKeys();
			for (uint i = 0; i < keys.length(); i++)
				parts.insertLast(GameLab::Quote(keys[i]) + ":" + SvJson(v.GetDictionaryEntry(keys[i])));
			return "{" + join(parts, ",") + "}";
		}
		return "\"?" + TypeName(t) + "\"";
	}

	// the leaves of a dict as "path = value" rows, for the preview
	void Leaves(SValue@ v, const string &in path, array<string>@ rows)
	{
		auto t = v.GetType();
		if (t == SValueType::Dictionary)
		{
			auto keys = v.GetDictionaryKeys();
			for (uint i = 0; i < keys.length(); i++)
				Leaves(v.GetDictionaryEntry(keys[i]), path == "" ? keys[i] : path + "." + keys[i], rows);
		}
		else if (t == SValueType::Array)
		{
			auto arr = v.GetArray();
			if (arr.length() == 0)
				rows.insertLast(path + " = []");
			for (uint i = 0; i < arr.length(); i++)
				Leaves(arr[i], path + "." + i, rows);
		}
		else
			rows.insertLast(path + " = " + LeafText(v));
	}
}
}
