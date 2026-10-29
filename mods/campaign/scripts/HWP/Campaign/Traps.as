// HoH1 traps in generated floors (bugs 10.22.26 line 29, "hoh1 traps bring em back"; issue
// #37, "add all the traps from hoh1"): spike, poison, drain, frost and confusion plates,
// pressure spikes, flame jets, bomb, dart, confusion, frost and curse glyphs, arrow, poison
// arrow, fire ball and blade shooters on the walls, arrow turrets, flame gargoyles, falling
// stalactites and bricks and bear traps, in normal HoH2 runs and in the campaign. HoH2 has
// some of the trap units (doodads/traps/) but places them only inside a few themed rooms;
// here a generator command of our own, HWPTrapSpawn, is added at the end of every
// DungeonGenerator's command list (every indoor floor of every mission; outdoor
// ForestBrush floors paint nothing from the cells and are skipped), the way the puzzles
// module adds its rooms. It places small prefabs of the hwp_traps set (prefabs/hwp/traps/
// *.pfb, defined in tweak/hwp/campaign_prefabs.sval; most of them written by
// tools/make_hwp_traps.py, the HWPTrap units of TrapBehavior.as) on walkable cells and
// walls, the kinds weighted by the floor's theme (WEIGHTS: stalactites in caves, shooters
// and turrets in barracks and dungeons, drain plates and curse glyphs in crypts and halls,
// as HoH1's acts had them), and then one teleporter pad (Teleporters.as) with a destination
// picked from the floor. The traps go only on the
// floors of one HoH2 mission whose floors suit them, the Crypt (crypt and temple floors) by
// default, and on the Forsaken Tower's, HoH1's own tower (issue #30: spikes on every level of
// every map felt random); the teleporter pad still goes on every floor. Settings:
// campaign.traps (default on), campaign.trap_map (which mission), campaign.trap_density
// (percent of the default count, 100), and the teleporter's campaign.teleporters.
// Everything runs on the host, inside generation.
class HWPTrapSpawn : DungeonGenerationCommands
{
	bool Execute(DungeonBrush@ brush, PrefabPlacement@ pfbPlacer) override
	{
		HWP::Campaign::Traps::Run(brush, pfbPlacer);
		return true;   // never fails a floor
	}
}

namespace HWP
{
	namespace Campaign
	{
		namespace Traps
		{
			const string SET = "hwp_traps";
			const string DEFS = "tweak/hwp/campaign_prefabs.sval";
			const array<string> UNITS = {
				"doodads/hwp/traps/hwp_glyph_bomb.unit", "doodads/hwp/traps/hwp_glyph_bomb_explode.unit",
				"doodads/hwp/traps/hwp_glyph_confusion.unit", "doodads/hwp/traps/hwp_glyph_confusion_explode.unit",
				"doodads/hwp/traps/hwp_glyph_dart.unit", "doodads/hwp/traps/hwp_glyph_dart_burst.unit",
				"doodads/traps/floors/floor_fire.unit", "doodads/traps/mines/glyph_shadow.unit",
				"doodads/traps/statues/haunted_gargoyle/haunted_gargoyle_s.unit",
				"doodads/hwp/traps/hwp_plate_spikes.unit", "doodads/hwp/traps/hwp_pressure_spikes.unit",
				"doodads/hwp/traps/hwp_plate_poison.unit", "doodads/hwp/traps/hwp_plate_drain.unit",
				"doodads/hwp/traps/hwp_plate_frost.unit", "doodads/hwp/traps/hwp_plate_confusion.unit",
				"doodads/hwp/traps/hwp_glyph_frost.unit", "doodads/hwp/traps/hwp_dropper_stalactite.unit",
				"doodads/hwp/traps/hwp_crusher_bricks.unit", "doodads/hwp/traps/hwp_bear_trap.unit",
				"doodads/hwp/traps/hwp_turret_arrows.unit",
				"doodads/hwp/traps/hwp_shooter_arrow_s.unit", "doodads/hwp/traps/hwp_shooter_arrow_e.unit", "doodads/hwp/traps/hwp_shooter_arrow_w.unit",
				"doodads/hwp/traps/hwp_shooter_poison_s.unit", "doodads/hwp/traps/hwp_shooter_poison_e.unit", "doodads/hwp/traps/hwp_shooter_poison_w.unit",
				"doodads/hwp/traps/hwp_shooter_fire_s.unit", "doodads/hwp/traps/hwp_shooter_fire_e.unit", "doodads/hwp/traps/hwp_shooter_fire_w.unit",
				"doodads/hwp/traps/hwp_shooter_blade_s.unit", "doodads/hwp/traps/hwp_shooter_blade_e.unit", "doodads/hwp/traps/hwp_shooter_blade_w.unit",
				"doodads/hwp/teleport_pad.unit" };
			// The kind table: how often each family of trap prefab (the prefab id without its
			// last "_part": shooter_arrow_s and _e are shooter_arrow) comes up on a floor of
			// each theme group, HoH1's acts translated to HoH2's themes. 0 = never there. A
			// family's weight is shared by its prefabs (three facings of a shooter roll as
			// often together as one plate). A family missing from the table weighs 1.
			const array<string> GROUPS = { "cave", "crypt", "barracks", "halls", "dungeon", "other" };
			const array<string> FAMILIES = {
				"plate_spikes", "pressure_spikes", "fire", "plate_poison", "plate_drain", "plate_frost", "plate_confusion",
				"glyph_bomb", "glyph_dart", "glyph_confusion", "glyph_frost", "glyph_curse",
				"shooter_arrow", "shooter_poison", "shooter_fire", "shooter_blade", "turret_arrows", "gargoyle_flame",
				"dropper_stalactite", "crusher_bricks", "bear_trap" };
			const array<int> WEIGHTS = {
			//	cave crypt barracks halls dungeon other
				1, 3, 3, 2, 3, 3,    // plate_spikes
				1, 2, 2, 1, 2, 2,    // pressure_spikes
				0, 1, 2, 2, 1, 1,    // fire (HoH2's flame jet)
				2, 1, 0, 1, 2, 1,    // plate_poison
				0, 2, 0, 2, 1, 1,    // plate_drain
				2, 1, 0, 1, 0, 1,    // plate_frost
				0, 1, 0, 2, 1, 1,    // plate_confusion
				1, 1, 1, 1, 1, 1,    // glyph_bomb
				0, 1, 1, 1, 1, 1,    // glyph_dart
				0, 1, 0, 1, 0, 1,    // glyph_confusion
				1, 1, 0, 1, 0, 1,    // glyph_frost
				0, 1, 0, 2, 0, 1,    // glyph_curse (HoH2's shadow glyph)
				0, 2, 3, 1, 3, 2,    // shooter_arrow
				0, 1, 1, 0, 2, 1,    // shooter_poison
				0, 1, 2, 2, 1, 1,    // shooter_fire
				0, 1, 2, 1, 2, 1,    // shooter_blade
				0, 1, 2, 1, 2, 1,    // turret_arrows
				0, 2, 0, 2, 0, 1,    // gargoyle_flame (HoH2's haunted gargoyle)
				4, 0, 0, 0, 0, 0,    // dropper_stalactite
				0, 1, 1, 1, 1, 1,    // crusher_bricks
				2, 0, 1, 0, 1, 1 };  // bear_trap
			// a prefab whose id has one of these is somewhere worth being teleported into
			const array<string> ROOM_WORDS = { "trap", "puzzle", "secret", "treasure", "chest", "vault", "loot" };
			const int CELLS_PER_TRAP = 120;
			const int MAX_TRAPS = 24;
			// campaign.trap_map: the HoH2 mission whose floors get traps, by index; one past
			// the end is every mission
			const array<string> TRAP_MAPS = { "crypt", "bandit_keep", "dark_citadel", "spider_caves" };
			// HoH1's own tower always has them (with campaign.traps on)
			const array<string> TOWER = { "hwp_forsaken_tower", "hwp_forsaken_tower_hoh1" };

			bool g_enabled = true;
			int g_density = 100;
			int g_map = 0;
			int g_installed = 0;

			void RefreshSettings()
			{
				// campaign.enabled off (the settings page's switch) turns them off with the rest
				g_enabled = HWP::Settings::GetBool("campaign.enabled", true) && HWP::Settings::GetBool("campaign.traps", true);
				g_density = clamp(HWP::Settings::GetInt("campaign.trap_density", 100), 0, 400);
				g_map = clamp(HWP::Settings::GetInt("campaign.trap_map", 0), 0, int(TRAP_MAPS.length()));
			}

			string MapSetting()
			{
				return g_map < int(TRAP_MAPS.length()) ? TRAP_MAPS[g_map] : "every map";
			}

			// the mission of the floor being generated ("" outside a mission)
			string MissionId()
			{
				auto gm = cast<MissionGameModeBase>(g_gameMode);
				if (gm is null || gm.m_missionLevel is null || gm.m_missionLevel.m_mission is null)
					return "";
				return gm.m_missionLevel.m_mission.m_id;
			}

			bool TrapsOn(const string &in mission)
			{
				if (g_map >= int(TRAP_MAPS.length()) || TOWER.find(mission) >= 0)
					return true;
				return mission == TRAP_MAPS[g_map];
			}

			// a DungeonBrush theme ("crypt", "cave_dark", ...) -> its GROUPS entry
			string Group(const string &in theme)
			{
				if (theme.findFirst("cave") == 0)
					return "cave";
				if (theme.findFirst("crypt") == 0 || theme.findFirst("temple") == 0)
					return "crypt";
				if (theme.findFirst("barracks") == 0 || theme.findFirst("keep") == 0)
					return "barracks";
				if (theme.findFirst("courts") == 0 || theme.findFirst("dark_halls") == 0)
					return "halls";
				if (theme.findFirst("dungeon") == 0 || theme.findFirst("prison") == 0)
					return "dungeon";
				return "other";
			}

			// "prefabs/hwp/traps/shooter_arrow_s.pfb" -> "shooter_arrow"
			string Family(const string &in id)
			{
				string name = id;
				int slash = name.findLast("/");
				if (slash >= 0)
					name = name.substr(slash + 1);
				int us = name.findLast("_");
				return us > 0 ? name.substr(0, us) : name;
			}

			int Weight(const string &in family, int group)
			{
				int f = FAMILIES.find(family);
				if (f < 0 || group < 0)
					return 1;
				return WEIGHTS[f * GROUPS.length() + group];
			}

			// Set this floor's roll chance on every hwp_traps prefab from the kind table, and
			// take the weight-0 ones out of this generation (PlacePrefabs rolls among the rest;
			// with chance 0 alone a type could still come up once the others are used up).
			// Returns the families that can come up, for the log.
			string ApplyWeights(const string &in group)
			{
				int g = GROUPS.find(group);
				uint trapSet = HashString(SET);
				array<string> fams;
				array<int> counts;
				for (uint i = 0; i < MissionPrefabDef::Instances.length(); i++)
				{
					auto def = MissionPrefabDef::Instances[i];
					if (def.m_set != trapSet)
						continue;
					string fam = Family(def.m_id);
					int k = fams.find(fam);
					if (k < 0)
					{
						fams.insertLast(fam);
						counts.insertLast(1);
					}
					else
						counts[k]++;
				}
				string on = "";
				for (uint i = 0; i < MissionPrefabDef::Instances.length(); i++)
				{
					auto def = MissionPrefabDef::Instances[i];
					if (def.m_set != trapSet)
						continue;
					string fam = Family(def.m_id);
					int w = Weight(fam, g);
					def.CanGet();   // starts this generation's count for it (m_currGenNumId)
					if (w <= 0)
					{
						def.m_foundNoPlacement = true;
						continue;
					}
					def.m_rollChance = max(1, w * 60 / counts[fams.find(fam)]);
					if (on.findFirst(fam + " ") < 0)
						on += fam + " " + w + ", ";
				}
				return on.length() > 2 ? on.substr(0, on.length() - 2) : "none";
			}

			bool Walkable(CellGrid@ grid, int x, int y)
			{
				if (x < 0 || y < 0 || x >= grid.m_width || y >= grid.m_height)
					return false;
				Cell c = grid.GetCell(x, y);
				return c == Cell::Floor || c == Cell::PlaceFloor || c == Cell::Bridge;
			}

			int FloorCells(CellGrid@ grid)
			{
				int n = 0;
				for (int y = 0; y < grid.m_height; y++)
					for (int x = 0; x < grid.m_width; x++)
						if (Walkable(grid, x, y))
							n++;
				return n;
			}

			// a cell's centre in the world (DungeonBrush.MakePrefabsToSpawn: 16 * cell + offset)
			vec2 World(DungeonBrush@ brush, ivec2 cell)
			{
				return vec2(16 * cell.x + brush.m_posOffset.x + 8, 16 * cell.y + brush.m_posOffset.y + 8);
			}

			bool NearestWalkable(CellGrid@ grid, ivec2 from, int radius, ivec2 &out cell)
			{
				for (int r = 0; r <= radius; r++)
				{
					for (int dy = -r; dy <= r; dy++)
					{
						for (int dx = -r; dx <= r; dx++)
						{
							if (abs(dx) != r && abs(dy) != r)
								continue;
							if (Walkable(grid, from.x + dx, from.y + dy))
							{
								cell = ivec2(from.x + dx, from.y + dy);
								return true;
							}
						}
					}
				}
				return false;
			}

			int DistSq(ivec2 a, ivec2 b)
			{
				return (a.x - b.x) * (a.x - b.x) + (a.y - b.y) * (a.y - b.y);
			}

			// Where a pad at padCell sends its users: the farthest trap, puzzle or treasure
			// prefab already on the floor (its centre, moved to a walkable cell), else the
			// farthest open floor cell.
			bool PickDestination(CellGrid@ grid, ivec2 padCell, ivec2 &out cell, string &out why)
			{
				int best = -1;
				uint padSet = HashString(Teleporters::SET);
				uint trapSet = HashString(SET);
				for (uint i = 0; i < grid.m_pointsOfInterest.length(); i++)
				{
					auto type = grid.m_pointsOfInterest[i].m_type;
					if (type is null || type.m_set == padSet)
						continue;
					bool room = type.m_set == trapSet;
					for (uint w = 0; w < ROOM_WORDS.length() && !room; w++)
						room = type.m_id.findFirst(ROOM_WORDS[w]) >= 0;
					if (!room)
						continue;
					// m_pos is the prefab origin (match position + grid offset); its footprint
					// starts at the match position and spans grid-size cells
					ivec2 origin = grid.m_pointsOfInterest[i].m_pos;
					ivec2 centre = ivec2(origin.x - type.m_gridOffset.x + type.m_gridSz.x / 2, origin.y - type.m_gridOffset.y + type.m_gridSz.y / 2);
					ivec2 c;
					if (!NearestWalkable(grid, centre, 4, c))
						continue;
					int d = DistSq(c, padCell);
					if (d > best && d >= 12 * 12)
					{
						best = d;
						cell = c;
						why = type.m_id;
					}
				}
				if (best >= 0)
					return true;
				for (int y = 1; y < grid.m_height - 1; y += 2)
				{
					for (int x = 1; x < grid.m_width - 1; x += 2)
					{
						if (!Walkable(grid, x, y) || grid.IsConsumed(x, y))
							continue;
						int d = DistSq(ivec2(x, y), padCell);
						if (d > best)
						{
							best = d;
							cell = ivec2(x, y);
							why = "the far side of the floor";
						}
					}
				}
				return best >= 12 * 12;
			}

			// HWPTrapSpawn.Execute: after every vanilla set of the floor
			void Run(DungeonBrush@ brush, PrefabPlacement@ placer)
			{
				RefreshSettings();
				Teleporters::RefreshSettings();
				Teleporters::Clear();
				CellGrid@ grid = placer.m_grid;
				if (grid is null || brush is null)
					return;
				int cells = FloorCells(grid);
				int want = 0;
				int placed = 0;
				string mission = MissionId();
				bool here = TrapsOn(mission);
				uint firstPoi = grid.m_pointsOfInterest.length();
				string group = Group(brush.m_theme);
				if (g_enabled && g_density > 0 && here)
				{
					HWP::Log("campaign", "traps: theme " + brush.m_theme + " (" + group + "): " + ApplyWeights(group));
					want = clamp(cells * g_density / 100 / CELLS_PER_TRAP, 1, MAX_TRAPS);
					// One roll per trap. PlacePrefabs places up to typeMinLimit of the type it
					// rolls before it rolls another, and spikes_1 had no max-num, so a single
					// call (limit 100) filled a whole floor with spike floors whenever spikes_1
					// came up first (issue #30). With one trap per call each trap is rolled
					// among the types that still can be placed (CanGet: max-num), by the
					// weights ApplyWeights set; a type that fits nowhere is skipped for the
					// rest of the floor (m_foundNoPlacement), so a floor without long walls
					// simply gets no shooters.
					for (int k = 0; k < want; k++)
					{
						int n = placer.PlacePrefabs(HashString(SET), 1, 1.0f, 1);
						if (n < 0)
						{
							if (placed == 0)
								HWP::LogError("campaign", "traps: no prefab of set " + SET + " fits or none is defined (" + DEFS + ")");
							break;
						}
						if (n == 0)
							break;
						placed += n;
					}
				}
				HWP::Log("campaign", "traps: placed " + placed + "/" + want + " on a " + grid.m_width + "x" + grid.m_height + " floor (" + cells + " floor cells, density " + g_density + "%"
					+ (g_enabled ? "" : ", traps off") + ", mission " + (mission.isEmpty() ? "none" : mission)
					+ (here ? "" : ", not a trap map: campaign.trap_map is " + MapSetting()) + ")");
				if (placed > 0)
					HWP::Log("campaign", "traps: kinds " + Kinds(grid, firstPoi));

				if (!Teleporters::g_enabled)
				{
					HWP::Log("campaign", "teleporter: off (campaign.teleporters)");
					return;
				}
				uint before = grid.m_pointsOfInterest.length();
				int pads = placer.PlacePrefabs(HashString(Teleporters::SET), 1, 1.0f, 100);
				if (pads <= 0)
				{
					HWP::Log("campaign", "teleporter: no spot on this floor");
					return;
				}
				uint padSet = HashString(Teleporters::SET);
				for (uint i = before; i < grid.m_pointsOfInterest.length(); i++)
				{
					auto type = grid.m_pointsOfInterest[i].m_type;
					if (type is null || type.m_set != padSet)
						continue;
					// the pad prefab has grid-pos -1 -1 in a 3x3, so the origin is its centre
					// cell and the pad unit sits at 8,8: World() of that cell is the pad
					ivec2 padCell = grid.m_pointsOfInterest[i].m_pos;
					ivec2 destCell;
					string why;
					if (!PickDestination(grid, padCell, destCell, why))
					{
						HWP::Log("campaign", "teleporter at cell " + padCell.x + "," + padCell.y + ": no destination, the pad picks one at use");
						continue;
					}
					vec2 padW = World(brush, padCell);
					vec2 destW = World(brush, destCell);
					Teleporters::Add(padW, destW, why);
					HWP::Log("campaign", "teleporter placed at " + int(padW.x) + "," + int(padW.y) + " (cell " + padCell.x + "," + padCell.y + ") -> " + int(destW.x) + "," + int(destW.y) + " (cell " + destCell.x + "," + destCell.y + ", " + why + ")");
				}
			}

			// how many of each trap prefab generation placed: "spikes_1 6, fire_1 4, ..."
			string Kinds(CellGrid@ grid, uint from)
			{
				uint trapSet = HashString(SET);
				array<string> ids;
				array<int> counts;
				for (uint i = from; i < grid.m_pointsOfInterest.length(); i++)
				{
					auto type = grid.m_pointsOfInterest[i].m_type;
					if (type is null || type.m_set != trapSet)
						continue;
					string id = type.m_id;
					int slash = id.findLast("/");
					if (slash >= 0)
						id = id.substr(slash + 1);
					if (id.findLast(".pfb") == int(id.length()) - 4)
						id = id.substr(0, id.length() - 4);
					int k = ids.find(id);
					if (k < 0)
					{
						ids.insertLast(id);
						counts.insertLast(1);
					}
					else
						counts[k]++;
				}
				string s = "";
				for (uint i = 0; i < ids.length(); i++)
					s += (i > 0 ? ", " : "") + ids[i] + " " + counts[i];
				return s;
			}

			SValue@ EmptyParams()
			{
				SValueBuilder sb;
				sb.PushDictionary();
				sb.PopDictionary();
				return sb.Build();
			}

			// From the module constructor (every level load, before generation); idempotent.
			// Returns how many generators got the command this time.
			int Install()
			{
				int added = 0;
				int floors = 0;
				for (uint i = 0; i < MissionDef::Instances.length(); i++)
				{
					auto mission = MissionDef::Instances[i];
					for (uint j = 0; j < mission.m_levels.length(); j++)
					{
						auto gen = cast<DungeonGenerator>(mission.m_levels[j].m_generator);
						if (gen is null)
							continue;
						if (cast<ForestBrush>(gen.m_brush) !is null)
							continue;
						floors++;
						bool present = false;
						for (uint k = 0; k < gen.m_genCommands.length() && !present; k++)
							present = cast<HWPTrapSpawn>(gen.m_genCommands[k]) !is null;
						if (present)
							continue;
						HWPTrapSpawn cmd;
						array<SValue@> params = { EmptyParams() };
						cmd.LoadParams(params);   // exec-chance 1, no conditionals
						gen.m_genCommands.insertLast(cmd);
						added++;
					}
				}
				g_installed = floors;
				if (added > 0)
					HWP::Log("campaign", "traps: generator command on " + added + " of " + floors + " indoor floors");
				return added;
			}
		}
	}
}
