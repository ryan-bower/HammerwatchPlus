// Party frames: the top-left co-op list as raid frames. The bar is the frame: class-coloured
// health, a % readout, a mana strip, a shield at the end of the health, the ally's potion charges.
// Two sizes (partyframes.size), two shield styles (partyframes.shield) and two potion styles
// (partyframes.potions), per machine.
//
// HWPPartyFramesHUD replaces HUDCoop in place and overrides Draw only, so vanilla's Update and
// Refresh keep picking the records (peer 255, spectating, level 0, RefreshPortrait) and turning
// the setting off mid-level falls straight through to vanilla's Draw. HUD.as casts to HUDCoop,
// so this has to stay a subclass. The renderer reads FrameData alone: BuildFrame fills it from
// a record, and `hwp partyframes demo` fills it with stub allies for a solo screenshot.
// Shields and potion counts come through HWP::AllyStatus; a debuff from the ally's replicated
// buff list. Colours are the owner's approved mockup (see the 2026-11-06 status entry).
namespace HWP
{
	namespace PartyFrames
	{
		const int X = 4, Y = 5;
		const int THICK_W = 100, THICK_H = 34, THICK_HP = 28, THICK_MANA_Y = 30, THICK_MANA = 3;
		const int THIN_W = 104, THIN_H = 22, THIN_HP = 14, THIN_MANA_Y = 16, THIN_MANA = 5;
		const int GAP = 2;
		const int THIN_TAGS_W = 20;           // the column of tags between a Thin bar and its potion
		const int STRIPE_W = 102;             // the strip's width in the sheet
		const int MAX_NAME = 12;
		const int COLUMN_W = 7;               // what a potion column may take, either style
		const int GEM_MAX = 8;                // a gem stays gem-shaped, however few charges
		const float LOW = 0.3f;

		const uint LIVING_MANA = HashString("hwp_sor_living_mana");

		bool g_enabled = true;
		bool g_thin = false;
		bool g_striped = false;
		bool g_showLevel = false;
		bool g_showClass = false;
		bool g_greenHealth = false;
		bool g_hollowPotions = false;

		void Reload()
		{
			g_enabled = HWP::Settings::GetBool("partyframes.enabled", true);
			g_thin = HWP::Settings::GetInt("partyframes.size", 0) == 1;
			g_striped = HWP::Settings::GetInt("partyframes.shield", 0) == 1;
			g_showLevel = HWP::Settings::GetBool("partyframes.level", false);
			g_showClass = HWP::Settings::GetBool("partyframes.class", false);
			g_greenHealth = HWP::Settings::GetBool("partyframes.green", false);
			g_hollowPotions = HWP::Settings::GetInt("partyframes.potions", 0) == 1;
		}

		void OnSettingChanged(const string &in key)
		{
			if (key.findFirst("partyframes.") == 0)
				Reload();
		}

		class FrameData
		{
			string name;
			string code;           // the root class, in three letters
			int level = 0;
			vec4 color = vec4(0.5f, 0.5f, 0.54f, 1);
			float hp = 1;
			float mana = 0;
			float shield = 0;
			bool dead = false;
			bool loading = false;  // no actor, not dead: between levels
			bool pool = false;     // Living Mana: one number, so one bar
			int potionsLeft = 0;
			int potionsMax = 0;
			ScriptSprite@ debuff;
		}

		// strings rebuilt only when their text changes (ArcaneHUD.as does the same)
		class TextCache
		{
			BitmapString@ m_text;
			string m_for;
			vec4 m_color;

			BitmapString@ Get(BitmapFont@ font, const string &in s, const vec4 &in color)
			{
				if (m_text is null || m_for != s || m_color.x != color.x || m_color.y != color.y || m_color.z != color.z)
				{
					@m_text = font.BuildText(s, -1, TextAlignment::Left, color);
					m_for = s;
					m_color = color;
				}
				return m_text;
			}
		}

		class RowCache
		{
			TextCache name, level, code, status;
		}

		// the batch's colours are linear (ParseColorRGBA decodes its sRGB hex the same way), so a
		// mockup value drawn as it stands comes out far too pale
		float Linear(int c) { return pow(c / 255.0f, 2.2f); }
		vec4 Rgb(int r, int g, int b, float a = 1) { return vec4(Linear(r), Linear(g), Linear(b), a); }

		vec4 Shade(const vec4 &in c, float f)
		{
			float k = pow(f, 2.2f); // f is a brightness as the eye sees it, as in the mockup
			return vec4(min(1.0f, c.x * k), min(1.0f, c.y * k), min(1.0f, c.z * k), 1);
		}

		PlayerClass@ RootClass(PlayerRecord@ record)
		{
			auto cls = record.playerClass;
			if (cls !is null && cls.parent != 0)
			{
				auto parent = PlayerClass::Get(cls.parent);
				if (parent !is null)
					@cls = parent;
			}
			return cls;
		}

		// the toggles add these inside the bar, which never changes size for them; empty when off
		string LevelTag(FrameData@ f) { return g_showLevel && f.level > 0 ? "" + f.level : ""; }
		string CodeTag(FrameData@ f) { return g_showClass ? f.code : ""; }

		// the bar's colour already says the class, so three letters are enough to name it
		string ClassCode(PlayerClass@ cls)
		{
			if (cls is null) return "";
			if (cls.m_id == "paladin") return "PAL";
			if (cls.m_id == "priest") return "PRI";
			if (cls.m_id == "ranger") return "RNG";
			if (cls.m_id == "rogue") return "ROG";
			if (cls.m_id == "sorcerer") return "SOR";
			if (cls.m_id == "warlock") return "WLK";
			if (cls.m_id == "warrior") return "WAR";
			if (cls.m_id == "wizard") return "WIZ";
			if (cls.m_id == "hwp_gladiator") return "GLA";
			if (cls.m_id == "hwp_thief") return "THF";
			if (cls.m_id == "hwp_witch_hunter") return "WHT";
			if (cls.m_id == "hwp_firearms") return "GUN";
			return utf8string(cls.m_id.substr(0, 3)).toUpper().plain(); // another mod's class
		}

		// WoW's retail class colours. HoH's own classes borrow the colour of a WoW class:
		// sorcerer evoker, gladiator death knight, thief monk, witch hunter demon hunter, firearms druid
		vec4 ClassColor(PlayerRecord@ record)
		{
			auto cls = RootClass(record);
			if (cls !is null)
			{
				if (cls.m_id == "paladin") return Rgb(244, 140, 186);
				if (cls.m_id == "priest") return Rgb(255, 255, 255);
				if (cls.m_id == "ranger") return Rgb(170, 211, 114);
				if (cls.m_id == "rogue") return Rgb(255, 244, 104);
				if (cls.m_id == "sorcerer") return Rgb(51, 147, 127);
				if (cls.m_id == "warlock") return Rgb(135, 136, 238);
				if (cls.m_id == "warrior") return Rgb(198, 155, 109);
				if (cls.m_id == "wizard") return Rgb(63, 199, 235);
				if (cls.m_id == "hwp_gladiator") return Rgb(196, 30, 58);
				if (cls.m_id == "hwp_thief") return Rgb(0, 255, 152);
				if (cls.m_id == "hwp_witch_hunter") return Rgb(163, 48, 201);
				if (cls.m_id == "hwp_firearms") return Rgb(255, 124, 10);
			}
			return ParseColorRGBA("#" + GetPlayerColor(record.peer) + "ff");
		}

		bool HasLivingMana(PlayerBase@ plr)
		{
			if (plr is null)
				return false;
			for (uint i = 0; i < plr.m_skills.length(); i++)
				if (plr.m_skills[i] !is null && plr.m_skills[i].m_skillId == LIVING_MANA)
					return true;
			return false;
		}

		ScriptSprite@ FirstDebuff(PlayerBase@ plr)
		{
			if (plr is null)
				return null;
			for (uint i = 0; i < plr.m_buffs.m_buffs.length(); i++)
			{
				auto buff = plr.m_buffs.m_buffs[i];
				if (buff.IsDebuff() && buff.GetBuffIcon() !is null)
					return buff.GetBuffIcon();
			}
			for (uint i = 0; i < plr.m_buffs.m_stacks.length(); i++)
			{
				auto stack = plr.m_buffs.m_stacks[i];
				if (stack.IsDebuff() && stack.GetBuffIcon() !is null)
					return stack.GetBuffIcon();
			}
			return null;
		}

		void BuildFrame(FrameData@ f, PlayerRecord@ record)
		{
			auto plr = cast<PlayerBase>(record.actor);
			f.name = strTruncate(record.name, MAX_NAME);
			f.color = ClassColor(record);
			f.level = record.level;
			f.code = ClassCode(RootClass(record));
			f.dead = record.IsDead();
			f.loading = record.actor is null && !f.dead;
			f.hp = clamp(float(record.hp), 0.0f, 1.0f);
			f.mana = clamp(float(record.mana), 0.0f, 1.0f);
			f.shield = HWP::AllyStatus::Shield(record);
			f.pool = HasLivingMana(plr);
			f.potionsLeft = HWP::AllyStatus::PotionsLeft(record);
			f.potionsMax = HWP::AllyStatus::PotionsMax(record);
			@f.debuff = FirstDebuff(plr);
		}

		// hwp partyframes demo: stub allies for GameLab's solo screenshots; never g_players or the net
		array<FrameData@> g_demo;

		FrameData@ Demo(const string &in name, const vec4 &in color, float hp, float mana, float shield, int left, int total)
		{
			FrameData f;
			f.name = name;
			f.color = color;
			f.hp = hp;
			f.mana = mana;
			f.shield = shield;
			f.dead = hp <= 0;
			f.potionsLeft = left;
			f.potionsMax = total;
			return f;
		}

		void DemoParty(int count)
		{
			g_demo.removeRange(0, g_demo.length());
			g_demo.insertLast(Demo("Aldric", Rgb(244, 140, 186), 0.23f, 0.62f, 0.25f, 5, 5));
			g_demo.insertLast(Demo("Mira", Rgb(170, 211, 114), 0.50f, 0.38f, 0.25f, 1, 3));
			g_demo.insertLast(Demo("Zev", Rgb(63, 199, 235), 1.00f, 0.75f, 0.25f, 0, 3));
			g_demo.insertLast(Demo("Dorn", Rgb(198, 155, 109), 0.00f, 0.00f, 0.00f, 2, 3));
			auto pool = Demo("Sable", Rgb(51, 147, 127), 0.70f, 0.70f, 0.10f, 2, 4);
			pool.pool = true;
			g_demo.insertLast(pool);
			g_demo.insertLast(Demo("Longnamedhero", Rgb(255, 244, 104), 0.82f, 0.50f, 0.00f, 2, 6));
			g_demo.insertLast(Demo("Wren", Rgb(255, 124, 10), 0.40f, 1.00f, 1.50f, 4, 5));
			string[] codes = { "PAL", "RNG", "WIZ", "WAR", "SOR", "ROG", "GUN" };
			for (uint i = 0; i < g_demo.length(); i++)
			{
				g_demo[i].code = codes[i];
				g_demo[i].level = 8 + 2 * i;
			}
			g_demo.resize(clamp(count, 0, int(g_demo.length())));
		}

		// Every charge in a column is the same height and every gap the same: rows that don't divide
		// go to the margins, never to one charge. Two rows between charges while each stays 3 tall.
		class PotionColumn
		{
			int count;   // charges drawn, fewer only past what the rows can hold
			int height;
			int step;    // height + gap
			int bottom;  // last row of the lowest charge, which is the first to fill

			PotionColumn(int top, int rows, int total, int maxHeight)
			{
				count = min(total, (rows + 1) / 2);
				int gap = (rows - (count - 1) * 2) / count >= 3 ? 2 : 1;
				height = min((rows - (count - 1) * gap) / count, maxHeight);
				step = height + gap;
				int used = count * height + (count - 1) * gap;
				bottom = top + rows - 1 - (rows - used) / 2;
			}

			int Top(int i) { return bottom - i * step - height + 1; }
			int Bottom(int i) { return bottom - i * step; }
		}

		// the cut corners of one row of a 5 wide gem: short gems are hexagons, tall ones pointed
		int GemCut(int top, int bottom, int row)
		{
			int k = min(row - top, bottom - row);
			int height = bottom - top + 1;
			return height >= 5 ? max(0, 2 - k) : (height >= 3 ? max(0, 1 - k) : 0);
		}

		// Where the tutorial panel ends, or 0 with none on screen. It draws over this corner, and
		// over the native cards too (HUDTutorials::m_drawOnTop); these are the terms of its Draw.
		int TutorialBottom()
		{
			auto hud = GetHUD();
			for (uint i = 0; hud !is null && i < hud.m_components.length(); i++)
			{
				auto tut = cast<HUDTutorials>(hud.m_components[i]);
				if (tut is null)
					continue;
				auto gm = cast<BaseGameMode>(g_gameMode);
				if (!tut.m_visible || tut.m_currTutorial is null || (gm !is null && !gm.m_windowManager.IsEmpty()))
					return 0;
				return int(tut.m_rootPanel.m_origin.y) + tut.m_rootPanel.m_height;
			}
			return 0;
		}

		int g_top = Y; // where the stack last started, for the status line

		// a new character's tutorial panel sits over the same corner
		void ShowTutorials(bool show)
		{
			auto hud = GetHUD();
			for (uint i = 0; hud !is null && i < hud.m_components.length(); i++)
				if (cast<HUDTutorials>(hud.m_components[i]) !is null)
					hud.m_components[i].m_visible = show;
		}

		void CmdPartyFrames(array<string>@ args)
		{
			if (args.length() > 0 && args[0] == "demo")
			{
				if (args.length() > 1 && args[1] == "off")
					g_demo.removeRange(0, g_demo.length());
				else
					DemoParty(args.length() > 1 ? parseInt(args[1]) : 7);
				ShowTutorials(g_demo.length() == 0);
			}
			HWP::Log("partyframes", (g_enabled ? "on" : "off") + ", " + (g_thin ? "thin" : "thick") + ", "
				+ (g_striped ? "striped edge" : "leading edge") + ", demo allies " + g_demo.length()
				+ ", frames start at " + g_top + ", tutorial panel ends at " + TutorialBottom()
				+ ", potions " + (g_hollowPotions ? "hollow" : "gems"));
			for (uint i = 0; i < g_players.length(); i++)
			{
				auto r = g_players[i];
				if (r.peer == 255)
					continue;
				auto relayed = HWP::AllyStatus::Find(r.peer); // what came back through the host
				HWP::Log("partyframes", "peer " + r.peer + (r.local ? " (local)" : "") + ": shield "
					+ HWP::AllyStatus::Shield(r) + ", potions " + HWP::AllyStatus::PotionsLeft(r) + "/"
					+ HWP::AllyStatus::PotionsMax(r) + (HWP::AllyStatus::HasReport(r) ? "" : ", no report")
					+ (relayed is null ? ", nothing relayed" : ", relayed shield " + relayed.shield
						+ ", potions " + relayed.left + "/" + relayed.total)
					+ (HasLivingMana(cast<PlayerBase>(r.actor)) ? ", living mana pool" : ""));
			}
		}
	}
}

class HWPPartyFramesHUD : HUDCoop
{
	BitmapFont@ m_font;
	ScriptSprite@ m_skull;
	Texture2D@ m_stripes;
	array<HWP::PartyFrames::FrameData@> m_frames;
	array<HWP::PartyFrames::RowCache@> m_rows;

	HWPPartyFramesHUD(GUIBuilder@ b)
	{
		super(b);
		@m_font = Resources::GetBitmapFont("gui/fonts/hw8.fnt");
		auto hud = Resources::GetTexture2D("gui/hud.png");
		@m_skull = ScriptSprite(hud, vec4(34, 257, 9, 10));
		@m_stripes = Resources::GetTexture2D("gui/hwp_partyframes_stripes.png");
	}

	void Rect(SpriteBatch& sb, int x, int y, int w, int h, const vec4 &in color)
	{
		if (w > 0 && h > 0)
			sb.FillRectangle(vec4(x, y, w, h), color);
	}

	void Outline(SpriteBatch& sb, int x, int y, int w, int h, const vec4 &in color)
	{
		Rect(sb, x, y, w, 1, color);
		Rect(sb, x, y + h - 1, w, 1, color);
		Rect(sb, x, y + 1, 1, h - 2, color);
		Rect(sb, x + w - 1, y + 1, 1, h - 2, color);
	}

	void FadeAcross(SpriteBatch& sb, int x, int y, int w, int h, const vec4 &in left, const vec4 &in right)
	{
		sb.DrawLineFade(vec2(x, y + h / 2.0f), vec2(x + w, y + h / 2.0f), h, left, right);
	}

	void FadeDown(SpriteBatch& sb, int x, int y, int w, int h, const vec4 &in top, const vec4 &in bottom)
	{
		sb.DrawLineFade(vec2(x + w / 2.0f, y), vec2(x + w / 2.0f, y + h), w, top, bottom);
	}

	// left-to-right, faint where it meets the health, strongest at its end
	void DrawLeadingEdge(SpriteBatch& sb, int x, int y, int w, int h)
	{
		FadeAcross(sb, x, y, w, h, HWP::PartyFrames::Rgb(58, 132, 255, 0.35f), HWP::PartyFrames::Rgb(205, 236, 255, 0.97f));
		FadeAcross(sb, x, y, w, 1, vec4(1, 1, 1, 0), vec4(1, 1, 1, 0.3f));
		Rect(sb, x + w - 1, y, 1, h, vec4(1, 1, 1, 1));
	}

	// baked by tools/generate/make_partyframes_art.py: a 102 wide strip per bar height, its bright
	// end on the right. Right-aligned, so a narrow shield keeps the end and starts part way in.
	void DrawStriped(SpriteBatch& sb, int x, int y, int w, int h, bool thin)
	{
		int srcH = thin ? HWP::PartyFrames::THIN_HP : HWP::PartyFrames::THICK_HP;
		int srcY = thin ? HWP::PartyFrames::THICK_HP : 0;
		int srcW = min(w, HWP::PartyFrames::STRIPE_W);
		sb.DrawSprite(m_stripes, vec4(x, y, w, h), vec4(HWP::PartyFrames::STRIPE_W - srcW, srcY, srcW, srcH));
	}

	// the mockup's glow is additive; the batch has no blend mode, so these columns approximate it
	void DrawGlow(SpriteBatch& sb, int x, int y, int h)
	{
		for (int i = 0; i < 3; i++)
		{
			vec4 c = i == 0 ? HWP::PartyFrames::Rgb(210, 255, 255, 0.95f)
				: (i == 1 ? HWP::PartyFrames::Rgb(130, 240, 255, 0.7f) : HWP::PartyFrames::Rgb(60, 180, 230, 0.35f));
			Rect(sb, x - i, y + 1, 1, h - 2, c);
			Rect(sb, x - i, y, 1, 1, vec4(c.x, c.y, c.z, c.w * 0.55f));
			Rect(sb, x - i, y + h - 1, 1, 1, vec4(c.x, c.y, c.z, c.w * 0.55f));
		}
	}

	// returns the shield's left edge, or -1 without one
	int DrawHealth(SpriteBatch& sb, HWP::PartyFrames::FrameData@ f, const vec4 &in color, int x, int y, int w, int h, bool thin)
	{
		if (f.dead || f.loading)
		{
			Rect(sb, x, y, w, h, HWP::PartyFrames::Rgb(52, 52, 58));
			return -1;
		}
		bool green = HWP::PartyFrames::g_greenHealth && !f.pool; // a pool is mana, so it stays blue
		Rect(sb, x, y, w, h, green ? HWP::PartyFrames::Rgb(21, 21, 21) : HWP::PartyFrames::Shade(color, 0.24f));
		int fill = int(w * f.hp);
		if (fill > 0 && green)
		{
			// Blizzard's raid frame: pure green through Raid-Bar-Hp-Fill, 128 at the edges and 180 mid-bar
			vec4 edge = HWP::PartyFrames::Rgb(0, 128, 0), middle = HWP::PartyFrames::Rgb(0, 180, 0);
			FadeDown(sb, x, y, fill, h / 2, edge, middle);
			FadeDown(sb, x, y + h / 2, fill, h - h / 2, middle, edge);
		}
		else if (fill > 0)
			FadeDown(sb, x, y, fill, h, HWP::PartyFrames::Shade(color, 0.62f), HWP::PartyFrames::Shade(color, 1.07f));
		if (f.shield <= 0)
			return -1;
		// As WoW's frames: a shield only fills the health that's missing, never over what's left,
		// and whatever doesn't fit shows as the glow at the end of the bar
		int sw = max(1, int(w * f.shield));
		bool over = fill + sw >= w;
		sw = min(sw, w - fill);
		int sx = x + fill;
		if (sw > 0)
		{
			if (HWP::PartyFrames::g_striped)
				DrawStriped(sb, sx, y, sw, h, thin);
			else
				DrawLeadingEdge(sb, sx, y, sw, h);
		}
		if (over)
			DrawGlow(sb, x + w - 1, y, h);
		return sw > 0 ? sx : -1;
	}

	void DrawMana(SpriteBatch& sb, HWP::PartyFrames::FrameData@ f, int x, int y, int w, int h)
	{
		auto mana = HWP::PartyFrames::Rgb(40, 130, 235);
		Rect(sb, x, y, w, h, HWP::PartyFrames::Rgb(10, 16, 36));
		int fill = f.dead ? 0 : int(w * f.mana);
		Rect(sb, x, y, fill, h, mana);
		Rect(sb, x, y, fill, 1, HWP::PartyFrames::Shade(mana, 1.3f));
	}

	// one rectangle per charge, a full one red and a spent one an empty ring so they differ by shape
	void DrawHollowCharges(SpriteBatch& sb, HWP::PartyFrames::FrameData@ f, int x, int y, int h, bool docked)
	{
		const int w = 4;
		Rect(sb, x, y + 1, w + 1, h - 2, vec4(0, 0, 0, 1));
		Rect(sb, docked ? x : x - 1, y, docked ? w : w + 1, 1, vec4(0, 0, 0, 1));
		Rect(sb, docked ? x : x - 1, y + h - 1, docked ? w : w + 1, 1, vec4(0, 0, 0, 1));
		if (!docked)
			Rect(sb, x - 1, y + 1, 1, h - 2, vec4(0, 0, 0, 1));
		HWP::PartyFrames::PotionColumn col(y + 1, h - 2, f.potionsMax, 99);
		for (int i = 0; i < col.count; i++)
		{
			int top = col.Top(i);
			if (i < f.potionsLeft)
			{
				Rect(sb, x, top, w, col.height, HWP::PartyFrames::Rgb(226, 36, 58));
				if (col.height >= 4)
				{
					Rect(sb, x, top, w, 1, HWP::PartyFrames::Rgb(246, 58, 72));
					Rect(sb, x, col.Bottom(i), w, 1, HWP::PartyFrames::Rgb(168, 20, 44));
				}
			}
			else if (col.height >= 3)
				Outline(sb, x, top, w, col.height, HWP::PartyFrames::Rgb(96, 100, 120));
			else
				Rect(sb, x, top, w, col.height, HWP::PartyFrames::Rgb(48, 50, 60)); // too short to be a ring
		}
	}

	// cut rubies, each with its own black edge. The edges go down first, as neighbours share theirs
	void DrawGemCharges(SpriteBatch& sb, HWP::PartyFrames::FrameData@ f, int x, int y, int h, bool docked)
	{
		const int w = 5;
		HWP::PartyFrames::PotionColumn col(y + 1, h - 2, f.potionsMax, HWP::PartyFrames::GEM_MAX);
		int left = docked ? 0 : -1; // a docked gem's left edge is the bar's own
		for (int i = 0; i < col.count; i++)
			for (int row = col.Top(i); row <= col.Bottom(i); row++)
			{
				int cut = HWP::PartyFrames::GemCut(col.Top(i), col.Bottom(i), row);
				int from = max(cut - 1, left);
				Rect(sb, x + from, row - 1, w + 1 - cut - from, 3, vec4(0, 0, 0, 1));
			}
		for (int i = 0; i < col.count; i++)
		{
			int top = col.Top(i), bottom = col.Bottom(i);
			for (int row = top; row <= bottom; row++)
			{
				int cut = HWP::PartyFrames::GemCut(top, bottom, row);
				if (i >= f.potionsLeft)
				{
					Rect(sb, x + cut, row, w - 2 * cut, 1, HWP::PartyFrames::Rgb(44, 46, 58));
					continue;
				}
				Rect(sb, x + cut, row, w - 2 * cut, 1, HWP::PartyFrames::Rgb(226, 36, 58));
				if (row * 2 < top + bottom)
					Rect(sb, x + cut, row, 3 - cut, 1, HWP::PartyFrames::Rgb(246, 58, 72));
				else if (row * 2 > top + bottom)
				{
					int from = max(2, cut);
					Rect(sb, x + from, row, w - cut - from, 1, HWP::PartyFrames::Rgb(168, 20, 44));
				}
			}
		}
	}

	void DrawPotions(SpriteBatch& sb, HWP::PartyFrames::FrameData@ f, int x, int y, int h, bool docked)
	{
		if (f.potionsMax <= 0)
			return;
		if (HWP::PartyFrames::g_hollowPotions)
			DrawHollowCharges(sb, f, x, y, h, docked);
		else
			DrawGemCharges(sb, f, x, y, h, docked);
	}

	void DrawDebuff(SpriteBatch& sb, HWP::PartyFrames::FrameData@ f, int x, int y)
	{
		if (f.debuff is null)
			return;
		Rect(sb, x, y, 11, 11, HWP::PartyFrames::Rgb(70, 220, 90));
		f.debuff.Draw(sb, vec4(x + 1, y + 1, 9, 9), g_menuTime);
	}

	string Status(HWP::PartyFrames::FrameData@ f)
	{
		if (f.dead)
			return "DEAD";
		return f.loading ? "..." : int(round(f.hp * 100)) + "%";
	}

	vec4 StatusColor(HWP::PartyFrames::FrameData@ f)
	{
		return f.dead ? HWP::PartyFrames::Rgb(225, 80, 76) : vec4(1, 1, 1, 1);
	}

	void DrawLow(SpriteBatch& sb, HWP::PartyFrames::FrameData@ f, int x, int y, int w, int h)
	{
		if (f.dead || f.loading || f.hp >= HWP::PartyFrames::LOW)
			return;
		auto red = HWP::PartyFrames::Rgb(230, 40, 36);
		Outline(sb, x - 1, y - 1, w + 2, h + 2, red);
		Outline(sb, x, y, w, h, red);
	}

	vec4 NameColor(HWP::PartyFrames::FrameData@ f)
	{
		return f.dead ? HWP::PartyFrames::Rgb(205, 205, 212) : vec4(1, 1, 1, 1);
	}

	// quieter than the name, so the name stays what you read first
	vec4 TagColor(HWP::PartyFrames::FrameData@ f)
	{
		return f.dead ? NameColor(f) : HWP::PartyFrames::Rgb(205, 208, 216);
	}

	vec4 BarColor(HWP::PartyFrames::FrameData@ f)
	{
		return f.pool ? HWP::PartyFrames::Rgb(40, 130, 235) : f.color;
	}

	void DrawThick(SpriteBatch& sb, HWP::PartyFrames::FrameData@ f, HWP::PartyFrames::RowCache@ row, int x, int y)
	{
		const int w = HWP::PartyFrames::THICK_W, h = HWP::PartyFrames::THICK_H;
		Rect(sb, x, y, w, h, vec4(0, 0, 0, 1));
		DrawHealth(sb, f, BarColor(f), x + 1, y + 1, w - 2, f.pool ? h - 2 : HWP::PartyFrames::THICK_HP, false);
		if (!f.pool)
			DrawMana(sb, f, x + 1, y + HWP::PartyFrames::THICK_MANA_Y, w - 2, HWP::PartyFrames::THICK_MANA);
		auto name = row.name.Get(m_font, f.name, NameColor(f));
		auto status = row.status.Get(m_font, Status(f), StatusColor(f));
		sb.DrawString(vec2(x + (w - name.GetWidth()) / 2, y + 4), name);
		sb.DrawString(vec2(x + (w - status.GetWidth()) / 2, y + 15), status);
		// the corners either side of the %, which nothing else uses
		string levelText = HWP::PartyFrames::LevelTag(f);
		string codeText = HWP::PartyFrames::CodeTag(f);
		if (levelText.length() > 0)
			sb.DrawString(vec2(x + 4, y + 15), row.level.Get(m_font, levelText, TagColor(f)));
		if (codeText.length() > 0)
		{
			auto code = row.code.Get(m_font, codeText, TagColor(f));
			sb.DrawString(vec2(x + w - code.GetWidth() - 4, y + 15), code);
		}
		if (f.dead)
			m_skull.Draw(sb, vec2(x + 4, y + 3), g_menuTime);
		DrawLow(sb, f, x, y, w, h);
		DrawTile(sb, f, x + w, y, h, true);
	}

	// the potion column, and the debuff beside that. Docked, the column starts where the bar ends
	// and uses the bar's edge as its own, so it never paints over a low-health border.
	void DrawTile(SpriteBatch& sb, HWP::PartyFrames::FrameData@ f, int x, int y, int h, bool docked)
	{
		DrawPotions(sb, f, x, y, h, docked);
		DrawDebuff(sb, f, x + HWP::PartyFrames::COLUMN_W, y);
	}

	void DrawThin(SpriteBatch& sb, HWP::PartyFrames::FrameData@ f, HWP::PartyFrames::RowCache@ row, int x, int y)
	{
		const int w = HWP::PartyFrames::THIN_W, h = HWP::PartyFrames::THIN_H;
		Rect(sb, x, y, w, h, vec4(0, 0, 0, 1));
		int sx = DrawHealth(sb, f, BarColor(f), x + 1, y + 1, w - 2, f.pool ? h - 2 : HWP::PartyFrames::THIN_HP, true);
		if (!f.pool)
			DrawMana(sb, f, x + 1, y + HWP::PartyFrames::THIN_MANA_Y, w - 2, HWP::PartyFrames::THIN_MANA);
		auto name = row.name.Get(m_font, f.name, NameColor(f));
		auto status = row.status.Get(m_font, Status(f), StatusColor(f));
		int nameX = x + (f.dead ? 15 : 4);
		int statusX = x + w - status.GetWidth() - 4;
		if (sx >= 0 && !f.dead && sx < statusX + status.GetWidth())
			statusX = max(nameX + name.GetWidth() + 2, sx - status.GetWidth() - 2); // tuck it left of the shield
		sb.DrawString(vec2(nameX, y + 4), name);
		sb.DrawString(vec2(statusX, y + 4), status);
		if (f.dead)
			m_skull.Draw(sb, vec2(x + 3, y + 3), g_menuTime);
		DrawLow(sb, f, x, y, w, h);
		int tagsW = DrawThinTags(sb, f, row, x + w + 2, y);
		if (tagsW > 0)
			DrawTile(sb, f, x + w + 2 + tagsW + 1, y, h, false);
		else
			DrawTile(sb, f, x + w, y, h, true);
	}

	// the bar has no room for these on one row, so they stack beside it. Every row in the party
	// takes the same width, which keeps the potions in a line. Returns that width.
	int DrawThinTags(SpriteBatch& sb, HWP::PartyFrames::FrameData@ f, HWP::PartyFrames::RowCache@ row, int x, int y)
	{
		string levelText = HWP::PartyFrames::LevelTag(f);
		string codeText = HWP::PartyFrames::CodeTag(f);
		bool both = levelText.length() > 0 && codeText.length() > 0;
		const int w = HWP::PartyFrames::THIN_TAGS_W;
		if (levelText.length() > 0)
		{
			auto level = row.level.Get(m_font, levelText, TagColor(f));
			sb.DrawString(vec2(x + (w - level.GetWidth()) / 2, y + (both ? 2 : 7)), level);
		}
		if (codeText.length() > 0)
		{
			auto code = row.code.Get(m_font, codeText, TagColor(f));
			sb.DrawString(vec2(x + (w - code.GetWidth()) / 2, y + (both ? 12 : 7)), code);
		}
		return HWP::PartyFrames::g_showLevel || HWP::PartyFrames::g_showClass ? w : 0;
	}

	void Draw(SpriteBatch& sb, int idt) override
	{
		if (!HWP::PartyFrames::g_enabled)
		{
			HUDCoop::Draw(sb, idt);
			return;
		}
		if (!m_visible)
			return;
		DoLayout(); // or m_invalidated stays set and HUDCoop::Update refreshes every frame

		uint count = 0;
		bool demo = HWP::PartyFrames::g_demo.length() > 0;
		if (demo)
			count = HWP::PartyFrames::g_demo.length();
		else
			for (uint i = 0; i < m_coopWidgets.length(); i++)
			{
				auto w = m_coopWidgets[i];
				if (w is null || w.m_record is null || !w.m_widget.m_visible)
					continue;
				if (count >= m_frames.length())
					m_frames.insertLast(HWP::PartyFrames::FrameData());
				HWP::PartyFrames::BuildFrame(m_frames[count++], w.m_record);
			}
		while (m_rows.length() < count)
			m_rows.insertLast(HWP::PartyFrames::RowCache());

		int top = max(HWP::PartyFrames::Y, HWP::PartyFrames::TutorialBottom() + HWP::PartyFrames::GAP);
		HWP::PartyFrames::g_top = top;
		bool thin = HWP::PartyFrames::g_thin;
		int rowH = (thin ? HWP::PartyFrames::THIN_H : HWP::PartyFrames::THICK_H) + HWP::PartyFrames::GAP;
		if (!thin && top + int(count) * rowH > g_gameMode.m_wndHeight * 2 / 3)
		{
			thin = true; // a big party keeps its stack on screen
			rowH = HWP::PartyFrames::THIN_H + HWP::PartyFrames::GAP;
		}
		for (uint i = 0; i < count; i++)
		{
			auto f = demo ? HWP::PartyFrames::g_demo[i] : m_frames[i];
			int y = top + int(i) * rowH;
			if (thin)
				DrawThin(sb, f, m_rows[i], HWP::PartyFrames::X, y);
			else
				DrawThick(sb, f, m_rows[i], HWP::PartyFrames::X, y);
		}
	}
}

namespace HWPPartyFrames
{
	[Hook]
	void HUDConstructor(HUD@ hud, GUIBuilder@ b)
	{
		for (uint i = 0; i < hud.m_components.length(); i++)
		{
			if (cast<HUDCoop>(hud.m_components[i]) is null || cast<HWPPartyFramesHUD>(hud.m_components[i]) !is null)
				continue;
			@hud.m_components[i] = HWPPartyFramesHUD(b);
			return;
		}
	}
}

namespace Modules
{
	class HWPPartyFramesModule : Module
	{
		HWPPartyFramesModule()
		{
			super("hwp-partyframes");
			HWP::PartyFrames::Reload();
			HWP::Commands::Register("partyframes", "[demo [count | off]]  the party frames' settings and each player's reported shield and potions; demo draws stub allies for a solo test", HWP::Commands::Handler(HWP::PartyFrames::CmdPartyFrames));
			HWP::Commands::OnSettingChanged(HWP::Commands::SettingListener(HWP::PartyFrames::OnSettingChanged));
			HWP::Log("partyframes", "ready");
		}
	}
}
