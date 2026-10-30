"""Issue #30: the HoH1 traps only on the trap map's floors (campaign.trap_map) and the Forsaken Tower.

Counts the HWP trap glyphs on the floor (`gl unitsof`; only the hwp_traps prefabs place them)
and the spike floors and flame jets (vanilla also puts those in a few themed rooms, so they
are reported, not asserted). kwargs: traps (true: the floor should have the HWP glyphs or the
log's placed count above 0; false: no glyph, placed 0).

With traps, the log's `traps: kinds` line must show a mix: no kind over its max-num
(campaign_prefabs.sval) and, from 10 traps up, at least 3 kinds. Before the fix one
PlacePrefabs call could fill a floor with spikes_1 alone."""
import re
from pathlib import Path

DEFS = Path(__file__).resolve().parents[2] / "mods" / "campaign" / "tweak" / "hwp" / "campaign_prefabs.sval"
GLYPHS = [f"doodads/hwp/traps/hwp_glyph_{g}.unit" for g in ("bomb", "dart", "confusion")]
VANILLA = ["doodads/hwp/traps/hwp_plate_spikes.unit", "doodads/traps/floors/floor_fire.unit"]
# max-num of each hwp_traps prefab, read from campaign_prefabs.sval (-1: none)
CAPS = {m.group(1): int(m.group(2)) for m in re.finditer(
    r'<string name="id">prefabs/hwp/traps/(\w+)\.pfb</string>\s*<string name="theme">hwp_traps</string>\s*<int name="max-num">(-?\d+)</int>',
    DEFS.read_text(encoding="utf-8"))}


def run(p, traps=True, **_):
    g = p.game
    placed = re.findall(r"traps: placed (\d+)/(\d+) on a \d+x\d+ floor \([^)]*mission ([a-z_0-9]+)", g.read_log())
    last = placed[-1] if placed else ("-1", "-1", "?")
    r = g.gl_cmd("unitsof", *(GLYPHS + VANILLA))
    counts = {u.split("/")[-1]: (r.get(u) or {}).get("count", 0) for u in GLYPHS + VANILLA}
    glyphs = sum(counts[u.split("/")[-1]] for u in GLYPHS)
    lines = re.findall(r"traps: kinds (.*)", g.read_log())
    kinds = {}
    for part in (lines[-1].strip().split(", ") if lines else []):
        name, _, n = part.rpartition(" ")
        kinds[name] = int(n)
    over = {k: n for k, n in kinds.items() if CAPS.get(k, -1) >= 0 and n > CAPS[k]}
    if traps:
        ok = int(last[0]) > 0 and sum(kinds.values()) == int(last[0]) and not over             and (int(last[0]) < 10 or len(kinds) >= 3)
    else:
        ok = int(last[0]) == 0 and glyphs == 0
    return {"ok": ok, "placed": int(last[0]), "wanted": int(last[1]), "mission": last[2], "glyphs": glyphs,
            "kinds": kinds, "over_cap": over,
            "terminal": f"placed {last[0]}/{last[1]} on {last[2]}; kinds {kinds}; units {counts}"}
