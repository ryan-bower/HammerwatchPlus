"""mods/objectives: where the floor levers go (issue #74).

Two kinds of check, both offline:

- The data agree with each other: each lever side's prefab def (tweak/hwp/objectives_prefabs.sval)
  is a 3x3 floor patch plus a 3-cell wall run on the right edge, its .pfb puts the right unit
  where Generation.as LeverInPfb says, on the wall run's edge facing the patch, and each unit
  file defines its wall and kind for objective_lever_wall.inc.
- A Python model of Generation.as PickLever / LeverFits / ComputeReach on synthetic grids: walls
  on the north, east and west of the floor are all used, south walls never, the pick is spread
  over the far half and not the single farthest corner, cut-off floor is skipped, and a floor
  with no wall run falls back to the floor patch. This tests the model, kept line for line with
  the AngelScript; the game itself was not run.
"""
import random
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
MOD = REPO / "mods" / "objectives"
GEN = MOD / "scripts" / "HWP" / "Objectives" / "Generation.as"
SVAL = MOD / "tweak" / "hwp" / "objectives_prefabs.sval"
GAMECODE = REPO / "gamecode" / "sdk" / "hoh2"

SIDES = {"": "floor", "_n": "north", "_e": "east", "_w": "west"}
KINDS = {"hwp_objectives_switch": ("vault_switch", "objective_switch"),
         "hwp_objectives_exit": ("exit_switch", "objective_exit_switch")}
WALK, WALL = 0x07, 0x05            # Pattern::Walkable, Pattern::Wall
PLACE_FLOOR, PLACE_WALL = 0x06, 0x05  # PatternCommand::PlaceFloor, PlaceWall


def prefab_defs():
    defs = {}
    for block in re.findall(r"<dict>(.*?)</dict>", SVAL.read_text(encoding="utf-8"), re.S):
        get = lambda name: re.search(rf'name="{name}">([^<]*)<', block).group(1)  # noqa: E731
        w, h = map(int, get("grid-size").split())
        defs[get("theme")] = {"id": get("id"), "size": (w, h), "grid_pos": get("grid-pos"),
                              "pattern": bytes.fromhex(get("grid-pattern")),
                              "command": bytes.fromhex(get("grid-command"))}
    return defs


def lever_in_pfb():
    """Generation.as LeverInPfb, by side suffix."""
    src = GEN.read_text(encoding="utf-8")
    body = re.search(r"vec2 LeverInPfb\(int side\)\s*\{(.*?)\n\t\t\t\}", src, re.S).group(1)
    out = {}
    for side, x, y in re.findall(r"side == SIDE_(\w)\) return vec2\((\d+), (\d+)\)", body):
        out["_" + side.lower()] = (int(x), int(y))
    sx, sy = re.search(r"SWITCH_IN_PFB = vec2\((\d+), (\d+)\)", src).groups()
    out[""] = (int(sx), int(sy))
    return out


def cells(d, value, field="pattern"):
    w, h = d["size"]
    return {(i % w, i // w) for i, b in enumerate(d[field]) if b == value}


@pytest.mark.parametrize("set_name", list(KINDS))
@pytest.mark.parametrize("suffix", list(SIDES))
def test_side_defs_prefabs_and_units_agree(set_name, suffix):
    defs = prefab_defs()
    d = defs[set_name + suffix]
    pfb_stem, unit_stem = KINDS[set_name]
    assert d["id"] == f"prefabs/hwp/objectives/{pfb_stem}{suffix}.pfb"
    assert d["grid_pos"] == "0 0"
    w, h = d["size"]
    assert len(d["pattern"]) == len(d["command"]) == w * h
    floor, wall = cells(d, WALK), cells(d, WALL)
    assert floor | wall == {(x, y) for x in range(w) for y in range(h)}
    # the floor is PlaceFloor and the wall PlaceWall: the brush paints both as the floor's own
    assert cells(d, PLACE_FLOOR, "command") == floor and cells(d, PLACE_WALL, "command") == wall
    # a 3x3 patch, and the wall run on the side's edge
    xs, ys = {x for x, _ in floor}, {y for _, y in floor}
    assert len(floor) == 9 and len(xs) == len(ys) == 3
    run = {"": set(), "_n": {(0, 0), (1, 0), (2, 0)}, "_e": {(3, 0), (3, 1), (3, 2)},
           "_w": {(0, 0), (0, 1), (0, 2)}}[suffix]
    assert wall == run

    # the .pfb: one unit, the kind's unit for the side, where LeverInPfb says
    pfb = (MOD / d["id"]).read_text(encoding="utf-8")
    units = re.findall(r'<array name="([^"]+)">\s*<vec2>(\d+) (\d+)</vec2>\s*<int>\d+</int>', pfb)
    assert len(units) == 1
    unit, x, y = units[0]
    assert unit == f"doodads/hwp/{unit_stem}{suffix}.unit"
    pos = (int(x), int(y))
    assert pos == lever_in_pfb()[suffix]
    # on the wall run's edge facing the patch, at the middle of the run (north) or at the top of
    # its middle cell (east, west); the floor lever in the patch's centre
    expected = {"": (24, 24), "_n": (24, 16), "_e": (48, 16), "_w": (16, 16)}[suffix]
    assert pos == expected

    text = (MOD / unit).read_text(encoding="utf-8")
    if suffix:
        assert f"%define WALL_{suffix[1].upper()}" in text
        assert ("%define EXIT" in text) == (set_name == "hwp_objectives_exit")
        assert '%include "doodads/hwp/objective_lever_wall.inc"' in text
    else:
        assert f'<string name="kind">{"exit" if "exit" in set_name else "vault"}</string>' in text


def test_wall_include_has_every_side_and_scene():
    inc = (MOD / "doodads" / "hwp" / "objective_lever_wall.inc").read_text(encoding="utf-8")
    assert inc.count("%if") == inc.count("%endif")
    for side in "NEW":
        # the shared art, the unused pose and the pull, per wall
        assert inc.count(f"%if WALL_{side}") == 3
    for scene in ("shared", "left", "marked", "right"):
        assert f'<scene name="{scene}"' in inc
    assert 'special/minimap.unit:info_poi' in inc
    assert "WALL_S" not in inc


@pytest.mark.needs_gamecode
def test_wall_art_frames_are_vanillas_pull_lever():
    """The wall levers draw the vanilla wall pull levers' frames (doodads/buttons/button_wall_pull_*)."""
    inc = (MOD / "doodads" / "hwp" / "objective_lever_wall.inc").read_text(encoding="utf-8")
    for side in "new":
        vanilla = (GAMECODE / "doodads" / "buttons" / f"button_wall_pull_{side}.unit").read_text(encoding="utf-8")
        blocks = re.findall(rf"%if WALL_{side.upper()}\n(.*?)%endif", inc, re.S)
        assert len(blocks) == 3
        for block in blocks:
            for frame in re.findall(r"<frame[^>]*>([\d -]+)</frame>", block):
                assert frame in vanilla, (side, frame)


# ---- a model of Generation.as PickLever ------------------------------------------------------

FLOOR, WALLC, RESERVED, CLIFF = ".", "#", "R", "~"


class Grid:
    def __init__(self, rows):
        self.h = len(rows)
        self.w = len(rows[0])
        self.cell = [list(r) for r in rows]
        self.consumed = [[False] * self.w for _ in range(self.h)]

    def get(self, x, y):
        if 0 <= x < self.w and 0 <= y < self.h:
            return self.cell[y][x]
        return None

    def is_consumed(self, x, y):  # CellGrid.IsConsumed: the outer ring counts as consumed
        if x < 1 or y < 1 or x >= self.w - 1 or y >= self.h - 1:
            return True
        return self.consumed[y][x]

    def walkable(self, x, y):
        return self.get(x, y) == FLOOR

    def free(self, x, y):  # HWP::Carve::Free
        return 0 <= x < self.w and 0 <= y < self.h and not self.is_consumed(x, y) and self.get(x, y) == WALLC


def side_patterns():
    defs = prefab_defs()
    return {s: defs["hwp_objectives_switch" + suffix] for suffix, s in SIDES.items()}


def compute_reach(g):
    passable = lambda x, y: g.walkable(x, y) or g.get(x, y) == RESERVED  # noqa: E731
    comp = [[-1] * g.w for _ in range(g.h)]
    best, best_count, label = -1, 0, 0
    for y in range(g.h):
        for x in range(g.w):
            if comp[y][x] >= 0 or not passable(x, y):
                continue
            comp[y][x] = label
            queue, count, head = [(x, y)], 0, 0
            while head < len(queue):
                cx, cy = queue[head]
                head += 1
                count += g.walkable(cx, cy)
                for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
                    if 0 <= nx < g.w and 0 <= ny < g.h and comp[ny][nx] < 0 and passable(nx, ny):
                        comp[ny][nx] = label
                        queue.append((nx, ny))
            if count > best_count:
                best, best_count = label, count
            label += 1
    return {(x, y) for y in range(g.h) for x in range(g.w) if best >= 0 and comp[y][x] == best}


def lever_fits(g, reach, d, side, x, y, clear_below=True):
    w, h = d["size"]
    if x < 1 or y < 1 or x + w >= g.w or y + h >= g.h:
        return False
    for j in range(h):
        for i in range(w):
            p = d["pattern"][j * w + i]
            cx, cy = x + i, y + j
            if p == WALK and (not g.walkable(cx, cy) or g.is_consumed(cx, cy) or (cx, cy) not in reach):
                return False
            if p == WALL and not g.free(cx, cy):
                return False
    if side == "floor" and clear_below:
        return all(g.walkable(x + i, y + h) for i in range(w))
    return True


def pick_lever(g, reach, from_cell, rng, levers=(), far_share=0.5, spacing=12.0):
    defs, offsets = side_patterns(), lever_in_pfb()
    by_name = {v: k for k, v in SIDES.items()}
    spots = []
    for wanted, clear_below in ((("north", "east", "west"), True), (("floor",), True), (("floor",), False)):
        for side in wanted:
            d = defs[side]
            lx, ly = (v / 16 for v in offsets[by_name[side]])
            for y in range(1, g.h - d["size"][1]):
                for x in range(1, g.w - d["size"][0]):
                    if lever_fits(g, reach, d, side, x, y, clear_below):
                        lever = (x + lx, y + ly)
                        spots.append((side, (x, y), lever, ((lever[0] - from_cell[0]) ** 2 + (lever[1] - from_cell[1]) ** 2) ** 0.5))
        if spots:
            break
    if not spots:
        return None
    farthest = max(s[3] for s in spots)
    far = [s for s in spots if s[3] >= far_share * farthest]
    spaced = [s for s in far if all(((s[2][0] - a) ** 2 + (s[2][1] - b) ** 2) ** 0.5 >= spacing for a, b in levers)]
    pool = spaced or far
    present = []
    for s in pool:
        if s[0] not in present:
            present.append(s[0])
    side = present[rng.randrange(len(present))]
    on_side = [s for s in pool if s[0] == side]
    return on_side[rng.randrange(len(on_side))]


def room(w, h, extra=()):
    """A walled w x h floor: wall ring two cells thick, floor inside."""
    rows = [[WALLC] * w for _ in range(h)]
    for y in range(2, h - 2):
        for x in range(2, w - 2):
            rows[y][x] = FLOOR
    for x, y, c in extra:
        rows[y][x] = c
    return Grid(["".join(r) for r in rows])


def test_model_uses_north_east_and_west_walls_never_south():
    g = room(40, 30)
    reach = compute_reach(g)
    rng = random.Random(74)
    seen_sides, seen_spots = set(), set()
    for _ in range(300):
        side, pos, lever, _ = pick_lever(g, reach, (20, 2), rng)
        seen_sides.add(side)
        seen_spots.add(pos)
        if side == "north":
            assert pos[1] == 1  # the run on the top wall row, the patch below it
        elif side == "east":
            assert pos[0] + 3 == 38
        elif side == "west":
            assert pos[0] == 1
    assert seen_sides == {"north", "east", "west"}
    # spread, not one corner
    assert len(seen_spots) > 20


def test_model_south_wall_spots_do_not_exist():
    """No side puts its run south of the patch: a south wall shows only its top over the floor."""
    for d in side_patterns().values():
        w, h = d["size"]
        wall = cells(d, WALL)
        floor = cells(d, WALK)
        assert not any((x, y - 1) in floor for x, y in wall)


def test_model_pick_is_spread_not_the_farthest_corner():
    """The old FarSwitchSpot took the single farthest 3x3 block: with the vault on the top edge,
    a bottom corner every time (the issue). The new pick is spread over the far half, on the
    walls of the floor's inner blocks too."""
    pillars = [(x, y, WALLC) for x0 in (10, 18, 26) for x in range(x0, x0 + 4) for y in range(16, 20)]
    g = room(40, 30, pillars)
    reach = compute_reach(g)
    rng = random.Random(1)
    picks = [pick_lever(g, reach, (20, 2), rng) for _ in range(300)]
    levers = {p[2] for p in picks}
    assert any(y < 15 for _, y in levers)  # not only the bottom half
    assert any(14 < x < 26 for x, _ in levers)  # not only the corners
    # the pillars' south faces carry north-wall levers (the patch below the pillar)
    assert any(p[0] == "north" and p[1][1] == 19 for p in picks)
    # never the old answer only: many distinct spots
    assert len(levers) > 30


def test_model_skips_floor_cut_off_by_a_pit():
    # a big room, and a small walled-off pocket on the far side of a cliff
    rows = room(40, 30)
    for y in range(2, 28):
        rows.cell[y][30] = CLIFF
    reach = compute_reach(rows)
    assert (35, 15) not in reach and (10, 15) in reach
    rng = random.Random(3)
    for _ in range(100):
        _, pos, lever, _ = pick_lever(rows, reach, (2, 15), rng)
        assert lever[0] < 30


def test_model_reserved_prefab_cells_connect_floor():
    g = room(40, 30)
    for y in range(2, 28):
        g.cell[y][20] = WALLC
    g.cell[15][20] = RESERVED  # a vanilla prefab room's cells join the halves
    reach = compute_reach(g)
    assert (10, 10) in reach and (30, 10) in reach


def test_model_keeps_away_from_the_other_lever_and_falls_back_to_the_floor():
    g = room(40, 30)
    reach = compute_reach(g)
    rng = random.Random(9)
    first = pick_lever(g, reach, (20, 2), rng)
    for _ in range(50):
        second = pick_lever(g, reach, (20, 2), rng, levers=[first[2]])
        assert ((second[2][0] - first[2][0]) ** 2 + (second[2][1] - first[2][1]) ** 2) ** 0.5 >= 12

    # every wall consumed (a prefab's): no wall run fits, the old floor patch does
    for y in range(g.h):
        for x in range(g.w):
            if g.get(x, y) == WALLC:
                g.consumed[y][x] = True
    side, pos, _, _ = pick_lever(g, reach, (20, 2), rng)
    assert side == "floor"
    # clear of the bottom wall: the row below the patch is floor
    assert all(g.walkable(pos[0] + i, pos[1] + 3) for i in range(3))


def test_model_floor_lever_with_a_wall_below_when_nothing_else_fits():
    # a 3-row corridor: every floor patch has the bottom wall under it, and no wall is free.
    # The lever still goes on the floor (the exit must not stay open for want of a spot).
    g = room(40, 7)
    for y in range(g.h):
        for x in range(g.w):
            if g.get(x, y) == WALLC:
                g.consumed[y][x] = True
    reach = compute_reach(g)
    picked = pick_lever(g, reach, (2, 2), random.Random(1))
    assert picked is not None and picked[0] == "floor"
