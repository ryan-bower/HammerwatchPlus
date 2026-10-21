"""Writes the class planner's HoH1 row: planner/data/classes/hoh1_<cls>.json for the six
original HoH1 classes that HoH2 remade (Paladin, Priest, Ranger, Sorcerer, Warlock, Wizard).

python tools/planner_hoh1.py [--check]

Reads the HoH1 install read-only (res/assets.bin and res/language/english.lang, found by
gamepaths.hoh1_dir). Each record is the HoH1 kit as HoH1 shipped it: the attack, three
actives and three passives, each with its HoH1 numbers per level, plus the HoH1 base and
per-level stats. The summaries below are our own paraphrase; only the numbers come from
HoH1 (HoH1 text and art are never committed). Gear is armor only: HoH1 had no weapons,
the attack is a skill. The kits have no orbs (HoH1 never had any); new orbs are planner
`mods` records whose `skill` is one of these skill ids.

--check exits 1 when a record on disk differs from what this would write."""
import json, re, sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gamepaths
import hwr_archive as hwr

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "planner/data/classes"

# HoH1 kit order in char.sval: the attack, three actives, three passives.
KINDS = ["active"] * 4 + ["passive"] * 3

# skill file stem -> (summary with {n} = the n-th number of the HoH1 level text, labels).
# A label is (name, unit); the numbers appear in the level text in this order.
KITS = {
 "paladin": dict(name="Paladin", order=21, gear=["chest_str_t1a", "feet_str_t1a"], skills={
  "sword": ("Swing your sword for {0} physical damage across a {1}° arc.", [("Damage", ""), ("Arc", "°")]),
  "charge": ("Dash forward; enemies you hit take {0} physical damage and are stunned for {1}s. Higher levels dash faster and farther.", [("Damage", ""), ("Stun", "s")]),
  "lay_on_hands": ("Allies around you get a {0}s blessing that heals {1} + {2}% of max health and gives a {3}% chance to block {4} magical damage.", [("Duration", "s"), ("Heal", ""), ("Heal of max health", "%"), ("Block chance", "%"), ("Magical blocked", "")]),
  "whirlwind": ("Spin for {1}s, dealing {0} physical damage to every enemy around you.", [("Damage", ""), ("Duration", "s")]),
  "shield": ("Your shield stops most projectiles in a {0}° arc in front of you, and has a {1}% chance to block {2} physical damage.", [("Arc", "°"), ("Block chance", "%"), ("Physical blocked", "")]),
  "stunning_blows": ("Sword hits have a {0}% chance to stun for {1}s.", [("Chance", "%"), ("Stun", "s")]),
  "flames_of_devotion": ("Each Sword hit adds {0} magical damage to all your skills, up to {1} stacks of {2}s each.", [("Magical per stack", ""), ("Max stacks", ""), ("Stack duration", "s")]),
 }),
 "priest": dict(name="Priest", order=22, gear=["chest_int_t1a", "feet_int_t1a"], skills={
  "smite": ("A short-range blast for {0} hybrid damage; the area grows with level.", [("Damage", "")]),
  "holy_light": ("A beam that builds up to {0} magical damage on an enemy, or heals an ally for {1} + {2}% of max health.", [("Damage", ""), ("Heal", ""), ("Heal of max health", "%")]),
  "consecrated_ground": ("Consecrate the ground for {0}s: enemies in it take {1} magical damage per second, and {2}% of that heals allies standing in it.", [("Duration", "s"), ("Damage per second", ""), ("Returned as healing", "%")]),
  "aura": ("An aura for {2}s: nearby enemies are slowed and lose resistance by {0}%, and allies in it take {1}% less damage.", [("Slow and resistance cut", "%"), ("Ally damage reduction", "%"), ("Duration", "s")]),
  "divine_protection": ("A shield absorbs {0}% of incoming damage, paid for at {1} mana per point absorbed.", [("Absorbed", "%"), ("Mana per damage", "")]),
  "remedy": ("All healing you receive is {0}% more effective.", [("Healing received", "%")]),
  "celestial_orb": ("{0} orbs circle you and fire beams for {1} magical damage, following Holy Light's target.", [("Orbs", ""), ("Damage", "")]),
 }),
 "ranger": dict(name="Ranger", order=23, gear=["chest_dex_t1a", "feet_dex_t1a"], skills={
  "bow": ("An arrow for {0} physical damage that pierces up to {1} enemies; you move {2}% slower while shooting.", [("Damage", ""), ("Pierce", ""), ("Move slow", "%")]),
  "flurry_of_arrows": ("Spin and loose {0} Bow Shot arrows in every direction.", [("Arrows", "")]),
  "grasping_roots": ("Roots hold every enemy around you for {0}s and cut their armor by {1}%.", [("Root", "s"), ("Armor cut", "%")]),
  "powershot": ("Charge {0} arrows for up to {1} magical damage that ignore {2}% resistance; a full charge takes {3}s and adds range and speed.", [("Arrows", ""), ("Damage", ""), ("Resistance ignored", "%"), ("Full charge", "s")]),
  "on_the_prowl": ("Casting a skill gives {1}% movement speed and {2}% evasion for {0}s.", [("Duration", "s"), ("Move speed", "%"), ("Evasion", "%")]),
  "marked_prey": ("Bow Shot has a {0}% chance to crit and Mark the target for {1}s; Marked enemies take a critical hit from any source {2}% of the time.", [("Chance", "%"), ("Mark", "s"), ("Crit taken", "%")]),
  "twinned_arrows": ("Bow Shot arrows have a {0}% chance to split and seek another target.", [("Split chance", "%")]),
 }),
 "sorcerer": dict(name="Sorcerer", order=24, gear=["chest_int_t1a", "feet_int_t1a"], skills={
  "frost_shard": ("A shard for {0} hybrid damage that ricochets off walls and enemies up to {1} times, +{2}% damage per bounce.", [("Damage", ""), ("Ricochets", ""), ("Per bounce", "%")]),
  "comet": ("A comet lands in front of you: {0} hybrid damage split among the enemies hit, who freeze for {1}s.", [("Damage", ""), ("Freeze", "s")]),
  "frost_nova": ("{0} frost balls burst out in every direction for {1} hybrid damage each.", [("Frost balls", ""), ("Damage", "")]),
  "orb_of_winter": ("A slow ice orb drifts forward for {0}s, spraying shards for {1} hybrid damage.", [("Duration", "s"), ("Damage", "")]),
  "biting_chill": ("Your skills slow by {0}% for {1}s and have a {2}% chance to freeze for {3}s.", [("Slow", "%"), ("Slow duration", "s"), ("Freeze chance", "%"), ("Freeze", "s")]),
  "ice_barrier": ("Casting a skill adds a barrier for {0}s that cuts one hit's damage by {1}%; up to {2} barriers.", [("Duration", "s"), ("Reduction", "%"), ("Max barriers", "")]),
  "shatter": ("Frozen enemies you kill burst for {0} hybrid damage to enemies near them.", [("Damage", "")]),
 }),
 "warlock": dict(name="Warlock", order=25, gear=["chest_int_t1a", "feet_int_t1a"], skills={
  "soul_dagger": ("A short stab that applies Soul Consumption, {0} magical damage per second for {1}s; you regain {2}% of it as health and {3}% as mana.", [("Damage per second", ""), ("Duration", "s"), ("Health back", "%"), ("Mana back", "%")]),
  "lightning_bolt": ("A bolt that chains to {0} targets for {1} magical damage each.", [("Targets", ""), ("Damage", "")]),
  "summon_gargoyle": ("Summon a gargoyle for {1}s that shoots lightning for {0} magical damage; nearby gargoyles link with a static beam for {2}% damage that stuns. Up to {3} at once.", [("Damage", ""), ("Duration", "s"), ("Link damage", "%"), ("Max gargoyles", "")]),
  "eye_of_the_storm": ("A storm follows you for {1}s and strikes nearby enemies for {0} magical damage; it links with gargoyles.", [("Damage", ""), ("Duration", "s")]),
  "extended_domain": ("All your skills reach {0}% farther.", [("Range", "%")]),
  "soul_cleaver": ("Soul Consumption victims pass {0}% of their damage taken to nearby enemies, and spread Soul Consumption when they die {1}% of the time.", [("Damage spread", "%"), ("Spread on death", "%")]),
  "stormlash": ("Each lightning bolt has a {0}% chance to fire another at {1}% damage.", [("Chance", "%"), ("Damage", "%")]),
 }),
 "wizard": dict(name="Wizard", order=26, gear=["chest_int_t1a", "feet_int_t1a"], skills={
  "fireball": ("A fireball for {0} magical damage in a small area; range and area grow with level.", [("Damage", "")]),
  "fire_breath": ("Breathe fire in a forward cone, {0} magical damage per hit.", [("Damage per hit", "")]),
  "blast_wave": ("A blast around you for {0} magical damage that confuses and slows enemies by {1}% for {2}s and destroys most projectiles.", [("Damage", ""), ("Slow", "%"), ("Duration", "s")]),
  "meteor_shower": ("{0} meteors fall around you for {1} hybrid damage.", [("Meteors", ""), ("Damage", "")]),
  "combustion": ("Your skills set enemies burning for {0} magical damage per second over {1}s.", [("Damage per second", ""), ("Duration", "s")]),
  "flame_shield": ("A shield cuts one hit's damage by {0}% and sets off your Blast Wave; it recharges in {1}s.", [("Reduction", "%"), ("Recharge", "s")]),
  "scorched_earth": ("Your skills leave burning ground for {0} magical damage per second; level 2 also doubles how long it burns.", [("Damage per second", "")]),
 }),
}

WORDS = {"two": "2", "three": "3", "four": "4", "five": "5", "six": "6"}
NUM = re.compile(r"\d+(?:\.\d+)?")


def numbers(text: str) -> list:
    text = re.sub(r"\\c[0-9a-fA-F]{6}|\\d", "", text)   # colour codes carry hex digits
    text = re.sub(r"\b(" + "|".join(WORDS) + r")\b", lambda m: WORDS[m.group(1).lower()], text, flags=re.I)
    return NUM.findall(text)


def level_dicts(sval: str) -> list:
    """The per-level dicts of a HoH1 skill sval (skills array, index 0 is <null/>)."""
    root = ET.fromstring(sval)
    arr = next(a for a in root if a.tag == "array" and a.get("name") == "skills")
    return [d for d in arr if d.tag == "dict"]


def top(d, name):
    for x in d:
        if x.get("name") == name and x.tag in ("int", "float"):
            return float(x.text)
    return None


def fmt(v: float) -> str:
    return str(int(v)) if v == int(v) else f"{v:g}"


def build(archive, lang) -> dict:
    out = {}
    for cls, kit in KITS.items():
        char = ET.fromstring(archive.read_file(f"players/{cls}/char.sval").decode("utf-8", "replace"))
        files = [s.text for a in char if a.get("name") == "skills" for s in a]
        st = {x.get("name"): float(x.text) for x in char if x.tag == "float"}
        base = []
        for i, f in enumerate(files):
            stem = Path(f).stem
            summary, labels = kit["skills"][stem]
            sval = archive.read_file(f).decode("utf-8", "replace")
            key = re.search(r'name="name">\.?([^<]+)<', sval).group(1)
            levels = []
            for n, d in enumerate(level_dicts(sval), 1):
                if f"{key}.{n}" not in lang: break   # a few svals carry a level HoH1 never sold or described
                nums = numbers(lang[f"{key}.{n}"])
                if len(nums) < len(labels):   # a later level adds a clause (Crippling Net style)
                    raise SystemExit(f"{f} level {n}: {len(nums)} numbers for {len(labels)} labels")
                vals = [v + u for v, (_, u) in zip(nums, labels)]
                params = [[name, v] for (name, _), v in zip(labels, vals)]
                mana, cd = top(d, "mana-cost"), top(d, "cooldown")
                if mana: params.append(["Mana Cost", fmt(mana)])
                if cd: params.append(["Cooldown", fmt(cd / 1000) + "s"])
                levels.append({"params": params, "q": "common", "text": summary.format(*nums)})
            base.append({"class": d.find("string[@name='class']").text if d.find("string[@name='class']") is not None else "",
                         "desc": summary.format(*["#"] * len(labels)), "file": f, "hoh1_file": f,
                         "id": f"hoh1_{cls}_{stem}", "kind": KINDS[i], "levels": levels, "mods": [],
                         "name": lang[key], "port": "HoH1", "summon": False,
                         "type": "Attack" if i == 0 else "Passive" if KINDS[i] == "passive" else "Spell"})
        names = [s["name"] for s in base]
        out[f"hoh1_{cls}"] = {
            "base": base, "cut": [],
            "desc": (f"The {kit['name']} as HoH1 shipped it, parked for later. {names[0]} is the attack (a skill: "
                     f"HoH1 had no weapons, so this kit starts with armor only); {', '.join(names[1:4])} are the actives; "
                     f"{', '.join(names[4:])} the passives. HoH1 had no orbs: add new ones on any skill here."),
            "gear": kit["gear"], "name": kit["name"] + " (HoH1)", "order": kit["order"], "port": "HoH1",
            "row": "hoh1", "specs": [], "status": "idea",
            "stats": {"health": fmt(st["base-health"]) + " (+" + fmt(st["level-health"]) + "/lv)",
                      "mana": fmt(st["base-mana"]) + " (+" + fmt(st["level-mana"]) + "/lv)",
                      "armor": fmt(st["base-armor"]) + " (+" + fmt(st["level-armor"]) + "/lv)",
                      "resistance": fmt(st["base-resistance"]) + " (+" + fmt(st["level-resistance"]) + "/lv)",
                      "health regen": fmt(st["base-health-regen"]) + " (+" + fmt(st["level-health-regen"]) + "/lv)",
                      "mana regen": fmt(st["base-mana-regen"]) + " (+" + fmt(st["level-mana-regen"]) + "/lv)"},
            "vanilla": True}
    return out


def main():
    check = "--check" in sys.argv
    game = gamepaths.hoh1_dir()
    archive = hwr.Archive.read(game / "res" / "assets.bin")
    text = (game / "res" / "language" / "english.lang").read_text(encoding="utf-8-sig")
    lang = dict(re.findall(r'<string name="([^"]+)">(.*?)</string>', text, re.S))
    stale = []
    for rid, rec in build(archive, lang).items():
        path = OUT / f"{rid}.json"
        body = json.dumps(rec, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
        if check:
            if not path.exists() or path.read_text(encoding="utf-8") != body: stale.append(path.name)
        else:
            path.write_text(body, encoding="utf-8", newline="\n")
            print("wrote", path.relative_to(REPO))
    if stale:
        print("stale:", ", ".join(stale)); sys.exit(1)


if __name__ == "__main__":
    main()
