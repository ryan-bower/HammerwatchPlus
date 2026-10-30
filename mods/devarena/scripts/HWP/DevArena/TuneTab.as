// The dock's Tune tab (docs/devarena/SPEC.md, "Tuner"): the version bar, a chip per skill of
// the local player, the field filter, then three cards for the chosen skill.
//
// FEEL: castpoint, anim-length and the blocking window at the skill's current level. An edit
// goes to the level dict that supplies the value now (the upgrade when it sets the field
// itself, else the base), so it changes what the player feels and nothing else. A castpoint
// edit also moves the timeline entries that sat on the old castpoint (timeline [0,"start",
// 150,"cast"]: the "cast" event fires at the castpoint).
//
// NUMBERS: every numeric leaf at the top level and under binds, one row of per-level cells
// (own value bright, inherited dim, pinned on a darker fill), then growth: [-] [+] steppers,
// a slider (drag; the range is fixed when grabbed, the edit commits on release) and a
// sparkline of the curve. Pin mode turns a cell click into a pin toggle. A blue * marks a
// field a learned sub-skill sets itself, so an edit there is masked in play.
//
// REFS: string binds that name a resource path. Editing one is allowed, but the resource is
// loaded when the game loads the skill's unit files, so the badge says it needs a relaunch.
namespace HWP
{
namespace DevArena
{
	string g_tuneSkill;
	bool g_pinMode;
	bool g_needsRelaunch;

	// the slider being dragged
	string g_dragPath;
	vec4 g_dragRect;
	float g_dragG0;
	float g_dragRange;
	float g_dragG;

	const array<string> FEEL = { "castpoint", "anim-length", "blocking.0", "blocking.1" };

	// the player's skills with params, in skill-bar order, ids unique
	array<string>@ TuneSkills()
	{
		array<string> ids;
		auto plr = LocalPlayer();
		if (plr is null)
			return ids;
		for (uint i = 0; i < plr.m_skills.length(); i++)
		{
			string id = plr.m_skills[i].m_id;
			auto def = FindDef(id);
			if (def is null || Levels(def) == 0 || ids.find(id) >= 0)
				continue;
			ids.insertLast(id);
		}
		return ids;
	}

	int OwnerLevel(PlayerSkillDef@ def)
	{
		auto plr = LocalPlayer();
		if (plr is null || plr.m_record is null)
			return 1;
		return clamp(plr.m_record.GetSkillLevel(def), 1, max(1, Levels(def)));
	}

	// the m_levelParams index that supplies `path` at level L
	int OwnerIndex(PlayerSkillDef@ def, int L, const string &in path)
	{
		if (L > 1 && L <= Levels(def) && Lookup(def.m_levelParams[L - 1], path) !is null)
			return L - 1;
		return 0;
	}

	bool IsFeel(const string &in path)
	{
		return FEEL.find(path) >= 0 || path == "timeline" || path.findFirst("timeline.") == 0
			|| path == "blocking" || path.findFirst("blocking.") == 0;
	}

	void CollectLeaves(SValue@ d, const string &in prefix, array<string>@ nums, array<string>@ refs)
	{
		if (d is null || d.GetType() != SValueType::Dictionary)
			return;
		auto keys = d.GetDictionary().getKeys();
		keys.sortAsc();
		for (uint i = 0; i < keys.length(); i++)
		{
			string path = prefix + keys[i];
			auto v = d.GetDictionaryEntry(keys[i]);
			if (v is null)
				continue;
			if (prefix == "" && keys[i] == "binds")
			{
				CollectLeaves(v, "binds.", nums, refs);
				continue;
			}
			if (IsFeel(path))
				continue;
			if (IsNumeric(v))
			{
				if (nums.find(path) < 0)
					nums.insertLast(path);
			}
			else if (v.GetType() == SValueType::String && v.GetString().findFirst("/") >= 0)
			{
				if (refs.find(path) < 0)
					refs.insertLast(path);
			}
		}
	}

	bool PassFilter(const string &in path)
	{
		return g_filter == "" || path.findFirst(g_filter) >= 0;
	}

	string Short(Ui@ ui, const string &in s, float w)
	{
		if (ui.TextW(s) <= w)
			return s;
		string t = s;
		while (t.length() > 1 && ui.TextW(t + "..") > w)
			t = t.substr(0, t.length() - 1);
		return t + "..";
	}

	float LayoutTune(Ui@ ui, float x, float y, float w)
	{
		float row = RowH();
		EnsureVersions();

		// version bar
		float bx = x;
		if (ui.Button("ver-prev", vec4(bx, y, 12, row), "<"))
			StepVersion(-1);
		bx += 14;
		string vt = "v" + g_want + "/" + (g_versions.length() - 1);
		ui.Text(bx, y + 1, vt);
		bx += ui.TextW(vt) + 4;
		if (ui.Button("ver-next", vec4(bx, y, 12, row), ">"))
			StepVersion(1);
		bx += 16;
		string ab = ShortKeyLabel(KeyAB()) + " " + (g_onB ? "B" : "A");
		if (ui.Button("ab-swap", vec4(bx, y, ui.TextW(ab) + 5, row), ab))
			SwapAB();
		bx += ui.TextW(ab) + 7;
		if (ui.Button("ab-pin", vec4(bx, y, ui.TextW("pin other") + 5, row), "pin other"))
			PinOther();
		bx += ui.TextW("pin other") + 7;
		if (ui.Button("ab-keep", vec4(bx, y, ui.TextW("keep B") + 5, row), "keep B"))
			KeepB();
		y += row + PAD;

		// skill chips, wrapped
		auto skills = TuneSkills();
		if (skills.length() == 0)
		{
			ui.Text(x, y, "no player skills", COL_DIM);
			return y + row;
		}
		if (skills.find(g_tuneSkill) < 0)
			g_tuneSkill = skills.length() > 1 ? skills[1] : skills[0];   // [0] is the attack
		float cx = x;
		for (uint i = 0; i < skills.length(); i++)
		{
			auto def = FindDef(skills[i]);
			string label = def.m_name == "" ? skills[i] : def.m_name;
			float cw = min(ui.TextW(label) + 5, w);
			if (cx > x && cx + cw > x + w)
			{
				cx = x;
				y += row + 2;
			}
			if (ui.Button("skill|" + skills[i], vec4(cx, y, cw, row), Short(ui, label, cw - 4),
				g_tuneSkill == skills[i] ? COL_ON : COL_BUTTON))
			{
				g_tuneSkill = skills[i];
				g_scroll = 0;
			}
			cx += cw + 2;
		}
		y += row + PAD;

		// filter + pin mode
		float pw = ui.TextW("pin mode") + 5;
		Field(ui, "filter", vec4(x, y, w - pw - 2, row), g_filter == "" ? "" : g_filter, COL_TEXT);
		if (g_filter == "" && !(g_typing && g_editId == "filter"))
			ui.Text(x + 2, y + 1, "filter", COL_DIM);
		if (ui.Button("pin-mode", vec4(x + w - pw, y, pw, row), "pin mode", g_pinMode ? COL_ON : COL_BUTTON))
			g_pinMode = !g_pinMode;
		y += row + PAD;

		auto def = FindDef(g_tuneSkill);
		if (def is null)
			return y;
		int L = OwnerLevel(def);
		int n = Levels(def);

		// FEEL
		ui.Text(x, y, "FEEL  " + g_tuneSkill + "  L" + L + "/" + n, COL_HEAD);
		y += row;
		float half = (w - 4) / 2;
		for (uint i = 0; i < FEEL.length(); i++)
		{
			float fx = x + (i % 2 == 0 ? 0.0f : half + 4);
			bool own;
			auto v = LevelLeaf(def, L, FEEL[i], own);
			float lw = half * 0.55f;
			ui.Text(fx, y + 1, FEEL[i], COL_DIM);
			if (v is null)
				ui.Text(fx + lw, y + 1, "-", COL_DIM);
			else
				Field(ui, "feel|" + FEEL[i], vec4(fx + lw, y, half - lw, row), LeafText(v));
			if (i % 2 == 1)
				y += row + 2;
		}
		y += PAD;

		// NUMBERS
		array<string> nums, refs;
		for (int i = 0; i < n; i++)
			CollectLeaves(def.m_levelParams[i], "", nums, refs);
		ui.Text(x, y, "NUMBERS" + (g_pinMode ? "  (click = pin)" : ""), COL_HEAD);
		y += row;
		float labelW = w * 0.3f;
		float cellW = n == 0 ? 0 : (w - labelW) / float(n);
		for (uint i = 0; i < nums.length(); i++)
		{
			string path = nums[i];
			if (!PassFilter(path))
				continue;
			string label = path.findFirst("binds.") == 0 ? path.substr(6) : path;
			string mask = SubMask(def, path);
			ui.Text(x, y + 1, Short(ui, label, labelW - (mask == "" ? 2 : 8)), COL_TEXT);
			if (mask != "")
				ui.Text(x + labelW - 6, y + 1, "*", COL_SUB);
			for (int lv = 1; lv <= n; lv++)
			{
				bool own;
				auto v = LevelLeaf(def, lv, path, own);
				vec4 cr = vec4(x + labelW + cellW * (lv - 1), y, cellW - 1, row);
				string id = "cell|" + path + "|" + lv;
				bool pinned = IsPinned(g_tuneSkill, path, lv);
				vec4 fill = pinned ? COL_ON : COL_BUTTON;
				string shown = v is null ? "-" : NumText(NumOf(v), v.GetType() == SValueType::Integer);
				if (g_pinMode)
				{
					if (lv > 1 && ui.Button(id, cr, shown, fill, own ? COL_TEXT : COL_DIM))
						TogglePin(g_tuneSkill, path, lv);
					else if (lv == 1)
						ui.Button(id + "|base", cr, shown, COL_BUTTON, COL_TEXT);
				}
				else
					Field(ui, id, cr, shown, own ? COL_TEXT : COL_DIM, fill);
			}
			y += row + 1;

			// growth line
			auto curve = CurveValues(def, path);
			float g = FitGrowth(curve);
			float step = GrowthStep(def, path);
			bool isInt = v1Int(def, path);
			float gx = x + 4;
			if (ui.Button("grow-|" + path, vec4(gx, y, 10, row), "-"))
				ApplyGrowth(def, path, g - step);
			gx += 12;
			float shownG = g_dragPath == path ? g_dragG : g;
			string gt = "g " + NumText(shownG, false);
			ui.Text(gx, y + 1, gt, COL_DIM);
			gx += max(ui.TextW("g -00.000"), ui.TextW(gt)) + 2;
			if (ui.Button("grow+|" + path, vec4(gx, y, 10, row), "+"))
				ApplyGrowth(def, path, g + step);
			gx += 12;
			float sparkW = min(60.0f, w * 0.25f);
			vec4 sr = vec4(gx, y + row * 0.3f, x + w - sparkW - 4 - gx, row * 0.4f);
			if (sr.z > 10)
			{
				if (ui.Button("slide|" + path, vec4(sr.x, y, sr.z, row), "", vec4(0, 0, 0, 0)))
				{
					g_dragPath = path;
					g_dragRect = vec4(sr.x, y, sr.z, row);
					g_dragG0 = g;
					g_dragRange = max(abs(g), step * 10);
					g_dragG = g;
				}
				ui.Fill(sr, COL_BUTTON);
				float t = g_dragRange <= 0 || g_dragPath != path ? 0.5f
					: clamp((shownG - g_dragG0) / (g_dragRange * 2) + 0.5f, 0.0f, 1.0f);
				ui.Fill(vec4(sr.x + sr.z * t - 1, y + 1, 3, row - 2), COL_HEAD);
			}
			DrawSpark(ui, vec4(x + w - sparkW, y + 1, sparkW, row - 2), curve, isInt);
			y += row + 3;
		}

		// REFS
		bool anyRef = false;
		for (uint i = 0; i < refs.length(); i++)
		{
			string path = refs[i];
			if (!PassFilter(path))
				continue;
			if (!anyRef)
			{
				ui.Text(x, y + PAD, "REFS", COL_HEAD);
				y += row + PAD;
				anyRef = true;
			}
			bool own;
			auto v = LevelLeaf(def, L, path, own);
			string label = path.findFirst("binds.") == 0 ? path.substr(6) : path;
			ui.Text(x, y + 1, Short(ui, label, labelW - 2), COL_TEXT);
			float bw = ui.TextW("relaunch") + 4;
			Field(ui, "ref|" + path, vec4(x + labelW, y, w - labelW - bw - 2, row), Short(ui, LeafText(v), w - labelW - bw - 6));
			ui.Text(x + w - bw + 2, y + 1, "relaunch", COL_HEAD);
			y += row + 1;
		}
		return y + PAD;
	}

	bool v1Int(PlayerSkillDef@ def, const string &in path)
	{
		bool own;
		auto v = LevelLeaf(def, 1, path, own);
		return v !is null && v.GetType() == SValueType::Integer;
	}

	void DrawSpark(Ui@ ui, vec4 r, const array<float>@ v, bool isInt)
	{
		if (ui.sb is null || v.length() == 0)
			return;
		float lo = v[0], hi = v[0];
		for (uint i = 1; i < v.length(); i++)
		{
			lo = min(lo, v[i]);
			hi = max(hi, v[i]);
		}
		lo = min(lo, 0.0f);
		float span = hi - lo;
		float bw = r.z / float(v.length());
		for (uint i = 0; i < v.length(); i++)
		{
			float h = span <= 0 ? 1.0f : max(1.0f, (v[i] - lo) / span * r.w);
			ui.Fill(vec4(r.x + bw * i, r.y + r.w - h, max(1.0f, bw - 1), h), COL_BAR);
		}
	}

	void ApplyGrowth(PlayerSkillDef@ def, const string &in path, float g)
	{
		// the fit reads the live skill; while an edit waits on a cast it is the old one
		if (Pending())
		{
			g_lastError = path + ": an edit is still waiting on a cast, growth not applied";
			HWP::Log("devarena", "growth refused " + path + ": edit pending");
			return;
		}
		auto edits = GrowthEdits(g_tuneSkill, def, path, g);
		if (edits.length() == 0)
		{
			g_lastAction = path + ": already on the line";
			return;
		}
		string err;
		Commit(edits, path + " growth " + NumText(g, false), err);
	}

	// the slider: follows the pointer while the button is held, commits on release
	void TickDrag(MenuInput& menuInput, vec2 mouse)
	{
		if (g_dragPath == "")
			return;
		float t = g_dragRect.z <= 0 ? 0.5f : clamp((mouse.x - g_dragRect.x) / g_dragRect.z, 0.0f, 1.0f);
		g_dragG = g_dragG0 + (t * 2 - 1) * g_dragRange;
		if (menuInput.Forward.Down && !menuInput.Forward.Released)
			return;
		string path = g_dragPath;
		g_dragPath = "";
		auto def = FindDef(g_tuneSkill);
		if (def !is null && abs(g_dragG - g_dragG0) > 1e-4f)
			ApplyGrowth(def, path, g_dragG);
	}

	// the time of a timeline's "start" event stays put when the castpoint moves (Entangle is
	// [0,"start",150,"cast"]; a castpoint of 0 shares its time)
	bool IsStartEntry(array<SValue@>@ arr, uint i)
	{
		return i + 1 < arr.length() && arr[i + 1].GetType() == SValueType::String && arr[i + 1].GetString() == "start";
	}

	// a field of the Tune tab was submitted
	void TuneSubmit(const string &in id, const string &in text)
	{
		auto parts = id.split("|");
		auto def = FindDef(g_tuneSkill);
		if (def is null || parts.length() < 2)
			return;
		string path = parts[1];
		string err;
		if (parts[0] == "cell" && parts.length() == 3)
		{
			int lv = parseInt(parts[2]);
			bool own;
			auto cur = LevelLeaf(def, lv, path, own);
			if (!Pending() && cur !is null && LeafText(cur) == text)
				return;
			Commit1(g_tuneSkill, lv - 1, path, text, err);
		}
		else if (parts[0] == "feel")
		{
			int L = OwnerLevel(def);
			int k = OwnerIndex(def, L, path);
			bool own;
			auto cur = LevelLeaf(def, L, path, own);
			if (!Pending() && cur !is null && LeafText(cur) == text)
				return;
			array<Edit@> edits = { MakeEdit(g_tuneSkill, k, path, text) };
			if (path == "castpoint" && cur !is null)
			{
				// the timeline entries on the old castpoint move with it
				int tk = OwnerIndex(def, L, "timeline");
				auto tl = Lookup(def.m_levelParams[tk], "timeline");
				array<SValue@>@ arr = (tl is null || tl.GetType() != SValueType::Array) ? null : tl.GetArray();
				for (uint i = 0; arr !is null && i < arr.length(); i++)
					if (IsNumeric(arr[i]) && LeafText(arr[i]) == LeafText(cur) && !IsStartEntry(arr, i))
						edits.insertLast(MakeEdit(g_tuneSkill, tk, "timeline." + i, text));
			}
			Commit(edits, g_tuneSkill + " " + path + "=" + text, err);
		}
		else if (parts[0] == "ref")
		{
			int k = OwnerIndex(def, OwnerLevel(def), path);
			if (Commit1(g_tuneSkill, k, path, text, err) >= 0)
				g_needsRelaunch = true;
		}
	}
}
}
