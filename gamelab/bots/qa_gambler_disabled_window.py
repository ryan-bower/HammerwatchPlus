"""Legal single-player open-menu disable reproduction; no production method calls."""
import time

from gamelab.bots.plan_checks import Checks
from gamelab.bots.qa_town_economy_oracle import assess, equipment_identity


def run(p):
    c = Checks(p)
    required = ["disabled_fixture", "disabled_window_open", "disabled_setting_readback",
                "disabled_no_gold_or_item_change", "disabled_window_closed",
                "reenabled_single_npc", "reenabled_one_gold_charge"]
    try:
        c.set_gold(100000)
        c.hwp("tokens 3", 0.2)
        equipped = c.gl("kit", 1, "rare", "mainhand_mace_01", "seed=20261030")
        actual_item = c.gl("bagitems").get("main") or {}
        item_ok = (actual_item.get("id") == "mainhand_mace_01" and actual_item.get("quality") == 4
                   and actual_item.get("ilvl") == 1)
        c.flag("disabled_fixture", equipped.get("ok") is True and item_ok, str((equipped, actual_item)))
        if equipped.get("ok") is not True or not item_ok:
            raise RuntimeError("native equipment prerequisite failed")
        opened = c.gl("use", "hwp_gambler")
        window = c.gl("state").get("window") or ""
        c.flag("disabled_window_open", opened.get("ok") is True and "HWPGamblerMenu" in window, window)
        if opened.get("ok") is not True or "HWPGamblerMenu" not in window:
            raise RuntimeError("native Gambler window prerequisite failed")
        def token_balance():
            reply = c.gl("inspect", "player", "hwp")
            if reply.get("ok") is not True or reply.get("truncated"):
                raise RuntimeError("token save readback refused/truncated")
            return reply.get("value", {}).get("bet_tokens", 0)
        before_gold, before_item, before_tokens = c.gold(), equipment_identity(c.gl("qa_item_identity", "mainhand_mace_01")), token_balance()
        # Host-owned setting command; no synthetic RPC peer or direct GameShop method.
        c.hwp("set gambler.enabled 0", 0.2)
        setting = c.hwp("get gambler.enabled", 0.2)
        c.flag("disabled_setting_readback", "gambler.enabled" in setting
               and ("= 0" in setting or ": 0" in setting or "false" in setting.lower()), setting)
        # func is the existing widget event API. If the menu closed, no action can run.
        # A stale enabled menu on baseline remains usable; each mutation is sent only once.
        for action in ("reroll", "reroll-tokens", "play"):
            if "HWPGamblerMenu" in (c.gl("state").get("window") or ""):
                c.gl("func", action)
                time.sleep(0.8)
        after_gold, after_item, after_tokens = c.gold(), equipment_identity(c.gl("qa_item_identity", "mainhand_mace_01")), token_balance()
        c.flag("disabled_no_gold_or_item_change", after_gold == before_gold and after_item == before_item
               and after_tokens == before_tokens == 3,
               f"gold{before_gold}->{after_gold}; tokens{before_tokens}->{after_tokens}; item{before_item}->{after_item}")
        c.flag("disabled_window_closed", "HWPGamblerMenu" not in (c.gl("state").get("window") or ""),
               str(c.gl("state").get("window")))
        c.hwp("set gambler.enabled 1", 0.2)
        time.sleep(1.5)
        units = c.gl("unitsof", "actors/npcs/town/hwp_gambler.unit").get("actors/npcs/town/hwp_gambler.unit", {}).get("units", [])
        c.flag("reenabled_single_npc", len(units) == 1, str(units))
        c.gl("use", "hwp_gambler")
        before = c.gold()
        c.gl("press", "reroll-btn")
        time.sleep(0.8)
        c.flag("reenabled_one_gold_charge", before - c.gold() == 2000, f"gold{before}->{c.gold()}")
    except Exception as exc:
        c.flag("disabled_case_crashed", False, repr(exc))
    finally:
        # Best-effort cleanup does not hide a failing readback or mutation row.
        c.g.console("hwp set gambler.enabled 1")
    c.out.update(assess(c.out, required))
    c.out.update(notes=c.notes, terminal=" | ".join(c.notes)[-3000:])
    return c.out
