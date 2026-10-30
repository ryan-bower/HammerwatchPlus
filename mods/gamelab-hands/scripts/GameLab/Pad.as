// gamelab-hands: an emulated controller button for HWP hotkeys. hwplib's HWP::Input
// (mods/hwplib/scripts/HWP/Core/Input.as) reads pad buttons with Platform::IsKeyDown,
// which no write into GameInput reaches. A held button goes to GlobalCache EMU_HELD as
// "gp_dl", which HWP::Input::Held reads as down; EMU_USING "1" stands for a controller in
// use (GameInput.UsingGamepad). No symbol is shared, so hands still loads without hwplib.
//
// Unlike the input verb's holds, a pad hold also counts down in paused frames: the Plus
// tab's capture runs behind the character menu, which pauses a solo game.
namespace GameLab
{
	const string PAD_HELD = "hwp_pad_held";
	const string PAD_USING = "hwp_pad_using";
	const array<string> PAD_BUTTONS = { "gp_a", "gp_b", "gp_x", "gp_y", "gp_lb", "gp_rb", "gp_back", "gp_start",
		"gp_du", "gp_dd", "gp_dl", "gp_dr", "gp_lth", "gp_rth" };

	string g_padButton;
	int g_padMs = 0;

	void SetPadHeld(const string &in held)
	{
		if (GlobalCache::Get(PAD_HELD) != held)
			GlobalCache::Set(PAD_HELD, held);
	}

	// every frame, paused or not
	void UpdatePad(int ms)
	{
		if (g_padMs <= 0)
			return;
		g_padMs -= ms;
		if (g_padMs <= 0)
		{
			SetPadHeld("");
			Json j;
			Emit(j.Str("ev", "pad_done").Str("button", g_padButton));
		}
	}

	// pad on|off: a controller in use or not; pad hold <gp id> <ms>: hold that button
	// (pad release lets go at once); pad: what is held
	void VerbPad(const string &in id, array<string>@ args)
	{
		string what = args.length() > 0 ? args[0] : "";
		if (what == "on" || what == "off")
			GlobalCache::Set(PAD_USING, what == "on" ? "1" : "");
		else if (what == "hold")
		{
			if (args.length() < 3 || PAD_BUTTONS.find(args[1]) < 0)
			{
				Fail(id, "usage: pad hold <" + join(PAD_BUTTONS, "|") + "> <ms>");
				return;
			}
			g_padButton = args[1];
			g_padMs = int(parseInt(args[2]));
			SetPadHeld(g_padButton);
		}
		else if (what == "release")
		{
			g_padMs = 0;
			SetPadHeld("");
		}
		else if (what != "")
		{
			Fail(id, "usage: pad [on|off|hold <button> <ms>|release]");
			return;
		}
		Emit(Reply(id, true).Bool("using", GlobalCache::Get(PAD_USING) == "1").Str("held", GlobalCache::Get(PAD_HELD))
			.Int("ms", g_padMs > 0 ? g_padMs : 0));
	}
}
