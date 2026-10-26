// Level curves for the Tune tab's NUMBERS card.
//
// Level L (1-based) of a skill reads its params from {m_levelParams[L-1], m_levelParams[0]},
// the upgrade first (PlayerBase.AddPlayerSkill, PlayerBase.as:178-186, and for binds the
// m_currSkillData list built in the same order). So a field's value at L is the upgrade's
// leaf when it has one, else the base's. A cell edit at L writes into m_levelParams[L-1].
//
// Growth is the slope of the line through level 1 that fits the other levels best (least
// squares with the intercept fixed at the base): g = sum((L-1)(v_L - v_1)) / sum((L-1)^2).
// Setting a growth rewrites every level from 2 up to v_1 + g(L-1), rounded for int fields,
// except pinned cells. tools/devarena/curve.py is the same math, tested in tests/.
namespace HWP
{
namespace DevArena
{
	int Levels(PlayerSkillDef@ def)
	{
		return def is null ? 0 : int(def.m_levelParams.length());
	}

	// the leaf at level L (1-based); own is true when level L's dict has it itself
	SValue@ LevelLeaf(PlayerSkillDef@ def, int L, const string &in path, bool &out own)
	{
		own = false;
		if (def is null || L < 1 || L > Levels(def))
			return null;
		if (L > 1)
		{
			auto v = Lookup(def.m_levelParams[L - 1], path);
			if (v !is null)
			{
				own = true;
				return v;
			}
		}
		own = L == 1;
		return Lookup(def.m_levelParams[0], path);
	}

	bool IsNumeric(SValue@ v)
	{
		return v !is null && (v.GetType() == SValueType::Integer || v.GetType() == SValueType::Float);
	}

	float NumOf(SValue@ v)
	{
		if (v is null)
			return 0;
		return v.GetType() == SValueType::Integer ? float(v.GetInteger()) : v.GetFloat();
	}

	array<float>@ CurveValues(PlayerSkillDef@ def, const string &in path)
	{
		array<float> res;
		for (int L = 1; L <= Levels(def); L++)
		{
			bool own;
			res.insertLast(NumOf(LevelLeaf(def, L, path, own)));
		}
		return res;
	}

	float FitGrowth(const array<float>@ v)
	{
		float num = 0, den = 0;
		for (uint i = 1; i < v.length(); i++)
		{
			num += float(i) * (v[i] - v[0]);
			den += float(i * i);
		}
		return den == 0 ? 0 : num / den;
	}

	string NumText(float f, bool isInt)
	{
		if (isInt)
			return "" + int(f < 0 ? f - 0.5f : f + 0.5f);
		return formatFloat(f, "", 0, 3);
	}

	string PinKey(const string &in skill, const string &in path, int L)
	{
		return skill + "|" + path + "|" + L;
	}

	bool IsPinned(const string &in skill, const string &in path, int L)
	{
		return g_pins.exists(PinKey(skill, path, L));
	}

	void TogglePin(const string &in skill, const string &in path, int L)
	{
		auto k = PinKey(skill, path, L);
		if (g_pins.exists(k))
			g_pins.delete(k);
		else
			g_pins.set(k, true);
		g_lastAction = (g_pins.exists(k) ? "pinned " : "unpinned ") + path + " L" + L;
		EmitOverride();
	}

	// the edits that put `path` on the line v_1 + g(L-1); pinned levels and levels already on
	// the line are left out
	array<Edit@>@ GrowthEdits(const string &in skill, PlayerSkillDef@ def, const string &in path, float g)
	{
		array<Edit@> res;
		bool own;
		auto base = LevelLeaf(def, 1, path, own);
		if (!IsNumeric(base))
			return res;
		bool isInt = base.GetType() == SValueType::Integer;
		float v1 = NumOf(base);
		for (int L = 2; L <= Levels(def); L++)
		{
			if (IsPinned(skill, path, L))
				continue;
			string want = NumText(v1 + g * float(L - 1), isInt);
			if (LeafText(LevelLeaf(def, L, path, own)) == want)
				continue;
			res.insertLast(MakeEdit(skill, L - 1, path, want));
		}
		return res;
	}

	// a growth step: 5% of the base, at least 1 for an int field
	float GrowthStep(PlayerSkillDef@ def, const string &in path)
	{
		bool own;
		auto base = LevelLeaf(def, 1, path, own);
		float s = NumOf(base) * 0.05f;
		if (s < 0)
			s = -s;
		if (base !is null && base.GetType() == SValueType::Integer)
			s = max(1.0f, float(int(s + 0.5f)));
		return s <= 0 ? 0.05f : s;
	}

	// sub-skills (modifier-skills) the player has learned that set `path` themselves: they are
	// inserted ahead of the skill's own params and win (PlayerBase.as:188-210)
	string SubMask(PlayerSkillDef@ def, const string &in path)
	{
		auto plr = LocalPlayer();
		if (def is null || plr is null || plr.m_record is null)
			return "";
		array<string> ids;
		for (uint i = 0; i < def.m_modSkills.length(); i++)
		{
			auto m = def.m_modSkills[i];
			int lvl = plr.m_record.GetSkillLevel(m);
			if (lvl <= 0 || m.m_levelParams.length() == 0)
				continue;
			bool hit = Lookup(m.m_levelParams[0], path) !is null;
			if (!hit && lvl > 1 && lvl <= int(m.m_levelParams.length()))
				hit = Lookup(m.m_levelParams[lvl - 1], path) !is null;
			if (hit)
				ids.insertLast(m.m_id);
		}
		return join(ids, ",");
	}
}
}
