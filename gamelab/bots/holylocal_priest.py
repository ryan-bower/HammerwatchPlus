"""The Priest in character creation. With mods/holylocal enabled (the `dlc has holy` conditional
removed from the class and its weapons) the create-character class list offers the Priest, it can be
selected, and "create" makes a Priest character; without it the list has no Priest (the lab's game
has no Celestial Ruins DLC). Flags are prefixed by `tag` (with / without) so one scenario's expect
can read either side."""
import json
import time

from gamelab.bots.plan_checks import Checks


class Priest(Checks):
    def class_ids(self):
        """The class ids the create-character class list offers (the class widgets are SetID(class id),
        CreateCharacterClass.as), with the list's visible titles."""
        w = self.gl("widgets", 6)
        ids = []
        for root in w.get("roots") or []:
            if "CreateCharacter" not in (root.get("root") or ""):
                continue
            nodes = root.get("nodes") or []
            in_list = False
            for n in nodes:
                if n.get("id") == "class-list":
                    in_list, depth = True, n.get("d", 0)
                    continue
                if in_list:
                    if n.get("d", 0) <= depth:
                        in_list = False
                    elif n.get("d", 0) == depth + 1 and n.get("id"):
                        ids.append(n["id"])
        return ids

    def title(self):
        w = self.gl("widgets", 6)
        for root in w.get("roots") or []:
            for n in root.get("nodes") or []:
                if n.get("id") == "class-title":
                    return n.get("text", "")
        return ""

    def run(self, tag, want):
        self.gl("charcreate")
        time.sleep(1.0)
        ids = self.class_ids()
        listed = "priest" in ids
        self.flag(f"{tag}_window", bool(ids), f"the create-character class list: {ids}")
        self.flag(f"{tag}_priest_listed", listed == want, f"priest {'in' if listed else 'not in'} {ids} (want {'in' if want else 'out'})")
        if not want:
            self.g.shot(f"{tag}_classlist", settle=False)
            self.g.key("escape")
            time.sleep(0.5)
            return
        self.gl("func", "select", "priest")
        time.sleep(0.4)
        t = self.title()
        self.flag(f"{tag}_priest_selected", t.lower() == "priest", f"class title after 'select priest': {t!r}")
        self.g.shot(f"{tag}_priest_selected", settle=False)
        self.gl("func", "name-random")          # the name field must not be empty for "create"
        time.sleep(0.3)
        self.gl("func", "create")               # CreateCharacterWindow.OnFunc "create": PlayerRecord.CreateCharacter + SpawnLocalPlayers
        time.sleep(3.0)
        st = self.gl("state")
        plr = st.get("player") or {}
        self.flag(f"{tag}_priest_created", plr.get("class") == "priest" and (plr.get("level") or 0) >= 1 and not st.get("window"),
                  f"after create: class {plr.get('class')!r} level {plr.get('level')} window {st.get('window')!r}")
        self.g.shot(f"{tag}_priest_in_town", settle=False)


def run(p, tag="with", want=True, **_):
    c = Priest(p)
    c.run(tag, bool(want))
    c.out["notes"] = c.notes
    return c.out
