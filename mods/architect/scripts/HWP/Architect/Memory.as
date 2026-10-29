// Run-start memory: the local player's last architect picks and New Game+ level, and
// three named presets, kept on the player record (HWP::SaveData::Local(), keys
// architect.last / architect.ngp / architect.preset1..3) so they follow the character.
//
//   architect.last     { ids: [int] }                    my own picks, as last set
//   architect.ngp      int                               the NG+ level the host picked last
//   architect.preset<n> { name, ids: [int], ngp }        preset slot n (1..PRESETS)
//
// The loadout (MissionArchitect.as override) restores the last picks when the menu
// opens with none of mine, the menu (MissionLoadoutMenu.as override) the NG+ level;
// the picker's preset row and `hwp architect preset ...` save and load the slots.
namespace HWP
{
	namespace Architect
	{
		const string KEY_LAST = "architect.last";
		const string KEY_NGP = "architect.ngp";
		const int PRESETS = 3;
		const int NAME_MAX = 24;

		string PresetKey(int slot) { return "architect.preset" + slot; }

		SValue@ PickList(array<int>@ ids, const string &in name, int ngp)
		{
			SValueBuilder b;
			b.PushDictionary();
			if (name != "")
				b.PushString("name", name);
			if (ngp >= 0)
				b.PushInteger("ngp", ngp);
			b.PushArray("ids");
			for (uint i = 0; i < ids.length(); i++)
				b.PushInteger(ids[i]);
			b.PopArray();
			b.PopDictionary();
			return b.Build();
		}

		// ---- last picks / NG+ ----------------------------------------------------

		void RememberPicks(array<int>@ ids)
		{
			HWP::SaveData::Local().Take(KEY_LAST, PickList(ids, "", -1));
			HWP::Log("architect", "remembered " + ids.length() + " pick(s)");
		}

		array<int>@ LastPicks()
		{
			return HWP::SV::Ints(HWP::SaveData::Local().Get(KEY_LAST), "ids");
		}

		void RememberNGP(int ngp)
		{
			auto bag = HWP::SaveData::Local();
			if (bag.GetInt(KEY_NGP, -1) == ngp)
				return;
			bag.SetInt(KEY_NGP, ngp);
			HWP::Log("architect", "remembered NG+ " + ngp);
		}

		// -1 when nothing was picked yet
		int LastNGP()
		{
			return HWP::SaveData::Local().GetInt(KEY_NGP, -1);
		}

		// ---- presets --------------------------------------------------------------

		bool ValidSlot(int slot) { return slot >= 1 && slot <= PRESETS; }
		bool HasPreset(int slot) { return ValidSlot(slot) && HWP::SaveData::Local().Has(PresetKey(slot)); }

		string PresetName(int slot)
		{
			if (!ValidSlot(slot))
				return "";
			return HWP::SV::Str(HWP::SaveData::Local().Get(PresetKey(slot)), "name");
		}

		array<int>@ PresetPicks(int slot)
		{
			array<int> none;
			if (!ValidSlot(slot))
				return none;
			return HWP::SV::Ints(HWP::SaveData::Local().Get(PresetKey(slot)), "ids");
		}

		int PresetNGP(int slot)
		{
			if (!ValidSlot(slot))
				return -1;
			return HWP::SV::Int(HWP::SaveData::Local().Get(PresetKey(slot)), "ngp", -1);
		}

		// a typed name: the console's own key (`) can land in a focused field, so it goes,
		// as do surrounding spaces; capped at NAME_MAX characters
		string CleanName(const string &in raw)
		{
			string s = "";
			for (uint i = 0; i < raw.length(); i++)
			{
				string c = raw.substr(i, 1);
				if (c == "`" || c == "\"" || c == "\\")
					continue;
				s += c;
			}
			s = strTrim(s);
			if (s.length() > uint(NAME_MAX))
				s = s.substr(0, NAME_MAX);
			return s;
		}

		void SavePreset(int slot, const string &in rawName, array<int>@ ids, int ngp)
		{
			if (!ValidSlot(slot))
				return;
			string name = CleanName(rawName);
			if (name == "")
				name = Resources::GetString(".hwp.architect.preset_default", {{ "slot", slot }});
			HWP::SaveData::Local().Take(PresetKey(slot), PickList(ids, name, ngp));
			HWP::Log("architect", "preset " + slot + " '" + name + "' saved: " + ids.length() + " pick(s), NG+ " + ngp);
		}

		void ClearPreset(int slot)
		{
			if (!ValidSlot(slot))
				return;
			HWP::SaveData::Local().Remove(PresetKey(slot));
			HWP::Log("architect", "preset " + slot + " cleared");
		}

		// ---- the party state, from my side --------------------------------------

		// my own picks in the synced list
		array<int>@ MyPicks()
		{
			array<int> mine;
			int me = Lobby::GetLocalPeer();
			for (uint i = 0; i < g_ids.length(); i++)
			{
				if (i < g_payers.length() && g_payers[i] == me)
					mine.insertLast(g_ids[i]);
			}
			return mine;
		}

		// the ids this character may pick from the set (a remembered id from a higher
		// architect tier, or another mod version, is dropped)
		array<int>@ Available(array<int>@ ids, PlayerRecord@ plr, uint setHash)
		{
			array<int> keep;
			if (plr is null)
				return keep;
			auto buffs = MissionBuff::GetMissionBuffs(plr, setHash);
			for (uint i = 0; i < ids.length(); i++)
			{
				for (uint j = 0; j < buffs.length(); j++)
				{
					if (buffs[j].m_idHash == uint(ids[i]))
					{
						keep.insertLast(ids[i]);
						break;
					}
				}
			}
			return keep;
		}

		MissionLoadoutMenu@ OpenLoadoutMenu()
		{
			auto gm = cast<BaseGameMode>(g_gameMode);
			if (gm is null || gm.m_windowManager is null)
				return null;
			for (uint i = 0; i < gm.m_windowManager.m_objects.length(); i++)
			{
				auto menu = cast<MissionLoadoutMenu>(gm.m_windowManager.m_objects[i]);
				if (menu !is null)
					return menu;
			}
			return null;
		}

		// a preset onto the run: my picks become the preset's (the host merges and syncs
		// them back), and on the host the New Game+ level follows
		bool ApplyPreset(int slot, PlayerRecord@ plr, uint setHash)
		{
			if (!HasPreset(slot))
			{
				HWP::Log("architect", "preset " + slot + " is empty");
				return false;
			}
			auto ids = Available(PresetPicks(slot), plr, setHash);
			SendPicks(ids);
			RememberPicks(ids);
			int ngp = PresetNGP(slot);
			auto menu = OpenLoadoutMenu();
			if (menu !is null && ngp >= 0 && Network::IsServer())
				menu.HWPSetNGP(ngp);
			HWP::Log("architect", "preset " + slot + " '" + PresetName(slot) + "' loaded: " + ids.length() + " pick(s), NG+ " + ngp);
			return true;
		}

		// a client that left the host's run-start setup (Back) picks any mission on the
		// board: while the host's setup is still up (the mission is set), its own window
		// comes back
		bool RejoinLoadout()
		{
			if (Network::IsServer())
				return false;
			if (MissionManager::g_module is null || MissionManager::g_module.m_missionDefHash == 0)
				return false;
			if (OpenLoadoutMenu() !is null)
				return false;
			auto gm = cast<BaseGameMode>(g_gameMode);
			if (gm is null || gm.m_windowManager is null)
				return false;
			gm.m_windowManager.AddWindowObject(MissionLoadoutMenu(gm.m_guiBuilder));
			HWP::Log("architect", "client rejoined the host's run-start setup");
			return true;
		}

		// hwp architect preset [list | save <n> [name...] | load <n> | clear <n>]
		void CmdPreset(array<string>@ args)
		{
			string sub = "list";
			if (args.length() > 1)
				sub = args[1];
			int slot = 0;
			if (args.length() > 2)
				slot = int(parseInt(args[2]));
			if (sub == "save" && ValidSlot(slot))
			{
				string name = "";
				for (uint i = 3; i < args.length(); i++)
					name += (i > 3 ? " " : "") + args[i];
				int ngp = -1;
				auto menu = OpenLoadoutMenu();
				if (menu !is null && menu.m_ngp)
					ngp = int(g_ngp + 0.5f);
				SavePreset(slot, name, MyPicks(), ngp);
				RefreshOpenPicker();
			}
			else if (sub == "load" && ValidSlot(slot))
			{
				auto plr = GetLocalPlayerRecord();
				if (!ApplyPreset(slot, plr, HashString("architect")))
					HWP::Commands::Reply("preset " + slot + " is empty");
				RefreshOpenPicker();
			}
			else if (sub == "clear" && ValidSlot(slot))
			{
				ClearPreset(slot);
				RefreshOpenPicker();
			}
			else if (sub != "list")
			{
				HWP::Commands::Reply("usage: hwp architect preset [list | save <1-" + PRESETS + "> [name] | load <n> | clear <n>]");
				return;
			}
			for (int i = 1; i <= PRESETS; i++)
			{
				if (!HasPreset(i))
				{
					HWP::Commands::Reply("preset " + i + ": empty");
					continue;
				}
				auto ids = PresetPicks(i);
				string names = "";
				for (uint j = 0; j < ids.length(); j++)
					names += (j > 0 ? ", " : "") + BuffName(ids[j]);
				HWP::Commands::Reply("preset " + i + ": '" + PresetName(i) + "' NG+ " + PresetNGP(i) + " [" + names + "]");
			}
		}

		void RefreshOpenPicker()
		{
			auto gm = cast<BaseGameMode>(g_gameMode);
			if (gm is null || gm.m_windowManager is null)
				return;
			for (uint i = 0; i < gm.m_windowManager.m_objects.length(); i++)
			{
				auto picker = cast<SelectArchitectSelector>(gm.m_windowManager.m_objects[i]);
				if (picker !is null)
					picker.HWPRefreshPresets();
			}
		}
	}
}
