"""Native solo item-link entry points; chat rendering needs separate image review.

No menu-context hook, chat/event injector, or persistent chat probe is added.
Loot-log events prove native linking, not the HWP persistent chat line. The saved
images must be reviewed before crediting that line, its slot/ilvl, or colours.
"""
import re
import time

from gamelab.bots.plan_gear import Checks as GearChecks
from gamelab.hps import hash_string


def event_matches(reply, name, colour):
    if reply.get("ok") is not True or not name or not re.fullmatch(r"[0-9a-fA-F]{6}", colour or ""):
        return False
    return any(a.get("hud") in ("LootLog", "LootLog::LootLog") and "show" in a.get("text", "").lower()
               and ("\\c" + colour + "[" + name + "]") in a.get("text", "")
               for a in reply.get("announces", []))


class Checks(GearChecks):
    def __init__(self, pilot):
        super().__init__(pilot)
        self.receipts = []

    def equipped(self):
        r = self.gl("inspect", "player", "equipped")
        return r, r.get("value")

    def fixture(self, item, slot):
        receipt = self.gl("equip", item, "rare", 1)
        raw, items = self.equipped()
        self.menu()
        hover = self.hover("mainhand" if slot == 0 else "offhand")
        valid = (raw.get("ok") is True and receipt.get("ok") is True and receipt.get("ilvl") == 1
                 and isinstance(items, list) and len(items) == 7
                 and isinstance(items[slot], list) and len(items[slot]) >= 4
                 and int(items[slot][1]) & 0xffffffff == hash_string(item)
                 and items[slot][3] == 1 and hover.get("ok") is True
                 and hover.get("type") == 0 and bool(hover.get("item"))
                 and re.fullmatch(r"[0-9a-fA-F]{6}", hover.get("color", "")) is not None)
        self.flag(item + "_fixture", valid, str(dict(equip=receipt, native=raw, hover=hover)))
        self.close()
        return valid, hover

    def command(self, suffix, tag, hover):
        # Expire the previous six-second native loot announcement. No retry or
        # synthetic event can turn a missing command response into a pass.
        time.sleep(6.3)
        self.g.console("hwp link" + (" " + suffix if suffix else ""))
        deadline = time.monotonic() + 2
        reads = []
        while True:
            reply = self.gl("overlays")
            reads.append(reply)
            if event_matches(reply, hover.get("item"), hover.get("color")) or time.monotonic() >= deadline:
                break
            time.sleep(.1)
        self.flag(tag, event_matches(reply, hover.get("item"), hover.get("color")), str(reads))
        self.g.shot(tag + "_chat", settle=False)
        self.receipts.append(dict(case=tag, hovered_item=hover, native_announcements=reads,
                                  image=tag + "_chat.png", image_review="PENDING"))

    def solo(self):
        self.new_char("QAChatLinks")
        if not self.out.get("QAChatLinks_ready"):
            return
        self.flag("chat_requirements_enabled", self.req_cheat(False))
        # Equipping a native two-hander clears the off-hand by normal native
        # EquippedItems rules. Only fixture creation uses the existing equip verb.
        reset = self.gl("equip", "twohanded_shortbow_01", "common", 1)
        raw, items = self.equipped()
        empty = (reset.get("ok") is True and isinstance(items, list)
                 and len(items) == 7 and items[1] is None)
        self.flag("chat_empty_off_fixture", empty, str(raw))
        if not empty:
            return
        mark = len(self.g.read_log())
        self.g.console("hwp link off")
        deadline = time.monotonic() + 3
        while "Nothing equipped in that slot (off)." not in self.g.read_log()[mark:] and time.monotonic() < deadline:
            time.sleep(.1)
        self.flag("chat_empty_off_hint", "Nothing equipped in that slot (off)." in self.g.read_log()[mark:])
        self.g.shot("chat_empty_off_hint", settle=False)
        good, main = self.fixture("mainhand_longsword_01", 0)
        if not good:
            return
        self.command("", "chat_default_main_native_event", main)
        self.command("main", "chat_explicit_main_native_event", main)
        good, off = self.fixture("offhand_shield_01", 1)
        if not good:
            return
        self.command("off", "chat_explicit_off_native_event", off)
        # The original plan consumer drives actual menu context-down/up handlers
        # and requires the hovered bag item's native linked-item event/rarity.
        time.sleep(6.3)
        self.menu()
        context_item = self.hover("equipment-inventory", 0)
        self.close()
        self.chat_link()
        context_event = self.gl("overlays")
        self.flag("chat_inventory_context_fresh_native_event",
                  context_item.get("ok") is True and context_item.get("type") == 1
                  and event_matches(context_event, context_item.get("item"), context_item.get("color")),
                  str(dict(hover=context_item, native_event=context_event)))
        self.receipts.append(dict(case="chat_inventory_context_fresh_native_event",
                                  hovered_item=context_item, native_announcements=context_event,
                                  input_scope="Inherited posted bound key followed by native context-handler fallback if needed; binding success is not asserted.",
                                  image="chat_inventory_context.png", image_review="PENDING"))
        self.g.shot("chat_inventory_context", settle=False)


def run(p, **_):
    c = Checks(p)
    try:
        c.solo()
    except Exception as exc:
        c.flag("chatlinks_crashed", False, repr(exc))
    mandatory = ("QAChatLinks_ready", "chat_requirements_enabled", "chat_empty_off_fixture",
                 "chat_empty_off_hint", "mainhand_longsword_01_fixture", "offhand_shield_01_fixture",
                 "chat_default_main_native_event", "chat_explicit_main_native_event",
                 "chat_explicit_off_native_event", "link_event", "link_rarity_colour", "chat_inventory_context_fresh_native_event")
    return dict(**c.out, ok=all(c.out.get(k) is True for k in mandatory),
                mandatory=list(mandatory), receipts=c.receipts, notes=c.notes,
                persistent_chat_rendering="PENDING_IMAGE_REVIEW",
                limits="Solo controlled ilvl1 fixtures only. Head/chest/feet/hands/back commands, true co-op, other locales/resolutions and chat history lifecycle remain open.")
