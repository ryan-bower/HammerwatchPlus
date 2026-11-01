# bufftips

Hover a buff or debuff icon in the HUD's buff bar to get a tooltip: the time
left in seconds on top (counting down), then the effect's name (red for
debuffs, "x N" for stacks) and its description.

- HUD components get no mouse input, so `HWPBuffTipsHUD` (added through
  `[Hook] HUDConstructor`, drawn on top) hit-tests the cursor against the
  `HUDBuffs` icon widgets every frame, scaled by the buff bar's own
  `ui_hud_scale_buffs`, and draws a vanilla `CreateTooltip` box with the time
  as its header. The box is rebuilt only when the hovered buff, the whole
  seconds left or the stack count change.
- Name and description come from the buff's def (`ActorBuff`), its stack def
  or buff def (`ActorBuffStacked`), or the skill (`Skills::StackSkill`).
- Hidden while a menu is open.
- Buffs without a `hud` icon never reach the buff bar, so they get no tooltip;
  the Effects tab of the character menu still lists them by name and
  description. HWP buffs given descriptions (and icons where they are
  one-shot) for this: spec reworks, HoH1 class skills, pet Morale (no icon:
  re-applied every 2 s), Spirit Cloak.
- **Class buff icons** (issue #28). Vanilla gives almost none of the class
  skill buffs a `hud` icon, so War Cry and others never showed on the bar.
  The module supports all 31 ranks from 13 families at runtime (`ApplySkillIcons`, the list in
  `SkillBuffs.as`): War Cry; Fuel the Flame, Invigorating Touch and
  Cleansing Touch (Paladin); Holy Flames (Priest); Healing Wisps and Hot
  Pursuit (Ranger); Lethal Opening (Rogue); Flamewalker and Power Surge
  (Sorcerer); and the three Combo Bursting buffs. It reads only name, description and HUD metadata from the 31 raw SValues, then patches
  definitions already loaded by the game. It does not call `LoadActorBuff` or parse
  gameplay modifiers/effects to install display metadata. A guarded watcher observes
  later native loads, definition/hash replacement and HUD/list replacement; a first
  active buff receives its missing widget through `HUD.ShowBuffIcon`. It patches each
  loaded definition in place, with the
  middle 14x14 of the skill's own icon (`gui/hwp/bufftips/icons.png`). A def
  with an icon of its own keeps it, and a name or description is filled in
  only when the def has none. It logs `skill buff metadata: 31 of 31 raw definitions available, 0 invalid`;
  its separate icon count reports only definitions that the game has actually loaded.
  Off removes only the exact sprites installed here; later third-party sprites remain.
  Native skill loads still parse their original gameplay data, including any upstream
  data diagnostics; this display-only change does not repair or suppress that schema. Each machine patches its own
  defs; an ally hit by War Cry gets the same def, so their bar should show
  it too (co-op not tried in the lab).
  `tools/make_bufftips_icons.py` writes the sheet and `SkillBuffs.as` from
  one table (`--check` for stale files).
- Not given icons: buffs under about 1 s, which are refreshed while
  something lasts (auras, banners); effect carriers with no stats (the
  Warlock's `aura_effect_*`); debuffs (the game shows those over the head);
  and the HoH1 trinket buffs (`trinkets`), whose icon sheet is imported from
  the player's own HoH1 install.

## Settings

On the HammerwatchPlus tab of the player menu (Quality of Life > Buff tooltips), per player:

- `bufftips.enabled` (on): off, hovering a buff shows nothing. Takes effect at once.
- `bufftips.skill_icons` (on): class skill buffs the game shows no icon for get one on
  the buff bar. Off, later casts show no icon. Takes effect at once.

## Test checklist

1. `python -m gamelab run mod-bufftips --mode lab`: `[HWP:bufftips] ready`, no script errors.
2. In a run, get a timed buff (a shrine, a potion, a class skill). Hover its
   icon: the tooltip shows "Ns left" counting down, the name and what it does.
3. A debuff's title is red; a stacking buff shows "x N".
4. Open the character menu: no buff tooltip over the menu.
5. Effects tab: Warden's Resolve (and the other HWP buffs) show a description.
6. `python -m gamelab run fix-bufftips-skill-icons --mode lab` (passes): a fresh
   Warrior casts War Cry; the bar shows it as "War Cry", "Faster weapon and
   movement speed.", and hovering it shows the tooltip; `bufftips.skill_icons`
   off and on; the other 12 buffs given with `gl givebuff` each show a named,
   described icon. Shots `warcry-bar`, `warcry-tip`, `skill-buffs-bar`.
7. By hand: play a Warrior, cast War Cry next to an ally; both bars show it
   for 8 s (not tried yet).
