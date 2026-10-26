# colors

Accessibility colours for projectiles.

- `module.json` **class_swaps** `NewProjectile`, `RayProjectile` and
  `BeamProjectile` to `HWP*` subclasses that call
  `HWP::Colors::Tint(m_unit, owner)` after the base `Initialize`
  (`tools/class_units.py` copies the 184 base projectile units with our class
  in; info.xml classmaps are ignored by the engine, which is why the tints
  never applied before). Projectiles that other HWP mods add (HoH1 bosses,
  firearms) keep their own class and are not tinted. Friendly = the owner
  resolves through `GetPlayerOwner` (players, summons, turrets); everything
  else is enemy. The tint is `UnitPtr.SetMultiplyColor`, so it multiplies the
  sprite: dark sprites get darker, white/pale ones take the colour best. The
  first tinted shot of a level is logged (`[HWP:colors] tinted <unit> enemy #...`).
- Presets: `default` (no tint), `contrast` (red vs light blue),
  `deuteranopia` (orange vs blue), `protanopia` (yellow vs blue),
  `tritanopia` (red vs teal). Per-team overrides as hex.
- The preset is picked in the player menu's **Plus** tab (core
  `HWP::Options`, row `colors`): click the button for the next preset (it
  clears custom colours). The game's own Options menu cannot take it: it runs
  in the menu script, without mod scripts or gui files (GameLab
  `probe-options-menu`). Stored as the HWP setting `colors.preset`.
- Custom per-team colours (per machine, in your own town record):
  `colors.enemy`, `colors.friendly`. Commands:
  `hwp colors` (show), `hwp colors deuteranopia`,
  `hwp colors enemy ff8800`, `hwp colors friendly 44aaff`, `hwp colors off`.

Open question: whether effects/AoE telegraphs should be tinted too (they
are `EffectBehavior` units, not projectiles).

## Player colours on the maps (bugs 10.22.26 line 24)

`scripts/HWP/Colors/PlayerColors.as`. Every player already has a colour by
peer (`Tweak::PlayerColors`, `GetPlayerColor(peer)`); the maps did not show
it. Now:

- Each player's minimap marker sprite is tinted with their colour
  (`GetMinimapSprite().SetColor`, the PingBehavior way), once per level and
  again when the palette changes (`[HWP:colors] player markers tinted: N of M`).
- `HWPPlayerColorsHUD` (a HUDComponent added after the minimap) draws, on the
  corner minimap, the Tab overlay map and the player menu's Map tab, a dot in
  each other player's colour, pinned to the map edge when they are outside
  it, and their name above the dot (`GetPlayerDisplayName`, their colour)
  when they are pinned or farther than `playercolors.distance` px (default
  300) from you. The map tab is drawn from the module's `RenderWidgets`
  (after the window manager, so on top).
- Settings (per machine): `playercolors.palette` `default` (the game's
  peer colours) or `safe` (Okabe-Ito, distinguishable with colour-blindness),
  `playercolors.names` on/off, `playercolors.distance`. Command
  `hwp playercolors [default|safe] [names on|off] [distance N]`; without
  arguments it replies the status (`Player colours: palette ..., you are peer
  N #rrggbb, map names on beyond 300 px`), which the level start also logs.
- Untested in the lab so far: that the minimap sprite's colour is
  per instance (not the shared scene resource); the overlay map's
  world-per-pixel when `ui_hud_scale_overlay` is not 1.

## Test checklist

1. `python -m gamelab run mod-colors --mode lab`: a spawned guard sentry's
   crossbow bolt is tinted (`tinted actors/undead/guard/projectiles/crossbow_bolt.unit
   enemy #ff5959`), no script errors. `mod-options-tab`: the Plus tab row cycles presets.
2. `hwp colors contrast`, fire a ranged skill: your projectiles are blue-ish;
   ranged enemies' projectiles are red-ish. Beams (wizard) and ray projectiles
   also tint.
3. `hwp colors enemy 00ff00`: enemy shots go green; `hwp colors off` restores.
4. Player menu > Plus: "Projectile colors" shows the preset; clicking it
   steps through them, tints change right away, and `hwp colors` shows the new preset.
5. Leave and re-enter town: the choice persists (`[HWP:colors] preset ...` in the log).
6. Co-op: a client's choice only changes that client's screen.
7. `python -m gamelab run fix-map-colors --mode lab`: the level start logs the
   player colours status, the marker tint line, `hwp playercolors` steps
   through safe/names/distance and back, and the minimap, overlay map and
   map tab are shot (one player: no other dots; the shots are for the eye).
8. Co-op, two machines: on every map each other player is a dot in their
   colour; names appear beyond 300 px or when pinned to the edge;
   `hwp playercolors safe` recolours the markers at once.
