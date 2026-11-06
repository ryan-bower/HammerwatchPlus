# Branding and Bannerlord rework draft

Status: source implementation, 2026-11-05. **Native compilation and gameplay/co-op
validation pending.** Six source/data contract tests pass; GameLab doctor cannot
import the Windows-only launcher on this Linux worktree. No runtime evidence.
Numbers below are initial tuning targets, not measured balance findings. Existing
comparisons come from committed skill data, not a new runtime measurement.

## Warlock: Branding

### Pyrebrand

- Proliferation becomes baseline: spread to enemies within 100 units, carrying
  100% of stored damage and existing charge. Keep the existing 20-brand safety cap.
- Brand duration is 6 seconds, without the old Proliferation duration penalty.
  Transfers preserve remaining duration and charge rather than restarting them.
- Death should trigger a burst and spread instead of losing the payoff. Manual
  detonation also spreads the investment and should remain the stronger deliberate
  payout: initial implementation grants manual claws 25% more damage.
- Keep Combustion unchanged initially: spend Essence for increased claw damage and area.
- Replace the Proliferation perk with **Enfeeblement**: branded enemies have
  Minor Weakness / Weakness / Greater Weakness at its three ranks. Use the native
  status values and stacking rules, not custom 5/10/15% damage reduction.
  Maintain Weakness while branded; do not remove another source's debuff on expiry.
  Inspected native definitions use 0.9/0.8/0.7 outgoing-damage multipliers.
  Apply the native area variants with a 200 ms lease, refreshed every 150 ms;
  their lower category priority preserves ordinary timed Weakness from other sources.

Claw damage cannot feed brands. Each transferred lineage records visited victims;
manual batch targets are excluded from that batch's spread, already branded targets
are skipped, and the 20-brand cap and original expiry are preserved.

### Essence Extraction

Keep magic-weapon Essence generation at 2 / 1.75 / 1.5 / 1.25 / 1 seconds and
doubled gain effects against Pyrebranded enemies. Replace both existing perks:

| Perk | Rank 1 | Rank 2 | Rank 3 |
|---|---|---|---|
| Soul Guard: shield per Essence gained | 1% max HP | 1.5% max HP | 2% max HP |
| Soul Guard: shield cap | 5% max HP | 7.5% max HP | 10% max HP |
| Soul Stride: movement speed | +10% | +15% | +20% |

- Soul Guard lasts 4 seconds, refreshed by gains. Replenish up to the cap;
  doubled gains add two increments. Spending Essence does not remove the shield.
- Soul Stride lasts 3 seconds, refreshed rather than stacked. Doubled gains do
  not double its speed or duration.
- Replacement mapping: Essence Empowerment -> Soul Guard; Released Essence -> Soul Stride.

Reference: vanilla Ranger Hot Pursuit grants +10/20/30% movement speed for 4 seconds
on hitting marked enemies (`planner/data/classes/ranger.json`). Modded Rogue
Tailwind uses +10/15/20% (`mods/specs/players/hwp/specs/winddancer/protective_gale.sval`).
Soul Stride starts lower than Hot Pursuit because its trigger is broadly available.
Soul Guard's percentage shield is a proposed value, not an established vanilla analogue.

## Warrior: Bannerlord

### Battlefield Standard

Replace the damage-reduction aura with visible, periodic temporary shields.

| Property | Draft |
|---|---|
| Radius | 120 units, up from 75 |
| Shield per pulse | 3 / 3.5 / 4 / 4.5 / 5% of the Bannerlord's maximum HP |
| Pulse interval | 3 seconds |
| Shield base duration | 4 seconds |
| Standard lifetime | Keep 10 / 13 / 15 / 17 / 20 seconds |
| Cooldown | Keep 60 / 55 / 50 / 45 / 40 seconds initially |
| Mana | Keep existing cost initially |

- Initial cast pulses immediately. Free recast throws the banner 180 units in the
  aimed direction instead of planting at the Warrior's feet. Terrain/collision
  behavior needs native validation.
- Throwing preserves remaining lifetime: no halving and no timer restart.
- After throwing, pulses originate from both the Warrior and the planted banner.
- Throwing immediately refreshes shields but must not award extra offensive stacks.
- Shields replenish a shared Standard shield up to the listed amount, not an
  accumulating pool. Overlapping locations cannot double shields or stack grants.
  Resolve multiple Bannerlords without additive duplicate auras.
- Snapshot the source Bannerlord's maximum HP on each pulse, not the recipient's.
  Building maximum Health therefore increases shields provided to the whole party.
  Soul Guard remains based on the Warlock's own maximum HP.
- Clearly show protection on recipients and both pulse origins. A spectral carried
  standard is a possible visual after the physical standard is thrown.

Reference: the current Standard gives 2/4/6/8/10% DR, doubled when planted, but
halves its remaining duration. The new radius has 60% more reach and about 2.56x
the area per origin. Shields are not equivalent to DR: repeated small-hit protection
and protection against a single large hit differ and require playtesting.

### Standard perks

**Feared Crest -> Rallying Standard** (working name): replace Vulnerability with
1 / 2 / 3 Killing Spree stacks per pulse for the Warrior and covered allies.

- Shared stacks use the supporting Warrior's Killing Spree rank and perk benefits.
- Recipients maintain and build their own shared stack pool through their own kills,
  refreshing its timer without requiring continuous banner coverage.
- One pool, capped at 10 stacks, not separate kill-earned and banner-earned bonuses.
- Base duration is the source Warrior's native 6/7/8/9/10 seconds.
- Retain the shared effect definition after leaving coverage until the pool expires.
- Share Brutality and Killer Physique per-stack effects. Dauntless remains the
  source Warrior's generation mechanic; do not grant allies extra melee-hit triggers.
- Native Killing Spree and multiple supporting Warriors share one stack pool.
  Keep the strongest inherited damage/crit/regen components and base duration until
  that pool expires; apply only the improvement over the recipient's native benefits.
  A recipient-side 3-second grant gate prevents additive grants from multiple sources.

Existing vanilla Killing Spree numbers (`planner/data/classes/warrior.json`):

| Benefit | Existing values |
|---|---|
| Damage per stack, by passive rank | +2 / 2.5 / 3 / 4 / 5% |
| Brutality crit chance per stack | +1 / 1.5 / 2 percentage points, weapon and spell |
| Killer Physique health regeneration per stack | +2 / 4 / 8% increased regeneration |
| Stack cap | 10 |

At full investment, sharing ten stacks means a 1.5x native damage multiplier,
native CriticalHit strength 0.2 (combined with existing crit by the game's formula,
not a guaranteed additive 20 percentage points), and +80% increased regeneration
(not 80% max-HP healing). Native Killer Physique interpolates its multiplier from
1.0 at one stack to the endpoint at ten; implementation preserves that behavior.
Three stacks per pulse reaches the cap after 9 seconds from the first pulse,
without kills. This party-wide access is the largest offensive increase in this
draft; tune delivery rate first if excessive rather than stripping inherited perks.
Do not claim a damage equivalence to Vulnerability without checking native scaling.

**Martyr's Banner:** replace its DR multiplier with 1.25x / 1.5x / 1.75x allied
shield strength, while the Warrior receives no Standard shield. At maximum Standard
rank, allied shields are 6.25 / 7.5 / 8.75% of the Bannerlord's maximum HP.
Killing Spree sharing is unaffected.
The old 1.5x/2x/3x DR multipliers are not carried across to replenishable shields.

### Righteous Crusade and perks

- Keep +10/20/30/40/50% buff duration for the Warrior and covered allies.
  Ally coverage works at both Standard locations after throwing.
- **New shields and shared Killing Spree explicitly receive this increase.**
  At maximum Crusade: 4-second shields last 6 seconds; native 6–10-second
  Killing Spree lasts 9–15 seconds. Apply duration scaling once, never once per
  origin or once on the source and again on the recipient.
- The Standard's own 10–20-second lifetime is not extended by its own aura.
- Keep **War Drum**: Warcry and Standard casts escalate nearby enemies' Weakness,
  up to Minor / normal / Greater Weakness by perk rank. Do not apply or escalate
  Weakness on periodic shield pulses. Proposed: throwing is not an extra cast for
  escalation; confirm during implementation. Keep current cast-based scope rather
  than silently adding triggers to every AoE buff in the game.
- Keep **Shared Provisions** initially: 1/2/3% personal cooldown reduction per buff
  on the party, capped at 30%. Count stack-based buffs once, not per stack, and
  deduplicate overlapping aura instances.

## Implementation and validation follow-up

Scripts, skill data, planner records and tooltips are updated. Existing perk IDs
and icon slots are retained so purchased ranks remain available under the replacements;
Soul Stride gains a third rank. No real saves or install files were edited.
Shields use a recipient-authoritative absorb pool through the native damage-taken
modifier API, with HUD buffs and an existing protective effect; absorption is before
the engine's subsequent mitigation/block stages, like its ManaShield modifier.
Explicitly timed shield and shared-stack duration applies recipient BuffScale once;
Crusade aura categories prevent overlapping tiers multiplying together. Warriors
already owning Crusade receive only the improvement to the stronger allied tier,
not a second full multiplier on top of their passive.
Inherited stack duration is retained after leaving coverage for kill refreshes.
Verify native Weakness values, timer synchronization, modifier inheritance, duration
scaling order and absorption on the pinned game build before claiming gameplay proof.

Test solo and real co-op: transferred brands, death/manual spread, chain limits,
remote ally kills maintaining Killing Spree, native Warrior recipients, multiple
Bannerlords, moving between origins, source departure, shield replenishment,
Martyr exclusion, and duration scaling exactly once. Assess boss encounters as
well as trash packs; shared crit and existing Warlock siphon sustain are key risks.
