"""The Devil Forgemaster's icons, round 4: the Heresy 5+ status, the user's kept round-1 pick
(sp_pri.py's b: the red-hot eye with rays) with its purple swapped for the necrotic green
(their round-3 note). The only purple in it is the eye's round. --finals also writes round 3's
four settled picks to art/specs/override/.

    python tools/icon_art/sp_pri4.py [--picker]    # out/specs/pri4/, ids specsP4.<name>
    python tools/icon_art/sp_pri4.py --finals      # round 3's settled picks to art/specs/override/
    python tools/icon_art/sp_pri4.py --pick FILE   # the pick to art/specs/override/
"""
import json
import math
import sys
from pathlib import Path
from PIL import Image
from sp import *   # noqa: F401,F403 (the grounds, ramps and motifs)
import sp
from sp_pri import HERESY5
from sp_pri3 import eye, NSCLERA

OUT = sp.HERE / "out" / "specs" / "pri4"
R1 = sp.HERE / "out" / "specs" / "pri"
R3 = sp.HERE / "out" / "specs" / "pri3"
# Round 3 (specsP3.<name>, 2026-10-22), settled with no note.
FINALS = {"pri_call_of_heresy": "a", "pri_pyre_sacrifice": "b", "hud_heresy": "a", "hud_devouring": "b"}


def hud_heresy_5():
    # round-1 b exactly, the eye's purple round swapped: the darkest green (the one hud_heresy
    # uses); a step lighter; lighter again, so the round still shows inside the glow
    out = []
    for sclera in (NSCLERA, R("081410", "10241a", "1a3a28", "2a5a3c"), R("0a1a12", "143222", "205036", "30704a")):
        ic = S("priest", (7, 7))
        ic.glow(7, 7, 7, "f04010", 0.7)
        for k in range(8):
            a = math.radians(k * 45 + 22.5)
            ic.energy(seg(7 + math.cos(a) * 4.8, 7 + math.sin(a) * 4.0, 7 + math.cos(a) * 6.6, 7 + math.sin(a) * 6.2, 0.35, 0.2), HERESY5, falloff=0.3)
        eye(ic, 7, 7, 1.0, HERESY5, sclera, open_=1.25)
        out.append(ic)
    return out


ITEMS = [("hud_heresy_5", "Heresy, 5+ (status)",
          "Your kept round-1 pick with its purple (the eye's round) swapped for the green: A the darkest green, as below 5 uses; "
          "B and C lighter, so the round shows inside the red glow. 14x14, shown at its size.")]


def now(n):
    return Image.open(R1 / f"{n}_b.png").convert("RGBA")


def render():
    OUT.mkdir(parents=True, exist_ok=True)
    ims = [ic.done() for ic in hud_heresy_5()]
    for k, im in zip("abc", ims):
        im.save(OUT / f"hud_heresy_5_{k}.png")
    sheet([("hud_heresy_5", ims + [now("hud_heresy_5")])], OUT / "sheet_priest.png")


def picker():
    its = [{"id": "specsP4." + n, "name": lab, "key": n, "desc": what,
            "imgs": dict({k: sp.uri(Image.open(OUT / f"{n}_{k}.png")) for k in "abc"}, now=sp.uri(now(n)))} for n, lab, what in ITEMS]
    groups = [{"id": "specsP4.priest", "title": "Priest: Devil Forgemaster, round 4", "items": its}]
    tpl = (sp.HERE / "picker_tpl.html").read_text(encoding="utf-8").replace("Skill Icon Picks", "Spec Icon Picks")
    assert "/*DATA*/null" in tpl
    page = OUT / "picker.html"
    page.write_text(tpl.replace("/*DATA*/null", json.dumps(groups)), encoding="utf-8")
    return page


def save(n, im):
    assert im.size == ((14, 14) if n.startswith("hud_") else (24, 24)), (n, im.size)
    im.save(sp.OVR / f"{n}.png")
    print("wrote", sp.OVR / f"{n}.png")


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["--finals"]:
        for n, k in FINALS.items():
            save(n, Image.open(R3 / f"{n}_{k}.png").convert("RGBA"))
    elif a[:1] == ["--pick"]:
        for k, v in json.loads(Path(a[1]).read_text(encoding="utf-8")).items():
            c = v.get("choice") if isinstance(v, dict) else v
            if c in ("a", "b", "c"):
                save("hud_heresy_5", Image.open(OUT / f"hud_heresy_5_{c}.png").convert("RGBA"))
    else:
        render()
        if "--picker" in a:
            print(picker())
