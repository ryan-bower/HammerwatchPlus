"""Clone a vanilla subclass (spec) into a new spec mod (docs/devarena/SPEC.md, build step 7).

    python tools/devarena/clone_spec.py --from ranger_nature --id ranger_test --name "Test Warden"
    python tools/devarena/clone_spec.py ... --log gamelab/results/<run>/logs/pass1.HWR2.exe.log [--version live]

Writes mods/spec-<id with - for _>/:
  info.xml, module.json            requires core
  players/hwp/spec_<id>/class_<id>.sval
                                   the source subclass dict (PlayerClass::LoadMultiple) with the new
                                   id and a new name key, the parent's SharedStats block, the
                                   parent's icon. Skills shared with the parent's other subclasses
                                   stay vanilla paths; the spec's own skills are copied.
  players/hwp/spec_<id>/skills/*.sval
                                   the spec's own skills, raw text, every id inside renamed to
                                   hwp_<id>_<old id> (so they never clash with the vanilla ones).
  res/language/english/hwp_spec_<id>.lang
                                   the class name, and the name of a composed skill (placeholders:
                                   descriptions stay the vanilla keys).

With --log (or --sval), the tuner version's edits are baked into the copies:
  @compose  the slot's base dict becomes the "compose-dict <slot> {...}" line logged by the last
            Flush that put the chosen version live,
            its upgrades and modifier sub-skills are cut to their skill-cost (as Compose.as does
            live), and its name becomes the draft's n=.
  others    a leaf at level k ("castpoint", "binds.area-dmg", "timeline.1"): the value in the
            file's level-k dict is replaced. A leaf the file does not spell out at that level is
            refused (exit 1), not guessed.

Star budget: the total skill-cost of the spec's skills (all levels, modifier sub-skills too,
skills_cost.inc resolved) is printed beside its siblings'; a clone that differs from its source
fails (exit 1).
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent))
from tools.devarena import overrides  # noqa: E402

REPO = overrides.REPO
GAME = REPO / "gamecode" / "sdk" / "hoh2"
COST_INC = GAME / "players" / "skills_cost.inc"
DICT_LINE = re.compile(r"\[HWP:devarena\] compose-dict (\S+) (\{.*\})\s*$")
LIVE_LINE = re.compile(r"\[HWP:devarena\] live v(\d+) \(")


# ---- the source class file -------------------------------------------------------------------
def find_class_file(spec: str) -> Path:
    for p in sorted((GAME / "players").glob("*/class_*.sval")):
        if f'<string name="id">{spec}</string>' in p.read_text(encoding="utf-8", errors="replace"):
            return p
    raise SystemExit(f"no players/*/class_*.sval defines subclass '{spec}'")


def strip_comments(t: str) -> str:
    return re.sub(r"<!--.*?-->", "", t, flags=re.S)


def class_dicts(text: str) -> list[str]:
    """The top-level <dict> blocks of a LoadMultiple class file (one tab in)."""
    return re.findall(r"^\t<dict>\n.*?^\t</dict>", strip_comments(text).replace("\r\n", "\n"), flags=re.M | re.S)


def field(block: str, name: str) -> str:
    m = re.search(rf'<string name="{name}">([^<]*)</string>', block)
    return m.group(1) if m else ""


def skill_paths(block: str) -> list[str]:
    m = re.search(r'<array name="skills">(.*?)</array>', block, flags=re.S)
    return re.findall(r"<string>([^<]+)</string>", m.group(1)) if m else []


def defblock(text: str, name: str) -> str:
    m = re.search(rf"^%defblock {name}\n.*?^%endblock\n", text.replace("\r\n", "\n"), flags=re.M | re.S)
    if not m:
        raise SystemExit(f"no %defblock {name}")
    return m.group(0)


# ---- star budget -------------------------------------------------------------------------------
def cost_macros() -> dict[str, int]:
    return {k: int(v) for k, v in re.findall(r"%replace (\w+) (\d+)", COST_INC.read_text(encoding="utf-8"))}


def skill_cost(text: str, macros: dict[str, int]) -> int:
    total = 0
    for v in re.findall(r'<int name="skill-cost">([^<]+)</int>', strip_comments(text)):
        v = v.strip()
        total += int(v) if v.lstrip("-").isdigit() else macros.get(v, 0)
    return total


def budget(paths: list[str], root: Path, macros: dict[str, int]) -> int:
    n = 0
    for rel in paths:
        p = root / rel
        if p.is_file():
            n += skill_cost(p.read_text(encoding="utf-8", errors="replace"), macros)
    return n


# ---- sval text surgery ---------------------------------------------------------------------------
def block_span(text: str, open_re: str, indent: int, start: int = 0, end: int | None = None):
    """(start, end) of the element opened by open_re at `indent` tabs, its closing tag included."""
    pad = "\t" * indent
    m = re.compile(rf"^{pad}{open_re}[ \t]*$", re.M).search(text, start, len(text) if end is None else end)
    if not m:
        return None
    tag = re.match(r"\s*<(\w+)", m.group(0)).group(1)
    c = re.compile(rf"^{pad}</{tag}>[ \t]*$", re.M).search(text, m.end())
    if not c:
        return None
    return m.start(), c.end()


def cost_only(block: str) -> str:
    """A level dict cut to its skill-cost line."""
    lines = block.split("\n")
    keep = [lines[0]] + [ln for ln in lines[1:-1] if 'name="skill-cost"' in ln] + [lines[-1]]
    return "\n".join(keep)


def dict_items(text: str, start: int, end: int, indent: int) -> list[tuple[int, int]]:
    spans, pos = [], start
    while True:
        s = block_span(text, r"<dict>", indent, pos, end)
        if not s:
            return spans
        spans.append(s)
        pos = s[1]


def xml_of(v, indent: int, name: str | None = None) -> str:
    """Compose.as SvJson typed JSON -> SValue XML (ints are ints, {"f"} floats, {"ivec2"} ...)."""
    pad = "\t" * indent
    a = f' name="{name}"' if name is not None else ""
    if isinstance(v, bool):
        return f"{pad}<bool{a}>{'true' if v else 'false'}</bool>"
    if isinstance(v, int):
        return f"{pad}<int{a}>{v}</int>"
    if isinstance(v, str):
        return f"{pad}<string{a}>{v.replace('&', '&amp;').replace('<', '&lt;')}</string>"
    if isinstance(v, list):
        if not v:
            return f"{pad}<array{a}></array>"
        return f"{pad}<array{a}>\n" + "\n".join(xml_of(x, indent + 1) for x in v) + f"\n{pad}</array>"
    if isinstance(v, dict):
        if set(v) == {"f"}:
            return f"{pad}<float{a}>{v['f']:g}</float>"
        if set(v) == {"ivec2"}:
            return f"{pad}<ivec2{a}>{v['ivec2'][0]} {v['ivec2'][1]}</ivec2>"
        if set(v) == {"vec2"}:
            return f"{pad}<vec2{a}>{v['vec2'][0]:g} {v['vec2'][1]:g}</vec2>"
        if not v:
            return f"{pad}<dict{a}></dict>"
        return f"{pad}<dict{a}>\n" + "\n".join(xml_of(x, indent + 1, k) for k, x in v.items()) + f"\n{pad}</dict>"
    raise TypeError(f"cannot write {v!r}")


def compose_into(text: str, built: dict, name_key: str | None) -> str:
    """The skill file with the composed base dict, upgrades and modifier sub-skills cut to cost."""
    s = block_span(text, r'<dict name="skill">', 1)
    if not s:
        raise SystemExit("no top-level <dict name=\"skill\"> to compose into")
    text = text[:s[0]] + xml_of(built, 1, "skill") + text[s[1]:]
    up = block_span(text, r'<array name="upgrades">', 1)
    if up:
        items = dict_items(text, up[0], up[1], 2)
        for a, b in reversed(items):
            text = text[:a] + cost_only(text[a:b]) + text[b:]
    mods = block_span(text, r'<array name="modifier-skills">', 1)
    if mods:
        for a, b in reversed(dict_items(text, mods[0], mods[1], 2)):
            sub = text[a:b]
            sk = block_span(sub, r'<dict name="skill">', 3)
            if sk:
                sub = sub[:sk[0]] + cost_only(sub[sk[0]:sk[1]]) + sub[sk[1]:]
            u2 = block_span(sub, r'<array name="upgrades">', 3)
            if u2:
                for c, d in reversed(dict_items(sub, u2[0], u2[1], 4)):
                    sub = sub[:c] + cost_only(sub[c:d]) + sub[d:]
            text = text[:a] + sub + text[b:]
    if name_key:
        text = re.sub(r'^(\t<string name="name">)[^<]*(</string>)', rf"\g<1>{name_key}\g<2>", text, count=1, flags=re.M)
    return text


def level_span(text: str, level: int):
    if level == 0:
        return block_span(text, r'<dict name="skill">', 1), 2
    up = block_span(text, r'<array name="upgrades">', 1)
    items = dict_items(text, up[0], up[1], 2) if up else []
    return (items[level - 1] if level - 1 < len(items) else None), 3


def patch_leaf(text: str, level: int, path: str, value: str) -> tuple[str, str]:
    """(new text, "" ok or the reason it was refused)."""
    span, ind = level_span(text, level)
    if not span:
        return text, f"level {level} not in the file"
    a, b = span
    parts = path.split(".")
    for p in parts[:-1]:
        if p.isdigit():
            return text, f"{path}: an index in the middle of a path"
        s = block_span(text, rf'<(?:dict|array) name="{re.escape(p)}">', ind, a, b)
        if not s:
            return text, f"{path}: no '{p}' at level {level} in the file"
        a, b, ind = s[0], s[1], ind + 1
    leaf = parts[-1]
    seg = text[a:b]
    if leaf.isdigit():
        # an array element; the array can be one line (<array name="timeline"><int>..)
        elems = list(re.finditer(r"<(int|float|string|bool|i|f|s|b)>([^<]*)</\1>", seg))
        i = int(leaf)
        if i >= len(elems):
            return text, f"{path}: index {i} out of range"
        m = elems[i]
    else:
        m = re.search(rf'<(int|float|string|bool|i|f|s|b) name="{re.escape(leaf)}">([^<]*)</\1>', seg)
        if not m:
            return text, f"{path}: not spelled out at level {level} in the file"
    s0, s1 = a + m.start(2), a + m.end(2)
    return text[:s0] + value + text[s1:], ""


def fix_tooltips(text: str, vanilla: dict | None) -> tuple[str, list[str]]:
    """The copy's top-level description-params made to show its own numbers (the tooltip lint's
    by-value binding, tools/devarena/tooltip_lint.py): a changed field's param shows the new
    value, a param whose fields a compose removed is dropped. Notes per change."""
    if vanilla is None:
        return text, []
    from tools.devarena import tooltip_lint
    changes, notes = tooltip_lint.rewrite_params(vanilla, tooltip_lint.parse_sval_text(text))
    span = block_span(text, r'<array name="description-params">', 1)
    if not changes or not span:
        return text, notes
    rows = list(re.finditer(r"^\t\t<array>.*</array>\n", text[span[0]:span[1]], re.M))
    for i, new in sorted(changes, reverse=True):
        if i >= len(rows):
            continue
        m = rows[i]
        a, b = span[0] + m.start(), span[0] + m.end()
        if new is None:
            text = text[:a] + text[b:]
            continue
        head = re.match(r"\t\t<array><s>[^<]*</s>(?:<b>[^<]*</b>)?<s>[^<]*</s>", m.group(0)).group(0)
        text = text[:a] + head + "".join(f"<s>{v}</s>" for v in new) + "</array>\n" + text[b:]
    return text, notes


# ---- edits ------------------------------------------------------------------------------------
def load_state(a) -> tuple[dict | None, str]:
    if a.log:
        t = Path(a.log).read_text(encoding="utf-8", errors="replace")
        return overrides.last_in(t), t
    if a.sval:
        return overrides.from_sval(Path(a.sval).read_text(encoding="utf-8")), ""
    return None, ""


def version_edits(state: dict, which: str) -> list[list]:
    from tools.devarena.export import pick
    v = pick(state, which)
    return [] if v == 0 else [list(e) for e in state["versions"][v - 1]["edits"]]


def version_dicts(log: str, version: int) -> dict[str, dict] | None:
    """The compose-dict lines logged by the last Flush that put `version` live (they come just
    before its "live vN (" line), or None when that version was never live in the log. The last
    compose-dict of a slot can belong to another version (review 6: --version a shipped B's
    cooldown under A's name)."""
    out = None
    pending: dict[str, dict] = {}
    for ln in log.splitlines():
        m = DICT_LINE.search(ln)
        if m:
            pending[m.group(1)] = json.loads(m.group(2))
            continue
        m = LIVE_LINE.search(ln)
        if m:
            if int(m.group(1)) == version:
                out = pending
            pending = {}
    return out


def draft_name(draft: str) -> str:
    for kv in draft.split(";"):
        if kv.startswith("n="):
            return kv[2:]
    return ""


# ---- main -------------------------------------------------------------------------------------
def build(a) -> int:
    new_id = a.id
    if not re.fullmatch(r"[a-z][a-z0-9_]*", new_id):
        raise SystemExit(f"--id '{new_id}': lowercase letters, digits and _ only")
    src_file = find_class_file(a.src)
    text = src_file.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n")
    dicts = class_dicts(text)
    src = next((d for d in dicts if field(d, "id") == a.src), None)
    parent = field(src, "parent")
    if not parent:
        raise SystemExit(f"'{a.src}' has no parent: clone a subclass, not a base class")
    siblings = [d for d in dicts if field(d, "id") != a.src]
    shared = {p for d in siblings for p in skill_paths(d)}
    paths = skill_paths(src)
    own = [p for p in paths if p not in shared]

    mod_name = "spec-" + new_id.replace("_", "-")
    mod = Path(a.out) / mod_name if a.out else REPO / "mods" / mod_name
    if mod.exists():
        if not a.force:
            raise SystemExit(f"{mod} exists (--force replaces it)")
        shutil.rmtree(mod)
    rel_dir = f"players/hwp/spec_{new_id}"
    (mod / rel_dir / "skills").mkdir(parents=True)

    state, log = load_state(a)
    edits = version_edits(state, a.version) if state else []
    picked = None
    if state:
        from tools.devarena.export import pick
        picked = pick(state, a.version)
    dicts_by_slot = (version_dicts(log, picked) if picked is not None else None) or {}
    lang = {f".skills.hwp_{new_id}.mastery.name": a.name}
    refused = []

    # the spec's own skills
    id_map: dict[str, str] = {}
    copies: dict[str, str] = {}
    for rel in own:
        t = (GAME / rel).read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n")
        for old in re.findall(r'<string name="id">([^<]+)</string>', t):
            id_map[old] = f"hwp_{new_id}_{old}"
        copies[rel] = t
    new_paths = []
    from tools.devarena import tooltip_lint
    vanilla_entries = tooltip_lint.skill_entries()
    tooltip_notes: list[str] = []
    for rel, t in copies.items():
        top = re.search(r'^\t<string name="id">([^<]+)</string>', t, flags=re.M)
        top_id = top.group(1) if top else Path(rel).stem
        for e in [e for e in edits if e[0] == top_id]:
            skill, level, path, value = e
            if path == "@compose":
                built = dicts_by_slot.get(skill)
                if built is None:
                    refused.append(f"{skill}: @compose needs the compose-dict line logged when v{picked} "
                                   "was live (--log; make that version live once, then ship)")
                    continue
                key = None
                n = draft_name(value)
                if n:
                    key = f".skills.hwp_{new_id}.{skill}.name"
                    lang[key] = n
                t = compose_into(t, built, key)
            else:
                t, why = patch_leaf(t, int(level), path, str(value))
                if why:
                    refused.append(f"{skill}[{level}].{path}={value}: {why}")
        t, notes = fix_tooltips(t, vanilla_entries.get(top_id))
        tooltip_notes += notes
        for old, new in sorted(id_map.items(), key=lambda kv: -len(kv[0])):
            t = re.sub(rf">{re.escape(old)}<", f">{new}<", t)
        out_rel = f"{rel_dir}/skills/{id_map.get(top_id, top_id)}.sval"
        (mod / out_rel).write_text(t, encoding="utf-8", newline="\n")
        new_paths.append((rel, out_rel))
    tops = {re.search(r'^\t<string name="id">([^<]+)</string>', c, flags=re.M).group(1) for c in copies.values()}
    others = sorted({e[0] for e in edits} - tops)
    if others:
        refused.append(f"edits on skills the spec does not own: {', '.join(others)}")

    # the class file
    block = src
    for rel, out_rel in new_paths:
        block = block.replace(f"<string>{rel}</string>", f"<string>{out_rel}</string>")
    block = block.replace(f'<string name="id">{a.src}</string>', f'<string name="id">{new_id}</string>')
    block = re.sub(r'<string name="name">[^<]*</string>', f'<string name="name">.skills.hwp_{new_id}.mastery.name</string>', block, count=1)
    block = re.sub(r'<string name="description">[^<]*</string>', f'<string name="description">subclass of {parent}</string>', block, count=1)
    cls = ('<loader order="1">PlayerClass::LoadMultiple</loader>\n\n'
           f"<!-- {a.name}: a clone of {a.src}, written by tools/devarena/clone_spec.py. Stats are the\n"
           f"     parent's SharedStats block ({src_file.relative_to(GAME).as_posix()}); keep them in sync. -->\n"
           + defblock(text, "SharedStats") + "\n<array>\n" + block + "\n</array>\n")
    (mod / rel_dir / f"class_{new_id}.sval").write_text(cls, encoding="utf-8", newline="\n")

    (mod / "info.xml").write_text(
        "<dict>\n"
        f"\t<string name=\"name\">HammerwatchPlus spec: {a.name}</string>\n"
        "\t<string name=\"author\">Dev Arena</string>\n"
        f"\t<string name=\"description\">{a.name}, a {parent} subclass cloned from {a.src} by the Dev Arena "
        "(tools/devarena/clone_spec.py). Part of HammerwatchPlus; requires HWP Core.</string>\n"
        "</dict>\n", encoding="utf-8", newline="\n")
    (mod / "module.json").write_text(json.dumps({"id": mod_name, "requires": ["core"], "overrides": [], "exclude": []}, indent=2) + "\n",
                                     encoding="utf-8", newline="\n")
    lang_dir = mod / "res" / "language" / "english"
    lang_dir.mkdir(parents=True)
    rows = "\n".join(f'\t<string name="{k.lstrip(".")}">{v}</string>' for k, v in lang.items())
    (lang_dir / f"hwp_spec_{new_id}.lang").write_text(f'<lang name="English" official="false">\n{rows}\n</lang>\n',
                                                      encoding="utf-8", newline="\n")

    # star budget
    macros = cost_macros()
    mine = budget([p for p in paths if p not in dict(new_paths)], GAME, macros) + budget([o for _, o in new_paths], mod, macros)
    theirs = budget(paths, GAME, macros)
    print(f"wrote {mod.relative_to(REPO) if mod.is_relative_to(REPO) else mod}: class {new_id} ({a.name}), "
          f"{len(new_paths)} own skills, {len(edits)} edits")
    print(f"star budget: {new_id} {mine}, {a.src} {theirs}; siblings "
          + ", ".join(f"{field(d, 'id')} {budget(skill_paths(d), GAME, macros)}" for d in siblings if field(d, "parent")))
    for n in tooltip_notes:
        print("tooltip:", n)
    for r in refused:
        print("refused:", r)
    if mine != theirs:
        print(f"star budget differs from {a.src}")
        return 1
    return 1 if refused else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--from", dest="src", required=True, help="the vanilla subclass id, e.g. ranger_nature")
    ap.add_argument("--id", required=True, help="the new subclass id, e.g. ranger_test")
    ap.add_argument("--name", required=True, help='the shown name, e.g. "Test Warden"')
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--log", help="a game log: bake its last override line's version in")
    g.add_argument("--sval", help="an override .sval to bake in (no @compose: that needs --log)")
    ap.add_argument("--version", default="live", help="N, live, a or b (default live)")
    ap.add_argument("--out", help="a directory to write the mod into (default mods/)")
    ap.add_argument("--force", action="store_true", help="replace an existing mod folder")
    return build(ap.parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
