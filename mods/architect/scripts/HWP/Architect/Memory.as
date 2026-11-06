// Run-start memory: the local player's last architect picks and New Game+ level, and
// three named presets, kept on the player record (HWP::SaveData::Local(), keys
// architect.last / architect.ngp / architect.preset1..3) so they follow the character.
//
//   architect.last     { ids: [int] }                    my own picks, as last set
//   architect.ngp      int                               the NG+ level the host picked last
//   architect.preset<n> { name, ids: [int], ngp }        preset slot n (1..PRESETS)
//   architect.loadout  { <row id>: <the row's own Save> } the other rows, as last used
//
// The loadout (MissionArchitect.as override) restores the last picks when the menu
// opens with none of mine (if the character can pay for them), the menu
// (MissionLoadoutMenu.as override) the NG+ level and the other rows (RestoreRow);
// the picker's preset row and `hwp architect preset ...` save and load the slots.
namespace HWP
{
	namespace Architect
	{
		const string KEY_LAST = "architect.last";
		const string KEY_NGP = "architect.ngp";
		const string KEY_LOADOUT = "architect.loadout";
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

		// ---- the other rows: last used, per character (issue #96) ------------------
		//
		// Vanilla keeps the loadout rows' picks in the MissionLoadout singletons and saves
		// them with the local record ("architect-loadout", PlayerRecord.as:818-823), but
		// loads them back when the record loads (PlayerRecord.as:1276-1281), before any
		// BuildGUI has set the rows' m_player and with no actor, so their validity checks
		// (MissionBuff::IsValidMissionBuff, CheckConditionals) run without the player; and the
		// singletons carry one character's picks over to the next. Here every row's own
		// Save() goes under the character's hwp key when the setup closes or the run starts,
		// and its own Load() runs again when the setup opens, with the player set.

		// the vanilla rows whose picks come back: the chapel's blessing, the Magic Shop's
		// skill sphere, the tavern's food and drinks (vanilla or the tavern mod's), the boon.
		// The architect row has its own memory (architect.last, above); the rest are left alone.
		bool RemembersRow(MissionLoadout@ loadout)
		{
			return cast<SelectBuffLoadout>(loadout) !is null || cast<SelectBoonLoadout>(loadout) !is null
				|| cast<SelectSkillSphereLoadout>(loadout) !is null || cast<SelectFoodLoadout>(loadout) !is null;
		}

		void RememberLoadout(array<MissionLoadout@>@ loadouts)
		{
			if (loadouts is null)
				return;
			SValueBuilder b;
			b.PushDictionary();
			int rows = 0;
			for (uint i = 0; i < loadouts.length(); i++)
			{
				if (loadouts[i] is null || !RemembersRow(loadouts[i]))
					continue;
				loadouts[i].Save(b);
				rows++;
			}
			b.PopDictionary();
			HWP::SaveData::Local().Take(KEY_LOADOUT, b.Build());
			HWP::Log("architect", "remembered the run-start rows (" + rows + ")");
		}

		// the rows' Load() validates against m_player, which only BuildGUI sets
		void SetRowPlayer(MissionLoadout@ loadout, PlayerRecord@ plr)
		{
			auto buff = cast<SelectBuffLoadout>(loadout);
			if (buff !is null)
				@buff.m_player = plr;
			auto boon = cast<SelectBoonLoadout>(loadout);
			if (boon !is null)
				@boon.m_player = plr;
			auto food = cast<SelectFoodLoadout>(loadout);
			if (food !is null)
				@food.m_player = plr;
			auto sphere = cast<SelectSkillSphereLoadout>(loadout);
			if (sphere !is null)
			{
				@sphere.m_player = plr;
				// vanilla's Load keeps the old hash when the saved string is empty, and the
				// row would show a sphere that OnPlay (by the string) never gives
				sphere.m_selected = 0;
				sphere.m_selectedString = "";
			}
		}

		// Before the row's BuildGUI: its picks from last time, through its own Load()
		// (which drops what the character may no longer pick). A row that costs (the
		// tavern) keeps what it had when the restored picks plus `spent` (the rows restored
		// before it) are more than the character can pay.
		void RestoreRow(MissionLoadout@ loadout, PlayerRecord@ plr, ShopCost@ spent)
		{
			if (loadout is null || plr is null || !Enabled() || !RemembersRow(loadout))
				return;
			auto saved = HWP::SaveData::Local().Get(KEY_LOADOUT);
			if (saved is null)
				return;

			SValueBuilder b;
			b.PushDictionary();
			loadout.Save(b);
			b.PopDictionary();
			SValue@ before = b.Build();

			SetRowPlayer(loadout, plr);
			loadout.Load(plr, saved);

			auto cost = loadout.GetCost();
			if (cost !is null)
			{
				auto total = ShopCost();
				total.AddCost(spent);
				total.AddCost(cost);
				if (!total.CanAfford(plr))
				{
					SetRowPlayer(loadout, plr);
					loadout.Load(plr, before);
					HWP::Log("architect", "run-start row " + loadout.m_id + ": the remembered picks cost more than " + plr.GetName() + " has; not restored");
					cost = loadout.GetCost();
				}
				else
					HWP::Log("architect", "run-start row " + loadout.m_id + ": remembered picks restored");
				if (cost !is null)
					spent.AddCost(cost);
			}
			else
				HWP::Log("architect", "run-start row " + loadout.m_id + ": remembered pick restored");
			before.Delete();
		}

		// what one player pays for a pick list alone (CalcMyCost's sum without a split): the
		// remembered picks only come back when this, with the rows before, is affordable
		ShopCost@ SoloBill(array<int>@ ids)
		{
			array<uint> hashes;
			for (uint i = 0; i < ids.length(); i++)
				hashes.insertLast(uint(ids[i]));
			float mul = CostMul(hashes);
			auto sum = ShopCost();
			auto off = ShopCost();
			for (uint i = 0; i < hashes.length(); i++)
			{
				auto buff = MissionBuff::Get(hashes[i]);
				auto d = ChallengeDiscount(hashes[i]);
				if (d !is null)
					off.AddCost(d);
				else if (buff !is null)
					sum.AddCost(buff.m_cost);
			}
			auto bill = ShopCost();
			for (uint j = 0; j + 1 < sum.m_cost.length(); j += 2)
			{
				int amount = int(sum.m_cost[j + 1] * mul) - off.GetCost(MaterialType(sum.m_cost[j]));
				if (amount > 0)
					bill.AddCost(MaterialType(sum.m_cost[j]), amount);
			}
			return bill;
		}

		// the row ids with a remembered pick (for `hwp architect`)
		string RememberedRows()
		{
			auto saved = HWP::SaveData::Local().Get(KEY_LOADOUT);
			if (saved is null)
				return "none";
			auto keys = saved.GetDictionary().getKeys();
			string s = "";
			for (uint i = 0; i < keys.length(); i++)
				s += (i > 0 ? ", " : "") + keys[i];
			return s == "" ? "none" : s;
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
