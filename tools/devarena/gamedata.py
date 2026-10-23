"""Read-only views of the game tables the Dev Arena tools need: classes, skills (costs, levels,
sub-skills, tags), base items and trinkets. Source: gamecode/datatables/*.sval.json, the game's
own .sval files as the bootstrap dumped them (the include preprocessor already expanded).

The cost rules are PlayerRecord.SkillUp's (PlayerRecord.as:1563-1626) and PlayerClass.LoadParams'
(PlayerClass.as:66-200): a skill's level k costs m_levelSkillCost[startingLevel + k]; the base
"skill" dict's skill-cost defaults to 1 and each upgrade inherits the one before it. A skill can
be picked len(levels) - startingLevel times. Stars: (level - 1) * SkillPtsPerLevel 3, plus town
accomplishments; attribute points: (level - 1) * StatsPerLevel 3 (Data/Player.as:102-109).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DATA = REPO / "gamecode" / "datatables"
STARS_PER_LEVEL = 3
STATS_PER_LEVEL = 3
COMBO_FILES = ("players/shared/skills/combo_choices.sval", "players/shared/skills/combo_levlable.sval")
ITEM_FILES = ("shared_back", "shared_chest", "shared_feet", "shared_hands", "shared_head",
              "weapons_mainhand", "weapons_offhand", "weapons_twohanded")
TRINKET_FILES = ("common", "uncommon", "rare", "epic")


def load(rel: str):
    """A datatable by its game path (players/ranger/skills/x.sval) or a path under DATA."""
    p = DATA / (rel if rel.endswith(".json") else rel + ".json")
    return json.loads(p.read_text(encoding="utf-8"))


def costs_of(entry: dict) -> list[int]:
    base = entry.get("skill")
    if not isinstance(base, dict):
        return []
    out = [int(base.get("skill-cost", 1))]
    for up in entry.get("upgrades", []) or []:
        out.append(int(up.get("skill-cost", out[-1])))
    return out


@dataclass
class Skill:
    id: str
    type: str
    start: int
    costs: list[int]
    tags: list[str]
    blockers: list[str] = field(default_factory=list)
    parent: str | None = None
    mods: list["Skill"] = field(default_factory=list)
    desc_params: list = field(default_factory=list)
    entry: dict = field(default_factory=dict, repr=False)

    @property
    def picks(self) -> int:
        """How many SkillUp calls take it from unpicked to max."""
        return max(0, len(self.costs) - self.start)

    def cost(self, picked: int) -> int:
        """Stars for the next SkillUp at `picked`."""
        return self.costs[self.start + picked]

    @property
    def active(self) -> bool:
        return self.type == "spell" and "passive" not in self.tags


def skill_from(entry: dict, parent: str | None = None) -> Skill:
    s = Skill(id=entry["id"], type=entry.get("type", "mod" if parent else "passive"),
              start=int(entry.get("starting-level", 0)), costs=costs_of(entry),
              tags=list(entry.get("tags", []) or []), blockers=list(entry.get("blocked-by-skills", []) or []),
              parent=parent, desc_params=list(entry.get("description-params", []) or []), entry=entry)
    if parent is None:
        s.mods = [skill_from(m, s.id) for m in entry.get("modifier-skills", []) or [] if isinstance(m, dict) and m.get("id")]
    return s


def skills_in(rel: str) -> list[Skill]:
    d = load(rel)
    return [skill_from(e) for e in (d if isinstance(d, list) else [d]) if isinstance(e, dict) and e.get("id")]


@dataclass
class PlayerClass:
    id: str
    parent: str | None
    base: dict
    skills: list[Skill]
    start_gear: list[str]

    @property
    def primary(self) -> str:
        """The attribute the starting chest asks for (chest_<attr>_t1a): str, dex or int."""
        for g in self.start_gear:
            parts = g.split("_")
            if parts[0] == "chest":
                return parts[1]
        return max(("str", "dex", "int"), key=lambda a: self.base.get("base-" + a, 0))


@lru_cache(maxsize=None)
def classes() -> dict[str, PlayerClass]:
    out = {}
    for f in sorted((DATA / "players").glob("*/class_*.sval.json")):
        for c in json.loads(f.read_text(encoding="utf-8")):
            sk = [s for rel in c.get("skills", []) for s in skills_in(rel)]
            out[c["id"]] = PlayerClass(c["id"], c.get("parent"), {k: v for k, v in c.items() if k.startswith("base-")},
                                       sk, list(c.get("starting-equipment", [])))
    return out


def subclasses() -> list[PlayerClass]:
    return [c for c in classes().values() if c.parent]


@lru_cache(maxsize=None)
def combos() -> dict[str, Skill]:
    return {s.id: s for rel in COMBO_FILES for s in skills_in(rel)}


@lru_cache(maxsize=None)
def items() -> dict[str, dict]:
    out = {}
    for name in ITEM_FILES:
        for it in load(f"tweak/items/equipment/equipment_{name}.sval"):
            out[it["id"]] = it
    return out


@lru_cache(maxsize=None)
def trinkets() -> dict[str, dict]:
    out = {}
    for name in TRINKET_FILES:
        for t in load(f"tweak/trinkets/{name}.sval"):
            out[t["id"]] = t
    return out


def stars_at(level: int) -> int:
    return (level - 1) * STARS_PER_LEVEL


def stat_points_at(level: int) -> int:
    return (level - 1) * STATS_PER_LEVEL
