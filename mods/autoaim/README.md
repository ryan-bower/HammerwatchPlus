# Auto Aim

A remake of kearneyTim's "Auto Aim for controller AOE skills" (Steam Workshop
3732392493), for the skills you aim with a reticle: the Ranger's Marked Shot, the
Warrior's Leap, the Sorcerer's Firewall and the like.

- **Auto aim:** the reticle snaps to an enemy. It picks the one nearest where the reticle
  would have been, among the enemies in the skill's range, inside the aim cone and in
  plain sight. The cone is centred on where you aim (the stick, or the cursor).
- **Auto fire:** once the reticle is on an enemy, the skill fires. You don't need to press
  attack, or to let go of the skill button with quick cast.
- **Auto skill:** while you aim at nothing, a ready AOE skill casts itself at an enemy in
  range. It waits until your mana is at or over the set share, and casts at most once every
  2 s.

The original works with a controller only. Here it is on for controllers by default and
can be switched on for mouse play too. The settings are on the **Plus** tab of the
character menu:

| Row | Setting | Default | Choices |
|---|---|---|---|
| Auto aim (AOE skills) | `autoaim.mode` | Controller | Off, Controller, Controller + mouse |
| Auto aim cone | `autoaim.cone` | 180 degrees | 90, 180, 270, 360 (any value 0-360 by `hwp set`) |
| Auto fire | `autoaim.fire` | On | On, Off |
| Auto skill | `autoaim.skill`, `autoaim.skill_mana` | Mana 60%+ | Off, then Mana 0%+, 40%+, 60%+, 80%+ |

Two more settings take `hwp set` only:
- `autoaim.skill_buffer_ms` (2000): the time between auto skill casts.
- `autoaim.debug` (off): logs each auto shot.

These map onto the original's `caa_auto_aim`, `caa_auto_fire`, `caa_auto_skill`,
`caa_aim_angle`, `caa_skill_min_mana`, `caa_skill_buffer` and `caa_debug`.
`hwp autoaim` prints the settings and the last auto shot (the original's `caa_settings`).
The original's skill debug menu is left out.

How it hooks in: core already swaps the local player's targeting helper (for the Skill
4-6 keys), and that helper calls core's aim hooks (`HWP/Core/Aim.as`). This mod
registers there, so it overrides no game file.
