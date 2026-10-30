// hoh1.content off (HWP::HoH1::Enabled, the default): the HoH1 import may still be packed,
// but no floor may load an HoH1 file. A lobby whose players lack the import hangs on such a
// floor: the host loads hoh1/levels/battlements_1.lvl and every client waits forever on
// wait_loaded_level (game night 10.28.26, Dark Citadel floor 21). So each HoH1 floor is
// swapped, in place, for an HoH2 one with the same id, index, next floor and difficulty:
// a save already at such a floor (mission-level is the floor index) plays on, and the run
// ends where it would have. MissionDefs are rebuilt with every level, so this is undone as
// soon as the setting is on again. Runs from the module constructor, before generation.
namespace HWP
{
	namespace Campaign
	{
		namespace StandIns
		{
			// read here too, so tools/make_config.py finds the campaign config's key in campaign
			bool On() { return HWP::Settings::GetBool("hoh1.content", false); }

			// a generated floor of a theme, like vanilla's own Dark Halls entries
			MissionLevel@ Generated(MissionDef@ def, const string &in id, const string &in theme, int diff, int diffNgp, const string &in next, const string &in act)
			{
				SValueBuilder sb;
				sb.PushDictionary();
				sb.PushString("id", id);
				sb.PushString("mission-theme", theme);
				sb.PushInteger("diff-level", diff);
				sb.PushInteger("diff-level-ngp", diffNgp);
				if (!next.isEmpty())
					sb.PushString("next-level", next);
				if (!act.isEmpty())
					sb.PushString("act-name", act);
				sb.PushArray("flags");
				sb.PushString("place_well");
				sb.PopArray();
				sb.PopDictionary();
				// kept alive: the level hands out handles into its params (module data)
				SValue@ params = sb.Build();
				return MissionLevel(def, UnitPtr(), params);
			}

			// from: the HoH1 floor; like: the HoH2 tower's floor in its place. The new floor
			// keeps from's place in its mission (id, next, difficulty) and plays like.
			MissionLevel@ Copy(MissionDef@ def, MissionLevel@ from, MissionLevel@ like)
			{
				SValueBuilder sb;
				sb.PushDictionary();
				sb.PushString("id", from.m_id);
				sb.PushInteger("diff-level", from.m_diffLevel);
				sb.PushInteger("diff-level-ngp", from.m_diffLevelNgp);
				if (!from.m_idNext.isEmpty())
					sb.PushString("next-level", from.m_idNext);
				sb.PopDictionary();
				SValue@ params = sb.Build();
				auto l = MissionLevel(def, UnitPtr(), params);
				@l.m_themeDef = like.m_themeDef;
				@l.m_generator = like.m_generator;
				@l.m_moduleData = like.m_moduleData;
				l.m_level = like.m_level;
				l.m_minimapExploreRadius = like.m_minimapExploreRadius;
				@l.m_placedMaterialChances = like.m_placedMaterialChances;
				l.m_minNumSkillSpheres = like.m_minNumSkillSpheres;
				l.m_minNumTrinkets = like.m_minNumTrinkets;
				l.m_minNumEquipment = like.m_minNumEquipment;
				l.m_minNumResCaches = like.m_minNumResCaches;
				l.m_minNumCursedTrinkets = like.m_minNumCursedTrinkets;
				l.m_minNumCursedResCaches = like.m_minNumCursedResCaches;
				l.m_NumTrinketTriPicks = like.m_NumTrinketTriPicks;
				l.m_valuables = like.m_valuables;
				l.m_levelFlags = like.m_levelFlags;
				l.m_music = like.m_music;
				l.m_ambience = like.m_ambience;
				l.m_actNameBase = like.m_actNameBase;
				l.m_actName = like.m_actName;
				l.m_levelName = like.m_levelName;
				return l;
			}

			// the HoH2 tower's floor for an HoH1 floor id: the same id (mines_1, chambers_boss),
			// else the act's last generated one (mines_3 -> mines_2, bridge -> battlements_2)
			MissionLevel@ Counterpart(MissionDef@ hoh2, const string &in id)
			{
				for (uint i = 0; i < hoh2.m_levels.length(); i++)
					if (hoh2.m_levels[i].m_id == id)
						return hoh2.m_levels[i];
				int us = id.findFirst("_");
				string act = id == "bridge" ? "battlements" : (us > 0 ? id.substr(0, us) : id);
				MissionLevel@ last = null;
				for (uint i = 0; i < hoh2.m_levels.length(); i++)
				{
					auto l = hoh2.m_levels[i];
					if (l.m_id.findFirst(act + "_") == 0 && l.m_id.findFirst("_boss") < 0)
						@last = l;
				}
				return last;
			}

			string g_summary = "";

			// The constructor runs before the game mode loads the town record (AGameplayGameMode
			// builds an empty g_myTownRecord, then Load), so On() reads false there even with
			// the setting on: every level starts swapped, and Restore puts the HoH1 floors back
			// once the town says on (TownRecordLoad) or the setting turns on in town.
			array<MissionDef@> g_keptDefs;
			array<MissionLevel@> g_kept;   // the HoH1 floors swapped out, by mission and id
			bool g_tower = false;          // Tower() swapped the HoH1 tower this level

			void Swap(MissionDef@ def, uint i, MissionLevel@ to)
			{
				g_keptDefs.insertLast(def);
				g_kept.insertLast(def.m_levels[i]);
				@def.m_levels[i] = to;
			}

			// hoh1.content on: the swapped floors back in their places (ids, as the Dark
			// Citadel's indices move when dark_halls_2 is added), the HoH1 tower listed again
			void Restore()
			{
				if (g_kept.isEmpty())
					return;
				int back = 0;
				for (uint k = 0; k < g_kept.length(); k++)
				{
					auto def = g_keptDefs[k];
					for (uint i = 0; i < def.m_levels.length(); i++)
						if (def.m_levels[i].m_id == g_kept[k].m_id)
						{
							@def.m_levels[i] = g_kept[k];
							back++;
							break;
						}
				}
				g_keptDefs.removeRange(0, g_keptDefs.length());
				g_kept.removeRange(0, g_kept.length());
				auto hoh1 = MissionDef::Get(HashString(HOH1_MISSION_ID));
				if (g_tower && hoh1 !is null)
					hoh1.m_hidden = false;
				g_tower = false;
				Traps::Install();   // idempotent; fixed .lvl floors take no generator command
				HWP::Log("campaign", "hoh1.content on: " + back + " HoH1 floor(s) back");
			}

			// the setting as the town save holds it (HWP::SaveData's "hwp" dictionary), for
			// TownRecordLoad, whose order against hwplib's own hook is not fixed
			bool InSave(SValue@ data)
			{
				if (data is null || data.GetType() != SValueType::Dictionary)
					return false;
				auto hwp = data.GetDictionaryEntry("hwp");
				if (hwp is null || hwp.GetType() != SValueType::Dictionary)
					return false;
				auto v = hwp.GetDictionaryEntry("settings.hoh1.content");
				return v !is null && v.GetType() == SValueType::Boolean && v.GetBoolean();
			}

			// the HoH1 Forsaken Tower: hidden from the portal, and every floor from the HoH2
			// tower for a save already in it
			void Tower()
			{
				auto hoh1 = MissionDef::Get(HashString(HOH1_MISSION_ID));
				auto hoh2 = MissionDef::Get(HashString(MISSION_ID));
				if (hoh1 is null || hoh2 is null || On())
					return;
				if (g_tower)
				{
					HWP::Log("campaign", "hoh1.content off: " + g_summary);
					return;
				}
				g_tower = true;
				hoh1.m_hidden = true;
				int swapped = 0;
				string missing;
				for (uint i = 0; i < hoh1.m_levels.length(); i++)
				{
					auto from = hoh1.m_levels[i];
					auto like = Counterpart(hoh2, from.m_id);
					if (like is null)
					{
						missing += (missing.isEmpty() ? "" : ", ") + from.m_id;
						continue;
					}
					Swap(hoh1, i, Copy(hoh1, from, like));
					swapped++;
				}
				g_summary = HOH1_MISSION_ID + ": " + swapped + "/" + hoh1.m_levels.length() + " floors on HoH2 stand-ins";
				if (missing.isEmpty())
					HWP::Log("campaign", "hoh1.content off: " + g_summary);
				else
					HWP::LogError("campaign", "hoh1.content off: " + g_summary + ", no stand-in for " + missing);
			}

			// every HoH1 file still referenced by a mission floor (none when off)
			string Leftovers()
			{
				string bad;
				for (uint m = 0; m < MissionDef::Instances.length(); m++)
				{
					auto def = MissionDef::Instances[m];
					for (uint i = 0; i < def.m_levels.length(); i++)
						if (def.m_levels[i].m_level.findFirst("hoh1/") == 0)
							bad += (bad.isEmpty() ? "" : ", ") + def.m_id + ":" + def.m_levels[i].m_id;
				}
				return bad;
			}
		}
	}
}

namespace HWPCampaignHooks
{
	// the town record is in: the HoH1 floors back if its save says hoh1.content on
	[Hook]
	void TownRecordLoad(TownRecord@ town, SValue@ data)
	{
		if (town is g_myTownRecord && HWP::Campaign::StandIns::InSave(data))
			HWP::Campaign::StandIns::Restore();
	}
}
