"""hoh1_risen.py - the Devil Forgemaster's risen and intact bodies for the HoH1 enemies (used by
`import_hoh1.py campaign`).

tools/make_forgemaster_risen.py makes them for HoH2's enemies from the base game; this applies
the same transforms (risen_unit, body_unit) to the converted HoH1 units, so the Forgemaster
raises the Forsaken Tower's enemies and bosses too. What a HoH1 unit needs first:

- its includes inlined from the converted output (HoH1 resolves "./x" against the unit being
  loaded, so a copy in another folder needs them absolute), its `%define HWP_TAG_*` lines and
  the tag list under `%if` (hoh1_convert.Rewriter.tags) evaluated into the unit's own tags;
- a team line (HoH1 units have none; the default is enemy), which risen_unit turns to player;
- the HoH1 bosses' own behaviors (HoH1BossLich, HoH1BossVampire, HoH1BossEye in the campaign
  module, which wait for their arena's nodes and scripts) as CompositeActorBehavior, and their
  node movements as MeleeMovement (same anim-idle, anim-walk and speed), which the Forgemaster
  swaps for its follower movement like any other;
- HoH1's actor material as HoH2's enemy one, which the transforms swap for the summon's and the
  body's;
- a boss summon's health capped at BOSS_HP, as make_forgemaster_risen's BOSS_HP table does.

Everything is written into the campaign module's gitignored output with the rest of the import,
under the Forgemaster's folders with the unit's whole "hoh1/actors/..." path, and listed in
LIST (HWP/Specs/Forgemaster.as HoH1Raisable). Nothing derived from HoH1 is committed.
"""
from __future__ import annotations

import posixpath
import re

import hoh1_convert as hoh1c
import make_forgemaster_risen as mfr

LIST = mfr.FORGE + "hoh1_risen.sval"
BOSS_CLASSES = {"HoH1BossLich": "CompositeActorBehavior", "HoH1BossVampire": "CompositeActorBehavior",
                "HoH1BossEye": "CompositeActorBehavior", "HoH1CompositeActorBehaviorColorized": "CompositeActorBehavior"}
NODE_MOVEMENTS = ("HoH1BossLichMovement", "HoH1BossVampireMovement")
BOSS_HP = 6000
HOH1_ENEMY_MATERIAL = hoh1c.PREFIX + "system/default.mats:actor"
# not raisable: the tower's last boss (the next stop is town, as make_forgemaster_risen leaves
# out HoH2's mission-final bosses), fight props (the Wraiths' statues, the Vampire's thrall
# corpses, the dragon's ice), spawners, razed towers and the banners
EXCLUDE = [
    r"^actors/bosses/dragon/", r"^actors/bosses/wraith/statue_", r"_corpse\.unit$", r"_revive\.unit$",
    r"(^|/)spawners?/", r"(^|/)\w*spawn\w*\.unit$", r"_razed\.unit$", r"^actors/banners/", r"iceblock",
]
INCLUDE_RE = re.compile(r'^[ \t]*%include\s+"([^"]+)"[ \t]*(?:\r?\n|\Z)', re.M)
TAG_DEFINE_RE = re.compile(r"^%define HWP_TAG_\w+\r?\n", re.M)
TAGS_BLOCK_RE = re.compile(r'\n\t\t<array name="tags">(?:\n%if HWP_TAG_\w+\n\t\t\t<string>\w+</string>\n%endif)+\n\t\t</array>')
REL_ATTR_RE = re.compile(r'="(\.\.?/[^"]*)"')


def inline(path: str, texts: dict[str, str], owner: str, seen=()) -> str:
    """the converted `path` with its includes inlined; relative includes and values resolve
    against `owner`, the unit being loaded"""
    def sub(m):
        ref = m.group(1)
        q = hoh1c.resolve(owner, ref) if ref.startswith(".") else ref.removeprefix(hoh1c.PREFIX)
        if q in seen or q not in texts:
            return ""
        return inline(q, texts, owner, seen + (q,)).rstrip("\n") + "\n"
    text = mfr.COMMENT_RE.sub("", texts[path])
    return INCLUDE_RE.sub(sub, text)


def absolutize(text: str, owner: str) -> str:
    d = posixpath.dirname(owner)
    return REL_ATTR_RE.sub(lambda m: '="' + hoh1c.PREFIX + posixpath.normpath(posixpath.join(d, m.group(1))) + '"', text)


def prepared(path: str, texts: dict[str, str], tags: list[str]) -> str | None:
    """the HoH1 unit as make_forgemaster_risen expects an enemy unit, or None if its behavior
    is not one the Forgemaster raises"""
    text = absolutize(inline(path, texts, path), path)
    text = TAG_DEFINE_RE.sub("", text)
    literal = '\n\t\t<array name="tags">' + "".join(f"<string>{t}</string>" for t in tags) + "</array>"
    text = TAGS_BLOCK_RE.sub(lambda m: literal, text, count=1)
    m = re.search(r'<behavior class="(\w+)"([^>]*)>', text)
    if not m:
        return None
    cls = BOSS_CLASSES.get(m.group(1), m.group(1))
    if cls not in mfr.CLASSES:
        return None
    team = "" if 'name="team"' in text else '\n\t\t<string name="team">enemy</string>'
    text = text[:m.start()] + f'<behavior class="{cls}"{m.group(2)}>' + team + text[m.end():]
    # HoH1's enemy material, so risen_unit and body_unit give the summon's and the body's
    text = text.replace(f'material="{HOH1_ENEMY_MATERIAL}"', 'material="system/default.mats:enemy"')
    for mov in NODE_MOVEMENTS:
        text = text.replace(f'<string name="class">{mov}</string>', '<string name="class">MeleeMovement</string>')
    return text


def build(texts: dict[str, str], unit_tags: dict[str, list[str]]) -> tuple[dict[str, str], list[str]]:
    """({output path under the campaign module: text}, the raisable units' "hoh1/actors/..." paths).
    `texts` is the converted import (HoH1 path -> text), `unit_tags` Rewriter.unit_tags."""
    out: dict[str, str] = {}
    raisable: list[str] = []
    for path in sorted(unit_tags):
        if any(re.search(x, path) for x in EXCLUDE):
            continue
        text = prepared(path, texts, unit_tags[path])
        if text is None:
            continue
        rel = hoh1c.PREFIX + path            # the name under the Forgemaster's folders
        risen = mfr.risen_unit(rel, text)
        if "boss" in unit_tags[path]:
            risen = re.sub(r'<int name="hp">(\d+)</int>', lambda h: f'<int name="hp">{min(int(h.group(1)), BOSS_HP)}</int>',
                           risen, count=1)
        out[mfr.FORGE + "risen/" + rel] = risen
        out[mfr.FORGE + "bodies/" + rel] = mfr.body_unit(rel, text)
        raisable.append(rel)
    out[LIST] = ("<!-- Generated by tools/import_hoh1.py campaign (tools/hoh1_risen.py). -->\n<array>\n"
                 + "".join(f"\t<string>{r}</string>\n" for r in raisable) + "</array>\n")
    return out, raisable
