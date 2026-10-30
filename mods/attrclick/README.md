# attrclick

At the Attribute Trainer, Shift+Click places 20 attribute points and Ctrl+Click 5
(issue #22).

- **Vanilla.** The trainer (`actors/npcs/town/npc_attrib_trainer.unit`) is an
  `AttributeAssignerShopContent`. A click on a stat places one point, and
  holding the button repeats it, faster and faster. Every level and every NG+
  level adds points, so placing dozens took dozens of clicks.
- **Now.** Hold Shift and a click places 20, hold Ctrl and it places 5 (Shift
  wins when both are held). It never places more than you have: with 4 left,
  Shift+Click places 4. Holding the button repeats the same amount. The cost on
  each stat shows the amount while the key is held, and the points line reads
  "Shift 20, Ctrl 5". A gamepad has no modifier keys, so it keeps the hold
  repeat and shows no hint.
- **How.** A class swap (module.json `class_swaps`) points the trainer unit at
  `HWPAttributeAssignerShopContent`. Its `Buy` adds the amount to the picked
  stat at once, with one `SyncStatPoints`. Its window,
  `HWPAttributeAssignerWindow`, redraws the costs when Shift or Ctrl is pressed
  or let go. Respec is unchanged.

`hwp attrclick` shows the points left, the picked points and what a click
places now. `hwp attrclick force shift|ctrl|none|keys` holds a modifier for a
test (`keys` reads the real keys again).

## Settings

On the HammerwatchPlus tab of the player menu (your own), or `hwp set`:

- `attrclick.enabled` (on): off places one point a click, as vanilla.

## Test checklist

1. `python -m gamelab run mod-attrclick --mode lab`: `[HWP:attrclick]
   self-check done: on, Shift 20, Ctrl 5`. With 50 points, a plain click
   places 1, Shift 20, Ctrl 5, Shift with 4 left places 4, and a click with
   none left places nothing. Off, Shift places 1. The window is
   `HWPAttributeAssignerWindow`, and the shots show the costs at 20 and 4.
   The real Left Ctrl, held in the lab window, turns a click into 5 and back
   to 1 when let go.
2. By hand: at the trainer, hold Left or Right Shift and click a stat (20
   points), then Right Ctrl (5). Let go and the costs go back to 1. GameLab
   can't hold Shift: SDL lets go of a Shift key that Windows doesn't see
   held, and a posted key isn't.
3. With a gamepad: no hint, and holding the button still repeats.
