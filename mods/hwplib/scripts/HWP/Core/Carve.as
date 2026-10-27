// HWP::Carve - placing a prefab room into the solid wall of a generated dungeon floor, with a
// straight corridor out of its doorway to the nearest floor. The puzzles module forces its rooms
// this way when the vanilla matcher finds no spot, and the objectives module places its vaults
// (the part that was measured to come out walkable, docs/RE_NOTES.md). Cells are CellGrid cells
// (16 px); a spot is the room's top-left cell.
namespace HWP
{
	namespace Carve
	{
		const int MAX_CORRIDOR = 40;   // cells

		bool Walkable(CellGrid@ grid, int x, int y)
		{
			if (x < 0 || y < 0 || x >= grid.m_width || y >= grid.m_height)
				return false;
			Cell c = grid.GetCell(x, y);
			return c == Cell::Floor || c == Cell::Breakables || c == Cell::Bridge;
		}

		// a cell the room, its rim or its corridor may take: in the grid, not consumed, plain
		// wall. Nothing is painted as black blocks that spill a cell past their own, and a
		// cliff keeps its cliff tiles: a room on either came out partly covered.
		bool Free(CellGrid@ grid, int x, int y)
		{
			if (x < 0 || y < 0 || x >= grid.m_width || y >= grid.m_height)
				return false;
			if (grid.IsConsumed(x, y))
				return false;
			return grid.GetCell(x, y) == Cell::Wall;
		}

		// the room's door: the walkable cells on one edge of its pattern, and the way out
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
			Door m_door;
			int m_len;
			float m_score;
		}

		// the run of Walkable cells on one edge of the pattern: the doorway the room's
		// tiles leave open (the keep's 19x20 rooms: column 18, rows 7-12). The junction is
		// only a hint for the vanilla matcher and its centre is shifted (MissionPrefabDef
		// SVO_Init_Post), so it is not used here.
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

		// the first edge with a doorway: east, west, south, north; southFirst tries the south
		// edge before the others (a room whose door unit is on its south edge, the vault)
		bool GetDoor(MissionPrefabDef@ def, Door@ door, bool southFirst = false)
		{
			if (def.m_gridPattern is null)
				return false;
			ivec2 sz = def.m_gridSz;
			if (southFirst && EdgeRun(def, ivec2(0, sz.y - 1), ivec2(1, 0), ivec2(0, 1), door))
				return true;
			if (EdgeRun(def, ivec2(sz.x - 1, 0), ivec2(0, 1), ivec2(1, 0), door))
				return true;
			if (EdgeRun(def, ivec2(0, 0), ivec2(0, 1), ivec2(-1, 0), door))
				return true;
			if (!southFirst && EdgeRun(def, ivec2(0, sz.y - 1), ivec2(1, 0), ivec2(0, 1), door))
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

		// summed-area table of the cells a room may not take (not Free)
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

		// a def's best spot on the grid: the farthest from the middle, a short corridor
		// breaking ties; the room plus a one-cell wall rim, pad cells off every grid edge.
		// Null if none fits.
		Spot@ BestSpot(CellGrid@ grid, array<array<int>>@ sums, MissionPrefabDef@ def, int pad, bool southFirst = false)
		{
			def.UnpackGrid();
			Door door;
			if (def.m_gridPattern is null || !GetDoor(def, door, southFirst))
				return null;
			float cx = grid.m_width / 2.0f;
			float cy = grid.m_height / 2.0f;
			Spot@ best = null;
			ivec2 sz = def.m_gridSz;
			for (int y = pad; y + sz.y <= grid.m_height - pad; y++)
			{
				for (int x = pad; x + sz.x <= grid.m_width - pad; x++)
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
						best.m_door = door;
						best.m_len = len;
						best.m_score = score;
					}
				}
			}
			return best;
		}
	}
}
