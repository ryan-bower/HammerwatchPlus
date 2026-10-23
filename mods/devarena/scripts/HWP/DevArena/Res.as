namespace HWP::DevArena
{
	// da-res [<w>x<h>]: setup for the 1080p / 1440p layout check (SPEC "Decided during build" 1a).
	// What the options' resolution window does (GUI/Options/ResolutionsWindow.as:44) minus
	// Config::SaveVar, so the lab profile on disk is untouched; the window resizes on a later
	// frame. With no argument, a read-back: the cvar and the UI units the dock lays out in.
	void VerbRes(const string &in id, array<string>@ args)
	{
		if (args.length() >= 1)
		{
			auto parts = args[0].split("x");
			if (parts.length() != 2 || parseInt(parts[0]) < 320 || parseInt(parts[1]) < 180)
			{
				GameLab::Fail(id, "usage: da-res [<w>x<h>], at least 320x180");
				return;
			}
			SetVar("v_resolution", ivec2(int(parseInt(parts[0])), int(parseInt(parts[1]))));
		}
		ivec2 r = GetVarIvec2("v_resolution");
		GameLab::Emit(GameLab::Reply(id, true).Int("w", r.x).Int("h", r.y)
			.Int("uiW", int(g_gameMode.m_wndWidth)).Int("uiH", int(g_gameMode.m_wndHeight))
			.Num("scale", g_gameMode.m_wndScale));
	}
}
