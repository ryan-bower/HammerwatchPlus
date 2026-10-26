// GameLab::Inbox - the command channel that does not open the console. An open console pauses
// the game, and every "gl" line typed there opened it (docs/RE_NOTES.md, 2026-10-19).
//
// The probe reads the frame's text events (GUI/Widgets/TextInputWidget.as:91-94). They arrive
// without the engine expecting text input (inbox-arm 20261019-012135), and armed, it swallows
// the game's key controls: a posted "i" left the PlayerMenu shut (inbox-check 20261019-012018)
// and opened it unarmed. So gl_inbox is 1 (read, unarmed); 2 arms it as the chat does
// (GUI/Menus/InGameChat.as ExpectTextInput), 0 turns the reading off.
// gamelab/session.py sends a line as text: "!" starts it, "~" ends it.
//   !gl <id> <verb> [args]~   runs RunVerb, as the console's "gl" does, after an
//                             {"ev":"rx","cid":<id>} event (the console's "> gl <id>" echo)
//   !<anything else>~         is logged as {"ev":"rx_other"} and not run
// A gl line whose id ran in the last INBOX_DUP_FRAMES frames is logged as {"ev":"rx_dup"} and
// not run: session.py resends a line after two silent heartbeats, and a line only delayed, not
// lost, then arrived twice and ran twice (abyss-dormant 20261020-105538: two cracks per
// "hwp abyss here"). The window, not a plain set, lets a new Session reuse ids on the same game.
// Inside a line "%21" is "!", "%7E" is "~" and "%25" is "%" (session.py inbox_frame escapes them).
// A "!" mid-line drops the partial line (a lost "~"), and lines are capped. The heartbeat
// carries the totals (inLines, inDropped) and whether text input is armed (textIn).
namespace GameLab
{
	const uint INBOX_LINE_CAP = 4096;
	string g_inboxBuf;
	bool g_inboxIn = false;
	uint g_inboxLines = 0;
	uint g_inboxDropped = 0;
	bool g_inboxVar = false;
	bool g_inboxArmed = false;
	const uint INBOX_DUP_CAP = 32;
	const uint INBOX_DUP_FRAMES = 1800;
	array<string> g_inboxIds;
	array<uint> g_inboxIdFrames;
	uint g_inboxFrame = 0;
	uint g_inboxDups = 0;

	void InboxFrame()
	{
		if (!g_inboxVar)
		{
			AddVar("gl_inbox", 1);
			g_inboxVar = true;
		}
		g_inboxFrame++;
		int mode = GetVarInt("gl_inbox");
		auto cb = GetControlBindings();
		if (mode == 2)
		{
			if (cb !is null && !cb.IsExpectingTextInput())
			{
				cb.ExpectTextInput();
				g_inboxArmed = true;
			}
		}
		else if (g_inboxArmed)
		{
			// only what the inbox armed itself is undone, never the chat's
			if (cb !is null)
				cb.StopExpectTextInput();
			g_inboxArmed = false;
		}
		if (mode == 0)
			return;
		auto input = GetInput();
		if (input is null)
			return;
		int n = input.GetTextInputCount();
		for (int i = 0; i < n; i++)
		{
			auto evt = input.GetTextInput(i);
			if (evt is null || evt.evt != TextInputControlEventType::None)
				continue;
			InboxText(evt.text.plain());
		}
	}

	bool InboxExpecting()
	{
		auto cb = GetControlBindings();
		return cb !is null && cb.IsExpectingTextInput();
	}

	void InboxText(const string &in text)
	{
		for (uint k = 0; k < text.length(); k++)
		{
			string ch = text.substr(k, 1);
			if (ch == "!")
			{
				if (g_inboxIn && g_inboxBuf.length() > 0)
					g_inboxDropped++;
				g_inboxIn = true;
				g_inboxBuf = "";
				continue;
			}
			if (!g_inboxIn)
				continue;
			if (ch == "~")
			{
				g_inboxIn = false;
				string line = g_inboxBuf;
				g_inboxBuf = "";
				InboxLine(line);
				continue;
			}
			if (g_inboxBuf.length() >= INBOX_LINE_CAP)
			{
				g_inboxIn = false;
				g_inboxBuf = "";
				g_inboxDropped++;
				continue;
			}
			g_inboxBuf += ch;
		}
	}

	string InboxUnescape(const string &in s)
	{
		string res;
		uint k = 0;
		while (k < s.length())
		{
			string ch = s.substr(k, 1);
			if (ch == "%" && k + 3 <= s.length())
			{
				string code = s.substr(k + 1, 2);
				if (code == "21") { res += "!"; k += 3; continue; }
				if (code == "7E" || code == "7e") { res += "~"; k += 3; continue; }
				if (code == "25") { res += "%"; k += 3; continue; }
			}
			res += ch;
			k++;
		}
		return res;
	}

	// true (and an rx_dup event) when the line id ran in the last INBOX_DUP_FRAMES frames, through
	// the inbox or the console (session.py falls back to the console when the inbox is not read);
	// else the id is recorded and false
	bool RanRecently(const string &in id, const string &in verb)
	{
		for (uint k = 0; k < g_inboxIds.length(); k++)
		{
			if (g_inboxIds[k] == id && g_inboxFrame - g_inboxIdFrames[k] <= INBOX_DUP_FRAMES)
			{
				g_inboxDups++;
				Json dup;
				dup.Str("ev", "rx_dup").Str("cid", id).Str("verb", verb);
				Emit(dup);
				return true;
			}
		}
		if (g_inboxIds.length() >= INBOX_DUP_CAP)
		{
			g_inboxIds.removeAt(0);
			g_inboxIdFrames.removeAt(0);
		}
		g_inboxIds.insertLast(id);
		g_inboxIdFrames.insertLast(g_inboxFrame);
		return false;
	}

	void InboxLine(const string &in framed)
	{
		g_inboxLines++;
		string line = InboxUnescape(framed);
		auto raw = line.split(" ");
		array<string> args;
		for (uint i = 0; i < raw.length(); i++)
		{
			if (raw[i].length() > 0)
				args.insertLast(raw[i]);
		}
		if (args.length() == 0 || args[0] != "gl")
		{
			Json other;
			other.Str("ev", "rx_other").Str("head", args.length() > 0 ? args[0] : "");
			Emit(other);
			return;
		}
		if (args.length() < 3)
		{
			Fail(args.length() > 1 ? args[1] : "", "usage: !gl <id> <verb> [args]~");
			return;
		}
		string id = args[1];
		string verb = args[2];
		args.removeRange(0, 3);
		if (RanRecently(id, verb))
			return;
		Json j;
		j.Str("ev", "rx").Str("cid", id).Str("verb", verb);
		Emit(j);
		g_commands++;
		RunVerb(id, verb, args);
	}
}
