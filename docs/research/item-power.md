# How much character power comes from items in HoH2?

2026-11-12. Vanilla source investigation, with reproducible analytical comparisons.
Repository baseline: `4cfbb3bf838661e36ecc94a35d031aa0d986a2fd`.
Repository game pin: Steam build **25932569 / Build 176** (`gamelab/build_id.json`).
Read the existing dump at `/home/colinthatcher/Projects/Friends/HammerwatchPlus/gamecode/sdk/hoh2`;
the new worktree does not contain a dump. The results file records the SHA-256 of
every input read. No new game launch, extraction, build-pin verification against
the installed executable, player-save inspection, or ordinary-gameplay measurement
was performed. This is not a study of HammerwatchPlus's modified classes.

## Answer

**Items can supply a large part of a character's combat output. Matching them to
the build matters considerably. That does not establish that the item system is fun.**

Concrete demonstrations, without attunement or item-damage procs:

| Controlled comparison | Calculated result |
|---|---:|
| Five weapon-focused trinkets, existing attack power 0 | **1.64x weapon DPS** |
| Five spell-focused trinkets on that same weapon channel | **1.20x weapon DPS** |
| Five spell-focused trinkets, existing spell power 120 | **1.38x damage per cast** |
| Same spell selection, when cooldown-limited and mana-sustained | **2.76x spell throughput** |
| Selected offensive equipment affixes plus weapon trinkets | **2.28x weapon DPS** |
| Selected matching fire affixes plus spell trinkets, same ideal cadence assumptions | **4.51x fire-spell throughput** |
| Four ordinary ilvl-20 strength armor pieces on the specified Warrior | **1.79x physical effective health** |

These are purpose-built examples, **not proven best-in-slot sets, average-run
results, a global optimization, or promises of whole-character DPS**. The damage
examples hold weapon/base-equipment contributions fixed and change only named
trinkets and affixes. The armor example is a separate character and comparison.
Do not multiply every row together.

Your argument is supported as an explanation worth testing: a build can leave
substantial item power unused. The stronger claim, that your friend's items are
bad for his character, needs his actual class, specialization, abilities, items,
attunements and play pattern. Class name alone is not enough.

## 1. What counts as item power?

Separate three systems:

1. **Equipment:** persistent weapon, offhand, head, chest, feet, hands and back.
   Weapon bases supply damage, and equipment has base properties plus affixes.
2. **Trinkets:** collected during the mission, cleared for a new mission.
   Attunement selects an item's alternate modifier list; it is not an extra copy
   of the ordinary effect. Acquiring a specific set during a run is not guaranteed.
3. **Skill orbs:** another itemization layer that changes ability behavior.
   Not quantified here. Neither are permanent town upgrades, drinks, mastery,
   elixirs or multiplayer buffs.

An item can improve damage per hit, attack/cast cadence, mana sustain, defensive
uptime, mobility, control or coverage. There is no single honest percentage for
all of those. Armor does not protect against pure damage; boss-only damage is
not universal damage; cooldown reduction does nothing for a zero-cooldown skill.

Sources: `scripts/Items/Equipment.as:3-14,97-107,146-160`;
`scripts/Items/Trinkets.as:74-91`;
`scripts/Behaviors/Actors/Player/PlayerRecord.as:1997-2012`;
`scripts/Behaviors/Actors/Player/Player.as:523-529`.
All game-source paths in this document are relative to the dump's `hoh2/` root.

## 2. The formulas explain why matching matters

For a normal non-DoT hit, a useful simplified model is:

```text
damage per hit ~ base damage
               * (1 + relevant power / 200)
               * relevant damage-bonus bucket
               * expected critical multiplier
               * other applicable multipliers
               * target mitigation

expected critical multiplier = 1 + crit chance * (crit damage - 1)
```

Attack power applies to mainhand/offhand attacks. Spell power applies to spells
and combos. These are **skill categories, not damage elements**: a fire wand's
ordinary weapon attack is still an attack. Intelligence can supply weapon-base
scaling without making the weapon attack use spell power.

All eight vanilla class definitions assign two spell power per point of their
primary attribute: STR for Warrior/Paladin, DEX for Ranger/Rogue, INT for
Wizard/Sorcerer/Warlock, FOC for Priest. That is **spell power, not universal
damage**. STR additionally supplies armor and physical penetration; DEX supplies
weapon crit; INT supplies spell crit; VIT supplies health and FOC supplies mana.
The damage channel and ability tags matter at least as much as the class label.

Examples of marginal value:

| Added power | Existing relevant power | Damage-per-hit gain from that power alone |
|---|---:|---:|
| +40 | 0 | +20% |
| +40 | 200 | +10% |
| +40 | 600 | +5% |

The source constant is **200**. The nearby comment suggesting 50 power means
another 100% damage is stale and must not be used as the formula.

### Stacking rules that change the answer

- `Modifiers::Damage` bonuses share an additive bucket. Two +10% effects give
  1.20x, not 1.21x. Add another +10% trinket and the bucket becomes 1.30x.
- `SpeedAdd` adds to existing attack/cast speed. Adding 0.15 to speed 1.0 is
  +15% cadence; adding it to speed 1.5 is only +10% cadence.
- Separate crit-chance sources combine as `1 - product(1 - chance)`.
  They are not simply percentage points added to the final chance.
- Skill cooldown multipliers multiply. Hourglass and two matching 0.85
  equipment effects give `0.5 * 0.85 * 0.85 = 0.36125` of original cooldown.
- Cast animation speed and cooldown are separate constraints. Do not multiply
  every cast-speed increase into a cooldown-limited DPS estimate as well.

Sources: `scripts/Behaviors/Actors/Player/PlayerBase.as:798-805,840-894`;
`scripts/Data/Player.as:3-45`;
`scripts/Behaviors/Actors/Modifiers/Modifiers.as:483-532`;
`scripts/Behaviors/Actors/Modifiers/Modifiers.mas:113-118,267`;
`scripts/Behaviors/Actors/Modifiers/StatModifier.as:376-404,661-687`;
`scripts/Behaviors/Actors/Modifiers/SkillModifier.as:38-58`;
`scripts/Behaviors/Actors/Skills/PlayerSkillDirectional.as:40-44`;
`tweak/items/equipment/equipment_weapons_mainhand.sval` (`mainhand_wand_fire_03`).

## 3. Equal-rarity, matched versus mismatched trinkets

Each selection has **one common, two uncommon, one rare and one epic**. No
duplicates, curses, set bonuses or attunements. These are five acquired trinkets,
not a claim that the game has five trinket slots or lets players freely choose
these five at mission start.

| Weapon-focused selection | Modeled effect |
|---|---|
| `book_attacks` | +20 attack power |
| `girdle_might` | +10% attack damage |
| `torc_alactiy` (source spelling) | +0.15 attack speed |
| `codex_power` | +40 attack and spell power |
| `parry_medal` | Defensive and retaliation effects, excluded from DPS arithmetic |

| Spell-focused selection | Modeled effect |
|---|---|
| `book_spells` | +20 spell power |
| `pendant_prowess` | +10% spell damage |
| `focus_crystal` | Separate 5% spell-crit source and +0.10 spell crit damage |
| `codex_power` | +40 attack and spell power |
| `hourglass` | Spell cooldown x0.5; kill-based cooldown resets excluded |

### Weapon channel

Hold the weapon, attributes, crit, target and other bonuses fixed. Existing
attack speed is 1.0, no existing additive attack-damage bonus, sustained ordinary
attacks with no other cadence bottleneck. Parry damage is not counted.

| Existing attack power | Weapon selection | Spell selection on weapon attacks | Matched / mismatched |
|---:|---:|---:|---:|
| 0 | 1.645x | 1.200x | 1.370x |
| 100 | 1.518x | 1.133x | 1.339x |
| 300 | 1.417x | 1.080x | 1.312x |

At AP 0: `(260 / 200) * 1.10 * 1.15 = 1.6445`.
The mismatched selection still supplies Codex's +40 AP. The rest of its modeled
bonuses do not amplify ordinary weapon attacks.

### Spell channel

Hold INT at 60, which gives attribute-derived spell crit in the source formula.
The first row's SP 120 is consistent with that primary attribute before other
power sources; the other rows are power sensitivities, not complete character
builds. No other crit sources or additive spell-damage bonuses.

| Existing spell power | Spell selection, per cast | Spell selection, cooldown-limited | Weapon selection on spells |
|---:|---:|---:|---:|
| 120 | 1.378x | 2.756x | 1.125x |
| 300 | 1.300x | 2.599x | 1.080x |
| 600 | 1.247x | 2.495x | 1.050x |

At SP 120, matching delivers **2.45x** the spell throughput of the mismatched
selection under the cooldown-limited assumptions, but only **1.22x** its damage
per cast. The difference is Hourglass, not hidden damage scaling.

**The cooldown column is conditional potential, not measured sustained DPS.**
It requires enough mana, a positive relevant cooldown, enough animation headroom,
available targets, and actually casting again when ready. If mana or animation
already limits casting, Hourglass alone can provide little or no sustained DPS
increase. It can still improve burst timing or defensive skill availability.
If only half the baseline damage comes from the affected spell channel, a 2.756x
improvement there gives `0.5 + 0.5 * 2.756 = 1.878x` total damage, not 2.756x.

Sources: `tweak/trinkets/common.sval` (`book_attacks`, `book_spells`);
`uncommon.sval` (`girdle_might`, `pendant_prowess`, `torc_alactiy`, `focus_crystal`);
`rare.sval` (`codex_power`); `epic.sval` (`hourglass`, `parry_medal`).
These four filenames are under `tweak/trinkets/`.

## 4. Equipment optimization adds another substantial layer

This comparison keeps equipment bases and their ordinary stats fixed. It counts
only selected offensive affixes, rather than pretending to simulate complete
generated gear. It assumes their alternative affixes are neutral for the channel
being compared. Both examples fit the relevant slot tags and rarity budgets:
rare equipment has a first common/uncommon affix and one rare affix; epic adds
one epic affix, not three arbitrary epic affixes.

**Weapon:** +10% attack damage on chest and hands, +0.10 attack speed on head
and back, plus the weapon trinkets above:

```text
AP 0: 1.30 power * (1 + 0.10 + 0.10 + 0.10) damage
                 * (1 + 0.15 + 0.10 + 0.10) attack speed
      = 2.2815x weapon DPS
```

**Fire spell:** +10% spell damage on chest and hands, matching fire epic affix
on hands and back, plus the spell trinkets:

```text
SP 120: (380 / 320) power * 1.30 damage * focus-crystal crit ratio
        / (0.5 * 0.85 * 0.85) cooldown
        = 4.508x cooldown-limited fire-spell throughput
```

The fire affixes also increase skill animation speed. That is not counted as
another independent DPS multiplier. Equipment-base INT, mana reduction, spell
crit, damage, enchantments and damage procs are not added to these estimates.
The slots can support these affixes, but this is not a generated full-loadout
proof with requirements, rolls, acquisition cost and sustain all verified.

Sources: `tweak/items/modifiers_equipment_rare.sval`
(`mod_attack_damage`, `mod_spell_damage`, `mod_attack_speed`);
`tweak/items/modifiers_equipment_epic.sval` (`mod_epic_speed_fire`);
`scripts/Items/EquipmentGenerator.as:395-450,476-483`;
`scripts/Items/Equipment.as:97-107`.

## 5. Items are also a major defensive power source

For nonnegative armor, against physical damage with zero incoming penetration:

```text
damage taken fraction = 1 / (1 + armor / 200)
physical effective health = HP * (1 + armor / 200)
```

A legal level-20 NG0 Warrior example: 50 picked STR and seven picked VIT, no
town/elixir/skill modifiers. Base STR 10 and VIT 10 yield **STR 60, VIT 17,
350 HP and 132 armor** (the class armor contribution truncates to 12).

Four **common**, unenchanted, unupgraded ilvl-20 pieces:

| Item ID | Armor supplied | Required STR |
|---|---:|---:|
| `chest_str_t3a` | 77 | 60 |
| `head_str_t3a` | 62 | 58 |
| `feet_str_t3a` | 62 | 58 |
| `hands_str_3a` | 62 | 58 |
| Total | **263** | All satisfied |

Armor rises from 132 to 395. Physical EHP rises from **581 to 1,041**, or **79%**.
This compares those slots empty versus filled, not poor gear versus good gear.
There are no random affixes in this example, and shield/back/resistances/healing
are not counted. Rounding of individual damage packets can change small-hit
results, so EHP is a continuous approximation rather than a hit-count prediction.

One more example of potential impact, not added to the table: Dragon Heart
supplies +200 HP, which is **+57% HP** on this 350-HP character before other
health scaling, plus conditional stationary regeneration. Orb of Restoration
supplies +10 mana regeneration and healing scaled to 25% of mana spent.
If 40 mana per second is actually spent, that is nominally 10 HP/sec of triggered
healing, subject to game rounding, heal modifiers and overhealing. These can
change whether an offensive rotation is sustainable at all.

Sources: `scripts/Behaviors/Armor.as:1-23`; `scripts/Data/Misc.as:23-27`;
`scripts/Data/Player.as:37-41,102`;
`scripts/Behaviors/Actors/Modifiers/Modifiers.as:489-532`;
`players/warrior/class_warrior.sval:4-19,26-32`;
four `tweak/items/equipment/equipment_shared_{chest,head,feet,hands}.sval` files;
`tweak/trinkets/epic.sval:4-27,120-147`.

## 6. So what fraction of power originates in items?

Use a removal-based definition, with the rest of the character held fixed:

```text
item-attributable share = 1 - output_without_selected_items / output_with_items
                       = 1 - 1 / item_multiplier
```

- The five weapon trinkets at AP 0 account for **39% of that setup's weapon DPS**.
- The spell trinkets at SP 120 account for **27% of damage per cast**, or **64% of
  ideal cooldown-limited spell throughput**.
- Including the selected equipment affixes raises those illustrative removal
  shares to **56% weapon DPS** and **78% ideal fire-spell throughput**.
- The four common armor bases account for **44% of the example's physical EHP**.

These percentages apply only to the named items and channels under the stated
assumptions. They are not disjoint contributions that can be added to class,
skills, town and player skill to make a pie chart. Items and abilities multiply
and enable each other; removing a weapon can also change the available attack.
An unarmed comparison would largely measure losing a weapon, not optimization.

## 7. Where each argument is right

**Your case:** item relevance is real and sometimes decisive. A spell-damage
item can contribute nothing to a weapon-heavy rotation, even on a Wizard. An
attack-speed item can contribute little to a cooldown-bound spell build. Gear
for a different damage element can waste a valuable epic affix. Rarity alone
does not establish usefulness.

**Your friend's case:** a collection of passive percentage increases can be
strong without feeling interesting. Several ordinary items are modest marginal
upgrades once a damage bucket or power pool is already large. The spectacular
effects depend on finding specific pieces and supporting their resource costs.
“Items are not fun” is not refuted by proving that they raise DPS.

**Balance implication:** do not start with a blanket item-stat buff. These
examples already show large conditional gains, and a blanket buff could widen
the gap between coherent and incoherent builds. Investigate readability,
acquisition and build-changing effects separately from raw numerical strength.
This is a design inference, not playtest evidence.

## 8. What remains to settle the argument for his character

1. Get his class/spec, level/NG+, main damage skills, ordinary rotation, worn
   equipment including affixes/upgrades, trinkets and attunements. Do not infer
   how he plays from the class name.
2. Compare **his loadout**, a **same-budget obtainable improvement**, and an
   **aspirational optimized loadout**. Hold character progression, skill ranks,
   target and encounter conditions fixed. Keep equipment and trinket changes
   separate first, then combine them.
3. Measure boss and pack damage, mana-neutral sustained damage, burst, deaths,
   effective healing and skill uptime. Include a long enough trial to exhaust
   an unsustainable opening mana pool. Repeat stochastic proc trials.
4. Check whether power changes how the build plays or merely shortens kills.
   That last question needs his feedback, not just an optimizer.

No globally optimal per-class loadout, realistic drop-availability distribution,
proc-chain model, orb contribution or live DPS comparison is claimed by this
investigation. Those are the next measurements, not numbers to invent now.

## Reproduce

```bash
python -m tools.devarena.item_power --game-root /path/to/gamecode/sdk/hoh2
python -m pytest tests/test_item_power.py
```

[`item-power-results.json`](item-power-results.json) contains the generated
comparison values, assumptions, packet IDs, armor requirements and input hashes.
The script reads game data without modifying the dump. Its source-fragment
checks catch selected formula changes but are not a complete compatibility
verifier. The unit tests verify arithmetic, not native game behavior.

### Validation performed

- Generated the results successfully from the existing dump, including selected
  formula guards and the armor-requirement checks.
- `python scripts/test.py tests/test_item_power.py`, using the main checkout's
  existing virtualenv interpreter: **7 tests passed**; generated verb-list and
  settings-config checks also passed.
- `git diff --check`: passed.
- The unrestricted `python scripts/test.py` did **not** pass on this Linux host:
  18 existing Windows-runtime test modules fail during collection because
  `ctypes.WinDLL` is unavailable. The system Python also lacks pytest; the
  focused passing run used the existing virtualenv. No runtime-test fixes made.
- Ruff was unavailable in that virtualenv; no lint pass is claimed.
