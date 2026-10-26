// Dev Arena input log (da-inputlog on|off): what the game made of the player's hands, for the
// watch-mode e2e (gamelab/scenarios/devarena/watch-input.json). Read-only, edge-triggered and
// capped at INPUTLOG_CAP lines per "on"; read in UpdateFrame from the GameInput it is handed.
//   [HWP:devarena] input-btn <main|off|skill1|skill2|skill3|dash|potion|use> down|up
//   [HWP:devarena] input-move <x>,<y>          MoveDir, each component rounded to -1/0/1
//   [HWP:devarena] input-mouse <x>,<y> aim <ax>,<ay>   GameInput.MousePos (moved > 2 px, <= 4/s)
//   [HWP:devarena] input-skill <slot> <id> <button> <why>   a use: <why> is "active" (IsActive
//                  rose: an instant cast, a toggle on, or an aim marker shown), "cooldown" or
//                  "cast" (the cooldown or the cast point restarted: it fired)
//   [HWP:devarena] input-skill-end <slot> <id>       IsActive fell (a toggle off, an aim cancelled)
//   [HWP:devarena] input-skill-blocked <slot> <id> <why>   the slot's button is down and the game
//                  refused it (m_wasBlocked, PlayerTargetingHelper CheckUseSkill :520), once per
//                  press; <why> replays CheckSkillBlocked (:450): "equip <item id>" (requirements
//                  unmet), "disarm", "silence", "self", "aiming <id>", "active <id>" or "?"
//   [HWP:devarena] input-skill-idle <slot> <id> cd <ms> mana <0..1>/<max> can <0|1> active <0|1>
//                  cost <hp>/<mana> x<mul> dash <n> pts <UsePoints> cond <conditionals>
//                  the button has been down 200 ms, nothing fired and nothing refused it: the
//                  state CheckUseSkill (:516) decides on, once per press
//   [HWP:devarena] input-slots <slot>:<id>:<button>:<mode> ...   once, on the first frame;
//                  <mode> is Skills::TargetingMode (TargetAOE and DirectionCharge aim first:
//                  the press shows the marker, a left click places it, PlayerTargetingHelper.as:280)
//   [HWP:devarena] input-potion <used>          potionChargesUsed rose, or m_potionDelay restarted
//   [HWP:devarena] input-log off (<n> lines[, capped])
// "on reset" also zeroes each cooldown and refills mana after reading it (a cheat), so a test
// can press every binding back to back. While it is on, a red all-caps banner sits at the top
// of the screen (RenderInputBanner, every frame), and the same warning goes to the log and the
// local chat on "on" and every INPUTLOG_WARN_MS after, with a line on "off", so a player who sits
// down at a test window knows the resources are fake. The chat only shows in a lobby or after the
// vanilla show_chat, which lives in the menu's script (core Commands.as:13), so the banner is the
// part a single player sees; "off" logs how many frames drew it:
//   [HWP:devarena] input-warn <text>
//   [HWP:devarena] input-log off (<n> lines[, capped]) banner <frames>
// <button> is the input that fires the slot (PlayerTargetingHelper.GetSkillInput, :713-750).
namespace HWP
{
namespace DevArena
{
	const uint INPUTLOG_CAP = 400;
	const int INPUTLOG_WARN_MS = 15000;
	const string INPUTLOG_WARN = "GAMELAB TEST ENVIRONMENT: INFINITE MANA AND NO COOLDOWNS (da-inputlog reset). NOT NORMAL GAMEPLAY.";
	const array<string> INPUTLOG_BUTTONS = { "main", "off", "skill1", "skill2", "skill3", "dash", "potion", "use" };

	bool g_inLog;
	bool g_inReset;
	uint g_inLines;
	array<bool> g_inDown;
	vec2 g_inMove;
	vec2 g_inMouse;
	int g_inMouseMs;
	array<bool> g_inActive;
	array<int> g_inCd;
	array<int> g_inCast;
	array<bool> g_inBlocked;
	array<bool> g_inPressBlocked;
	array<int> g_inHeldMs;
	int g_inPotUsed;
	int g_inPotDelay;
	int g_inWarnMs;
	uint g_inBannerDrawn;

	// one line to the local chat and the log (not counted against INPUTLOG_CAP)
	void InputLogChat(const string &in color, const string &in text)
	{
		HWP::Log("devarena", "input-warn " + text);
		SValueBuilder b;
		b.PushString("\\c" + color + text + "\\d");
		SendSystemMessage("AddChat", b.Build());
	}

	void InputLogLine(const string &in s)
	{
		if (g_inLines >= INPUTLOG_CAP)
			return;
		g_inLines++;
		HWP::Log("devarena", s);
	}

	void SetInputLog(bool on)
	{
		if (!on && g_inLog)
			HWP::Log("devarena", "input-log off (" + g_inLines + " lines" + (g_inLines >= INPUTLOG_CAP ? ", capped)" : ")")
				+ " banner " + g_inBannerDrawn);
		g_inBannerDrawn = 0;
		g_inLog = on;
		g_inLines = 0;
		g_inDown.resize(0);
		g_inActive.resize(0);
		g_inCd.resize(0);
		g_inCast.resize(0);
		g_inBlocked.resize(0);
		g_inPressBlocked.resize(0);
		g_inHeldMs.resize(0);
		g_inMove = vec2();
		g_inMouse = vec2(-1, -1);
		g_inMouseMs = 0;
		g_inPotUsed = -1;
		g_inPotDelay = 0;
	}

	ButtonState InputButton(GameInput& input, uint i)
	{
		switch (i)
		{
		case 0: return input.MainHandAttack;
		case 1: return input.OffHandAttack;
		case 2: return input.Skill1;
		case 3: return input.Skill2;
		case 4: return input.Skill3;
		case 5: return input.Dash;
		case 6: return input.Potion;
		}
		return input.Use;
	}

	// the button that fires m_skills[i] (GetSkillInput, the same walk)
	string ButtonOf(PlayerBase@ plr, uint i)
	{
		auto s = plr.m_skills[i];
		if (s.m_type == PlayerSkillType::MainHand)
			return "main";
		if (s.m_type == PlayerSkillType::OffHand)
			return "off";
		if (s.m_type == PlayerSkillType::Dash)
			return "dash";
		if (s.GetTargetingMode() == Skills::TargetingMode::Passive || s.m_type != PlayerSkillType::Spell)
			return "none";
		int idx = 0;
		for (uint j = 1; j < i; j++)
		{
			auto o = plr.m_skills[j];
			if (o.GetTargetingMode() != Skills::TargetingMode::Passive && o.m_type == PlayerSkillType::Spell)
				idx++;
		}
		return "skill" + min(idx + 1, 3);
	}

	string TargetingName(Skills::TargetingMode m)
	{
		switch (m)
		{
		case Skills::TargetingMode::Passive: return "Passive";
		case Skills::TargetingMode::Direction: return "Direction";
		case Skills::TargetingMode::DirectionCharge: return "DirectionCharge";
		case Skills::TargetingMode::DirectionRepeating: return "DirectionRepeating";
		case Skills::TargetingMode::TargetAOE: return "TargetAOE";
		case Skills::TargetingMode::Channeling: return "Channeling";
		}
		return "Toggle";
	}

	// why CheckSkillBlocked (PlayerTargetingHelper.as:450) refuses the skill, in its order
	string BlockedWhy(PlayerBase@ plr, Skills::Skill@ s)
	{
		if (s.m_equipmentSource !is null && !plr.m_record.equipped.MayEquip(s.m_equipmentSource))
		{
			auto it = cast<Equipment::Item>(s.m_equipmentSource);
			return "equip " + (it !is null ? it.baseItem.m_id : "?");
		}
		bool attack = s.m_type == PlayerSkillType::MainHand || s.m_type == PlayerSkillType::OffHand;
		if (attack && plr.m_buffs.Disarm())
			return "disarm";
		if (s.m_type == PlayerSkillType::Spell && plr.m_buffs.Silence())
			return "silence";
		auto p = cast<Player>(plr);
		if (p !is null && p.m_targetHelper !is null && p.m_targetHelper.m_targetingSkill !is null)
			return "aiming " + p.m_targetHelper.m_targetingSkill.m_id;
		if (s.SelfBlocking())
			return "self";
		for (uint j = 0; j < plr.m_skills.length(); j++)
		{
			auto c = plr.m_skills[j];
			if (c !is s && c.IsActive() && c.IsBlocking())
				return "active " + c.m_id;
		}
		return "?";
	}

	int Unit(float v) { return v > 0.3f ? 1 : v < -0.3f ? -1 : 0; }

	void TickInputLog(int ms, GameInput& input, bool paused)
	{
		if (!g_inLog || paused)
			return;
		g_inDown.resize(INPUTLOG_BUTTONS.length());
		for (uint i = 0; i < INPUTLOG_BUTTONS.length(); i++)
		{
			bool d = InputButton(input, i).Down;
			if (d != g_inDown[i])
				InputLogLine("input-btn " + INPUTLOG_BUTTONS[i] + (d ? " down" : " up"));
			g_inDown[i] = d;
		}
		vec2 mv = vec2(Unit(input.MoveDir.x), Unit(input.MoveDir.y));
		if (mv.x != g_inMove.x || mv.y != g_inMove.y)
			InputLogLine("input-move " + int(mv.x) + "," + int(mv.y));
		g_inMove = mv;
		g_inMouseMs -= ms;
		vec2 mp = input.MousePos;
		if (g_inMouseMs <= 0 && (abs(mp.x - g_inMouse.x) > 2 || abs(mp.y - g_inMouse.y) > 2))
		{
			InputLogLine("input-mouse " + int(mp.x) + "," + int(mp.y) + " aim "
				+ formatFloat(input.AimDir.x, "", 0, 2) + "," + formatFloat(input.AimDir.y, "", 0, 2));
			g_inMouse = mp;
			g_inMouseMs = 250;
		}

		auto plr = cast<PlayerBase>(GetLocalPlayer());
		if (plr is null)
			return;
		uint n = plr.m_skills.length();
		bool first = g_inActive.length() != n;
		g_inActive.resize(n);
		g_inCd.resize(n);
		g_inCast.resize(n);
		g_inBlocked.resize(n);
		g_inPressBlocked.resize(n);
		g_inHeldMs.resize(n);
		if (first)
		{
			string slots;
			for (uint i = 0; i < n; i++)
				slots += " " + i + ":" + plr.m_skills[i].m_id + ":" + ButtonOf(plr, i) + ":" + TargetingName(plr.m_skills[i].GetTargetingMode());
			InputLogLine("input-slots" + slots);
		}
		for (uint i = 0; i < n; i++)
		{
			auto s = plr.m_skills[i];
			auto a = cast<Skills::ActiveSkill>(s);
			auto ps = cast<Skills::PlayerSkill>(s);   // weapon attacks (PlayerSkill.as:153) are not ActiveSkills
			bool act = s.IsActive();
			int cd = a !is null ? a.m_cooldownC : ps !is null ? ps.m_cooldownC : 0;
			int cp = a is null ? 0 : a.m_castingC;
			string why = cd > g_inCd[i] + ms ? "cooldown" : cp > g_inCast[i] + ms ? "cast" : act && !g_inActive[i] ? "active" : "";
			if (!first && why != "")
				InputLogLine("input-skill " + i + " " + s.m_id + " " + ButtonOf(plr, i) + " " + why);
			if (!first && !act && g_inActive[i])
				InputLogLine("input-skill-end " + i + " " + s.m_id);
			int b = INPUTLOG_BUTTONS.find(ButtonOf(plr, i));
			bool held = b >= 0 && g_inDown[b];
			if (!first && held && s.m_wasBlocked && !g_inPressBlocked[i])
			{
				InputLogLine("input-skill-blocked " + i + " " + s.m_id + " " + BlockedWhy(plr, s));
				g_inPressBlocked[i] = true;
			}
			if (!held)
				g_inPressBlocked[i] = false;
			if (!held || why != "" || act || g_inPressBlocked[i])
				g_inHeldMs[i] = held ? -1 : 0;
			else if (g_inHeldMs[i] >= 0)
			{
				g_inHeldMs[i] += ms;
				if (g_inHeldMs[i] >= 200)
				{
					string cost;
					if (a !is null || ps !is null)
					{
						auto c = a !is null ? a.GetCost() : ps.GetCost();
						auto cond = a !is null ? a.m_conditionals : ps.m_conditionals;
						cost = " cost " + c.flatCost.x + "/" + c.flatCost.y + " x" + formatFloat(c.multiplier.y, "", 0, 2)
							+ " dash " + c.dashCost + " pts " + (plr.UsePoints(false, false, c) ? 1 : 0)
							+ " cond " + (CheckConditionals(cond, plr) ? 1 : 0);
					}
					InputLogLine("input-skill-idle " + i + " " + s.m_id + " cd " + cd + " mana "
						+ formatFloat(plr.m_record.mana, "", 0, 2) + "/" + plr.m_record.MaxMana()
						+ " can " + (s.CanActivate(false) ? 1 : 0) + " active " + (act ? 1 : 0) + cost);
					g_inHeldMs[i] = -1;
				}
			}
			g_inBlocked[i] = s.m_wasBlocked;
			g_inActive[i] = act;
			g_inCd[i] = cd;
			g_inCast[i] = cp;
			if (g_inReset && cd > 0)
			{
				if (a !is null)
					a.m_cooldownC = 0;
				else if (ps !is null)
					ps.m_cooldownC = 0;
				g_inCd[i] = 0;
			}
		}
		if (g_inReset)
		{
			plr.m_record.mana = 1.0f;
			g_inWarnMs -= ms;
			if (g_inWarnMs <= 0)
			{
				InputLogChat("ff4040", INPUTLOG_WARN);
				g_inWarnMs = INPUTLOG_WARN_MS;
			}
		}
		auto p = cast<Player>(plr);
		if (p !is null)
		{
			int used = p.m_record.potionChargesUsed;
			if (g_inPotUsed >= 0 && (used > g_inPotUsed || p.m_potionDelay > g_inPotDelay + ms))
				InputLogLine("input-potion " + used);
			g_inPotUsed = used;
			g_inPotDelay = p.m_potionDelay;
		}
	}

	// the test-cheat warning, a strip at the top edge while "on reset" is on (Verbs.as RenderWidgets):
	// the HUD's small font, centred on the screen left of the dock so it never covers the F-key UIs
	void RenderInputBanner(SpriteBatch& sb)
	{
		if (!g_inReset)
			return;
		auto font = DockFont();
		string s = "TEST CHEATS: INF MANA, NO CD";
		vec2 sz = font.MeasureText(s);
		float right = g_dockOpen ? DockRect().x : g_gameMode.m_wndWidth;
		float x = max(4.0f, (right - sz.x) / 2);
		float y = 2;
		sb.FillRectangle(SnapRect(vec4(x - 3, y - 1, sz.x + 6, sz.y + 2)), vec4(0.45f, 0, 0, 0.85f));
		sb.DrawString(vec2(Snap(x), Snap(y)), font, s, vec4(1, 0.9f, 0.2f, 1));
		g_inBannerDrawn++;
	}

	// da-inputlog on [reset] | off: the input log above; "off" logs the line count
	void VerbInputLog(const string &in id, array<string>@ args)
	{
		if (args.length() < 1 || (args[0] != "on" && args[0] != "off"))
		{
			GameLab::Fail(id, "usage: da-inputlog <on [reset]|off>");
			return;
		}
		uint lines = g_inLines;
		bool wasReset = g_inReset;
		SetInputLog(args[0] == "on");
		g_inReset = g_inLog && args.length() > 1 && args[1] == "reset";
		g_inWarnMs = INPUTLOG_WARN_MS;
		if (g_inReset)
			InputLogChat("ff4040", INPUTLOG_WARN);
		else if (wasReset)
			InputLogChat("7fff7f", "GAMELAB TEST CHEATS OFF: MANA AND COOLDOWNS ARE NORMAL AGAIN.");
		GameLab::Emit(GameLab::Reply(id, true).Bool("on", g_inLog).Bool("reset", g_inReset).Int("lines", int(lines)));
	}
}
}
