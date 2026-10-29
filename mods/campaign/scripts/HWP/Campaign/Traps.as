// HoH1 traps in generated floors (bugs 10.22.26 line 29, "hoh1 traps bring em back"):
// spike floors, flame jets, bomb glyphs, dart glyphs and confusion glyphs, in normal HoH2
// runs and in the campaign. HoH2 has the trap units (doodads/traps/) but places them only
// inside a few themed rooms; here a generator command of our own, HWPTrapSpawn, is added
// at the end of every DungeonGenerator's command list (every indoor floor of every
// mission; outdoor ForestBrush floors paint nothing from the cells and are skipped), the
// way the puzzles module adds its rooms. It places small prefabs of the hwp_traps set
// (prefabs/hwp/traps/*.pfb, defined in tweak/hwp/campaign_prefabs.sval) on walkable
// cells - HoH2 units with HoH1 numbers for the new glyphs - and then one teleporter pad
// (Teleporters.as) with a destination picked from the floor. Settings: campaign.traps
// (default on), campaign.trap_density (percent of the default count, 100), and the
// teleporter's campaign.teleporters. Everything runs on the host, inside generation.
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
				"doodads/traps/floors/floor_spikes.unit", "doodads/traps/floors/floor_fire.unit",
				"doodads/hwp/teleport_pad.unit" };
			// a prefab whose id has one of these is somewhere worth being teleported into
			const array<string> ROOM_WORDS = { "trap", "puzzle", "secret", "treasure", "chest", "vault", "loot" };
			const int CELLS_PER_TRAP = 120;
			const int MAX_TRAPS = 24;

			bool g_enabled = true;
			int g_density = 100;
			int g_installed = 0;

			void RefreshSettings()
			{
				// campaign.enabled off (the settings page's switch) turns them off with the rest
				g_enabled = HWP::Settings::GetBool("campaign.enabled", true) && HWP::Settings::GetBool("campaign.traps", true);
				g_density = clamp(HWP::Settings::GetInt("campaign.trap_density", 100), 0, 400);
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
				if (g_enabled && g_density > 0)
				{
					want = clamp(cells * g_density / 100 / CELLS_PER_TRAP, 1, MAX_TRAPS);
					placed = placer.PlacePrefabs(HashString(SET), want, 1.0f, 100);
					if (placed < 0)
					{
						HWP::LogError("campaign", "traps: no prefab of set " + SET + " fits or none is defined (" + DEFS + ")");
						placed = 0;
					}
				}
				HWP::Log("campaign", "traps: placed " + placed + "/" + want + " on a " + grid.m_width + "x" + grid.m_height + " floor (" + cells + " floor cells, density " + g_density + "%" + (g_enabled ? "" : ", traps off") + ")");

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
