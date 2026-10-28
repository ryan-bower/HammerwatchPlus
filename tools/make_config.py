"""The settings page's data: every shipped module's `config` block (module.json) checked against
the code, then written where the game reads it (docs/modules.md, Settings).

python tools/make_config.py              write the files below
python tools/make_config.py --check      exit 1 when a file is stale or a config block is wrong
python tools/make_config.py --validate   only check the config blocks (writes nothing)

Writes:
  mods/hwplib/tweak/hwp/config.sval                    packages -> modules -> settings (HWP::Config)
  mods/hwplib/res/language/english/hwp_cfg.lang        the package titles
  mods/<id>/res/language/english/hwp_<id>_cfg.lang     the module's titles and texts; the module's
                                                       own file, so its title string is there only
                                                       when the module is (HWP::Config::Present)
  docs/generated/settings.md                           every setting, for the docs

A config block (module.json):

  "config": {
    "title": "Valuables",                 the module's row (default: info.xml name, no "HammerwatchPlus ")
    "about": "Valuables pay more gold.",  the hint line under the list when the row is selected
    "toggle": "valuables.enabled",        the module's on/off setting, read in the code as
                                          Settings::GetBool("<toggle>", true); null: it cannot be
                                          turned off in game (data only), "always_on" says why
    "scope": "host",                      host: in a lobby the host's value rules (gameplay);
                                          local: every player's own (display, keys)
    "applies": "now",                     now, or level: takes effect on the next level
    "settings": [
      {"key": "valuables.gold_mult", "type": "float", "default": 2, "values": [1, 1.5, 2, 3, 5],
       "suffix": "x", "title": "Gold multiplier", "about": "..."},
      {"key": "fishing.bite_min", "type": "int", "default": 3000, "min": 1000, "max": 8000,
       "step": 500, "suffix": " ms", "title": "...", "about": "..."},
      {"key": "autoaim.mode", "type": "int", "default": 1, "values": [0, 1, 2],
       "labels": ["Off", "Controller", "Always"], "title": "..."},
      {"key": "deathrecap.chat", "type": "bool", "default": true, "title": "..."},
      {"option": "swapkey"}               an HWP::Options::Option the module registers in code
    ]                                     (key binds, presets); its title comes from the Option
  }

Each key's type and default must match how the module's code reads it
(HWP::Settings::Get<Type>("<key>", <default>)). A setting's scope and applies default to the
module's. packages.json "settings_top" lists what the page shows above the packages
("option:<id>" or a setting key).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import xml.sax.saxutils as su
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
MODS = REPO / "mods"
SVAL = MODS / "hwplib" / "tweak" / "hwp" / "config.sval"
LIB_LANG = MODS / "hwplib" / "res" / "language" / "english" / "hwp_cfg.lang"
DOC = REPO / "docs" / "generated" / "settings.md"
PREFIX = "HammerwatchPlus"

BLOCK_KEYS = {"title", "about", "toggle", "always_on", "scope", "applies", "settings"}
SETTING_KEYS = {"key", "type", "default", "values", "labels", "min", "max", "step", "suffix",
                "title", "about", "scope", "applies", "option"}
GET = re.compile(r'Settings::Get(Bool|Int|Float)\(\s*"([^"]+)"\s*,\s*([^)]*?)\s*\)')


def mod_lang(mod: str) -> Path:
    return MODS / mod / "res" / "language" / "english" / f"hwp_{mod}_cfg.lang"


def strip_prefix(name: str) -> str:
    for p in (PREFIX + ": ", PREFIX + " "):
        if name.startswith(p):
            return name[len(p):]
    return name


def info_name(mod: str) -> str:
    m = re.search(r'<string name="name">([^<]*)</string>', (MODS / mod / "info.xml").read_text(encoding="utf-8"))
    return strip_prefix(m.group(1)) if m else mod


def literal(text: str):
    """A default as written in AngelScript: true, 2, 2.0f, -1, 0.5. None when it is not a literal."""
    t = text.strip()
    if t in ("true", "false"):
        return t == "true"
    t = t.rstrip("fF") if re.fullmatch(r"-?\d+\.\d*[fF]?|-?\d+[fF]", t) else t
    try:
        return int(t)
    except ValueError:
        pass
    try:
        return float(t)
    except ValueError:
        return None


def reads(mod: str) -> dict[str, list[tuple[str, object]]]:
    """key -> [(Bool|Int|Float, default literal or None)] for every Settings::Get in the module."""
    out: dict[str, list] = {}
    for f in sorted((MODS / mod / "scripts").rglob("*.as")) if (MODS / mod / "scripts").is_dir() else []:
        for m in GET.finditer(f.read_text(encoding="utf-8", errors="replace")):
            out.setdefault(m.group(2), []).append((m.group(1), literal(m.group(3))))
    return out


def registers_option(mod: str, oid: str) -> bool:
    for f in (MODS / mod / "scripts").rglob("*.as") if (MODS / mod / "scripts").is_dir() else []:
        text = f.read_text(encoding="utf-8", errors="replace")
        if f'Options::Register("{oid}"' in text:
            return True
        for m in re.finditer(r'Options::Register\("([^"]+)"\s*\+', text):
            if oid.startswith(m.group(1)):
                return True
    return False


def same(a, b) -> bool:
    if isinstance(a, bool) or isinstance(b, bool):
        return a is b or a == b and type(a) is type(b)
    return abs(float(a) - float(b)) < 1e-6


def check_block(mod: str, cfg, errors: list[str]) -> None:
    where = f"{mod}: config"
    if not isinstance(cfg, dict):
        errors.append(f"{where}: missing (every shipped module has one)")
        return
    for k in set(cfg) - BLOCK_KEYS:
        errors.append(f"{where}: unknown field {k!r}")
    code = reads(mod)
    if cfg.get("scope", "host") not in ("host", "local"):
        errors.append(f"{where}: scope must be host or local")
    if cfg.get("applies", "now") not in ("now", "level"):
        errors.append(f"{where}: applies must be now or level")
    if not cfg.get("about"):
        errors.append(f"{where}: about is missing")
    toggle = cfg.get("toggle")
    if toggle is None:
        if not cfg.get("always_on"):
            errors.append(f"{where}: no toggle, so always_on must say why it cannot be turned off")
    else:
        got = code.get(toggle, [])
        if not got:
            errors.append(f"{where}: toggle {toggle!r} is never read (Settings::GetBool(\"{toggle}\", true))")
        for kind, d in got:
            if kind != "Bool" or d is not True:
                errors.append(f"{where}: toggle {toggle!r} read as Get{kind}(..., {d}); want GetBool(..., true)")
    for i, s in enumerate(cfg.get("settings", [])):
        w = f"{where}.settings[{i}]"
        if not isinstance(s, dict):
            errors.append(f"{w}: not an object")
            continue
        for k in set(s) - SETTING_KEYS:
            errors.append(f"{w}: unknown field {k!r}")
        if "option" in s:
            if set(s) - {"option", "about"}:
                errors.append(f"{w}: an option entry takes only option (and about)")
            if not registers_option(mod, s["option"]):
                errors.append(f"{w}: no HWP::Options::Register(\"{s['option']}\", ...) in the module")
            continue
        key, kind = s.get("key"), s.get("type")
        w = f"{where}: {key}"
        if not key or kind not in ("bool", "int", "float"):
            errors.append(f"{w}: needs key and type bool, int or float")
            continue
        if not s.get("title"):
            errors.append(f"{w}: title is missing")
        if "default" not in s:
            errors.append(f"{w}: default is missing")
            continue
        d = s["default"]
        if kind == "bool":
            if not isinstance(d, bool):
                errors.append(f"{w}: a bool's default is true or false")
            if set(s) & {"values", "labels", "min", "max", "step", "suffix"}:
                errors.append(f"{w}: a bool takes no values, range or suffix")
        else:
            vals = s.get("values")
            rng = [s.get(k) for k in ("min", "max", "step")]
            if (vals is None) == (rng[0] is None):
                errors.append(f"{w}: give values, or min, max and step")
            elif vals is not None:
                if not vals or not all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in vals):
                    errors.append(f"{w}: values must be numbers")
                elif not any(same(v, d) for v in vals):
                    errors.append(f"{w}: default {d} is not one of the values")
                if kind == "int" and any(isinstance(v, float) and not v.is_integer() for v in vals or []):
                    errors.append(f"{w}: an int's values are whole numbers")
                if "labels" in s and len(s["labels"]) != len(vals or []):
                    errors.append(f"{w}: one label per value")
            else:
                if None in rng or rng[2] <= 0 or rng[0] >= rng[1]:
                    errors.append(f"{w}: min < max and step > 0")
                elif not (rng[0] <= d <= rng[1]):
                    errors.append(f"{w}: default {d} is outside {rng[0]}..{rng[1]}")
                if "labels" in s:
                    errors.append(f"{w}: labels go with values, not a range")
        if s.get("scope", "host") not in ("host", "local") or s.get("applies", "now") not in ("now", "level"):
            errors.append(f"{w}: scope host/local, applies now/level")
        got = code.get(key, [])
        if not got:
            errors.append(f"{w}: never read in mods/{mod}/scripts (Settings::Get{kind.title()}(\"{key}\", ...))")
        for k2, d2 in got:
            if k2.lower() != kind:
                errors.append(f"{w}: declared {kind}, read as Get{k2}")
            elif d2 is not None and not same(d2, d):
                errors.append(f"{w}: declared default {d}, the code reads it with {d2}")


def module_json(mod: str) -> dict:
    return json.loads((MODS / mod / "module.json").read_text(encoding="utf-8"))


def load():
    """packages.json and every package module's config block. Each package also gets `carried`:
    its mods, then the shared modules (module.json `shared`) they require from another package,
    which the package carries too (tools/build.py)."""
    pk = json.loads((REPO / "packages.json").read_text(encoding="utf-8"))
    mods = {}
    for p in pk["packages"]:
        for m in p["mods"]:
            mods[m] = module_json(m).get("config")
    pk["shared"] = sorted(m for m in mods if module_json(m).get("shared"))
    for p in pk["packages"]:
        carried, todo = list(p["mods"]), list(p["mods"])
        while todo:
            for r in module_json(todo.pop()).get("requires", []):
                if r in pk["shared"] and r not in carried:
                    carried.append(r)
                    todo.append(r)
        p["carried"] = carried
    return pk, mods


def validate(pk, mods) -> list[str]:
    errors: list[str] = []
    seen: dict[str, str] = {}
    for mod, cfg in mods.items():
        check_block(mod, cfg, errors)
        if not isinstance(cfg, dict):
            continue
        for key in [cfg.get("toggle")] + [s.get("key") for s in cfg.get("settings", []) if isinstance(s, dict)]:
            if key and key in seen and seen[key] != mod:
                errors.append(f"{mod}: {key} is {seen[key]}'s too")
            if key:
                seen[key] = mod
    options = {s["option"] for c in mods.values() if isinstance(c, dict)
               for s in c.get("settings", []) if isinstance(s, dict) and "option" in s}
    for t in pk.get("settings_top", []):
        if t.startswith("option:") and t[7:] not in options:
            errors.append(f"packages.json settings_top: {t} is no module's option entry")
        elif not t.startswith("option:") and t not in seen:
            errors.append(f"packages.json settings_top: {t} is no module's setting")
    return errors


# ---- output ----------------------------------------------------------------------------------

def x(text: str) -> str:
    return su.escape(str(text), {'"': "&quot;"})


def num(kind: str, v) -> str:
    return f"<i>{int(v)}</i>" if kind == "int" else f"<f>{float(v):g}</f>"


def sval(pk, mods) -> str:
    out = ["<!-- Generated by tools/make_config.py from every shipped module's module.json \"config\" block",
           "     (docs/modules.md, Settings). HWP::Config (scripts/HWP/Core/Config.as) reads it; do not edit. -->",
           "<dict>", '\t<array name="top">']
    out += [f"\t\t<s>{x(t)}</s>" for t in pk.get("settings_top", [])]
    out += ["\t</array>", '\t<array name="packages">']
    for p in pk["packages"]:
        out += ["\t\t<dict>", f'\t\t\t<string name="id">{x(p["id"])}</string>', '\t\t\t<array name="mods">']
        for mod in p["carried"]:
            c = mods[mod]
            host, level = c.get("scope", "host") == "host", c.get("applies", "now") == "level"
            out += ["\t\t\t\t<dict>", f'\t\t\t\t\t<string name="id">{x(mod)}</string>',
                    f'\t\t\t\t\t<bool name="shared">{str(mod in pk["shared"]).lower()}</bool>',
                    f'\t\t\t\t\t<string name="toggle">{x(c.get("toggle") or "")}</string>',
                    f'\t\t\t\t\t<bool name="host">{str(host).lower()}</bool>',
                    f'\t\t\t\t\t<bool name="level">{str(level).lower()}</bool>',
                    '\t\t\t\t\t<array name="settings">']
            for s in c.get("settings", []):
                if "option" in s:
                    out.append(f'\t\t\t\t\t\t<dict><string name="option">{x(s["option"])}</string></dict>')
                    continue
                kind = s["type"]
                sh = s.get("scope", c.get("scope", "host")) == "host"
                sl = s.get("applies", c.get("applies", "now")) == "level"
                f = [f'<string name="key">{x(s["key"])}</string>', f'<string name="type">{kind}</string>',
                     f'<bool name="host">{str(sh).lower()}</bool>', f'<bool name="level">{str(sl).lower()}</bool>']
                if kind == "bool":
                    f.append(f'<bool name="default">{str(s["default"]).lower()}</bool>')
                else:
                    f.append(num(kind, s["default"]).replace("<i>", '<int name="default">').replace("</i>", "</int>")
                             .replace("<f>", '<float name="default">').replace("</f>", "</float>"))
                    if "values" in s:
                        f.append('<array name="values">' + "".join(num(kind, v) for v in s["values"]) + "</array>")
                        f.append(f'<int name="labels">{len(s.get("labels", []))}</int>')
                    else:
                        for k in ("min", "max", "step"):
                            f.append(num(kind, s[k]).replace("<i>", f'<int name="{k}">').replace("</i>", "</int>")
                                     .replace("<f>", f'<float name="{k}">').replace("</f>", "</float>"))
                    f.append(f'<string name="suffix">{x(s.get("suffix", ""))}</string>')
                out.append("\t\t\t\t\t\t<dict>" + "".join(f) + "</dict>")
            out += ["\t\t\t\t\t</array>", "\t\t\t\t</dict>"]
        out += ["\t\t\t</array>", "\t\t</dict>"]
    out += ["\t</array>", "</dict>", ""]
    return "\n".join(out)


def lang(strings: list[tuple[str, str]], what: str) -> str:
    out = [f"<!-- Generated by tools/make_config.py ({what}); do not edit. -->",
           '<lang name="English" official="false">']
    out += [f'\t<string name="{k}">{x(v)}</string>' for k, v in strings]
    return "\n".join(out + ["</lang>", ""])


def mod_strings(mod: str, c: dict) -> list[tuple[str, str]]:
    s = [(f"hwp.cfg.{mod}", c.get("title") or info_name(mod)), (f"hwp.cfg.{mod}.about", c.get("about", ""))]
    if c.get("always_on"):
        s.append((f"hwp.cfg.{mod}.always_on", c["always_on"]))
    for e in c.get("settings", []):
        if "option" in e:
            if e.get("about"):
                s.append((f"hwp.cfg.o.{e['option']}.about", e["about"]))
            continue
        k = e["key"]
        s.append((f"hwp.cfg.s.{k}", e["title"]))
        if e.get("about"):
            s.append((f"hwp.cfg.s.{k}.about", e["about"]))
        for i, label in enumerate(e.get("labels", [])):
            s.append((f"hwp.cfg.s.{k}.v{i}", label))
    return s


def doc(pk, mods) -> str:
    out = ["# Settings", "",
           "Generated by `tools/make_config.py` from the modules' `config` blocks (`docs/modules.md`,",
           "Settings). Every one is on the HammerwatchPlus tab of the player menu and can be set with",
           "`hwp set <key> <value>`. Host: in a lobby the host's value rules. Level: takes effect on the",
           "next level.", ""]
    for p in pk["packages"]:
        out += [f"## {strip_prefix(p['name'])}", "", "| Module | Setting | Key | Default | Choices | Scope |",
                "|---|---|---|---|---|---|"]
        for mod in p["mods"]:
            c = mods[mod]
            title = c.get("title") or info_name(mod)
            scope = lambda e: ("host" if e.get("scope", c.get("scope", "host")) == "host" else "local") + \
                (", level" if e.get("applies", c.get("applies", "now")) == "level" else "")
            if c.get("toggle"):
                out.append(f"| {title} | On | `{c['toggle']}` | on | on, off | {scope({})} |")
            else:
                out.append(f"| {title} | always on: {c.get('always_on', '')} | | | | |")
            for e in c.get("settings", []):
                if "option" in e:
                    out.append(f"| {title} | (option `{e['option']}`) | | | | local |")
                    continue
                if "values" in e:
                    ch = ", ".join(f"{lab} ({v})" for v, lab in zip(e["values"], e["labels"])) if e.get("labels") \
                        else ", ".join(f"{v}{e.get('suffix', '')}" for v in e["values"])
                elif e["type"] == "bool":
                    ch = "on, off"
                else:
                    ch = f"{e['min']} to {e['max']}, step {e['step']}{e.get('suffix', '')}"
                d = ("on" if e["default"] else "off") if e["type"] == "bool" else f"{e['default']}{e.get('suffix', '')}"
                out.append(f"| {title} | {e['title']} | `{e['key']}` | {d} | {ch} | {scope(e)} |")
        out.append("")
    return "\n".join(out)


def outputs(pk, mods) -> dict[Path, str]:
    files = {SVAL: sval(pk, mods), DOC: doc(pk, mods),
             LIB_LANG: lang([(f"hwp.cfg.pkg.{p['id']}", strip_prefix(p["name"])) for p in pk["packages"]],
                            "the package titles")}
    for mod, c in mods.items():
        files[mod_lang(mod)] = lang(mod_strings(mod, c), f"mods/{mod}/module.json config")
    return files


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--check", action="store_true")
    g.add_argument("--validate", action="store_true")
    a = ap.parse_args(argv)
    pk, mods = load()
    errors = validate(pk, mods)
    for e in errors:
        print("CONFIG", e)
    if errors:
        return 1
    if a.validate:
        print(f"ok: {len(mods)} modules")
        return 0
    stale = []
    for path, text in outputs(pk, mods).items():
        if path.is_file() and path.read_text(encoding="utf-8") == text:
            continue
        if a.check:
            stale.append(str(path.relative_to(REPO)))
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
        print("wrote", path.relative_to(REPO))
    if stale:
        print("stale (run python tools/make_config.py):", ", ".join(stale))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
