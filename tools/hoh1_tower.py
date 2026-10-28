"""
hoh1_tower.py - HoH1's tower as a HoH2 mission, generated floors included (used by
`import_hoh1.py campaign`).

HoH1 generates its act floors with AngelScript (scripts/Generators/, called from
scripts/GameModes/GenerateDungeon.as) on the same engine API HoH2 still has
(Resources::GetPrefab/GetUnitProducer/GetTileset, Scene.PaintTileset, Prefab /
UnitProducer placement, a queue of prefabs fabricated when the level starts). So the
floors are made by HoH1's own code: this module copies those scripts out of the
player's install into the local mods/campaign/scripts/HWP/Campaign/HoH1Gen/, wrapped
in `namespace HoH1Gen` (HoH2 has its own DungeonGenerator, DungeonBrush, Cell...)
with every resource path moved under hoh1/, and writes the glue class the committed
HWPHoH1Generator (mods/campaign/scripts/HWP/Campaign/HoH1/Generator.as) runs.
Nothing HoH1 ships is committed: the output is gitignored and module-local.

The mission follows HoH1's tweak/dungeons/base.sval floor by floor (23 floors).
"""
from __future__ import annotations

import re

PREFIX = "hoh1/"

# HoH1 scripts the tower's acts need (the desert, pyramid and moon temple generators
# belong to the Temple of the Sun DLC and are left out)
GEN_SCRIPTS = [
    "scripts/Generators/DungeonBrush.as",
    "scripts/Generators/DungeonGenerator.as",
    "scripts/Generators/EnemyPlacement.as",
    "scripts/Generators/PatternMatcher.as",
    "scripts/Generators/PrefabPlacement.as",
    "scripts/Generators/GraniteMineBrush.as",
    "scripts/Generators/MinesGenerator.as",
    "scripts/Generators/PrisonBrush.as",
    "scripts/Generators/PrisonGenerator.as",
    "scripts/Generators/ArmoryBrush.as",
    "scripts/Generators/ArmoryGenerator.as",
    "scripts/Generators/ArchivesBrush.as",
    "scripts/Generators/ArchivesGenerator.as",
    "scripts/Generators/ChambersBrush.as",
    "scripts/Generators/ChambersGenerator.as",
]
GEN_DUNGEON = "scripts/GameModes/GenerateDungeon.as"
DLC_BRUSHES = ("SandCaves", "Desert", "PyramidSlum", "PyramidFancy")
# the brushes' LoadPrefabs / LoadBaseBrushTiles themes: the generator builds paths
# from them at run time, so their folders are copied whole
GEN_THEMES = ("mine_granite", "prison", "armory", "archives", "chambers")
GEN_DIRS = tuple(f"prefabs/{t}/" for t in GEN_THEMES) + tuple(f"doodads/walls/{t}/" for t in GEN_THEMES)
# DungeonBrush.DoLighting: "effects/lighting/" + theme + "_" + level, its .env and .unit
GEN_LIGHTING = tuple(f"effects/lighting/{t}_" for t in GEN_THEMES)
RES_ROOTS = ("prefabs", "doodads", "actors", "tilesets", "effects", "items", "system", "levels", "players", "gui", "loot")
LITERAL_RE = re.compile(r'"((?:%s)/[^"\n]*)"' % "|".join(RES_ROOTS))
PATH_LIT_RE = re.compile(r'"((?:%s)/)' % "|".join(RES_ROOTS))

DUNGEON_DEF = "tweak/dungeons/base.sval"
DUNGEON_ROW_RE = re.compile(
    r"<array><string>([^<]+)</string><int>(\d+)</int><int>(\d+)</int>"
    r"(?:<string>(\w+)</string>)?(?:<int>(\d+)</int><int>(\d+)</int>)?</array>")
ACT_KEYS = ["mines", "prison", "armory", "archives", "chambers", "battlements", "top"]
# boss / hand-made floors: id and floor-name key
NAMED_FLOORS = {
    "levels/boss_mines.lvl": ("mines_boss", ".hwp.campaign.h1.golem"),
    "levels/boss_prison.lvl": ("prison_boss", ".hwp.campaign.h1.warden"),
    "levels/boss_armory.lvl": ("armory_boss", ".hwp.campaign.h1.councilors"),
    "levels/boss_archives.lvl": ("archives_boss", ".hwp.campaign.h1.watcher"),
    "levels/boss_chambers.lvl": ("chambers_boss", ".hwp.campaign.h1.vampire"),
    "levels/battlements_1.lvl": ("battlements_1", ".hwp.campaign.h1.battlements_1"),
    "levels/battlements_2.lvl": ("battlements_2", ".hwp.campaign.h1.battlements_2"),
    "levels/bridge.lvl": ("bridge", ".hwp.campaign.h1.bridge"),
    "levels/boss_dragon.lvl": ("battlements_boss", ".hwp.campaign.h1.dragon"),
}
DIFF_FIRST, DIFF_LAST, NGP_ADD = 5, 22, 8


def tower_floors(base_sval: str) -> list[dict]:
    """HoH1's floor list: level file, act, level in the act, theme, width, height."""
    floors = []
    for m in DUNGEON_ROW_RE.finditer(re.sub(r"%//[^\n]*", "", base_sval)):
        lvl, act, level, theme, w, h = m.groups()
        floors.append({"level": lvl, "act": int(act), "act_level": int(level), "theme": theme or "",
                       "width": int(w or 0), "height": int(h or 0)})
    return floors


def generated(floor: dict) -> bool:
    return floor["level"] == "levels/generated.lvl"


def mission_floors_xml(floors: list[dict]) -> str:
    """The <array name="levels"> body: generated floors run HWPHoH1Generator with
    HoH1's act/level/theme/size, the others load the converted HoH1 level."""
    out = []
    n = len(floors)
    for i, f in enumerate(floors):
        diff = DIFF_FIRST + round(i * (DIFF_LAST - DIFF_FIRST) / max(1, n - 1))
        act = f["act"]
        lines = ["\t\t<dict>"]
        if generated(f):
            fid = "%s_%d" % (f["theme"], f["act_level"] + 1)
            lines += [f'\t\t\t<string name="id">{fid}</string>',
                      '\t\t\t<string name="gen-class">HWPHoH1Generator</string>',
                      f'\t\t\t<string name="hoh1-theme">{f["theme"]}</string>',
                      f'\t\t\t<int name="hoh1-act">{act}</int>',
                      f'\t\t\t<int name="hoh1-level">{f["act_level"]}</int>',
                      f'\t\t\t<int name="hoh1-level-count">{i}</int>',
                      f'\t\t\t<int name="width">{f["width"]}</int>',
                      f'\t\t\t<int name="height">{f["height"]}</int>']
            name = ".hwp.campaign.h1.floor_%d" % (f["act_level"] + 1)
        else:
            fid, name = NAMED_FLOORS[f["level"]]
            lines += [f'\t\t\t<string name="id">{fid}</string>',
                      f'\t\t\t<string name="level">{PREFIX}{f["level"]}</string>']
        lines += [f'\t\t\t<int name="diff-level">{diff}</int>',
                  f'\t\t\t<int name="diff-level-ngp">{diff + NGP_ADD}</int>',
                  "",
                  # HoH1's GenerateDungeon set these as level flags; act prefabs check them
                  # (the Mines entrance: CheckFlag lvl_0 for the cart you arrive in)
                  '\t\t\t<array name="flags">',
                  f'\t\t\t\t<string>act_{act}</string>',
                  f'\t\t\t\t<string>lvl_{f["act_level"]}</string>',
                  f'\t\t\t\t<string>lvlcount_{i}</string>']
        if f["theme"] == "mines" and f["act_level"] == 0:
            lines.append("\t\t\t\t<string>no_flowers</string>")
        lines += ["\t\t\t</array>",
                  "",
                  f'\t\t\t<string name="act-name">.hwp.campaign.act.{ACT_KEYS[min(act, len(ACT_KEYS) - 1)]}</string>',
                  f'\t\t\t<string name="level-name">{name}</string>',
                  "\t\t</dict>"]
        out.append("\n".join(lines))
    return "\n\n".join(out)


def tower_mission(committed_src: str, floors: list[dict], mission_id: str) -> str:
    """The committed HoH2-theme mission's head (id, set, conditionals, marker) with
    HoH1's floors."""
    head, sep, _ = committed_src.partition('<array name="levels">')
    if not sep:
        raise ValueError("committed mission has no levels array")
    head = head.replace('<string name="id">hwp_forsaken_tower</string>',
                        f'<string name="id">{mission_id}</string>', 1)
    head = head.replace(".mission.hwp_forsaken_tower.name", f".mission.{mission_id}.name", 1)
    head = head.replace(".mission.hwp_forsaken_tower.desc", f".mission.{mission_id}.desc", 1)
    head = re.sub(r"<!--.*?-->", "<!-- Generated by tools/import_hoh1.py campaign: HoH1's tower "
                  "(tweak/dungeons/base.sval), %d floors. Do not edit; not committed. -->" % len(floors),
                  head, count=1, flags=re.S)
    return head + sep + "\n" + mission_floors_xml(floors) + "\n\t</array>\n</dict>\n"


# ------------------------------------------------------------------ generator scripts

def literal_roots(texts, entries) -> set[str]:
    """Resource paths the generator scripts name: whole paths, and the files a
    partial path (concatenated at run time, "doodads/special/color_" + theme) starts."""
    roots: set[str] = set()
    for text in texts:
        for lit in LITERAL_RE.findall(text):
            if lit in entries:
                roots.add(lit)
            elif not lit.endswith("/") and "." not in lit.rsplit("/", 1)[-1]:
                roots |= {p for p in entries if p.startswith(lit)}
    return roots


def theme_roots(entries) -> set[str]:
    return {p for p in entries if p.startswith(GEN_DIRS + GEN_LIGHTING)}


def _function(text: str, signature: str) -> str:
    i = text.index(signature)
    m = re.compile(r"(?m)^}").search(text, i)
    return text[i:m.end()]


def move_paths(text: str) -> str:
    return PATH_LIT_RE.sub(lambda m: '"' + PREFIX + m.group(1), text)


OPT_CALL_RE = re.compile(r"array<ivec2> matches = OPT_FindAllPatterns\(pattern, brush\.m_grid, brush\.m_gridConsumed\);\s*/\*(.*?)\*/", re.S)
CLIFF_CASE = (
    "\t\t\t\t\t\tcase Pattern::Cliff:\n"
    "\t\t\t\t\t\t\tif (cell != Cell::Cliff)\n"
    "\t\t\t\t\t\t\t\tmatch = false;\n"
    "\t\t\t\t\t\t\tbreak;\n"
    "\t\t\t\t\t\t\n"
)


def script_pattern_matcher(text: str) -> str:
    """HoH1's FindAllPatterns calls the engine's OPT_FindAllPatterns, which HoH2 has with
    another signature, grid layout and Cell numbering; HoH1 keeps its script version of the
    search commented out under the call. That runs instead, with the Cliff case the engine's
    has (PrefabPlacement's cliff patterns; Anything matches every cell, as there)."""
    def sub(m):
        body = m.group(1).strip("\n")
        a = body.find("\t\t\t\t\t\tcase Pattern::Breakable:")
        if a < 0:
            raise ValueError("PatternMatcher: script search not found (game update?)")
        return body[:a] + CLIFF_CASE + body[a:] + "\n"
    text, n = OPT_CALL_RE.subn(sub, text)
    if n != 1:
        raise ValueError("PatternMatcher: OPT_FindAllPatterns call not found (game update?)")
    return text


def transform_script(path: str, text: str) -> str:
    text = text.replace("\r\n", "\n")
    if path.endswith("DungeonGenerator.as"):
        for b in DLC_BRUSHES:
            text, n = re.subn(r"\n\t\tcase DungeonTileset::%s:\s*@m_brush = \w+\(\);\s*break;" % b, "", text)
            if n != 1:
                raise ValueError(f"{path}: MakeBrush case {b} not found (game update?)")
    if path.endswith("PatternMatcher.as"):
        text = script_pattern_matcher(text)
    text = text.replace('GetVarBool("debug_dungeon_prefabs")', "false")
    head = "// Generated by tools/import_hoh1.py campaign from HoH1 %s. Not committed.\n" % path
    return head + "namespace HoH1Gen\n{\n" + move_paths(text) + "\n}\n"


def make_dungeon_generator(text: str) -> str:
    """HoH1's MakeDungeonGenerator for the tower's themes, reading the floor from
    HoH1Gen::g_level instead of HoH1's game mode."""
    text = text.replace("\r\n", "\n")
    fn = _function(text, "DungeonGenerator@ MakeDungeonGenerator(")
    fn, n = re.subn(r"\n\tauto gm = cast<BaseGameMode>\(g_gameMode\);\n\tauto level = gm\.m_dungeon\.GetLevel\(levelCount\);",
                    "\n\tauto level = g_level;", fn)
    if n != 1:
        raise ValueError("MakeDungeonGenerator: level lookup not found (game update?)")
    a = fn.find('\telse if (level.m_theme == "desert")')
    b = fn.find("\tif (dgn !is null)\n\t\t@dgn.m_enemyPlacer")
    if a < 0 or b < 0:
        raise ValueError("MakeDungeonGenerator: DLC themes not found (game update?)")
    fn = fn[:a] + "\n\t" + fn[b:]
    rect = _function(text, "ivec2 Rectangularize(")
    return move_paths(rect + "\n\n" + fn)


GLUE = """// Generated by tools/import_hoh1.py campaign: HoH1's GenerateDungeon for one
// floor, run by HWPHoH1Generator (scripts/HWP/Campaign/HoH1/Generator.as). Not committed.
namespace HoH1Gen
{
	// HoH1's DungeonLevel (its tweak/dungeons/base.sval row) for the floor being made
	class DungeonLevel
	{
		int m_act;
		int m_level;
		string m_theme;
		int m_width;
		int m_height;
	}
	DungeonLevel g_level;

	float g_ngp;
	vec2 g_spawnPos;

	array<PrefabToSpawn@> g_prefabsToSpawn;
	class PrefabToSpawn
	{
		Prefab@ m_pfb;
		vec3 m_pos;
		bool m_tileset;

		PrefabToSpawn(Prefab@ pfb, vec3 pos, bool includeTileset = false)
		{
			@m_pfb = pfb;
			m_pos = pos;
			m_tileset = includeTileset;
		}
	}

	// HoH1's town fountain wishes: HoH2 has none
	namespace Fountain
	{
		bool HasEffect(const string &in id) { return false; }
	}

	// HoH1's NG+ unit swap: the campaign module's copy of its map
	namespace UnitMap
	{
		UnitProducer@ Replace(UnitProducer@ prod) { return HWP::HoH1::TierFor(prod); }
	}

%(make)s
}

class HWPHoH1GenFloor : HWP::Campaign::HoH1Floor
{
	array<HoH1Gen::PrefabToSpawn@> m_prefabs;
	vec2 m_spawn;

	void Generate(const string &in theme, int act, int level, int levelCount, int width, int height, int numPlrs)
	{
		HoH1Gen::g_level.m_act = act;
		HoH1Gen::g_level.m_level = level;
		HoH1Gen::g_level.m_theme = theme;
		HoH1Gen::g_level.m_width = width;
		HoH1Gen::g_level.m_height = height;
		HoH1Gen::g_ngp = g_ngp;
		HoH1Gen::g_spawnPos = vec2();
		HoH1Gen::g_prefabsToSpawn.removeRange(0, HoH1Gen::g_prefabsToSpawn.length());

		HoH1Gen::DungeonGenerator@ dgn = HoH1Gen::MakeDungeonGenerator(levelCount, numPlrs);
		if (dgn is null)
		{
			PrintError("[HWP:campaign] HoH1 has no generator for theme " + theme);
			return;
		}
		dgn.MakeBrush();
		dgn.m_brush.m_lvl = ivec3(act, level, levelCount);
		dgn.m_numPlrs = numPlrs;
		dgn.Generate(g_scene);

		m_prefabs = HoH1Gen::g_prefabsToSpawn;
		m_spawn = HoH1Gen::g_spawnPos;
		HoH1Gen::g_prefabsToSpawn.removeRange(0, HoH1Gen::g_prefabsToSpawn.length());
	}

	vec2 SpawnPos() { return m_spawn; }
	uint PrefabCount() { return m_prefabs.length(); }
	Prefab@ PrefabAt(uint i) { return m_prefabs[i].m_pfb; }
	vec3 PrefabPosAt(uint i) { return m_prefabs[i].m_pos; }
}
"""


def generator_scripts(read) -> dict[str, str]:
    """{file name: script text} for the local HoH1Gen folder; `read(path)` gives a
    HoH1 file's text."""
    out = {}
    for path in GEN_SCRIPTS:
        out[path.rsplit("/", 1)[-1]] = transform_script(path, read(path))
    make = make_dungeon_generator(read(GEN_DUNGEON))
    out["GenerateDungeon.as"] = GLUE % {"make": "\n".join("\t" + ln if ln else ln for ln in make.split("\n"))}
    return out
