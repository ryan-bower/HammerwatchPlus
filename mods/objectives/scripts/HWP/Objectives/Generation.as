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
// its rooms (the shared HWP::Carve spot and corridor code,
// mods/hwplib/scripts/HWP/Core/Carve.as).
//
// Its lever, and the exit's (issue #74), is mounted on a wall: a 3-cell run of
// plain wall on the north, east or west side of a 3x3 floor patch the players
// reach (PickLever). The lever used to go on the 3x3 floor block farthest from
// what it opens, which is always a corner of the floor, and with the vault on
// the top edge (its door faces south) one of the two bottom corners, against
// the bottom wall. Now any spot at least half as far as the farthest one will
// do: a wall side is picked at random among those with a spot, then a spot on
// it. No south walls: a wall south of the floor shows only its top, drawn two
// cells up over the floor in front of it, so a lever there would be hidden. A
// floor with no wall run that fits gets the old floor lever on a 3x3 patch.
// Everything placed is logged with cell and world positions:
//   [HWP:objectives] vault 0 at cell X,Y of WxH, corridor N, world X,Y WxH, door X,Y, switch X,Y
//   [HWP:objectives] vault 0 lever: <side>, from N spot(s) far enough (north wall A, east wall B, west wall C)
//   [HWP:objectives] exit switch at cell X,Y world X,Y (exit at cell X,Y)
//   [HWP:objectives] placed N vault(s), exit switch yes|no on <level>
//
// The cells are PlaceFloor / PlaceWall (objectives_prefabs.sval) so the brush
// paints them as the floor's own (issue #26). Its build frees them before the
// painting list runs; HWPObjectivePainter, last on that list, takes the floor
// cells back afterwards, so the enemy spots placed after the build stay out
// of the vaults, as they did when the cells were reserved. It logs:
//   [HWP:objectives] painted: N floor cell(s) of M, ring W wall cell(s) of R, switches hidden|marked on <level>
class HWPObjectiveSpawn : DungeonGenerationCommands
{
	bool Execute(DungeonBrush@ brush, PrefabPlacement@ pfbPlacer) override
	{
		HWP::Objectives::Gen::Run(brush, pfbPlacer);
		return true; // never fails a floor
	}
}

class HWPObjectivePainter : DungeonBrush::IPainter
{
	void Paint(Scene@ scene, DungeonBrush@ brush)
	{
		HWP::Objectives::Gen::AfterPaint(brush);
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
			// the vault's units, relative to the prefab origin (vault_s.pfb)
			const vec2 DOOR_IN_PFB = vec2(48, 112);
			const vec2 SWITCH_IN_PFB = vec2(24, 24);

			// HWP (issue #74): where a lever goes. Each side is a prefab set of its own,
			// the kind's set plus the suffix (objectives_prefabs.sval): a 3x3 floor patch
			// and, for a wall, the 3-cell wall run beside it.
			const int SIDE_FLOOR = 0;  // vault_switch.pfb: the old floor lever, when no wall fits
			const int SIDE_N = 1;      // on the face of a wall north of the patch
			const int SIDE_E = 2;      // on a wall east of the patch
			const int SIDE_W = 3;      // on a wall west of the patch
			const int SIDES = 4;
			// a spot is far enough at this share of the farthest spot's distance
			const float FAR_SHARE = 0.5f;
			// cells kept between the floor's levers when the far spots allow it
			const float LEVER_SPACING = 12.0f;

			string SideSuffix(int side)
			{
				if (side == SIDE_N) return "_n";
				if (side == SIDE_E) return "_e";
				if (side == SIDE_W) return "_w";
				return "";
			}

			string SideName(int side)
			{
				if (side == SIDE_N) return "north wall";
				if (side == SIDE_E) return "east wall";
				if (side == SIDE_W) return "west wall";
				return "floor";
			}

			// the lever unit in its side's prefab, px from the top-left cell's corner (the .pfb
			// files). North: the middle wall cell's bottom edge, where vanilla stands its wall
			// buttons and torches (DungeonInstanceBrush.SpawnTorchDeco: cell + 8,16). East and
			// west: the wall's edge facing the patch, at the top of the run's middle cell, so the
			// art (drawn up to 30 px above the unit) is clear of the tops of any wall south of
			// the patch (every wall's art is drawn 32 px up from its cell).
			vec2 LeverInPfb(int side)
			{
				if (side == SIDE_N) return vec2(24, 16);
				if (side == SIDE_E) return vec2(48, 16);
				if (side == SIDE_W) return vec2(16, 16);
				return SWITCH_IN_PFB;
			}

			// this generation's walkable cells (vault interiors, doorways, corridors and the
			// switch patches), consumed again once the brush has painted them
			array<ivec2> g_floorCells;
			// the vaults' wall rings, for the painted line
			array<ivec2> g_ringCells;
			// the patch row against a north-wall lever's wall run (AfterPaint keeps torches off it)
			array<ivec2> g_frontCells;
			// this generation's levers, in cells, to keep the next one away from them
			array<vec2> g_leverCells;
			// the cells of the floor's largest connected walkable area (ComputeReach), x + y * width
			array<bool> g_reach;
			int g_reachWidth = 0;

			// a prefab's walkable cells at pos go on the list (its commands made them PlaceFloor)
			void KeepFloor(MissionPrefabDef@ def, ivec2 pos, bool ring)
			{
				for (int y = 0; y < def.m_gridSz.y; y++)
					for (int x = 0; x < def.m_gridSz.x; x++)
					{
						Pattern p = Pattern(def.m_gridPattern[y * def.m_gridSz.x + x]);
						if (p == Pattern::Walkable)
							g_floorCells.insertLast(pos + ivec2(x, y));
						else if (ring && p == Pattern::Wall)
							g_ringCells.insertLast(pos + ivec2(x, y));
					}
			}

			// HWPObjectivePainter: the build has turned the Place cells into Floor and Wall
			// and painted them; take the floor back so nothing after the build lands there
			void AfterPaint(DungeonBrush@ brush)
			{
				if (g_floorCells.length() == 0 && g_ringCells.length() == 0)
					return;
				int floor = 0;
				for (uint i = 0; i < g_floorCells.length(); i++)
				{
					ivec2 c = g_floorCells[i];
					if (brush.GetCell(c.x, c.y) == Cell::Floor)
						floor++;
					brush.SetConsumed(c.x, c.y, true);
				}
				int walls = 0;
				for (uint i = 0; i < g_ringCells.length(); i++)
				{
					ivec2 c = g_ringCells[i];
					if (brush.GetCell(c.x, c.y) == Cell::Wall && !brush.IsConsumed(c.x, c.y))
						walls++;
				}
				HWP::Log("objectives", "painted: " + floor + " floor cell(s) of " + g_floorCells.length() + ", ring "
					+ walls + " wall cell(s) of " + g_ringCells.length() + ", switches " + (HWP::Objectives::SwitchesMarked() ? "marked" : "hidden") + OnLevel());
				// HWP (issue #74): no torch on a north-wall lever's wall run. The walls are filled
				// after the painting list (DungeonInstanceBrush.Build), and a wall cell gets a
				// torch only with open floor below it (SpawnTorchDeco: IsOpen(x, y + 1), Floor or
				// Breakables). The patch row against the wall is painted and consumed already, so
				// it goes back to PlaceFloor: the walls' pass sees no open floor below the run,
				// and nothing after the build reads the cell (enemy spots skip it as consumed).
				for (uint i = 0; i < g_frontCells.length(); i++)
				{
					ivec2 c = g_frontCells[i];
					if (brush.GetCell(c.x, c.y) == Cell::Floor)
						brush.SetCell(c.x, c.y, Cell::PlaceFloor);
				}
				g_floorCells.removeRange(0, g_floorCells.length());
				g_ringCells.removeRange(0, g_ringCells.length());
				g_frontCells.removeRange(0, g_frontCells.length());
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

			// a kind's lever prefabs by side (set + SideSuffix), unpacked; null where missing
			array<MissionPrefabDef@>@ LeverDefs(const string &in set)
			{
				array<MissionPrefabDef@> defs;
				for (int s = 0; s < SIDES; s++)
				{
					auto def = FindDef(set + SideSuffix(s));
					if (def !is null)
						def.UnpackGrid();
					defs.insertLast(def);
				}
				return defs;
			}

			// the sides whose prefab is missing, for the error line
			string MissingSides(array<MissionPrefabDef@>@ defs)
			{
				string missing = "";
				for (int s = 0; s < SIDES; s++)
					if (defs[s] is null || defs[s].m_gridPattern is null)
						missing += (missing == "" ? "" : ", ") + SideName(s);
				return missing;
			}

			// a cell a player can cross: floor, or a prefab's cells (a room with its own art is
			// Reserved, a carved room PlaceFloor until the build)
			bool Passable(CellGrid@ grid, int x, int y)
			{
				if (HWP::Carve::Walkable(grid, x, y))
					return true;
				Cell c = grid.GetCell(x, y);
				return c == Cell::Reserved || c == Cell::PlaceFloor;
			}

			// g_reach: the floor's largest connected area of walkable cells (4-neighbour fill
			// over Passable cells, counted by their walkable cells). A lever patch must be in it,
			// so no lever lands on floor cut off by a pit or by walls.
			void ComputeReach(CellGrid@ grid)
			{
				int w = grid.m_width;
				int h = grid.m_height;
				g_reachWidth = w;
				array<int> comp(w * h, -1);
				array<int> queue;
				int best = -1;
				int bestCount = 0;
				int label = 0;
				for (int y = 0; y < h; y++)
				{
					for (int x = 0; x < w; x++)
					{
						int start = x + y * w;
						if (comp[start] >= 0 || !Passable(grid, x, y))
							continue;
						comp[start] = label;
						queue.resize(0);
						queue.insertLast(start);
						int count = 0;
						for (uint head = 0; head < queue.length(); head++)
						{
							int c = queue[head];
							int cx = c % w;
							int cy = c / w;
							if (HWP::Carve::Walkable(grid, cx, cy))
								count++;
							for (int d = 0; d < 4; d++)
							{
								int nx = cx + (d == 0 ? 1 : (d == 1 ? -1 : 0));
								int ny = cy + (d == 2 ? 1 : (d == 3 ? -1 : 0));
								if (nx < 0 || ny < 0 || nx >= w || ny >= h)
									continue;
								int n = nx + ny * w;
								if (comp[n] >= 0 || !Passable(grid, nx, ny))
									continue;
								comp[n] = label;
								queue.insertLast(n);
							}
						}
						if (count > bestCount)
						{
							bestCount = count;
							best = label;
						}
						label++;
					}
				}
				g_reach.resize(w * h);
				for (int i = 0; i < w * h; i++)
					g_reach[i] = best >= 0 && comp[i] == best;
			}

			bool Reached(int x, int y)
			{
				int i = x + y * g_reachWidth;
				return x >= 0 && x < g_reachWidth && i >= 0 && uint(i) < g_reach.length() && g_reach[i];
			}

			// the side's prefab fits with its top-left cell at x,y: its floor cells (pattern
			// Walkable) on unconsumed floor in the reached area, its wall cells (pattern Wall) on
			// free plain wall (unconsumed, so no prefab's own art is there, and it stays wall: the
			// prefab makes it PlaceWall). A floor lever also wants floor in the row below its
			// patch when clearBelow is set: a wall there draws its top over the lever (walls are
			// drawn 32 px up).
			bool LeverFits(CellGrid@ grid, MissionPrefabDef@ def, int side, int x, int y, bool clearBelow = true)
			{
				ivec2 sz = def.m_gridSz;
				if (x < 1 || y < 1 || x + sz.x >= grid.m_width || y + sz.y >= grid.m_height)
					return false;
				for (int j = 0; j < sz.y; j++)
				{
					for (int i = 0; i < sz.x; i++)
					{
						Pattern p = Pattern(def.m_gridPattern[j * sz.x + i]);
						int cx = x + i;
						int cy = y + j;
						if (p == Pattern::Walkable)
						{
							if (!HWP::Carve::Walkable(grid, cx, cy) || grid.IsConsumed(cx, cy) || !Reached(cx, cy))
								return false;
						}
						else if (p == Pattern::Wall)
						{
							if (!HWP::Carve::Free(grid, cx, cy))
								return false;
						}
					}
				}
				if (side == SIDE_FLOOR && clearBelow)
					for (int i = 0; i < sz.x; i++)
						if (!HWP::Carve::Walkable(grid, x + i, y + sz.y))
							return false;
				return true;
			}

			// The lever's spot, far from `from` (cells) but not always the farthest (issue #74):
			// every spot on a north, east or west wall that fits (the floor patches only when no
			// wall does, and a patch with a wall below it only when no other patch fits: a lever
			// partly hidden by a wall top beats no lever and an exit left open), those at least FAR_SHARE of the farthest one's distance away and, when
			// some are, LEVER_SPACING cells from the floor's other levers; then a side at random
			// among those left, so each wall side is as likely as the others whatever their
			// lengths, and a spot on it at random. False when nothing fits.
			bool PickLever(CellGrid@ grid, array<MissionPrefabDef@>@ defs, vec2 from, ivec2 &out cell, int &out side, string &out how)
			{
				array<int> sides;
				array<ivec2> spots;
				array<float> dists;
				// pass 0: the walls; 1: floor patches with floor below; 2: any floor patch
				for (int pass = 0; pass < 3 && spots.length() == 0; pass++)
				{
					for (int s = 0; s < SIDES; s++)
					{
						if ((pass == 0) == (s == SIDE_FLOOR))
							continue;
						auto def = defs[s];
						if (def is null || def.m_gridPattern is null)
							continue;
						vec2 lever = LeverInPfb(s) * (1.0f / CELL);
						for (int y = 1; y + def.m_gridSz.y < grid.m_height; y++)
						{
							for (int x = 1; x + def.m_gridSz.x < grid.m_width; x++)
							{
								if (!LeverFits(grid, def, s, x, y, pass < 2))
									continue;
								sides.insertLast(s);
								spots.insertLast(ivec2(x, y));
								dists.insertLast(dist(vec2(x, y) + lever, from));
							}
						}
					}
				}
				if (spots.length() == 0)
					return false;
				float farthest = 0;
				for (uint i = 0; i < dists.length(); i++)
					farthest = max(farthest, dists[i]);
				array<uint> pool;
				for (int spaced = 1; spaced >= 0 && pool.length() == 0; spaced--)
				{
					for (uint i = 0; i < spots.length(); i++)
					{
						if (dists[i] < FAR_SHARE * farthest)
							continue;
						if (spaced == 1 && !AwayFromLevers(vec2(spots[i].x, spots[i].y) + LeverInPfb(sides[i]) * (1.0f / CELL)))
							continue;
						pool.insertLast(i);
					}
				}
				array<int> perSide(SIDES, 0);
				array<int> present;
				for (uint k = 0; k < pool.length(); k++)
				{
					int s = sides[pool[k]];
					if (perSide[s] == 0)
						present.insertLast(s);
					perSide[s]++;
				}
				side = present[randi(present.length())];
				array<uint> onSide;
				for (uint k = 0; k < pool.length(); k++)
					if (sides[pool[k]] == side)
						onSide.insertLast(pool[k]);
				uint pick = onSide[randi(onSide.length())];
				cell = spots[pick];
				how = "on the " + SideName(side) + ", picked from " + pool.length() + " far spot(s) of " + spots.length() + " (";
				string sep = "";
				for (int s = 0; s < SIDES; s++)
				{
					if (s == SIDE_FLOOR && perSide[s] == 0)
						continue;
					how += sep + SideName(s) + " " + perSide[s];
					sep = ", ";
				}
				how += ")";
				return true;
			}

			bool AwayFromLevers(vec2 lever)
			{
				for (uint i = 0; i < g_leverCells.length(); i++)
					if (dist(g_leverCells[i], lever) < LEVER_SPACING)
						return false;
				return true;
			}

			// a lever of the kind whose prefabs are `defs`, far from `from` (cells): placed, its
			// floor kept for AfterPaint, and logged as "<what> lever: on the <side>, ..."
			bool PlaceLever(DungeonBrush@ brush, PrefabPlacement@ placer, array<MissionPrefabDef@>@ defs, vec2 from, const string &in what, ivec2 &out cell, vec2 &out world)
			{
				CellGrid@ grid = brush;
				int side = SIDE_FLOOR;
				ivec2 pos;
				string how;
				if (!PickLever(grid, defs, from, pos, side, how))
					return false;
				auto def = defs[side];
				placer.PlacePrefabAt(def, pos);
				KeepFloor(def, pos, false);
				if (side == SIDE_N)
					for (int i = 0; i < def.m_gridSz.x; i++)
						g_frontCells.insertLast(pos + ivec2(i, 1));
				cell = pos;
				world = World(brush, pos) + LeverInPfb(side);
				g_leverCells.insertLast(vec2(pos.x, pos.y) + LeverInPfb(side) * (1.0f / CELL));
				HWP::Log("objectives", what + " lever: " + how + OnLevel());
				return true;
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
			bool PlaceVault(DungeonBrush@ brush, PrefabPlacement@ placer, int index, MissionPrefabDef@ def, array<MissionPrefabDef@>@ swDefs)
			{
				CellGrid@ grid = brush;
				auto sums = HWP::Carve::BlockedSums(grid);
				auto spot = HWP::Carve::BestSpot(grid, sums, def, PAD, true); // the vault's door: its south edge
				if (spot is null)
				{
					HWP::Log("objectives", "vault " + index + ": no free wall block on the outskirts of a " + grid.m_width + "x" + grid.m_height + " floor" + OnLevel());
					return false;
				}
				ivec2 pos = spot.m_pos;
				HWP::Carve::Door@ door = spot.m_door;
				def.UnpackGrid();
				// the prefab's commands make the interior and doorway PlaceFloor and the ring
				// PlaceWall, all consumed until the build; the corridor out is carved through
				// the wall the same way, so no later command fills or furnishes it. Its side
				// walls stay unconsumed walls, painted as the floor's own.
				placer.PlacePrefabAt(def, pos);
				KeepFloor(def, pos, true);
				ivec2 base = pos + door.m_from;
				for (int k = 1; k < spot.m_len; k++)
					for (int w = 0; w < door.m_width; w++)
					{
						ivec2 c = base + door.m_out * k + door.m_along * w;
						if (grid.IsConsumed(c.x, c.y))
							continue;
						grid.SetCell(c.x, c.y, Cell::PlaceFloor);
						grid.SetConsumed(c.x, c.y, true);
						g_floorCells.insertLast(c);
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
				vec2 swWorld;
				if (PlaceLever(brush, placer, swDefs, centre, "vault " + index, sw, swWorld))
				{
					v.m_switchCell = sw;
					v.m_switch = swWorld;
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

			bool PlaceExitSwitch(DungeonBrush@ brush, PrefabPlacement@ placer, array<MissionPrefabDef@>@ defs)
			{
				bool found = false;
				vec2 from = ExitCell(brush, found);
				ivec2 sw;
				vec2 swWorld;
				if (!PlaceLever(brush, placer, defs, from, "exit", sw, swWorld))
				{
					HWP::Log("objectives", "exit switch: no 3x3 floor block on this floor; the exit stays open" + OnLevel());
					return false;
				}
				g_exitPresent = true;
				g_exitOpen = false;
				g_exitSwitch = swWorld;
				HWP::Log("objectives", "exit switch at cell " + sw.x + "," + sw.y + " world " + int(g_exitSwitch.x) + "," + int(g_exitSwitch.y)
					+ (found ? (" (exit at cell " + int(from.x) + "," + int(from.y) + ")") : " (no exit prefab yet; far from the middle)") + OnLevel());
				return true;
			}

			// HWPObjectiveSpawn.Execute
			void Run(DungeonBrush@ brush, PrefabPlacement@ placer)
			{
				RefreshSettings();
				ClearFloor();
				g_floorCells.removeRange(0, g_floorCells.length());
				g_ringCells.removeRange(0, g_ringCells.length());
				g_frontCells.removeRange(0, g_frontCells.length());
				g_leverCells.removeRange(0, g_leverCells.length());
				g_generatedHere = true;
				if (brush is null || placer is null)
					return;
				if (!g_enabled)
				{
					HWP::Log("objectives", "objectives.enabled is off: nothing placed" + OnLevel());
					return;
				}
				auto vaultDef = FindDef(SET_VAULT);
				auto swDef = FindDef(SET_SWITCH);
				auto exitDef = FindDef(SET_EXIT);
				if (vaultDef is null || swDef is null || exitDef is null)
				{
					HWP::LogError("objectives", "prefab defs missing or their prefabs failed to load (" + DEFS + "): vault " + (vaultDef is null ? "no" : "ok")
						+ ", switch " + (swDef is null ? "no" : "ok") + ", exit " + (exitDef is null ? "no" : "ok"));
					return;
				}
				// the wall levers (issue #74); a side whose prefab is missing is only skipped
				auto swDefs = LeverDefs(SET_SWITCH);
				auto exitDefs = LeverDefs(SET_EXIT);
				string missing = MissingSides(swDefs);
				if (missing != "")
					HWP::LogError("objectives", "vault lever prefabs missing (" + DEFS + "): " + missing);
				missing = MissingSides(exitDefs);
				if (missing != "")
					HWP::LogError("objectives", "exit lever prefabs missing (" + DEFS + "): " + missing);
				// the floor the players reach, before anything is placed (a vault turns wall into
				// its own cells, which reach nothing new; levers go on unconsumed floor only)
				ComputeReach(brush);
				int placed = 0;
				for (int i = 0; i < g_vaultCount; i++)
					if (PlaceVault(brush, placer, i, vaultDef, swDefs))
						placed++;
					else
						break;
				bool exit = false;
				if (g_exitOn)
					exit = PlaceExitSwitch(brush, placer, exitDefs);
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
						AddPainter(gen.m_brush);
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

			// HWPObjectivePainter goes last on the brush's painting list, once
			void AddPainter(DungeonBrush@ brush)
			{
				if (brush is null)
					return;
				for (uint k = 0; k < brush.m_painting.length(); k++)
					if (cast<HWPObjectivePainter>(brush.m_painting[k]) !is null)
						return;
				brush.m_painting.insertLast(HWPObjectivePainter());
			}

			bool EndsWith(const string &in s, const string &in suffix)
			{
				return s.length() >= suffix.length() && s.substr(s.length() - suffix.length()) == suffix;
			}
		}
	}
}
