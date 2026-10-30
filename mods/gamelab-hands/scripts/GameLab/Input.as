// gamelab-hands: an emulated controller. No OS input at all: what a verb (or the pilot)
// holds is written into the engine's GameInput from GameLabHandsModule.UpdateFrame, the
// same object the player's actor reads through GetInput() (main.as, Player.as).
namespace GameLab
{
	class HeldInput
	{
		int msLeft = 0;          // > 0 while held
		vec2 move;               // GameInput.MoveDir (unit length = full stick)
		vec2 aim;                // GameInput.AimDir, when aimSet
		bool aimSet = false;
		array<string> buttons;   // held Down; Pressed on the first frame only
		bool first = false;
		string owner;            // "input" verb id, or "pilot"
		uint frames = 0;
	}

	HeldInput g_held;
	uint g_inputFrames = 0;      // frames this process wrote input on

	const array<string> BUTTONS = { "use", "potion", "dash", "main", "off", "skill1", "skill2", "skill3",
		"hwp_skill4", "hwp_skill5", "hwp_skill6" };

	// the classes module's extra skill keys (mods/classes/scripts/HWP/Classes/SkillKeys.as) are raw keyboard keys,
	// no GameInput button: a held hwp_skillN goes to GlobalCache "hwp_skillkeys_held" as "4,5",
	// which SkillKeys.Poll reads as the key being down. No symbol is shared, so hands still
	// loads without it.
	const array<string> HWP_SKILL_KEYS = { "hwp_skill4", "hwp_skill5", "hwp_skill6" };
	const string SKILLKEYS_HELD = "hwp_skillkeys_held";
	const string SKILLKEYS_ON = "hwp_skillkeys_on";   // "1" once the classes module's keys run

	void WriteSkillKeys(array<string>@ buttons)
	{
		string held = "";
		for (uint i = 0; i < HWP_SKILL_KEYS.length(); i++)
		{
			if (buttons !is null && buttons.find(HWP_SKILL_KEYS[i]) >= 0)
				held += (held.isEmpty() ? "" : ",") + HWP_SKILL_KEYS[i].substr(9); // "hwp_skill4" -> "4"
		}
		if (GlobalCache::Get(SKILLKEYS_HELD) != held)
			GlobalCache::Set(SKILLKEYS_HELD, held);
	}

	// the button the idx-th active spell (0 = first, the GetSkillInput count) listens on: the
	// 4th to 6th have their own key while the classes module's keys run, else (vanilla
	// PlayerTargetingHelper.GetSkillInput) every spell from the 3rd on shares Skill3
	string SpellButton(PlayerBase@ plr, int idx)
	{
		if (idx == 0)
			return "skill1";
		if (idx == 1)
			return "skill2";
		auto p = cast<Player>(plr);
		if (idx >= 3 && idx < 6 && p !is null && p.m_targetHelper !is null
			&& Reflect::GetTypeName(p.m_targetHelper).findFirst("HWPTargetingHelper") >= 0
			&& GlobalCache::Get(SKILLKEYS_ON) == "1")
			return "hwp_skill" + (idx + 1);
		return "skill3";
	}

	void SetButton(GameInput@ gi, const string &in name, bool down, bool pressed)
	{
		if (name == "use") { gi.Use.Down = down; gi.Use.Pressed = pressed; }
		else if (name == "potion") { gi.Potion.Down = down; gi.Potion.Pressed = pressed; }
		else if (name == "dash") { gi.Dash.Down = down; gi.Dash.Pressed = pressed; }
		else if (name == "main") { gi.MainHandAttack.Down = down; gi.MainHandAttack.Pressed = pressed; }
		else if (name == "off") { gi.OffHandAttack.Down = down; gi.OffHandAttack.Pressed = pressed; }
		else if (name == "skill1") { gi.Skill1.Down = down; gi.Skill1.Pressed = pressed; }
		else if (name == "skill2") { gi.Skill2.Down = down; gi.Skill2.Pressed = pressed; }
		else if (name == "skill3") { gi.Skill3.Down = down; gi.Skill3.Pressed = pressed; }
	}

	// hold for ms: move (mx, my), optional aim, optional buttons. Replaces what was held.
	void Hold(const string &in owner, int ms, vec2 move, bool aimSet, vec2 aim, array<string>@ buttons)
	{
		g_held.owner = owner;
		g_held.msLeft = ms;
		g_held.move = move;
		g_held.aimSet = aimSet;
		g_held.aim = aim;
		g_held.buttons = buttons is null ? array<string>() : buttons;
		g_held.first = true;
		g_held.frames = 0;
	}

	void Release()
	{
		g_held.msLeft = 0;
		g_held.buttons.resize(0);
		g_releasePending = true;
	}

	// The engine does not rewrite GameInput on a frame without device events, and the
	// GameInput object handed to UpdateFrame is not always the same one (the console being
	// open is one switch): each object keeps its own last write. Measured, hands-release
	// 20261017-150922..151323: a hold written into one object left the other moving the
	// player whenever it became current again. So every distinct GameInput the frames have
	// handed out is remembered, and every write goes to all of them, every button included.
	const uint MAX_INPUTS = 8;
	array<GameInput@> g_inputs;
	const int RELEASE_FRAMES = 2;
	bool g_releasePending = false;
	int g_releaseFrames = 0;

	void SeeInput(GameInput& gi)
	{
		GameInput@ h = gi;
		for (uint i = 0; i < g_inputs.length(); i++)
		{
			if (g_inputs[i] is h)
				return;
		}
		if (g_inputs.length() < MAX_INPUTS)
			g_inputs.insertLast(h);
	}

	void WriteOne(GameInput@ gi, vec2 move, bool aimSet, vec2 aim, array<string>@ buttons, bool pressed)
	{
		gi.MoveDir = move;
		if (aimSet)
			gi.AimDir = aim;
		for (uint i = 0; i < BUTTONS.length(); i++)
		{
			bool down = buttons !is null && buttons.find(BUTTONS[i]) >= 0;
			SetButton(gi, BUTTONS[i], down, down && pressed);
		}
	}

	// one frame of emulated input, into every GameInput seen (the pilot calls this too)
	void WriteInput(GameInput& gi, vec2 move, bool aimSet, vec2 aim, array<string>@ buttons, bool pressed)
	{
		SeeInput(gi);
		for (uint i = 0; i < g_inputs.length(); i++)
			WriteOne(g_inputs[i], move, aimSet, aim, buttons, pressed);
		WriteSkillKeys(buttons);
		g_inputFrames++;
	}

	void ReleaseInput(GameInput& gi)
	{
		if (g_releasePending)
		{
			g_releasePending = false;
			g_releaseFrames = RELEASE_FRAMES;
		}
		WriteInput(gi, vec2(0, 0), false, vec2(0, 0), null, false);
		if (g_releaseFrames > 0)
			g_releaseFrames--;
	}

	bool Releasing()
	{
		return g_releasePending || g_releaseFrames > 0;
	}

	void ApplyHeld(int ms, GameInput& gi)
	{
		if (g_held.msLeft <= 0)
		{
			if (Releasing())
				ReleaseInput(gi);
			return;
		}
		WriteInput(gi, g_held.move, g_held.aimSet, g_held.aim, g_held.buttons, g_held.first);
		g_held.first = false;
		g_held.frames++;
		g_held.msLeft -= ms;
		if (g_held.msLeft <= 0)
			g_releasePending = true;
		if (g_held.msLeft <= 0 && g_held.owner != "pilot")
		{
			Json j;
			Emit(j.Str("ev", "input_done").Str("id", g_held.owner).Int("frames", g_held.frames));
		}
	}

	// input <ms> <mx> <my> [aimX aimY] [button,button]: hold an emulated stick/buttons for
	// ms of gameplay frames. Replies at once; "input_done" (same id) when the hold ends.
	void VerbInput(const string &in id, array<string>@ args)
	{
		if (args.length() < 3)
		{
			Fail(id, "usage: input <ms> <mx> <my> [aimX aimY] [button,button]");
			return;
		}
		int ms = int(parseInt(args[0]));
		vec2 move(parseFloat(args[1]), parseFloat(args[2]));
		bool aimSet = args.length() >= 5;
		vec2 aim = aimSet ? vec2(parseFloat(args[3]), parseFloat(args[4])) : vec2();
		array<string> buttons;
		string list = args.length() == 4 ? args[3] : (args.length() >= 6 ? args[5] : "");
		if (list != "")
		{
			auto parts = list.split(",");
			for (uint i = 0; i < parts.length(); i++)
			{
				if (BUTTONS.find(parts[i]) < 0)
				{
					Fail(id, "unknown button '" + parts[i] + "' (" + join(BUTTONS, ",") + ")");
					return;
				}
				buttons.insertLast(parts[i]);
			}
		}
		Hold(id, ms, move, aimSet, aim, buttons);
		Emit(Reply(id, true).Int("ms", ms).Num("mx", move.x).Num("my", move.y).Int("buttons", buttons.length()));
	}

	const array<string> MENU_BUTTONS = { "forward", "up", "down", "left", "right", "accept", "additional",
		"context", "prevtab", "nexttab", "prevsubtab", "nextsubtab" };
	string g_menuPending = "";
	string g_menuPendingId = "";
	string g_menuHeld = "";
	bool g_menuPad = false;

	// menubutton <name>: a press of a menu button (MenuInput, what windows read: a gamepad's
	// bumpers are MenuPreviousTab/MenuNextTab), written into MenuInput by the hands module's
	// UpdateFrame: down for one frame, let go (Released, what a list's buy waits for) the next,
	// cleared the one after. The engine does not clear a written Pressed itself: a press left in
	// place was read every frame (fix-merchant-controller-tabs 20261029-022658: the tab flipped
	// each frame). "menubutton_done" (same id) once it is cleared. With "pad" the GameInput says
	// UsingGamepad for those frames, as a gamepad's press does: a list then acts on its selected
	// entry, where with the mouse it wants one under the pointer (ScrollbarWidget.Update).
	void VerbMenuButton(const string &in id, array<string>@ args)
	{
		if (args.length() < 1 || MENU_BUTTONS.find(args[0]) < 0 || (args.length() > 1 && args[1] != "pad"))
		{
			Fail(id, "usage: menubutton <" + join(MENU_BUTTONS, "|") + "> [pad]");
			return;
		}
		g_menuPending = args[0];
		g_menuPendingId = id;
		g_menuPad = args.length() > 1;
		Emit(Reply(id, true).Str("button", args[0]).Bool("pad", g_menuPad));
	}

	// phase 1: down and pressed; 2: let go (released, which a list's buy waits for: ScrollbarWidget.Update);
	// 3: nothing
	void SetMenuButton(MenuInput& mi, const string &in name, int phase)
	{
		bool down = phase == 1;
		bool released = phase == 2;
		if (name == "forward") { mi.Forward.Down = down; mi.Forward.Pressed = down; mi.Forward.Released = released; }
		else if (name == "up") { mi.Up.Down = down; mi.Up.Pressed = down; mi.Up.Released = released; }
		else if (name == "down") { mi.Down.Down = down; mi.Down.Pressed = down; mi.Down.Released = released; }
		else if (name == "left") { mi.Left.Down = down; mi.Left.Pressed = down; mi.Left.Released = released; }
		else if (name == "right") { mi.Right.Down = down; mi.Right.Pressed = down; mi.Right.Released = released; }
		else if (name == "accept") { mi.Accept.Down = down; mi.Accept.Pressed = down; mi.Accept.Released = released; }
		else if (name == "additional") { mi.Additional.Down = down; mi.Additional.Pressed = down; mi.Additional.Released = released; }
		else if (name == "context") { mi.ContextMenu.Down = down; mi.ContextMenu.Pressed = down; mi.ContextMenu.Released = released; }
		else if (name == "prevtab") { mi.MenuPreviousTab.Down = down; mi.MenuPreviousTab.Pressed = down; mi.MenuPreviousTab.Released = released; }
		else if (name == "nexttab") { mi.MenuNextTab.Down = down; mi.MenuNextTab.Pressed = down; mi.MenuNextTab.Released = released; }
		else if (name == "prevsubtab") { mi.MenuPreviousSubTab.Down = down; mi.MenuPreviousSubTab.Pressed = down; mi.MenuPreviousSubTab.Released = released; }
		else if (name == "nextsubtab") { mi.MenuNextSubTab.Down = down; mi.MenuNextSubTab.Pressed = down; mi.MenuNextSubTab.Released = released; }
	}

	int g_menuPhase = 0;

	void ApplyMenuButton(GameInput& gi, MenuInput& mi)
	{
		if (g_menuPad && (g_menuHeld != "" || g_menuPending != ""))
			gi.UsingGamepad = true;
		if (g_menuHeld != "")
		{
			g_menuPhase++;
			SetMenuButton(mi, g_menuHeld, g_menuPhase);
			if (g_menuPhase >= 3)
			{
				Json j;
				Emit(j.Str("ev", "menubutton_done").Str("id", g_menuPendingId).Str("button", g_menuHeld));
				g_menuHeld = "";
			}
			return;
		}
		if (g_menuPending == "")
			return;
		g_menuPhase = 1;
		SetMenuButton(mi, g_menuPending, g_menuPhase);
		g_menuHeld = g_menuPending;
		g_menuPending = "";
	}

	// controller: the live GameInput the player reads (g_gameMode.m_currInput), read-only
	void VerbController(const string &in id, array<string>@ args)
	{
		auto gi = GetInput();
		if (gi is null)
		{
			Fail(id, "no current GameInput");
			return;
		}
		array<string> down;
		if (gi.Use.Down) down.insertLast("use");
		if (gi.Potion.Down) down.insertLast("potion");
		if (gi.Dash.Down) down.insertLast("dash");
		if (gi.MainHandAttack.Down) down.insertLast("main");
		if (gi.OffHandAttack.Down) down.insertLast("off");
		Emit(Reply(id, true).Num("mx", gi.MoveDir.x).Num("my", gi.MoveDir.y).Num("ax", gi.AimDir.x).Num("ay", gi.AimDir.y)
			.Bool("gamepad", gi.UsingGamepad).Raw("down", StrArray(down)).Bool("releasing", Releasing())
			.Int("held", g_held.msLeft).Int("frames", g_inputFrames).Int("buffers", g_inputs.length()));
	}
}
