// HWP puzzles: puzzle rooms back in the dungeons, plus HoH1's Constellation.
//
// HoH2 ships 88 puzzle rooms (prefabs/<biome>/special/puzzle_room_*, theme
// <biome>_puzzle in tweak/missions/prefabs/<biome>_special.sval) but no theme
// places them: temple and crypt have the SpawnPrefabSet commented out, cave_dark
// and barracks ask for "<biome>_puzzles", a set no prefab is in, and the rest
// never mention them. The mission defs, and with them each level's generator,
// are rebuilt on every level load, before any module, so the module ctor
// (every level, ahead of MissionGameMode.Generate) adds one PuzzleRoomSpawn to
// every level generator: at most one room a floor, skipped on no_special floors
// like the shrine and skill rooms, and placed after those so a puzzle room never
// takes the space a mandatory room needs. Its chance is puzzles.room_chance
// percent (default 60), rolled in Execute: the settings live in the town record,
// which Generate loads after the module ctor has run.
//
// A room first tries the vanilla way (a spot whose cells already match its
// pattern: a solid wall block with a corridor end at its door). Most floors have
// no such spot, so then it is forced onto the map's outskirts: the free wall
// block farthest from the middle whose door can reach the level, by a straight
// corridor carved through solid wall, in under MAX_CORRIDOR cells. DungeonBrush
// paints tiles from the cells, so the corridor and the room's frame look like
// the rest of the floor.
//
// The room's door is read off its pattern (the Walkable cells on one edge), not
// off the junction: the junction's y/x is shifted by SVO_Init_Post and the old
// math put the keep's corridor two rows below the doorway, so part of the door
// faced wall and the corridor's lower rows ran into the room's frame (the
// "partially obscured" rooms). A forced room sits on plain Wall only (never
// Nothing or Cliff: the black Nothing blocks spill a cell), keeps a one-cell
// Wall rim, stays PAD cells from the grid edge (the padding blocks cover the
// bottom 24 px) and its doorway and corridor cells are consumed once carved,
// so no later command (dead-end fills, walls, traps, crates, enemy spots)
// rewrites them. Every placed room is recorded (Room) for the summon hold
// (SummonHold.as) and for `hwp puzzles check`, which walks the recorded
// doorway, corridor and interior cells with the scene's point query and logs
// `check done: N room(s), M problem(s)`.
//
// Biomes without puzzle rooms borrow a near one (cave_spider: cave_dark).
// Forest and heaven floors (ForestBrush) are one authored prefab and paint
// nothing from the cells, so they have no wall to carve a room into. They get
// the Constellation in an open clearing instead (set hwp_puzzle_open,
// tweak/missions/hwp_puzzles_open.sval: walkable all over, reserved as floor),
// placed the vanilla way after the last set the floor requires (min > 0: the
// shortcut, the story encounters, well, glades, imp...) and before the edges and
// fillers take the space. Placed earlier it starved those sets of their clearing
// on the small encounter bases (forest_2 failed generation every try, 2026-10-25);
// placed after them it takes a spare clearing or none ("no open clearing" is not
// a failure).
// The keep is an OutdoorGenerator as well, but its DungeonInstanceBrush paints
// from the cells like any dungeon.
//
// The Constellation itself joins the larger rooms' picks in the PrefabPicker
// override (scripts/WorldScript/Prefabs/PrefabPicker.as).
namespace HWP
{
	namespace Puzzles
	{
		const int ROOM_CHANCE = 60;    // percent a floor
		const int PAD = 3;             // cells kept free along the grid edge (the padding blocks)
		const int CELL = 16;           // px
		const string CONSTELLATION_FLAG = "hwp_constellation_placed";
		const string OPEN_SET = "hwp_puzzle_open";   // tweak/missions/hwp_puzzles_open.sval

		// themes (theme_<biome>, theme_generic_<biome>) with a <biome>_puzzle prefab set
		const array<string> ROOM_BIOMES = {
			"barracks", "cave_dark", "cave_light", "cave_light_inhabited", "courts",
			"crypt", "dark_halls", "dungeon", "keep", "prison", "temple"
		};

		string Biome(MissionThemeDef@ theme)
		{
			if (theme is null)
				return "";
			string biome = theme.m_id;
			if (biome.findFirst("theme_") != 0)
				return "";
			biome = biome.substr(6);
			if (biome.findFirst("generic_") == 0)
				biome = biome.substr(8);
			return biome;
		}

		string RoomSet(MissionThemeDef@ theme)
		{
			string biome = Biome(theme);
			if (biome == "cave_spider")
				biome = "cave_dark";
			if (ROOM_BIOMES.find(biome) < 0)
				return "";
			return biome + "_puzzle";
		}

		int RoomChance()
		{
			return clamp(HWP::Settings::GetInt("puzzles.room_chance", ROOM_CHANCE), 0, 100);
		}

		// a def the set may still give out: CanGet (max count, conditionals, run-unique
		// flags), minus the failed PlacePrefabs' m_foundNoPlacement, which only says
		// the vanilla spot search found nothing
		bool Available(MissionPrefabDef@ def)
		{
			// CanGet clears the flag itself on a def's first look in a new generation
			// (MissionPrefabDef.as:71-76); a flag from an earlier level must not come back
			bool current = def.m_currGenNumId == g_genNumId;
			bool none = def.m_foundNoPlacement;
			def.m_foundNoPlacement = false;
			bool ok = def.CanGet();
			if (current)
				def.m_foundNoPlacement = none;
			return ok;
		}

		// a placed room: its cells and the world rect, for the summon hold and `hwp puzzles check`
		class Room
		{
			string m_id;
			MissionPrefabDef@ m_def;
			ivec2 m_pos;             // grid cell of the pattern's top-left
			ivec2 m_size;
			bool m_forced;
			array<ivec2> m_doorCells;      // grid cells of the doorway (pattern edge)
			array<ivec2> m_corridorCells;  // grid cells carved out of the door (forced only)
			vec2 m_offset;           // brush.m_posOffset: world = CELL * cell + offset
			uint m_gen;              // g_genNumId when placed

			// world rect of the whole pattern (walls included)
			vec4 WorldRect()
			{
				return vec4(m_offset.x + m_pos.x * CELL, m_offset.y + m_pos.y * CELL, m_size.x * CELL, m_size.y * CELL);
			}

			bool Contains(vec2 p, float margin = 0.0f)
			{
				vec4 r = WorldRect();
				return p.x >= r.x - margin && p.y >= r.y - margin && p.x <= r.x + r.z + margin && p.y <= r.y + r.w + margin;
			}

			vec2 CellCentre(ivec2 c)
			{
				return vec2(m_offset.x + c.x * CELL + CELL / 2, m_offset.y + c.y * CELL + CELL / 2);
			}
		}

		array<Room@> g_rooms;

		// the rooms of the level being played (a Generate retry leaves older entries behind)
		array<Room@>@ CurrentRooms()
		{
			array<Room@> rooms;
			for (uint i = 0; i < g_rooms.length(); i++)
				if (g_rooms[i].m_gen == g_genNumId)
					rooms.insertLast(g_rooms[i]);
			return rooms;
		}

		Room@ RoomAt(vec2 p, float margin = 0.0f)
		{
			for (uint i = 0; i < g_rooms.length(); i++)
				if (g_rooms[i].m_gen == g_genNumId && g_rooms[i].Contains(p, margin))
					return g_rooms[i];
			return null;
		}

		Room@ Record(DungeonBrush@ brush, MissionPrefabDef@ def, ivec2 pos, bool forced)
		{
			Room room;
			room.m_id = def.m_id;
			@room.m_def = def;
			room.m_pos = pos;
			room.m_size = def.m_gridSz;
			room.m_forced = forced;
			room.m_offset = brush.m_posOffset;
			room.m_gen = g_genNumId;
			HWP::Carve::Door door;
			if (HWP::Carve::GetDoor(def, door))
				for (int w = 0; w < door.m_width; w++)
					room.m_doorCells.insertLast(pos + door.m_from + door.m_along * w);
			g_rooms.insertLast(room);
			return room;
		}

		// the rooms PlacePrefabs just added: the new points of interest of the set. A point of
		// interest sits at the top-left cell plus the def's m_gridOffset
		// (PrefabPlacement.PlacePrefabAt), so that offset comes back off here
		void RecordPlaced(DungeonBrush@ brush, uint firstPoi)
		{
			for (uint i = firstPoi; i < brush.m_pointsOfInterest.length(); i++)
			{
				auto type = brush.m_pointsOfInterest[i].m_type;
				if (type is null)
					continue;
				ivec2 at = brush.m_pointsOfInterest[i].m_pos - type.m_gridOffset;
				auto room = Record(brush, type, at, false);
				vec4 r = room.WorldRect();
				HWP::Log("puzzles", "room " + room.m_id + " at cell " + at.x + "," + at.y + " world " + int(r.x) + "," + int(r.y) + " " + int(r.z) + "x" + int(r.w) + " door " + room.m_doorCells.length() + " cells (matched)");
			}
		}

		// the vanilla way failed: put the room on the outskirts and carve its corridor
		string ForcePlace(DungeonBrush@ brush, PrefabPlacement@ placer, const string &in set)
		{
			CellGrid@ grid = brush;
			uint setHash = HashString(set);
			array<MissionPrefabDef@> defs;
			for (uint i = 0; i < MissionPrefabDef::Instances.length(); i++)
			{
				auto def = MissionPrefabDef::Instances[i];
				if (def.m_set == setHash && def.m_prefab !is null && Available(def))
					defs.insertAt(randi(defs.length() + 1), def);
			}
			if (defs.length() == 0)
				return "no rooms left in " + set;

			auto sums = HWP::Carve::BlockedSums(grid);

			// each def's best spot. UsePrefab may hand back any of the def's variations, whose
			// size or door can differ, and it uses the room up (count, run flags) as it does: a
			// def is only a candidate when every variation has a spot of its own too
			array<HWP::Carve::Spot@> spots;
			for (uint i = 0; i < defs.length(); i++)
			{
				auto best = HWP::Carve::BestSpot(grid, sums, defs[i], PAD);
				if (best is null)
					continue;
				bool all = true;
				for (uint v = 0; v < defs[i].m_variations.length() && all; v++)
					all = HWP::Carve::BestSpot(grid, sums, defs[i].m_variations[v], PAD) !is null;
				if (all)
					spots.insertLast(best);
			}
			if (spots.length() == 0)
				return "no free wall block on the outskirts";

			// best first; a def UsePrefab turns down (used up meanwhile) passes to the next
			MissionPrefabDef@ room = null;
			HWP::Carve::Spot@ spot = null;
			while (room is null && spots.length() > 0)
			{
				uint top = 0;
				for (uint i = 1; i < spots.length(); i++)
					if (spots[i].m_score > spots[top].m_score)
						top = i;
				@spot = spots[top];
				spots.removeAt(top);
				@room = spot.m_def.UsePrefab();
			}
			if (room is null)
				return "every fitting room used up";
			// a variation gets its own spot (the def's could overlap or face a wall); the
			// candidate check above made sure it has one
			if (room !is spot.m_def)
			{
				@spot = HWP::Carve::BestSpot(grid, sums, room, PAD);
				if (spot is null)
					return "variation " + room.m_id + " has no free wall block on the outskirts";
			}
			ivec2 bestPos = spot.m_pos;
			HWP::Carve::Door@ bestDoor = spot.m_door;
			int bestLen = spot.m_len;
			room.UnpackGrid();
			placer.PlacePrefabAt(room, bestPos);

			auto rec = Record(brush, room, bestPos, true);

			// the doorway cells the pattern wants walkable, then the corridor out. Both are
			// consumed: every later command (FillDeadEndPaths, the wall/trap/deco sets, the
			// crates, the enemy spots) works on unconsumed cells only, so nothing fills or
			// furnishes the way in. The corridor's side walls stay unconsumed, so they get
			// their trim like any wall
			for (int y = 0; y < room.m_gridSz.y; y++)
				for (int x = 0; x < room.m_gridSz.x; x++)
					if (Pattern(room.m_gridPattern[y * room.m_gridSz.x + x]) == Pattern::Walkable)
					{
						grid.SetCellIfNotConsumed(bestPos.x + x, bestPos.y + y, Cell::Floor);
						grid.SetConsumed(bestPos.x + x, bestPos.y + y, true);
					}
			ivec2 base = bestPos + bestDoor.m_from;
			for (int k = 1; k < bestLen; k++)
			{
				for (int w = 0; w < bestDoor.m_width; w++)
				{
					ivec2 c = base + bestDoor.m_out * k + bestDoor.m_along * w;
					grid.SetCellIfNotConsumed(c.x, c.y, Cell::Floor);
					grid.SetConsumed(c.x, c.y, true);
					rec.m_corridorCells.insertLast(c);
				}
			}
			vec4 wr = rec.WorldRect();
			ivec2 d0 = bestPos + bestDoor.m_from;
			return "forced " + room.m_id + " at " + bestPos.x + "," + bestPos.y + " of " + grid.m_width + "x" + grid.m_height + ", corridor " + (bestLen - 1)
				+ " (door " + d0.x + "," + d0.y + " width " + bestDoor.m_width + " out " + bestDoor.m_out.x + "," + bestDoor.m_out.y + "; world " + int(wr.x) + "," + int(wr.y) + " " + int(wr.z) + "x" + int(wr.w) + ")";
		}

		// puzzles.debug_grid: the floor's cells in the log, one row a line
		void DumpGrid(CellGrid@ grid)
		{
			for (int y = 0; y < grid.m_height; y++)
			{
				string row = "";
				for (int x = 0; x < grid.m_width; x++)
				{
					Cell c = grid.GetCell(x, y);
					bool used = grid.m_gridConsumed[x][y];
					string ch = "?";
					if (c == Cell::Floor) ch = used ? "o" : ".";
					else if (c == Cell::Wall) ch = used ? "X" : "#";
					else if (c == Cell::Nothing) ch = " ";
					else if (c == Cell::Cliff) ch = "~";
					else if (c == Cell::Breakables) ch = "%";
					row += ch;
				}
				HWP::Log("puzzles", "grid " + formatInt(y, "0", 3) + " " + row);
			}
		}

		// " on keep_2": the mission level being generated, so a log reader (a scenario's
		// capture of the forced line) can tell this floor's line from an earlier floor's
		string OnLevel()
		{
			auto gm = cast<MissionGameModeBase>(g_gameMode);
			if (gm is null || gm.m_missionLevel is null)
				return "";
			return " on " + gm.m_missionLevel.m_id;
		}

		// SpawnPrefabSet with the chance read when the level is generated
		class PuzzleRoomSpawn : SpawnPrefabSet
		{
			bool Execute(DungeonBrush@ brush, PrefabPlacement@ pfbPlacer) override
			{
				if (HWP::Settings::GetBool("puzzles.debug_grid"))
					DumpGrid(brush);
				int chance = RoomChance();
				if (randi(100) >= chance)
				{
					HWP::Log("puzzles", m_set + " not rolled (" + chance + "%)");
					return true;
				}
				// an outdoor floor: any open clearing, nothing to carve
				uint pois = brush.m_pointsOfInterest.length();
				if (m_set == OPEN_SET)
				{
					int placed = pfbPlacer.PlacePrefabs(HashString(m_set), 1, m_numBoost, m_typeMinLimit);
					HWP::Log("puzzles", m_set + " rolled (" + chance + "%): " + (placed > 0 ? "placed in a clearing" : "no open clearing") + OnLevel());
					RecordPlaced(brush, pois);
					return true;
				}
				// puzzles.debug_force: skip the vanilla way, so a test lands on the forced one
				int n = 0;
				if (!HWP::Settings::GetBool("puzzles.debug_force"))
					n = pfbPlacer.PlacePrefabs(HashString(m_set), 1, m_numBoost, m_typeMinLimit);
				if (n > 0)
				{
					HWP::Log("puzzles", m_set + " rolled (" + chance + "%): placed in a matching spot" + OnLevel());
					RecordPlaced(brush, pois);
					return true;
				}
				HWP::Log("puzzles", m_set + " rolled (" + chance + "%): " + ForcePlace(brush, pfbPlacer, m_set) + OnLevel());
				return true;
			}
		}

		// ---- hwp puzzles check -----------------------------------------------------------

		// a cell is open when the scene's point query at its centre hits nothing solid (the
		// terrain probe's test); walls, black blocks and doodads with a body all count
		bool CellOpen(Room@ room, ivec2 c)
		{
			vec2 p = room.CellCentre(c);
			auto hits = g_scene.QueryRect(p, 1, 1, ~0, RaycastType::Any);
			for (uint i = 0; i < hits.length(); i++)
			{
				auto u = hits[i];
				if (!u.IsValid() || u.IsDestroyed())
					continue;
				if (cast<Actor>(u.GetScriptBehavior()) !is null)
					continue; // a player, a pet or an enemy standing there is not the level
				return false;
			}
			return true;
		}

		// the room's interior: the cells its pattern reserves (command Reserve)
		array<ivec2>@ InteriorCells(Room@ room)
		{
			array<ivec2> cells;
			auto def = room.m_def;
			if (def is null)
				return cells;
			def.UnpackGrid();
			if (def.m_gridCommand is null)
				return cells;
			for (int y = 0; y < room.m_size.y; y++)
				for (int x = 0; x < room.m_size.x; x++)
					if (PatternCommand(def.m_gridCommand[y * room.m_size.x + x]) == PatternCommand::Reserve)
						cells.insertLast(room.m_pos + ivec2(x, y));
			return cells;
		}

		int CountOpen(Room@ room, array<ivec2>@ cells)
		{
			int n = 0;
			for (uint i = 0; i < cells.length(); i++)
				if (CellOpen(room, cells[i]))
					n++;
			return n;
		}

		bool IsPuzzleUnit(UnitPtr unit)
		{
			if (!unit.IsValid())
				return false;
			auto prod = unit.GetUnitProducer();
			if (prod is null)
				return false;
			string path = prod.GetResourceName();
			if (path.findFirst("doodads/buttons/") == 0)
				return true;
			return path.findFirst("puzzle") >= 0;
		}

		// puzzle units (the buttons, levers, braziers, constellation dots) inside the room
		int PuzzleUnitsIn(Room@ room)
		{
			vec4 r = room.WorldRect();
			vec2 centre = vec2(r.x + r.z / 2, r.y + r.w / 2);
			int radius = int(max(r.z, r.w));
			auto units = g_scene.FetchAllUnits(~0, centre, radius);
			int n = 0;
			for (uint i = 0; i < units.length(); i++)
			{
				UnitPtr u = units[i];
				if (!u.IsValid() || u.IsDestroyed() || !room.Contains(xy(u.GetPosition())))
					continue;
				if (IsPuzzleUnit(u))
					n++;
			}
			return n;
		}

		// `hwp puzzles check`: every recorded room of this level, in the log and the chat:
		// doorway, corridor and interior cells open (the point query), puzzle units present
		// (the prefab's doodads spawned, so nothing drew over it). Ends with
		// "check done: N room(s), M problem(s)".
		void CmdPuzzles(array<string>@ args)
		{
			string a = args.length() > 0 ? args[0] : "";
			if (a != "check" && a != "rooms")
			{
				HWP::Commands::Reply("hwp puzzles check | rooms");
				return;
			}
			auto rooms = CurrentRooms();
			int problems = 0;
			for (uint i = 0; i < rooms.length(); i++)
			{
				auto room = rooms[i];
				vec4 r = room.WorldRect();
				string line = "room " + room.m_id + (room.m_forced ? " (forced)" : " (matched)") + " world " + int(r.x) + "," + int(r.y) + " " + int(r.z) + "x" + int(r.w);
				if (a == "rooms")
				{
					HWP::Commands::Reply(line);
					HWP::Log("puzzles", line);
					continue;
				}
				int doorOpen = CountOpen(room, room.m_doorCells);
				int corrOpen = CountOpen(room, room.m_corridorCells);
				auto interior = InteriorCells(room);
				int inOpen = CountOpen(room, interior);
				int units = PuzzleUnitsIn(room);
				int bad = 0;
				if (doorOpen < int(room.m_doorCells.length())) bad++;
				if (corrOpen < int(room.m_corridorCells.length())) bad++;
				// the interior holds the puzzle's own doodads (pillars, braziers with bodies), so
				// not every reserved cell is open; three quarters is the floor a walkable room shows
				if (interior.length() > 0 && inOpen * 4 < int(interior.length()) * 3) bad++;
				if (units == 0) bad++;
				problems += bad;
				line += ": door " + doorOpen + "/" + room.m_doorCells.length() + " open, corridor " + corrOpen + "/" + room.m_corridorCells.length()
					+ " open, interior " + inOpen + "/" + interior.length() + " open, " + units + " puzzle unit(s)" + (bad > 0 ? " PROBLEM" : " ok");
				HWP::Commands::Reply(line);
				HWP::Log("puzzles", line);
			}
			string done = "check done: " + rooms.length() + " room(s), " + problems + " problem(s)";
			HWP::Commands::Reply(done);
			HWP::Log("puzzles", done);
		}

		SValue@ RoomCommandData(const string &in set)
		{
			SValueBuilder sb;
			sb.PushDictionary();
			sb.PushString("class", "SpawnPrefabSet");
			sb.PushString("theme", set);
			sb.PushInteger("max", 1);
			sb.PushArray("conditionals");
			sb.PushArray();
			sb.PushString("flag");
			sb.PushString("isnt");
			sb.PushString("no_special");
			sb.PopArray();
			sb.PopArray();
			sb.PopDictionary();
			return sb.Build();
		}

		bool EndsWith(const string &in s, const string &in suffix)
		{
			return s.length() >= suffix.length() && s.substr(s.length() - suffix.length()) == suffix;
		}

		// returns how many generators got the command
		int AddPuzzleRooms()
		{
			int added = 0;
			for (uint i = 0; i < MissionDef::Instances.length(); i++)
			{
				auto mission = MissionDef::Instances[i];
				for (uint j = 0; j < mission.m_levels.length(); j++)
				{
					auto level = mission.m_levels[j];
					auto gen = cast<DungeonGenerator>(level.m_generator);
					if (gen is null)
						continue;
					// ForestBrush paints nothing from the cells; the keep is an
					// OutdoorGenerator too, but its DungeonInstanceBrush does
					bool outdoor = cast<ForestBrush>(gen.m_brush) !is null;
					string set = outdoor ? OPEN_SET : RoomSet(level.m_themeDef);
					if (set == "")
						continue;

					int at = -1;
					bool present = false;
					for (uint k = 0; k < gen.m_genCommands.length(); k++)
					{
						if (cast<PuzzleRoomSpawn>(gen.m_genCommands[k]) !is null)
							present = true;
						auto spawn = cast<SpawnPrefabSet>(gen.m_genCommands[k]);
						if (spawn is null)
							continue;
						if (!outdoor && (EndsWith(spawn.m_set, "_shrine") || EndsWith(spawn.m_set, "_skill")))
							at = k + 1;
						// outdoors: after the last set the floor must place (min > 0), so the
						// vanilla encounters, well and glades take their clearings first; the
						// edges and fillers (no min) come after. A floor without required
						// sets: after the first special set (heaven_special_arenas_1).
						if (outdoor && (spawn.m_min > 0 || (at < 0 && spawn.m_set.findFirst("_special") >= 0)))
							at = k + 1;
					}
					if (present)
						continue;

					PuzzleRoomSpawn cmd;
					array<SValue@> params = { RoomCommandData(set) };
					cmd.LoadParams(params);
					if (at < 0 || uint(at) >= gen.m_genCommands.length())
						gen.m_genCommands.insertLast(cmd);
					else
						gen.m_genCommands.insertAt(at, cmd);
					added++;
				}
			}
			return added;
		}
	}
}

namespace Modules
{
	class HWPPuzzlesModule : Module, HWP::ModuleStart
	{
		HWPPuzzlesModule()
		{
			super("hwp-puzzles");
			HWP::Puzzles::g_rooms.removeRange(0, HWP::Puzzles::g_rooms.length());
			int n = HWP::Puzzles::AddPuzzleRooms();
			if (n > 0)
				HWP::Log("puzzles", "puzzle rooms added to " + n + " mission level generator(s)");
			HWP::Commands::Register("puzzles", " puzzles check (every puzzle room of this floor: doorway, corridor and interior open, its units present) | rooms", HWP::Commands::Handler(HWP::Puzzles::CmdPuzzles));
			HWP::Commands::OnSettingChanged(HWP::Commands::SettingListener(HWP::Puzzles::SummonHold::OnSettingChanged));
		}

		void Start(StartMode sMode)
		{
			HWP::Settings::Sync("puzzles.");
			HWP::Puzzles::SummonHold::Start();
		}

		void UpdateFrame(int ms, GameInput& gameInput, MenuInput& menuInput, bool paused) override
		{
			if (paused)
				return;
			HWP::Puzzles::SummonHold::Update(ms);
		}
	}
}
