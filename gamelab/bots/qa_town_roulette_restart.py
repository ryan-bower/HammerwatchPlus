"""Actual lab process restart: pending stakes return to town exactly once.
Do not execute from an ignored path; root installs and runs the scenario in lab.
"""
import time

from gamelab.bots.fix_roulette import Checks as Base
from gamelab.bots.qa_town_economy_oracle import assess


class Checks(Base):
    def owed(self):
        reply = self.gl("inspect", "town", "hwp")
        if reply.get("ok") is not True or reply.get("truncated"):
            raise RuntimeError("town hwp readback is unavailable/truncated")
        value = reply.get("value")
        if not isinstance(value, dict):
            raise RuntimeError("town hwp is not a dictionary")
        return value.get("roulette.owed", 0)

    def identity(self):
        row = self.gl("state")
        player = row.get("player") or {}
        return row.get("phase") == "town" and player.get("name") == "GameLab" and player.get("class") == "paladin"

    def prepare(self):
        # Begin a fresh20s window so shutdown cannot accidentally settle the stake.
        self.hwp("set roulette.enabled 0", 0.2)
        self.hwp("set roulette.enabled 1", 0.2)
        self.set_gold(50000)
        phase = self.wait_phase(0)
        if not phase or int(phase[1]) != 0:
            raise RuntimeError("no betting phase")
        self.hwp("roulette clear", 0.2)
        before = self.gold()
        self.hwp("roulette bet black 7000", 0.2, until="on black")
        after = self.gold()
        owed = self.owed()
        self.flag("restart_pending_stake", self.identity() and before == 50000
                  and after == 43000 and owed == 7000, f"gold{before}->{after}; owed{owed}")
        # Explicit normal save, then scenario WM_CLOSE/restart. No setter follows this.
        saved = self.gl("save")
        self.flag("restart_saved", saved.get("ok") is True, str(saved))

    def verify(self):
        # Capture identity/currency/owed before any mutation after the real process restart.
        first = dict(identity=self.identity(), gold=self.gold(), owed=self.owed())
        time.sleep(1.2)
        second = dict(identity=self.identity(), gold=self.gold(), owed=self.owed())
        self.flag("restart_refund_once", first == second
                  and first == dict(identity=True, gold=50000, owed=0), str((first, second)))


def run(p, stage, required_flags):
    c = Checks(p)
    try:
        getattr(c, stage)()
    except Exception as exc:
        c.flag(stage + "_crashed", False, repr(exc))
    c.out.update(assess(c.out, required_flags))
    c.out.update(notes=c.notes, terminal=" | ".join(c.notes)[-3000:])
    return c.out
