// Floor generation (host only: MissionGameMode.Generate runs on the server and
// clients receive the level). HWPObjectiveSpawn is added to every indoor
// DungeonGenerator's command list in the module constructor, after the
// theme's shrine/skill sets like the puzzles module's rooms, so the vault
// lands before the fillers, decorations and enemy spots run. Authored levels
// (boss floors, town) have no DungeonGenerator and outdoor ForestBrush floors
// paint nothing from the cells: neither gets objectives.
//
// A vault (prefabs/hwp/objectives/vault_s.pfb, 9x8 cells, doorway on the
// south edge) is carved into a solid wall block on the outskirts with a
// straight corridor to the nearest floor, the way the puzzles module forces
// its rooms (BestSpot / corridor code copied from there, the part that was
// measured to come out walkable). Its switch is a 3x3 floor patch placed on
// existing floor as far from the vault as the floor allows; the exit switch
// likewise, as far from the exit prefab as possible. Everything placed is
// logged with cell and world positions:
//   [HWP:objectives] vault 0 at cell X,Y of WxH, corridor N, world X,Y WxH, door X,Y, switch X,Y
//   [HWP:objectives] exit switch at cell X,Y world X,Y (exit at cell X,Y)
//   [HWP:objectives] placed N vault(s), exit switch yes|no on <level>
class HWPObjectiveSpawn : DungeonGenerationCommands
{
	bool Execute(DungeonBrush@ brush, PrefabPlacement@ pfbPlacer) override
	{
		HWP::Objectives::Gen::Run(brush, pfbPlacer);
		return true; // never fails a floor
	}
}

namespace HWP
{
	namespace Objectives
	{
		namespace Gen
		{
			const string SET_VAULT = "hwp_objectives_vault";
			const string SET_SWITCH = "hwp_objectives_switch";
			const string SET_EXIT = "hwp_objectives_exit";
			const string DEFS = "tweak/hwp/objectives_prefabs.sval";
			const int CELL = 16;
			const int PAD = 2;          // cells off the grid's edge
			const int MAX_CORRIDOR = 40;
			const int SWITCH_SZ = 3;
			// the vault's units, relative to the prefab origin (vault_s.pfb)
			const vec2 DOOR_IN_PFB = vec2(48, 112);
			const vec2 SWITCH_IN_PFB = vec2(24, 24);

			bool Walkable(CellGrid@ grid, int x, int y)
			{
				if (x < 0 || y < 0 || x >= grid.m_width || y >= grid.m_height)
					return false;
				Cell c = grid.GetCell(x, y);
				return c == Cell::Floor || c == Cell::Breakables || c == Cell::Bridge;
			}

			// a cell the vault, its rim or its corridor may take: in the grid, not consumed,
			// plain wall (Nothing paints black blocks a cell past their own, cliffs keep tiles)
			bool Free(CellGrid@ grid, int x, int y)
			{
				if (x < 0 || y < 0 || x >= grid.m_width || y >= grid.m_height)
					return false;
				if (grid.IsConsumed(x, y))
					return false;
				return grid.GetCell(x, y) == Cell::Wall;
			}

			class Door
			{
				ivec2 m_from;    // first door cell on the pattern edge
				ivec2 m_along;   // step along the door
				ivec2 m_out;     // step out of the room
				int m_width;
			}

			class Spot
			{
				MissionPrefabDef@ m_def;
				ivec2 m_pos;
				Door@ m_door;
				int m_len;
				float m_score;
			}

			// the run of Walkable cells on one edge of the pattern: the doorway
			bool EdgeRun(MissionPrefabDef@ def, ivec2 start, ivec2 along, ivec2 outDir, Door@ door)
			{
				ivec2 sz = def.m_gridSz;
				int first = -1;
				int n = 0;
				for (int i = 0; ; i++)
				{
					ivec2 c = start + along * i;
					if (c.x < 0 || c.y < 0 || c.x >= sz.x || c.y >= sz.y)
						break;
					bool walk = Pattern(def.m_gridPattern[c.y * sz.x + c.x]) == Pattern::Walkable;
					if (walk && first < 0)
						first = i;
					if (walk && first >= 0 && n == i - first)
						n++;
				}
				if (first < 0 || n < 2)
					return false;
				door.m_from = start + along * first;
				door.m_along = along;
				door.m_out = outDir;
				door.m_width = n;
				return true;
			}

			bool GetDoor(MissionPrefabDef@ def, Door@ door)
			{
				if (def.m_gridPattern is null)
					return false;
				ivec2 sz = def.m_gridSz;
				// south edge first: that is where vault_s.pfb's door unit is
				if (EdgeRun(def, ivec2(0, sz.y - 1), ivec2(1, 0), ivec2(0, 1), door))
					return true;
				if (EdgeRun(def, ivec2(sz.x - 1, 0), ivec2(0, 1), ivec2(1, 0), door))
					return true;
				if (EdgeRun(def, ivec2(0, 0), ivec2(0, 1), ivec2(-1, 0), door))
					return true;
				if (EdgeRun(def, ivec2(0, 0), ivec2(1, 0), ivec2(0, -1), door))
					return true;
				return false;
			}

			// cells out of the door until the corridor meets the level, or -1
			int CorridorLength(CellGrid@ grid, ivec2 pos, Door@ door)
			{
				ivec2 base = pos + door.m_from;
				for (int k = 1; k <= MAX_CORRIDOR; k++)
				{
					bool all = true;
					for (int w = 0; w < door.m_width; w++)
					{
						ivec2 c = base + door.m_out * k + door.m_along * w;
						if (!Walkable(grid, c.x, c.y))
						{
							all = false;
							if (!Free(grid, c.x, c.y))
								return -1;
						}
					}
					if (all)
						return k;
				}
				return -1;
			}

			// summed-area table of the cells a vault may not take (not Free)
			array<array<int>>@ BlockedSums(CellGrid@ grid)
			{
				int w = grid.m_width;
				int h = grid.m_height;
				array<array<int>> s(w + 1, array<int>(h + 1, 0));
				for (int x = 0; x < w; x++)
					for (int y = 0; y < h; y++)
						s[x + 1][y + 1] = (Free(grid, x, y) ? 0 : 1) + s[x][y + 1] + s[x + 1][y] - s[x][y];
				return s;
			}

			int Blocked(array<array<int>>@ s, int x, int y, int w, int h)
			{
				return s[x + w][y + h] - s[x][y + h] - s[x + w][y] + s[x][y];
			}

			// the vault's best spot: the farthest from the middle, a short corridor breaking ties
			Spot@ BestSpot(CellGrid@ grid, array<array<int>>@ sums, MissionPrefabDef@ def)
			{
				def.UnpackGrid();
				Door door;
				if (def.m_gridPattern is null || !GetDoor(def, door))
					return null;
				float cx = grid.m_width / 2.0f;
				float cy = grid.m_height / 2.0f;
				Spot@ best = null;
				ivec2 sz = def.m_gridSz;
				for (int y = PAD; y + sz.y <= grid.m_height - PAD; y++)
				{
					for (int x = PAD; x + sz.x <= grid.m_width - PAD; x++)
					{
						if (Blocked(sums, x - 1, y - 1, sz.x + 2, sz.y + 2) > 0)
							continue;
						int len = CorridorLength(grid, ivec2(x, y), door);
						if (len < 0)
							continue;
						float dx = (x + sz.x / 2.0f - cx) / cx;
						float dy = (y + sz.y / 2.0f - cy) / cy;
						float score = dx * dx + dy * dy - len * 0.01f;
						if (best is null || score > best.m_score)
						{
							if (best is null)
								@best = Spot();
							@best.m_def = def;
							best.m_pos = ivec2(x, y);
							@best.m_door = door;
							best.m_len = len;
							best.m_score = score;
						}
					}
				}
				return best;
			}

			MissionPrefabDef@ FindDef(const string &in set)
			{
				uint hash = HashString(set);
				for (uint i = 0; i < MissionPrefabDef::Instances.length(); i++)
				{
					auto def = MissionPrefabDef::Instances[i];
					if (def.m_set == hash && def.m_prefab !is null)
						return def;
				}
				return null;
			}

			// an unconsumed, walkable SWITCH_SZ block whose top-left is x,y
			bool SwitchFits(CellGrid@ grid, int x, int y)
			{
				for (int j = 0; j < SWITCH_SZ; j++)
					for (int i = 0; i < SWITCH_SZ; i++)
						if (!Walkable(grid, x + i, y + j) || grid.IsConsumed(x + i, y + j))
							return false;
				return true;
			}

			// the switch block farthest from `from` (cells); false when no block fits
			bool FarSwitchSpot(CellGrid@ grid, vec2 from, ivec2 &out cell)
			{
				float best = -1;
				for (int y = 1; y + SWITCH_SZ < grid.m_height; y++)
				{
					for (int x = 1; x + SWITCH_SZ < grid.m_width; x++)
					{
						if (!SwitchFits(grid, x, y))
							continue;
						float dx = x + SWITCH_SZ / 2.0f - from.x;
						float dy = y + SWITCH_SZ / 2.0f - from.y;
						float d = dx * dx + dy * dy;
						if (d > best)
						{
							best = d;
							cell = ivec2(x, y);
						}
					}
				}
				return best >= 0;
			}

			vec2 World(DungeonBrush@ brush, ivec2 cell)
			{
				return vec2(CELL * cell.x + brush.m_posOffset.x, CELL * cell.y + brush.m_posOffset.y);
			}

			// the exit prefab's cell (its point of interest), or the grid centre
			vec2 ExitCell(DungeonBrush@ brush, bool &out found)
			{
				found = false;
				for (uint i = 0; i < brush.m_pointsOfInterest.length(); i++)
				{
					auto poi = brush.m_pointsOfInterest[i];
					if (poi.m_type is null)
						continue;
					string id = poi.m_type.m_id;
					if (id.findFirst("exit") >= 0)
					{
						found = true;
						return vec2(poi.m_pos.x, poi.m_pos.y);
					}
				}
				return vec2(brush.m_width / 2.0f, brush.m_height / 2.0f);
			}

			string OnLevel()
			{
				auto gm = cast<MissionGameModeBase>(g_gameMode);
				if (gm is null || gm.m_missionLevel is null)
					return "";
				return " on " + gm.m_missionLevel.m_id;
			}

			// one vault: carve it, its doorway and corridor, then its switch far away
			bool PlaceVault(DungeonBrush@ brush, PrefabPlacement@ placer, int index, MissionPrefabDef@ def, MissionPrefabDef@ swDef)
			{
				CellGrid@ grid = brush;
				auto sums = BlockedSums(grid);
				auto spot = BestSpot(grid, sums, def);
				if (spot is null)
				{
					HWP::Log("objectives", "vault " + index + ": no free wall block on the outskirts of a " + grid.m_width + "x" + grid.m_height + " floor" + OnLevel());
					return false;
				}
				ivec2 pos = spot.m_pos;
				Door@ door = spot.m_door;
				def.UnpackGrid();
				placer.PlacePrefabAt(def, pos);
				// the pattern's walkable cells (the interior and the doorway) stay floor and
				// consumed; the corridor out is carved through the wall and consumed too, so no
				// later command fills or furnishes it. Its side walls stay unconsumed for their trim.
				for (int y = 0; y < def.m_gridSz.y; y++)
					for (int x = 0; x < def.m_gridSz.x; x++)
						if (Pattern(def.m_gridPattern[y * def.m_gridSz.x + x]) == Pattern::Walkable)
						{
							grid.SetCellIfNotConsumed(pos.x + x, pos.y + y, Cell::Floor);
							grid.SetConsumed(pos.x + x, pos.y + y, true);
						}
				ivec2 base = pos + door.m_from;
				for (int k = 1; k < spot.m_len; k++)
					for (int w = 0; w < door.m_width; w++)
					{
						ivec2 c = base + door.m_out * k + door.m_along * w;
						grid.SetCellIfNotConsumed(c.x, c.y, Cell::Floor);
						grid.SetConsumed(c.x, c.y, true);
					}

				Vault@ v = Vault();
				v.m_cell = pos;
				v.m_size = def.m_gridSz;
				v.m_world = World(brush, pos);
				v.m_corridor = spot.m_len - 1;
				v.m_doors.insertLast(v.m_world + DOOR_IN_PFB);
				v.m_doorCell = base;
				v.m_outDir = door.m_out;

				vec2 centre = vec2(pos.x + def.m_gridSz.x / 2.0f, pos.y + def.m_gridSz.y / 2.0f);
				ivec2 sw;
				if (swDef !is null && FarSwitchSpot(grid, centre, sw))
				{
					swDef.UnpackGrid();
					placer.PlacePrefabAt(swDef, sw);
					v.m_switchCell = sw;
					v.m_switch = World(brush, sw) + SWITCH_IN_PFB;
					v.m_hasSwitch = true;
				}
				else
				{
					// no floor block for a switch: the vault would stay shut, so open it from the start
					v.m_opened = true;
					HWP::LogError("objectives", "vault " + index + ": no 3x3 floor block for its switch; the vault opens at the start");
				}
				g_vaults.insertLast(v);
				HWP::Log("objectives", "vault " + index + " at cell " + pos.x + "," + pos.y + " of " + grid.m_width + "x" + grid.m_height
					+ ", corridor " + v.m_corridor + ", world " + int(v.m_world.x) + "," + int(v.m_world.y) + " " + (def.m_gridSz.x * CELL) + "x" + (def.m_gridSz.y * CELL)
					+ ", door " + int(v.m_doors[0].x) + "," + int(v.m_doors[0].y)
					+ ", switch " + (v.m_hasSwitch ? ("" + int(v.m_switch.x) + "," + int(v.m_switch.y)) : "none") + OnLevel());
				return true;
			}

			bool PlaceExitSwitch(DungeonBrush@ brush, PrefabPlacement@ placer, MissionPrefabDef@ def)
			{
				CellGrid@ grid = brush;
				bool found = false;
				vec2 from = ExitCell(brush, found);
				ivec2 sw;
				if (!FarSwitchSpot(grid, from, sw))
				{
					HWP::Log("objectives", "exit switch: no 3x3 floor block on this floor; the exit stays open" + OnLevel());
					return false;
				}
				def.UnpackGrid();
				placer.PlacePrefabAt(def, sw);
				g_exitPresent = true;
				g_exitOpen = false;
				g_exitSwitch = World(brush, sw) + SWITCH_IN_PFB;
				HWP::Log("objectives", "exit switch at cell " + sw.x + "," + sw.y + " world " + int(g_exitSwitch.x) + "," + int(g_exitSwitch.y)
					+ (found ? (" (exit at cell " + int(from.x) + "," + int(from.y) + ")") : " (no exit prefab yet; far from the middle)") + OnLevel());
				return true;
			}

			// HWPObjectiveSpawn.Execute
			void Run(DungeonBrush@ brush, PrefabPlacement@ placer)
			{
				RefreshSettings();
				ClearFloor();
				if (brush is null || placer is null)
					return;
				auto vaultDef = FindDef(SET_VAULT);
				auto swDef = FindDef(SET_SWITCH);
				auto exitDef = FindDef(SET_EXIT);
				if (vaultDef is null || swDef is null || exitDef is null)
				{
					HWP::LogError("objectives", "prefab defs missing or their prefabs failed to load (" + DEFS + "): vault " + (vaultDef is null ? "no" : "ok")
						+ ", switch " + (swDef is null ? "no" : "ok") + ", exit " + (exitDef is null ? "no" : "ok"));
					return;
				}
				int placed = 0;
				for (int i = 0; i < g_vaultCount; i++)
					if (PlaceVault(brush, placer, i, vaultDef, swDef))
						placed++;
					else
						break;
				bool exit = false;
				if (g_exitOn)
					exit = PlaceExitSwitch(brush, placer, exitDef);
				HWP::Log("objectives", "placed " + placed + " vault(s), exit switch " + (exit ? "yes" : "no") + OnLevel());
			}

			// From the module constructor (every level load, before generation); idempotent.
			int Install()
			{
				int added = 0;
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
						int at = -1;
						bool present = false;
						for (uint k = 0; k < gen.m_genCommands.length(); k++)
						{
							if (cast<HWPObjectiveSpawn>(gen.m_genCommands[k]) !is null)
								present = true;
							auto spawn = cast<SpawnPrefabSet>(gen.m_genCommands[k]);
							if (spawn is null)
								continue;
							if (EndsWith(spawn.m_set, "_shrine") || EndsWith(spawn.m_set, "_skill"))
								at = k + 1;
						}
						if (present)
							continue;
						HWPObjectiveSpawn cmd;
						SValueBuilder sb;
						sb.PushDictionary();
						sb.PopDictionary();
						array<SValue@> params = { sb.Build() };
						cmd.LoadParams(params); // exec-chance 1, no conditionals
						if (at < 0 || uint(at) >= gen.m_genCommands.length())
							gen.m_genCommands.insertLast(cmd);
						else
							gen.m_genCommands.insertAt(at, cmd);
						added++;
					}
				}
				return added;
			}

			bool EndsWith(const string &in s, const string &in suffix)
			{
				return s.length() >= suffix.length() && s.substr(s.length() - suffix.length()) == suffix;
			}
		}
	}
}
