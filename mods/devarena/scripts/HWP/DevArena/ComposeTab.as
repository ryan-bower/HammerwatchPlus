// Dev Arena dock, Compose tab: build a skill from catalog parts onto a learned spell slot
// (Compose.as). Pick a slot, a start, a projectile and snippets; CHECK lists what the build
// refuses; Apply commits the draft as one tuner edit (a new version, so A/B, undo, the
// override file and the Bench all see it). "tune it" opens the Tune tab on the slot.
namespace HWP
{
namespace DevArena
{
	string g_cmpSlot;
	Draft@ g_cmpDraft;
	string g_cmpLoadedFor;      // the slot the draft was last loaded from
	string g_cmpCheckKey;       // cache: slot|draft|live
	array<string> g_cmpErrs;
	SValue@ g_cmpBuilt;
	int g_cmpApplies;

	const array<string> CMP_FIELDS = { "cp", "cd", "mc", "dmg" };
	const array<string> CMP_FIELD_LABELS = { "castpoint", "cooldown", "mana", "dmg" };

	// learned spell slots a draft can go on
	array<string> ComposeSlots()
	{
		array<string> ids;
		auto plr = LocalPlayer();
		if (plr is null)
			return ids;
		for (uint i = 1; i < plr.m_skills.length(); i++)
		{
			auto s = plr.m_skills[i];
			if (s.m_type != PlayerSkillType::Spell)
				continue;
			if (s.GetTargetingMode() == Skills::TargetingMode::Passive && !IsComposed(s.m_id))
				continue;
			ids.insertLast(s.m_id);
		}
		return ids;
	}

	string SkillLabel(const string &in id)
	{
		auto def = FindDef(id);
		return (def is null || def.m_name == "") ? id : def.m_name;
	}

	Draft@ CmpDraft()
	{
		if (g_cmpDraft is null)
			@g_cmpDraft = Draft();
		if (g_cmpLoadedFor != g_cmpSlot)
		{
			g_cmpLoadedFor = g_cmpSlot;
			string on = DraftOn(g_cmpSlot);
			if (on != "")
				@g_cmpDraft = ParseDraft(on);
		}
		return g_cmpDraft;
	}

	void CmpRecheck()
	{
		auto d = CmpDraft();
		string key = g_cmpSlot + "|" + d.Text() + "|" + g_live;
		if (key == g_cmpCheckKey)
			return;
		g_cmpCheckKey = key;
		g_cmpErrs.resize(0);
		@g_cmpBuilt = g_cmpSlot == "" ? null : ComposeCheck(g_cmpSlot, d.Text(), g_cmpErrs);
		if (g_cmpSlot == "")
			g_cmpErrs.insertLast("no spell slot (learn a skill first)");
	}

	string FieldOf(Draft@ d, const string &in f)
	{
		if (f == "cp") return d.cp;
		if (f == "cd") return d.cd;
		if (f == "mc") return d.mc;
		if (f == "dmg") return d.dmg;
		if (f == "n") return d.n;
		if (f == "src") return d.src;
		return "";
	}

	void ComposeSubmit(const string &in id, const string &in text)
	{
		auto d = CmpDraft();
		string f = id.substr(5);   // "cmpf|<field>"
		string v = text.replace(";", "").replace("=", "").replace("|", "");
		if (f == "cp") d.cp = v;
		else if (f == "cd") d.cd = v;
		else if (f == "mc") d.mc = v;
		else if (f == "dmg") d.dmg = v;
		else if (f == "n") d.n = v;
		else if (f == "src") d.src = v;
		HWP::Log("devarena", "compose draft " + d.Text());
	}

	// the effective value the start gives a field, shown dim while the field is empty
	string CmpEffective(const string &in f)
	{
		if (g_cmpBuilt is null)
			return "";
		if (f == "cp") return LeafText(g_cmpBuilt.GetDictionaryEntry("castpoint"));
		if (f == "cd") return LeafText(g_cmpBuilt.GetDictionaryEntry("cooldown"));
		if (f == "mc") return LeafText(g_cmpBuilt.GetDictionaryEntry("mana-cost"));
		auto d = CmpDraft();
		auto binds = g_cmpBuilt.GetDictionaryEntry("binds");
		string k = d.t == "nova" ? "nova-dmg" : StrOf(CatEntry("projectiles", d.p), "dmg-bind");
		if (k == "" && d.t == "clone")
			k = FirstDmgBind(binds);
		return k == "" || binds is null ? "-" : LeafText(binds.GetDictionaryEntry(k));
	}

	// wrapped toggle chips; `on` marks the lit ones. Returns the new y, `clicked` the id.
	float CmpChips(Ui@ ui, const string &in prefix, const array<string> &in ids, const array<string> &in labels,
		const array<bool> &in on, float x, float y, float w, string &out clicked)
	{
		clicked = "";
		float row = RowH();
		float cx = x;
		for (uint i = 0; i < ids.length(); i++)
		{
			string label = i < labels.length() ? labels[i] : ids[i];
			float bw = min(ui.TextW(label) + 6, w);
			if (cx > x && cx + bw > x + w)
			{
				cx = x;
				y += row + 2;
			}
			if (ui.Button(prefix + ids[i], vec4(cx, y, bw, row), Short(ui, label, bw - 4), on[i] ? COL_ON : COL_BUTTON))
				clicked = ids[i];
			cx += bw + 2;
		}
		return y + row + PAD;
	}

	float CmpPick(Ui@ ui, const string &in label, const string &in prefix, const array<string> &in ids,
		const array<string> &in labels, const string &in cur, float x, float y, float w, string &out clicked)
	{
		ui.Text(x, y + 1, label, COL_DIM);
		array<bool> on;
		for (uint i = 0; i < ids.length(); i++)
			on.insertLast(ids[i] == cur);
		return CmpChips(ui, prefix, ids, labels, on, x + 52, y, w - 52, clicked);
	}

	array<string> Toggle(const array<string> &in list, const string &in id)
	{
		array<string> r = list;
		int i = r.find(id);
		if (i >= 0)
			r.removeAt(i);
		else
			r.insertLast(id);
		return r;
	}

	float LayoutCompose(Ui@ ui, float x, float y, float w)
	{
		float row = RowH();
		string clicked;
		array<string> none;

		auto slots = ComposeSlots();
		if (slots.find(g_cmpSlot) < 0)
			g_cmpSlot = slots.length() > 0 ? slots[slots.length() - 1] : "";
		auto d = CmpDraft();

		y = Head(ui, x, y, "COMPOSE  (replaces a spell slot; Revert puts it back)");
		ui.Text(x, y + 1, "name", COL_DIM);
		Field(ui, "cmpf|n", vec4(x + 52, y, w - 52, row), d.n);
		y += row + PAD;

		array<string> slotLabels;
		for (uint i = 0; i < slots.length(); i++)
			slotLabels.insertLast(SkillLabel(slots[i]) + (IsComposed(slots[i]) ? " *" : ""));
		y = CmpPick(ui, "slot", "cmpslot|", slots, slotLabels, g_cmpSlot, x, y, w, clicked);
		if (clicked != "")
		{
			g_cmpSlot = clicked;
			d = CmpDraft();
		}

		y = CmpPick(ui, "start", "cmpt|", COMPOSE_STARTS, none, d.t, x, y, w, clicked);
		if (clicked != "")
			d.t = clicked;
		if (d.t == "clone")
		{
			ui.Text(x, y + 1, "source", COL_DIM);
			Field(ui, "cmpf|src", vec4(x + 52, y, w - 52, row), d.src == "" ? "(skill id)" : d.src, d.src == "" ? COL_DIM : COL_TEXT);
			y += row + 2;
			array<string> own;
			auto plr = LocalPlayer();
			for (uint i = 1; plr !is null && i < plr.m_skills.length(); i++)
				if (plr.m_skills[i].m_id != g_cmpSlot)
					own.insertLast(plr.m_skills[i].m_id);
			array<string> ownLabels;
			for (uint i = 0; i < own.length(); i++)
				ownLabels.insertLast(VanillaName(own[i]));
			y = CmpPick(ui, "", "cmpsrc|", own, ownLabels, d.src, x, y, w, clicked);
			if (clicked != "")
				d.src = clicked;
		}

		auto projs = CatIds("projectiles");
		projs.insertAt(0, "none");
		y = CmpPick(ui, "shoots", "cmpp|", projs, none, d.p == "" ? "none" : d.p, x, y, w, clicked);
		if (clicked != "")
			d.p = clicked == "none" ? "" : clicked;
		auto tm = CatEntry("templates", d.t);
		auto pe = CatEntry("projectiles", d.p);
		string about = d.t == "clone" ? "the source's own base dict" : StrOf(tm, "about");
		if (pe !is null)
			about += "; " + d.p + " from " + StrOf(pe, "from");
		ui.Text(x, y, Short(ui, about, w), COL_DIM);
		y += row + PAD;

		// CAST: four fields in one row
		y = Head(ui, x, y, "CAST  (empty = the start's value)");
		float fw = (w - 6) / 4;
		for (uint i = 0; i < CMP_FIELDS.length(); i++)
		{
			float fx = x + i * (fw + 2);
			ui.Text(fx, y, Short(ui, CMP_FIELD_LABELS[i], fw), COL_DIM);
			string v = FieldOf(d, CMP_FIELDS[i]);
			string id = "cmpf|" + CMP_FIELDS[i];
			Field(ui, id, vec4(fx, y + row, fw, row), v);
			if (v == "" && !(g_typing && g_editId == id))
				ui.Text(fx + 2, y + row + 1, Short(ui, CmpEffective(CMP_FIELDS[i]), fw - 4), COL_DIM);
		}
		y += row * 2 + PAD;

		// snippets
		auto sns = CatIds("snippets");
		array<string> startable, about2;
		for (uint i = 0; i < sns.length(); i++)
			if (StrOf(CatEntry("snippets", sns[i]), "needs") == "")
				startable.insertLast(sns[i]);
		y = Head(ui, x, y, "ADD");
		array<bool> on;
		for (uint i = 0; i < startable.length(); i++)
			on.insertLast(d.Has(d.s, startable[i]));
		ui.Text(x, y + 1, "on start", COL_DIM);
		y = CmpChips(ui, "cmps|", startable, none, on, x + 52, y, w - 52, clicked);
		if (clicked != "")
			d.s = Toggle(d.s, clicked);
		on.resize(0);
		for (uint i = 0; i < sns.length(); i++)
			on.insertLast(d.Has(d.c, sns[i]));
		ui.Text(x, y + 1, "on cast", COL_DIM);
		y = CmpChips(ui, "cmpc|", sns, none, on, x + 52, y, w - 52, clicked);
		if (clicked != "")
			d.c = Toggle(d.c, clicked);
		for (uint i = 0; i < sns.length(); i++)
			if (d.Has(d.c, sns[i]) || d.Has(d.s, sns[i]))
				about2.insertLast(sns[i] + ": " + StrOf(CatEntry("snippets", sns[i]), "about"));
		for (uint i = 0; i < about2.length(); i++)
		{
			ui.Text(x, y, Short(ui, about2[i], w), COL_DIM);
			y += row;
		}
		y += PAD;

		// ON HIT: only where our own Explode effects are (template or snippet)
		if (d.t != "clone" && DraftExplodes(d))
		{
			y = Head(ui, x, y, "ON HIT  (the explosions)");
			auto dts = CatIds("damage-types");
			y = CmpPick(ui, "damage", "cmpdt|", dts, none, d.dt, x, y, w, clicked);
			if (clicked != "")
				d.dt = clicked;
			auto sts = CatIds("statuses");
			sts.insertAt(0, "none");
			y = CmpPick(ui, "status", "cmpst|", sts, none, d.st, x, y, w, clicked);
			if (clicked != "")
				d.st = clicked;
			y += PAD;
		}

		// CHECK + buttons
		CmpRecheck();
		y = Head(ui, x, y, "CHECK");
		if (g_cmpErrs.length() == 0)
		{
			ui.Text(x, y, "ok: builds and loads", COL_BAR);
			y += row;
		}
		for (uint i = 0; i < g_cmpErrs.length(); i++)
		{
			ui.Text(x, y, Short(ui, "! " + g_cmpErrs[i], w), COL_ERR);
			y += row;
		}
		y += 2;
		bool ok = g_cmpErrs.length() == 0;
		float bx = x;
		string la = "Apply", lr = "Revert slot", lt = "tune it";
		if (ui.Button("cmp-apply", vec4(bx, y, ui.TextW(la) + 8, row), la, ok ? COL_ON : COL_BUTTON, ok ? COL_TEXT : COL_DIM) && ok)
		{
			string err;
			if (Commit1(g_cmpSlot, 0, COMPOSE_PATH, d.Text(), err) >= 0)
			{
				g_cmpApplies++;
				HWP::Log("devarena", "compose apply " + g_cmpSlot + " " + d.Text());
			}
		}
		bx += ui.TextW(la) + 10;
		bool composed = IsComposed(g_cmpSlot);
		if (ui.Button("cmp-revert", vec4(bx, y, ui.TextW(lr) + 8, row), lr, COL_BUTTON, composed ? COL_TEXT : COL_DIM) && composed)
		{
			string err;
			if (Commit1(g_cmpSlot, 0, COMPOSE_PATH, "", err) >= 0)
				HWP::Log("devarena", "compose revert " + g_cmpSlot);
		}
		bx += ui.TextW(lr) + 10;
		if (ui.Button("cmp-tune", vec4(bx, y, ui.TextW(lt) + 8, row), lt) && g_cmpSlot != "")
		{
			g_tab = "tune";
			g_tuneSkill = g_cmpSlot;
			g_scroll = 0;
		}
		y += row + 2;
		ui.Text(x, y, composed ? "on the slot: " + Short(ui, DraftOn(g_cmpSlot) == d.Text() ? "this draft" : "an older draft", w - 80)
			: "the slot is vanilla", COL_DIM);
		y += row + PAD;

		// PREVIEW
		if (g_cmpBuilt !is null)
		{
			y = Head(ui, x, y, "PREVIEW  (the slot's new base dict)");
			array<string> rows;
			Leaves(g_cmpBuilt, "", rows);
			uint cap = min(rows.length(), 40);
			for (uint i = 0; i < cap; i++)
			{
				ui.Text(x, y, Short(ui, rows[i], w), COL_SUB);
				y += row;
			}
			if (rows.length() > cap)
			{
				ui.Text(x, y, "+" + (rows.length() - cap) + " more", COL_DIM);
				y += row;
			}
		}
		return y;
	}
}
}
