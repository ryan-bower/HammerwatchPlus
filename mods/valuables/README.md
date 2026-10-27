# valuables

Valuables are worth more on NG+: their vanilla gold times one more than the run's NG+
level. Vanilla at NG+0, 2x at NG+1, 3x at NG+2, and so on.

- **What counts.** Every `Item::Valuable` (`tweak/items/items_valuables.sval`,
  26 of them): the world pickups that turn straight into gold, from the scarab
  scale (30) and wolf fur (75) through the ceramic vase (150) to the diamond
  (800). Gold coins, materials and inventory items are untouched.
- **How.** The vanilla pickup pays `GetPrice()` gold (`PlayerRecord.as`, the
  `Item::Valuable` branch), so the module sets each valuable's `m_price` to its
  vanilla price times 1 + NG+ (`g_ngp`, which every level takes from the save) and
  rebuilds its pickup text. The vanilla price is kept, so it never compounds. It is
  applied on every level and again when the mission window's NG+ arrows change
  `g_ngp` in town. Every machine applies it (each picker's own record pays out).
- **Vanilla's NG+ gold on top.** Vanilla already adds 20% to every gold pickup per NG+
  level (`Tweak::NGPMaterialGain`, `PlayerRecord.GetMaterialModifier`), so a vase (150)
  at NG+2 pays 150 x 3 x 1.4 = 630.
- `hwp valuables` shows the multiplier, the NG+ level and the ceramic vase's old and
  new price; `hwp valuables drop [id]` drops a valuable at the host's feet (test
  aid, in a run).
- No settings (the old `valuables.gold_mult` is gone).

## Test checklist

1. `python -m gamelab run mod-valuables --mode lab`: a run at NG+2 shows 3x, a dropped
   ceramic vase is worth 450 and picking it up adds 630 gold (vanilla's x1.4 on top);
   after an abort, a run at NG+0 is back to 150.
2. In an NG+ run, smash pots and pick up valuables: the pickup line shows the raised
   amount and the gold counter rises by it.
3. Co-op: the client's pickups pay the same.
