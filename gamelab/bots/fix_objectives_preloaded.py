"""Issue #27: on a floor the preloader generated (the host's records rebuilt from the units,
AdoptFromUnits), both levers work. Reads the 'floor not generated here' line, uses the vault
lever (the vault opens, its door units flip) and the exit lever (the sealed exits open),
and checks the exits were sealed before and enabled after. Teleports are measurement."""
import re
import time

from gamelab.bots.plan_checks import Checks
from gamelab.bots.fix_objectives import wait_log, exits

ADOPT = re.compile(r"\[HWP:objectives\] floor not generated here \(preloaded or from a save\): (?P<n>\d+) vault\(s\) and "
                   r"exit switch yes at (?P<ex>-?\d+),(?P<ey>-?\d+) taken from the units, vault 0 door -?\d+,-?\d+ "
                   r"switch (?P<sx>-?\d+),(?P<sy>-?\d+)")


def run(p, **kwargs):
    c = Checks(p)
    g = c.g
    m = None
    for line in g.read_log().splitlines():
        if "[preload]" not in line and ADOPT.search(line):
            m = ADOPT.search(line)
    c.flag("adopted", m is not None, m.group(0) if m else "no 'floor not generated here' line with a vault and an exit switch")
    if m is None:
        return c.out
    switch = (int(m.group("sx")), int(m.group("sy")))
    exit_sw = (int(m.group("ex")), int(m.group("ey")))
    total, enabled = exits(c)
    c.flag("exits_sealed", total > 0 and enabled == 0, f"{enabled} of {total} enabled")

    mark = len(g.read_log())
    c.gl("teleport", switch[0], switch[1] + 20)
    time.sleep(0.4)
    r = c.gl("use", "objective_switch")
    c.flag("vault_switch_used", bool(r.get("ok")) and "objective_switch" in str(r.get("unit", "")), str(r)[:120])
    hit = wait_log(c, r"\[HWP:objectives\] vault 0 opened by ", mark)
    c.flag("vault_opened", hit is not None, hit.group(0) if hit else "no 'vault 0 opened by' line")
    hit = wait_log(c, r"\[HWP:objectives\] vault 0 doors opened \((\d+) unit\(s\) found of (\d+)\)", mark)
    c.flag("vault_doors_flipped", hit is not None and int(hit.group(1)) > 0 and hit.group(1) == hit.group(2),
           hit.group(0) if hit else "no 'doors opened' line")
    bad = wait_log(c, r"\[HWP:objectives\] vault switch used at .* matches no vault", mark, timeout=0.5)
    c.flag("no_unmatched_lever", bad is None, bad.group(0) if bad else "")

    mark = len(g.read_log())
    c.gl("teleport", exit_sw[0], exit_sw[1] + 20)
    time.sleep(0.4)
    r = c.gl("use", "objective_exit_switch")
    c.flag("exit_switch_used", bool(r.get("ok")) and "objective_exit_switch" in str(r.get("unit", "")), str(r)[:120])
    hit = wait_log(c, r"\[HWP:objectives\] exits open: (\d+)", mark)
    c.flag("exits_opened", hit is not None and int(hit.group(1)) == total, hit.group(0) if hit else "no 'exits open' line")
    time.sleep(0.5)
    total2, enabled2 = exits(c)
    c.flag("exits_enabled", total2 > 0 and enabled2 == total2, f"{enabled2} of {total2} enabled")
    c.out["notes"] = c.notes
    return c.out
