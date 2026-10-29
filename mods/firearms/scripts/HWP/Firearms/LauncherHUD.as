namespace HWP
{
	namespace Firearms
	{
		// The HUD's off-hand slot for a two-hander draws the main-hand item's icon, mirrored
		// (HUDPlayer.RefreshSkills: SetSkill(offHandSkill, mainHandWeapon, true)). A rifle's
		// off-hand attack is its underbarrel grenade launcher, so that slot shows the launcher
		// close-up of the rifle's tier instead (items/hwp/firearms_items.png row 1, rifle_gl_0N),
		// unmirrored; a Flamethrower Rifle's is its flamethrower (row 3 from column 3,
		// flamerifle_nozzle_0N), a Full Auto Rifle's its full-auto close-up (row 4 from column 3,
		// autorifle_mode_0N). Only the skill bar: the inventory keeps the rifle's own icon.
		class LauncherIcon : Item::Item
		{
			ScriptSprite@ m_icon;
			int m_tier;
			string m_kind;

			LauncherIcon(const string &in kind, int tier, vec2 cell)
			{
				m_kind = kind;
				m_tier = tier;
				@m_icon = ScriptSprite(Resources::GetTexture2D("items/hwp/firearms_items.png"), vec4(24 * cell.x, 24 * cell.y, 24, 24));
			}

			ScriptSprite@ GetIcon() override { return m_icon; }
		}

		// the rifles' id prefixes, and the cell of each one's tier-1 close-up (the tiers follow it)
		const array<string> LAUNCHER_RIFLES = { "hwp_rifle_", "hwp_flamerifle_", "hwp_autorifle_" };
		const array<string> LAUNCHER_KINDS = { "launcher", "flamethrower", "full-auto" };
		const array<vec2> LAUNCHER_CELLS = { vec2(0, 1), vec2(3, 3), vec2(3, 4) };
		array<LauncherIcon@> g_launcherIcons;

		// the close-up for a rifle (hwp_rifle_01..03, hwp_flamerifle_01..03, hwp_autorifle_01..03), or null for anything else
		LauncherIcon@ LauncherIconFor(Item::Item@ weapon)
		{
			auto equip = cast<Equipment::Item>(weapon);
			if (equip is null || equip.baseItem is null)
				return null;
			string id = equip.baseItem.m_id;
			for (uint k = 0; k < LAUNCHER_RIFLES.length(); k++)
			{
				string pre = LAUNCHER_RIFLES[k];
				if (id.length() != pre.length() + 2 || id.substr(0, pre.length()) != pre)
					continue;
				int tier = parseInt(id.substr(pre.length())) - 1;
				if (tier < 0 || tier > 2)
					return null;
				if (g_launcherIcons.length() == 0)
				{
					for (uint r = 0; r < LAUNCHER_RIFLES.length(); r++)
					{
						for (int i = 0; i < 3; i++)
							g_launcherIcons.insertLast(LauncherIcon(LAUNCHER_KINDS[r], i, LAUNCHER_CELLS[r] + vec2(i, 0)));
					}
				}
				return g_launcherIcons[3 * k + tier];
			}
			return null;
		}
	}
}

namespace Modules
{
	// RefreshSkills rebuilds the slot's widget on every equipment or skill change, so each frame
	// a fresh off-hand widget under a rifle gets the close-up (a widget already showing it is
	// left alone).
	class HWPFirearmsLauncherHUDModule : Module
	{
		HWP::Firearms::LauncherIcon@ m_shown;

		HWPFirearmsLauncherHUDModule()
		{
			super("hwp-firearms-launcher-hud");
		}

		// HWP::Guard (tools/guard_modules.py): a script error here turns this off, not the game
		HWP::Guard m_guardUpdateFrame;
		void UpdateFrame(int ms, GameInput& gameInput, MenuInput& menuInput, bool paused) override
		{
			if (m_guardUpdateFrame.Skip("firearms", "HWPFirearmsLauncherHUDModule.UpdateFrame"))
				return;
			if (m_guardUpdateFrame.Raw())
			{
				GuardedUpdateFrame(ms, gameInput, menuInput, paused);
				m_guardUpdateFrame.Ok();
				return;
			}
			try { GuardedUpdateFrame(ms, gameInput, menuInput, paused); m_guardUpdateFrame.Ok(); }
			catch { m_guardUpdateFrame.Failed(); }
		}

		void GuardedUpdateFrame(int ms, GameInput& gameInput, MenuInput& menuInput, bool paused)
		{
			auto hud = g_gameMode.GetHUD();
			if (hud is null)
				return;
			// the HUD shows the spectated player's skills while spectating (HUD.RefreshSkills)
			PlayerRecord@ record = GetLocalPlayerRecord();
			auto gm = cast<AGameplayGameMode>(g_gameMode);
			if (gm !is null && gm.m_spectating && gm.m_spectatingPlayer >= 0 && gm.m_spectatingPlayer < int(g_players.length()))
				@record = g_players[gm.m_spectatingPlayer];
			if (record is null || record.equipped is null)
				return;
			auto icon = HWP::Firearms::LauncherIconFor(record.equipped.m_items[EquippedItemsSlots::MainHand]);
			if (icon is null)
				return;
			for (uint i = 0; i < hud.m_components.length(); i++)
			{
				auto comp = cast<HUDPlayer>(hud.m_components[i]);
				if (comp is null || comp.m_wOffHandSkillSlot is null)
					continue;
				array<Widget@>@ kids = comp.m_wOffHandSkillSlot.m_children;
				for (uint j = 0; j < kids.length(); j++)
				{
					auto w = cast<SkillWidget>(kids[j]);
					if (w is null || w.m_item is icon)
						continue;
					@w.m_item = icon;
					w.m_mirroredIcon = false;
					if (m_shown !is icon)
						print("[HWP:firearms] " + icon.m_kind + " close-up on the off-hand slot: tier " + (icon.m_tier + 1));
					@m_shown = icon;
				}
			}
		}
	}
}
