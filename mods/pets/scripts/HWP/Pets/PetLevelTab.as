// The active pet's level and XP progress in the player menu's character tab,
// beside the character's own "lvl N (xx%)" (gui/playermenu/character.gui,
// widget "player-level"). No override of GUI/PlayerMenu/Character.as (droptrade
// owns it): each frame the pets module looks for an open PlayerMenu whose
// current tab is the character tab, clones its "player-level" TextWidget once
// into the same row as "hwp-pet-level" (anchor and font come with the clone;
// the clone's tooltip button is hidden) and keeps its text and position up:
// right-anchored just left of the level text. If it would run into the name it
// falls back to the short `pet lvl N`, and is hidden if even that doesn't fit.
// Hidden while the player has no pet. Read back with `gl menu character - hwp-pet-level`
// (the tab is a MenuTab with its own widget tree, which `gl wtext` does not reach).
//
// Widget.CloneInto value-copies fields (`w = this`), so a fresh clone shares the
// level's BitmapString (m_text). Detach() gives the clone its own before its
// first SetText, which would otherwise Cleanup() the character's level text and
// leave it blank until the level string changes (issue #79).
namespace HWP
{
	namespace PetLevelTab
	{
		const string ID = "hwp-pet-level";
		const int GAP = 6; // px between the pet text and the level text (and the name)

		TextWidget@ g_text;   // our clone in the tab being shown
		TextWidget@ g_level;  // the vanilla level widget it sits beside
		bool g_logged = false;
		string g_layoutKey;   // what the last fit check was made for

		void Reset()
		{
			@g_text = null;
			@g_level = null;
			g_layoutKey = "";
		}

		// A clone shares the original's BitmapString and WidgetTooltip handles:
		// give the copy its own, and rebuild the level once in case the shared
		// text was already cleaned up through the copy.
		void Detach(TextWidget@ mine, TextWidget@ level)
		{
			@mine.m_tooltip = null;
			if (mine.m_text is null || mine.m_text !is level.m_text)
				return;
			@mine.m_text = null;
			mine.m_str = "";
			level.SetText(level.m_str, true, true);
		}

		PlayerMenuCharacterTab@ OpenTab()
		{
			auto gm = cast<BaseGameMode>(g_gameMode);
			if (gm is null || gm.m_windowManager is null)
				return null;
			for (int i = int(gm.m_windowManager.m_objects.length()) - 1; i >= 0; i--)
			{
				auto menu = cast<PlayerMenu>(gm.m_windowManager.m_objects[i]);
				if (menu is null || menu.m_tabSystem is null)
					continue;
				return cast<PlayerMenuCharacterTab>(menu.m_tabSystem.GetCurrentTab());
			}
			return null;
		}

		string Text(PlayerRecord@ rec, const string &in petId)
		{
			int lvl = HWP::Pets::Level(rec, petId);
			if (lvl >= HWP::Pets::g_maxLevel)
				return Resources::GetString(".hwp.pets.inv_level_max", { { "lvl", lvl } });
			int next = HWP::Pets::XpToNext(lvl);
			int pct = next > 0 ? clamp(HWP::Pets::Xp(rec, petId) * 100 / next, 0, 99) : 0;
			return Resources::GetString(".hwp.pets.inv_level", { { "lvl", lvl }, { "pct", pct } });
		}

		string ShortText(PlayerRecord@ rec, const string &in petId)
		{
			return Resources::GetString(".hwp.pets.inv_level_short", { { "lvl", HWP::Pets::Level(rec, petId) } });
		}

		// the pet text, right edge at `right` in the row, clears the name's right edge
		bool Fits(int right, int nameRight)
		{
			return right - g_text.m_width >= nameRight + GAP;
		}

		void Tick()
		{
			if (!HWP::Pets::g_enabled)
				return;
			auto tab = OpenTab();
			if (tab is null)
			{
				Reset();
				return;
			}
			auto level = cast<TextWidget>(tab.m_widget.GetWidgetById("player-level"));
			if (level is null || level.m_parent is null)
				return;
			if (g_level !is level || g_text is null)
			{
				// a (re)built tab: take the clone it has, or make one
				auto mine = cast<TextWidget>(tab.m_widget.GetWidgetById(ID));
				if (mine is null)
				{
					@mine = cast<TextWidget>(level.Clone());
					if (mine is null)
						return;
					Detach(mine, level);
					mine.SetID(ID);
					for (uint i = 0; i < mine.m_children.length(); i++)
						mine.m_children[i].m_visible = false; // the level tooltip's hover button
					level.m_parent.AddChild(mine);
					if (!g_logged)
					{
						g_logged = true;
						HWP::Log("pets", "pet level line added to the character tab (" + ID + ")");
					}
				}
				else
					Detach(mine, level);
				@g_text = mine;
				@g_level = level;
				g_layoutKey = "";
			}
			auto rec = GetLocalPlayerRecord();
			string petId = rec is null ? "" : HWP::Pets::ActivePetId(rec);
			if (petId.isEmpty())
			{
				g_text.m_visible = false;
				g_layoutKey = "";
				return;
			}
			// the level text is right-anchored at offset -3: sit just left of it
			g_text.m_offset = vec2(level.m_offset.x - float(level.m_width) - GAP, level.m_offset.y);
			string full = Text(rec, petId);
			auto name = cast<TextWidget>(tab.m_widget.GetWidgetById("player-name"));
			int nameRight = name is null ? 0 : int(name.m_offset.x) + name.m_width;
			int right = level.m_parent.m_width + int(g_text.m_offset.x);
			string key = full + "|" + nameRight + "|" + right;
			if (key == g_layoutKey)
				return;
			g_layoutKey = key;
			g_text.SetText(full);
			if (!Fits(right, nameRight))
				g_text.SetText(ShortText(rec, petId));
			g_text.m_visible = Fits(right, nameRight);
		}
	}
}
