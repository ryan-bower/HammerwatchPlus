// The active pet's level and XP progress in the player menu's character tab,
// beside the character's own "lvl N (xx%)" (gui/playermenu/character.gui,
// widget "player-level"). No override of GUI/PlayerMenu/Character.as (droptrade
// owns it): each frame the pets module looks for an open PlayerMenu whose
// current tab is the character tab, clones its "player-level" TextWidget once
// into the same row as "hwp-pet-level" (anchor and font come with the clone;
// the clone's tooltip button is hidden) and keeps its text and position up:
// right-anchored just left of the level text, so a long name never overlaps.
// Hidden while the player has no pet. Read back with `gl menu character - hwp-pet-level`
// (the tab is a MenuTab with its own widget tree, which `gl wtext` does not reach).
namespace HWP
{
	namespace PetLevelTab
	{
		const string ID = "hwp-pet-level";
		const int GAP = 6; // px between the pet text and the level text

		TextWidget@ g_text;   // our clone in the tab being shown
		TextWidget@ g_level;  // the vanilla level widget it sits beside
		bool g_logged = false;

		void Reset()
		{
			@g_text = null;
			@g_level = null;
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
				@g_text = mine;
				@g_level = level;
			}
			auto rec = GetLocalPlayerRecord();
			string petId = rec is null ? "" : HWP::Pets::ActivePetId(rec);
			if (petId.isEmpty())
			{
				g_text.m_visible = false;
				return;
			}
			g_text.m_visible = true;
			g_text.SetText(Text(rec, petId));
			// the level text is right-anchored at offset -3: sit just left of it
			g_text.m_offset = vec2(level.m_offset.x - float(level.m_width) - GAP, level.m_offset.y);
		}
	}
}
