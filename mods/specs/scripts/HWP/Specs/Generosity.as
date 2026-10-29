// Paladin of Generosity (the planner's paladin-spec4): Pelor's Blessing and Pelor's Fury.
// - Pelor's Blessing (stacks_specs.sval:pelors_blessing, max 10): GainBlessing on the paladin's
//   own client, every source sharing a GAIN_CD cooldown. Sources: Lay on Hands healing a
//   teammate (HWPGenHeal notes who it heals; solo, healing yourself counts, in a party it does
//   not), up to dg-max a cast (Display of Generosity), resolved the frame after the cast; a
//   Blessed Strike kill (the PlayerKilledActor hook, the killer's client); Conviction giving
//   mana (HWPGenConvictionMana), at most once every CONVICTION_CD. Each stack adds pb-pct to
//   Lay on Hands healing (the intensity of HWPGenHeal / HWPGenHPHeal), Blessed Strike damage
//   (the PlayerDamageActor hook, before the damage is worked out) and Conviction mana. Reset
//   by a party player's death (OnPlayerDied, players only), by Pelor's Fury and in town.
// - Pelor's Fury (HWPGenFury): Activate picks the enemy nearest the reticle (FURY_PICK) and
//   refuses, spending nothing, when there is none or it can't be held (FuryRefusal); the cast's
//   cost is held back (GetCost is 0 while casting) and paid in Deactivate once the castpoint is
//   passed and the target still holds (StartFury): the pelors_fury buff on the target (stun,
//   armor and resistances 0, damage taken +pf-dmg; intensity pf-dmg, duration pf-stun), every
//   Blessing stack spent, the cooldown 30 s or FURY_BOSS_CD on a boss. A failed hold gives the
//   cooldown back. In a party the caster is held (pelors_channel, the dash pinned); solo not.
//   The hold ends at pf-stun (Blinding Sun: bs-buff on the target) or when the target dies
//   (Holy Sacrifice: hs-stacks Blessing back and half the cooldown off).
// - The strikes: the caster asks the host (specs.fury_fx), the host cancels the target's
//   casting attacks and spells (the buff does the same where it lands) and broadcasts
//   specs.fury_play; every peer pulses pelors_strike.effect on the target every FX_PULSE_MS:
//   one strike on a normal enemy, a ring of 4 to 10 around a boss, by its size.
// - Descendent of Pentival (dp-on): HWPGenPentival / HWPGenPentivalLeech on the stack's buff.
// - `hwp gen`: status | stacks <n> | fury [now] | pick [dx dy] | cd | solo [on|off|auto].
namespace HWP
{
	namespace Specs
	{
		const uint PF = HashString("hwp_pal_pelors_fury");
		const uint PB = HashString("hwp_pal_pelors_blessing");
		const uint BLESSED_STRIKES = HashString("pal_blessed_strikes");
		const string BLESSING = "pelors_blessing";
		const string GENEROSITY_ID = "hwp_paladin_generosity";
		const int BLESSING_MAX = 10;
		const int GAIN_CD = 2000;
		const int CONVICTION_CD = 6000;
		const int FURY_BOSS_CD = 60000;
		const float FURY_PICK = 40.0f;
		const int FX_PULSE_MS = 300;

		int g_gainC = 0, g_convC = 0;
		int g_lohAllies = 0;
		bool g_lohSelf = false, g_lohPending = false;
		// `hwp gen solo on|off`: the tests' party switch (-1: the real player count)
		int g_soloForce = -1;
		// counters for `hwp gen status`
		int g_genGained = 0, g_genBlocked = 0, g_genLoH = 0, g_genKills = 0, g_genConv = 0, g_genResets = 0;
		int g_bsScaled = 0, g_lohScaled = 0, g_convScaled = 0;
		int g_furyCasts = 0, g_furyRefused = 0, g_furyFailed = 0, g_furySacrifices = 0, g_furyBlinds = 0, g_furyCancels = 0;
		// presses that asked CanActivate with a warning (the status line)
		int g_furyAsks = 0;
		string g_furyLast = "";

		class FuryHold
		{
			PlayerBase@ m_plr;
			Actor@ m_target;
			UnitPtr m_unit;
			HWPGenFury@ m_skill;
			int m_left;
			bool m_boss;
			bool m_locked;
			string m_bsBuff;
			int m_hsStacks;
			int m_dashReal = -1;
			int m_dashPinLeft = 0;
		}
		FuryHold@ g_fury;

		class FuryFx
		{
			UnitPtr m_unit;
			vec2 m_pos;
			int m_left;
			int m_pulseC;
			int m_n;
			float m_ring;
			bool m_moveOff = false;   // host: the hold switched the unit's movement off (see MoveGuard)
		}
		array<FuryFx@> g_furyFx;
		int g_furyPulses = 0;

		void ClearGenerosity()
		{
			if (g_fury !is null)
				EndFury("module start");
			@g_fury = null;
			for (uint i = 0; Network::IsServer() && i < g_furyFx.length(); i++)
			{
				if (g_furyFx[i].m_unit.IsValid() && !g_furyFx[i].m_unit.IsDestroyed())
					MoveGuard(g_furyFx[i], true);
			}
			g_furyFx.removeRange(0, g_furyFx.length());
			g_gainC = 0;
			g_convC = 0;
			g_lohPending = false;
			g_lohAllies = 0;
			g_lohSelf = false;
		}

		PlayerBase@ LocalGenerosity()
		{
			auto plr = cast<PlayerBase>(GetLocalPlayer());
			if (plr is null || plr.m_record is null || !Learned(plr, PB))
				return null;
			return plr;
		}

		bool Solo()
		{
			if (g_soloForce >= 0)
				return g_soloForce == 1;
			int n = 0;
			for (uint i = 0; i < g_players.length(); i++)
			{
				if (g_players[i].peer != 255)
					n++;
			}
			return n <= 1;
		}

		int Blessing(PlayerBase@ plr)
		{
			auto def = Stack(BLESSING);
			return plr is null || def is null ? 0 : plr.GetStacks(def);
		}

		void SetBlessing(PlayerBase@ plr, int n, const string &in why)
		{
			auto def = Stack(BLESSING);
			if (plr is null || def is null)
				return;
			int have = Blessing(plr);
			n = clamp(n, 0, BLESSING_MAX);
			if (n == have)
				return;
			plr.AddStacks(plr, def, n - have);
			Log("specs", "blessing " + have + " -> " + Blessing(plr) + " (" + why + ")");
		}

		// the multiplier Pelor's Blessing gives Lay on Hands, Blessed Strike and Conviction now
		float BlessingMul(Actor@ owner)
		{
			auto plr = cast<PlayerBase>(owner);
			if (plr is null || !Learned(plr, PB))
				return 1.0f;
			int n = Blessing(plr);
			return n <= 0 ? 1.0f : 1.0f + n * BindF(plr, PB, "pb-pct", 0.005f);
		}

		// a gain from one of the three sources; the 2 s cooldown is shared (bypass: Holy Sacrifice)
		bool GainBlessing(PlayerBase@ plr, int n, const string &in source, bool bypass = false)
		{
			if (plr is null || n <= 0 || !IsLocal(plr) || !Learned(plr, PB) || g_inTown)
				return false;
			if (!bypass && g_gainC > 0)
			{
				g_genBlocked++;
				return false;
			}
			if (!bypass)
				g_gainC = GAIN_CD;
			int before = Blessing(plr);
			SetBlessing(plr, before + n, source);
			g_genGained += Blessing(plr) - before;
			return true;
		}

		void ResetBlessing(PlayerBase@ plr, const string &in why)
		{
			if (plr is null || Blessing(plr) <= 0)
				return;
			SetBlessing(plr, 0, why);
			g_genResets++;
		}

		// HWPGenHeal on the caster's client: who this Lay on Hands heals (resolved next frame)
		void NoteLoH(Actor@ owner, Actor@ healed)
		{
			if (!IsLocal(owner) || healed is null || cast<PlayerBase>(healed) is null)
				return;
			if (healed is owner)
				g_lohSelf = true;
			else
				g_lohAllies++;
			g_lohPending = true;
		}

		void ResolveLoH(PlayerBase@ plr)
		{
			if (!g_lohPending)
				return;
			g_lohPending = false;
			int n = Solo() ? (g_lohSelf ? 1 : 0) : min(g_lohAllies, max(1, BindI(plr, PB, "dg-max", 1)));
			Log("specs", "lay on hands healed " + g_lohAllies + " ally(s)" + (g_lohSelf ? " and self" : "") + (Solo() ? " solo" : "") + ": +" + n);
			g_lohAllies = 0;
			g_lohSelf = false;
			if (n > 0 && GainBlessing(plr, n, "lay on hands"))
				g_genLoH++;
		}

		void OnConvictionMana(Actor@ owner)
		{
			auto plr = cast<PlayerBase>(owner);
			if (plr is null || !IsLocal(plr) || !Learned(plr, PB) || g_convC > 0)
				return;
			if (GainBlessing(plr, 1, "conviction"))
			{
				g_convC = CONVICTION_CD;
				g_genConv++;
			}
		}

		void OnBlessedKill(PlayerBase@ plr)
		{
			if (plr !is null && IsLocal(plr) && Learned(plr, PB) && GainBlessing(plr, 1, "blessed strike kill"))
				g_genKills++;
		}

		// every peer: a party player died (players only: GameEvents::PlayerDied)
		void OnPlayerDied(PlayerBase@ dead)
		{
			auto plr = LocalGenerosity();
			if (plr is null || dead is null)
				return;
			ResetBlessing(plr, "party player died");
		}

		// --- Pelor's Fury -----------------------------------------------------------------------------

		bool IsBossActor(Actor@ a)
		{
			return HasActorTag(a, "boss");
		}

		// why a cast on `a` can't hold, or "" when it can
		string FuryRefusal(PlayerBase@ plr, Actor@ a, float range = -1)
		{
			if (a is null)
				return "no target";
			if (a.IsDead() || !a.m_unit.IsValid() || a.m_unit.IsDestroyed())
				return "dead";
			if (plr !is null && a.Team == plr.Team)
				return "ally";
			auto ca = cast<CompositeActorBehavior>(a);
			if (ca is null)
				return "not an enemy";
			if (!a.IsTargetable())
				return "untargetable";
			// no body: underground or in the air in a scripted scene (the Serpent tunnelling, a boss
			// spirit's dive; plan-generosity-bosses 20261027-021403 held a tunnelling Serpent that
			// kept its skill): nothing to hold
			if (a.m_unit.GetPhysicsBody() is null)
				return "out of reach";
			if (ca.IsImmortal())
				return "invulnerable";
			if (ca.m_props.m_noBuffs)
				return "immune to buffs";
			if (range > 0 && plr !is null && dist(xy(a.m_unit.GetPosition()), xy(plr.m_unit.GetPosition())) > range)
				return "out of range";
			return "";
		}

		float UnitRadius(UnitPtr u)
		{
			auto body = u.GetPhysicsBody();
			return body is null ? 8.0f : body.GetEstimatedRadius();
		}

		// what a body part stands for: the actor it passes its damage to (m_transferTarget), when the
		// part itself can't be held. The Serpents of Demise's bodies are trails of boss-tagged
		// BossWormSegment units (untargetable, no-buffs, a 4 s ttl) passing their hits to the head
		// (issue #34: aimed at the body, the Fury picked a segment and was refused "untargetable"
		// 23 times of 24, fix-fury-serpent 20261029-045710). A serpent head (TransferDamageActor)
		// passes to the fight's health unit, which is never held: the head stays itself.
		Actor@ StandIn(PlayerBase@ plr, Actor@ a)
		{
			if (a is null || FuryRefusal(plr, a).isEmpty())
				return a;
			UnitPtr to;
			auto seg = cast<BossWormSegment>(a);
			if (seg !is null)
				to = seg.m_transferTarget;
			auto tr = cast<TransferDamageActor>(a);
			if (tr !is null)
				to = tr.m_transferTarget;
			if (!to.IsValid() || to.IsDestroyed() || to == a.m_unit)
				return a;
			auto owner = cast<Actor>(to.GetScriptBehavior());
			if (owner is null || owner.IsDead() || cast<CompositeActorBehavior>(owner) is null || (tr !is null && !owner.IsTargetable()))
				return a;
			// a segment is its serpent even when the head can't be held right now (underground):
			// the refusal then names the head's reason
			return owner;
		}

		string g_furyPickVia = "";   // the body part the last pick went through, "" for none

		// the actor nearest `aim` within FURY_PICK (and its own size) of it, a body part standing
		// for its owner (StandIn): the nearest one that can be held, else the nearest, so a
		// refusal names the reason (a segment over a surfaced head took 5 of 38 picks aimed at
		// the head, 045710)
		Actor@ PickFuryTarget(PlayerBase@ plr, vec2 aim)
		{
			Actor@ best = null;
			float bestD = 1e9f;
			Actor@ held = null;
			float heldD = 1e9f;
			string bestVia = "", heldVia = "";
			// the shape query, and the team's actor list: the boss spirits' bodies are aim-through
			// sensors the shape query skips (plan-generosity-bosses 20261027-013518, four spirits at
			// 8-97 px read "no target")
			array<UnitPtr> results;
			auto shapes = g_scene.QueryCircle(aim, int(FURY_PICK + 48), ~0, RaycastType::Any, true);
			auto foes = g_scene.FetchActorsWithOtherTeam(plr.Team, aim, uint(FURY_PICK + 48));
			for (uint i = 0; i < shapes.length(); i++)
				results.insertLast(shapes[i]);
			for (uint i = 0; i < foes.length(); i++)
				results.insertLast(foes[i]);
			for (uint i = 0; i < results.length(); i++)
			{
				auto a = cast<Actor>(results[i].GetScriptBehavior());
				if (a is null || a.IsDead() || a.Team == plr.Team || cast<CompositeActorBehavior>(a) is null)
					continue;
				float d = dist(xy(a.m_unit.GetPosition()), aim) - UnitRadius(a.m_unit);
				if (d > FURY_PICK)
					continue;
				auto s = StandIn(plr, a);
				string via = s is a ? "" : a.m_unit.GetId() + " " + a.m_unit.GetDebugName();
				if (d < bestD)
				{
					bestD = d;
					@best = s;
					bestVia = via;
				}
				if (d < heldD && FuryRefusal(plr, s).isEmpty())
				{
					heldD = d;
					@held = s;
					heldVia = via;
				}
			}
			g_furyPickVia = held !is null ? heldVia : bestVia;
			return held !is null ? held : best;
		}

		void Refuse(PlayerBase@ plr, const string &in why, bool warn = true)
		{
			g_furyRefused++;
			g_furyLast = "refused: " + why;
			if (warn && plr !is null)
				plr.m_record.PlayVoice("cant");
			Log("specs", "pelor's fury refused: " + why + " (blessing " + Blessing(plr) + ")");
		}

		// the hold, on the caster's client; true when the buff landed
		bool StartFury(PlayerBase@ plr, HWPGenFury@ sk, Actor@ a)
		{
			int stun = BindI(plr, PF, "pf-stun", 3000);
			float dmg = BindF(plr, PF, "pf-dmg", 0.2f);
			if (!Give(plr, a, Buff("pelors_fury"), dmg, stun))
				return false;
			FuryHold h;
			@h.m_plr = plr;
			@h.m_target = a;
			h.m_unit = a.m_unit;
			@h.m_skill = sk;
			h.m_left = stun;
			h.m_boss = IsBossActor(a);
			h.m_bsBuff = BindS(plr, PF, "bs-buff", "");
			h.m_hsStacks = BindI(plr, PF, "hs-stacks", 0);
			h.m_locked = !Solo();
			@g_fury = h;
			if (h.m_locked)
			{
				Give(plr, plr, Buff("pelors_channel"), 1.0f, stun);
				PinFuryDash(h);
			}
			ResetBlessing(plr, "pelor's fury");
			g_furyCasts++;
			g_furyLast = "held " + a.m_unit.GetId() + (h.m_boss ? " boss" : "") + " " + stun + " ms +" + Rounded(dmg * 100) + "%"
				+ (h.m_locked ? " locked" : " free");
			Log("specs", "pelor's fury on " + a.m_unit.GetId() + " (" + a.m_unit.GetDebugName() + ")" + (h.m_boss ? " boss" : "")
				+ (g_furyPickVia.isEmpty() ? "" : " via " + g_furyPickVia)
				+ " stun " + stun + " ms dmg +" + Rounded(dmg * 100) + "% " + (h.m_locked ? "caster locked" : "solo, caster free"));

			SValueBuilder b;
			b.PushDictionary();
			b.PushInteger("unit", int(a.m_unit.GetId()));
			b.PushInteger("ms", stun);
			b.PopDictionary();
			HWP::Net::Request("specs.fury_fx", b.Build());
			return true;
		}

		void PinFuryDash(FuryHold@ h)
		{
			auto dash = cast<Skills::Charge>(FindSkill(h.m_plr, DASH));
			if (dash is null)
				return;
			if (h.m_dashReal < 0)
			{
				h.m_dashReal = max(0, dash.m_cooldownC);
				h.m_dashPinLeft = h.m_left;
			}
			int want = h.m_left + DASH_PIN_MS;
			if (dash.m_cooldownC < want)
				dash.m_cooldownC = want;
		}

		void UnpinFuryDash(FuryHold@ h)
		{
			if (h.m_dashReal < 0)
				return;
			auto dash = cast<Skills::Charge>(FindSkill(h.m_plr, DASH));
			if (dash !is null && dash.m_cooldownC > 0 && dash.m_cooldownC <= h.m_left + DASH_PIN_MS)
				dash.m_cooldownC = max(0, h.m_dashReal - (h.m_dashPinLeft - h.m_left));
			h.m_dashReal = -1;
		}

		// a buff on the local player taken off early (the player's own client is its authority)
		void DropOwnBuff(PlayerBase@ plr, const string &in name)
		{
			auto def = Buff(name);
			if (plr is null || def is null)
				return;
			auto@ buffs = plr.m_buffs.m_buffs;
			for (uint i = 0; i < buffs.length(); i++)
			{
				if (buffs[i].m_def.m_pathHash == def.m_pathHash)
				{
					buffs[i].Clear();
					buffs.removeAt(i--);
				}
			}
		}

		void EndFury(const string &in why)
		{
			auto h = g_fury;
			@g_fury = null;
			if (h is null)
				return;
			if (h.m_locked)
			{
				UnpinFuryDash(h);
				DropOwnBuff(h.m_plr, "pelors_channel");
			}
			Log("specs", "pelor's fury ended: " + why);
		}

		void UpdateFury(int ms)
		{
			auto h = g_fury;
			if (h is null)
				return;
			if (h.m_plr is null || h.m_plr.IsDead())
			{
				EndFury("the caster died");
				return;
			}
			// died: its hp (CompositeActorBehavior::IsDead reads m_hp and m_dead, so it answers on
			// a destroyed unit's behavior too); gone without dying (a summon timing out, a boss
			// phase swapping its unit) ends the hold with no Holy Sacrifice
			bool died = h.m_target !is null && h.m_target.IsDead();
			bool gone = died || !h.m_unit.IsValid() || h.m_unit.IsDestroyed() || h.m_target is null;
			if (gone)
			{
				if (died && h.m_hsStacks > 0)
				{
					// Holy Sacrifice: half the cooldown off and Blessing back (no shared cooldown)
					if (h.m_skill !is null)
					{
						int full = h.m_boss ? FURY_BOSS_CD : h.m_skill.m_baseCooldown;
						h.m_skill.m_cooldownC = max(0, h.m_skill.m_cooldownC - int(full * h.m_skill.m_modCooldownMul) / 2);
					}
					GainBlessing(h.m_plr, h.m_hsStacks, "holy sacrifice", true);
					g_furySacrifices++;
				}
				EndFury(died ? "the target died" : "the target is gone");
				return;
			}
			if (h.m_locked)
				PinFuryDash(h);
			h.m_left -= ms;
			if (h.m_left > 0)
				return;
			if (!h.m_bsBuff.isEmpty())
			{
				auto blind = LoadActorBuff(h.m_bsBuff);
				if (Give(h.m_plr, h.m_target, blind))
				{
					g_furyBlinds++;
					Log("specs", "blinding sun: " + h.m_bsBuff + " on " + h.m_unit.GetId());
				}
				else
					Log("specs", "blinding sun refused by " + h.m_unit.GetId());
			}
			EndFury("the stun ran out");
		}

		// a skill the hold leaves running: the triggered and aura skills (phase changes, death and
		// hurt reactions, auras), the unit's own scripted parts
		bool Passive(ACompositeActorSkill@ sk)
		{
			string t = Reflect::GetTypeName(sk);
			return t.findFirst("Triggered") >= 0 || t.findFirst("Aura") >= 0;
		}

		// host: cut the held unit's casting skills. The buff's disarm and silence stop new casts
		// where the skill checks them; a skill with no attack or spell flag (Arista's, the Spider
		// Queen's and Dace Arden's, plan-generosity-bosses 20261027-013518) or one past that check
		// (a channel, a charge, a breath) runs on, so this runs at the start and every frame of the
		// hold
		// casting for real: a channel that was cancelled stays IsCasting through its stop animation
		// (ChannelingBaseSkill: m_durationC 0, m_endC > 0) and does nothing more; cancelling it
		// again every frame restarted that animation and kept it "casting" (the Serpent's
		// ChannelingSpewSkill, plan-generosity-bosses 20261029-051024, issue #34)
		bool Active(ACompositeActorSkill@ sk)
		{
			if (sk is null || !sk.IsCasting())
				return false;
			auto ch = cast<ChannelingBaseSkill>(sk);
			return ch is null || ch.m_durationC > 0;
		}

		int CutCasting(CompositeActorBehavior@ ca)
		{
			// a unit with no body is mid-air in a scripted scene (the Benevolence spirit's dive
			// holds a scene with no collision): cut there, it stays bodiless and the stunned idle
			// update null-derefs its body (MeleeMovement.as:162, plan-generosity-bosses
			// 20261027-015348). Its skill lands first, then the hold cuts what follows
			if (ca is null || ca.m_unit.GetPhysicsBody() is null)
				return 0;
			int n = 0;
			for (uint i = 0; ca !is null && i < ca.m_skills.length(); i++)
			{
				auto sk = ca.m_skills[i];
				if (Active(sk) && !Passive(sk))
				{
					sk.CancelSkill();
					n++;
				}
			}
			g_furyCancels += n;
			return n;
		}

		// the class names of the unit's skills casting now (the status line)
		string CastingNames(CompositeActorBehavior@ ca)
		{
			string ret = "";
			for (uint i = 0; ca !is null && i < ca.m_skills.length(); i++)
			{
				auto sk = ca.m_skills[i];
				if (!Active(sk))
					continue;
				ret += (ret.isEmpty() ? "" : ",") + Reflect::GetTypeName(sk) + (sk.m_restrictions.m_isAttack ? "/a" : "")
					+ (sk.m_restrictions.m_isSpell ? "/s" : "") + (Passive(sk) ? "/p" : "");
			}
			return ret;
		}

		// host: the target's casting attacks and spells are cut, then every peer plays the strikes
		void OnFuryFxRequest(uint8 peer, SValue@ data)
		{
			int id = GetParamInt(UnitPtr(), data, "unit", false, 0);
			int ms = GetParamInt(UnitPtr(), data, "ms", false, 3000);
			UnitPtr u = g_scene.GetUnit(id);
			if (!u.IsValid())
				return;
			auto ca = cast<CompositeActorBehavior>(u.GetScriptBehavior());
			if (ca is null)
				return;
			CutCasting(ca);
			bool boss = IsBossActor(ca);
			float r = UnitRadius(u);
			SValueBuilder b;
			b.PushDictionary();
			b.PushInteger("unit", id);
			b.PushInteger("ms", ms);
			b.PushInteger("n", boss ? clamp(int(r / 5 + 0.5f), 4, 10) : 1);
			b.PushFloat("ring", boss ? r + 8 : 0);
			b.PopDictionary();
			HWP::Net::Broadcast("specs.fury_play", b.Build());
		}

		void OnFuryPlay(SValue@ data)
		{
			FuryFx fx;
			fx.m_unit = g_scene.GetUnit(GetParamInt(UnitPtr(), data, "unit", false, 0));
			if (!fx.m_unit.IsValid())
				return;
			fx.m_pos = xy(fx.m_unit.GetPosition());
			fx.m_left = GetParamInt(UnitPtr(), data, "ms", false, 3000);
			fx.m_n = GetParamInt(UnitPtr(), data, "n", false, 1);
			fx.m_ring = GetParamFloat(UnitPtr(), data, "ring", false, 0);
			fx.m_pulseC = 0;
			g_furyFx.insertLast(fx);
			Log("specs", "fury strikes on " + fx.m_unit.GetId() + ": " + fx.m_n + " beam(s), ring " + Rounded(fx.m_ring));
		}

		// host: a stunned unit with no body (a boss spirit in a scene with no collision, between
		// the parts of its dive) null-derefs it in its idle update, which the stun's zero speed
		// sends it to (MeleeMovement.as:162; the Benevolence and Arcane spirits,
		// plan-generosity-bosses 20261027-015348 and 021003). A disabled movement skips that
		// update, so the hold switches it off while the body is gone and back on after
		void MoveGuard(FuryFx@ fx, bool ending)
		{
			auto ca = cast<CompositeActorBehavior>(fx.m_unit.GetScriptBehavior());
			if (ca is null || ca.m_movement is null)
				return;
			bool bodiless = !ending && fx.m_unit.GetPhysicsBody() is null;
			if (bodiless && ca.m_movement.m_enabled)
			{
				ca.m_movement.m_enabled = false;
				fx.m_moveOff = true;
			}
			else if (!bodiless && fx.m_moveOff)
			{
				ca.m_movement.m_enabled = true;
				fx.m_moveOff = false;
			}
		}

		void UpdateFuryFx(int ms)
		{
			for (uint i = 0; i < g_furyFx.length(); i++)
			{
				auto fx = g_furyFx[i];
				bool live = fx.m_unit.IsValid() && !fx.m_unit.IsDestroyed();
				fx.m_left -= ms;
				if (live)
				{
					fx.m_pos = xy(fx.m_unit.GetPosition());
					if (Network::IsServer())
					{
						MoveGuard(fx, fx.m_left <= 0);
						CutCasting(cast<CompositeActorBehavior>(fx.m_unit.GetScriptBehavior()));
					}
				}
				if (fx.m_left <= 0)
				{
					g_furyFx.removeAt(i--);
					continue;
				}
				fx.m_pulseC -= ms;
				if (fx.m_pulseC > 0)
					continue;
				fx.m_pulseC += FX_PULSE_MS;
				if (fx.m_n <= 1)
				{
					dictionary ps = { { 'radius', 24.0f }, { 'scale', 1.6f } };
					PlayEffect(FX + "pelors_strike.effect", fx.m_pos, ps);
				}
				else
				{
					float turn = randf() * PI * 2 / fx.m_n;
					for (int k = 0; k < fx.m_n; k++)
					{
						float ang = turn + PI * 2 * k / fx.m_n;
						dictionary ps = { { 'radius', 18.0f }, { 'scale', 2.0f } };
						PlayEffect(FX + "pelors_strike.effect", fx.m_pos + vec2(cos(ang), sin(ang)) * fx.m_ring, ps);
					}
				}
				g_furyPulses++;
			}
		}

		void UpdateGenerosity(int ms)
		{
			UpdateFuryFx(ms);
			auto plr = LocalGenerosity();
			if (plr is null)
			{
				if (g_fury !is null)
					EndFury("no generosity paladin");
				return;
			}
			if (g_inTown)
			{
				ResetBlessing(plr, "town");
				return;
			}
			if (g_gainC > 0)
				g_gainC -= ms;
			if (g_convC > 0)
				g_convC -= ms;
			ResolveLoH(plr);
			UpdateFury(ms);
			auto sk = cast<HWPGenFury>(FindSkill(plr, PF));
			if (sk !is null)
				sk.RestoreCooldown();
		}

		string GenStatus(PlayerBase@ plr)
		{
			string ret = "gen: blessing " + Blessing(plr) + "/" + BLESSING_MAX + " mul " + Rounded(BlessingMul(plr) * 1000)
				+ " solo " + (Solo() ? "yes" : "no") + " gaincd " + max(0, g_gainC) + " convcd " + max(0, g_convC)
				+ "; gained " + g_genGained + " blocked " + g_genBlocked + " loh " + g_genLoH + " kills " + g_genKills + " conv " + g_genConv
				+ " resets " + g_genResets + "; scaled bs " + g_bsScaled + " loh " + g_lohScaled + " conv " + g_convScaled
				+ "; fury casts " + g_furyCasts + " refused " + g_furyRefused + " failed " + g_furyFailed + " sacrifices " + g_furySacrifices
				+ " blinds " + g_furyBlinds + " cancels " + g_furyCancels + " pulses " + g_furyPulses + " asks " + g_furyAsks + " last " + g_furyLast
				+ "; pentival runs " + g_pentivalRuns + " " + g_pentivalLast;
			auto sk = cast<HWPGenFury>(FindSkill(plr, PF));
			if (sk !is null)
				ret += "; cd " + max(0, sk.m_cooldownC) + "/" + sk.m_cooldown;
			if (g_fury !is null)
			{
				auto t = g_fury.m_target;
				ret += "; holding " + g_fury.m_unit.GetId() + " left " + g_fury.m_left + (g_fury.m_locked ? " locked" : " free");
				if (t !is null)
				{
					auto ca = cast<CompositeActorBehavior>(t);
					// the casting skills the hold cuts (passive ones run on, see CutCasting)
					int casting = 0;
					for (uint i = 0; ca !is null && i < ca.m_skills.length(); i++)
					{
						if (Active(ca.m_skills[i]) && !Passive(ca.m_skills[i]))
							casting++;
					}
					if (ca !is null)
					{
						vec2 am = ca.m_buffs.ArmorMul();
						ret += " armormul " + Rounded(am.x * 1000) + " resmul " + Rounded(am.y * 1000) + " taken " + Rounded(ca.m_buffs.DamageTakenMul() * 1000);
					}
					ret += " casting " + casting + " [" + CastingNames(ca) + "]" + (ca.m_unit.GetPhysicsBody() is null ? " bodiless" : "");
				}
			}
			if (plr !is null)
				ret += "; mana " + int(ManaPts(plr) + 0.5f) + " locked " + (HasOwnBuff(plr, "pelors_channel") ? "yes" : "no");
			return ret;
		}

		bool HasOwnBuff(PlayerBase@ plr, const string &in name)
		{
			auto def = Buff(name);
			return plr !is null && def !is null && plr.HasBuff(def.m_pathHash);
		}

		void CmdGen(array<string>@ args)
		{
			auto plr = cast<PlayerBase>(GetLocalPlayer());
			if (plr is null || !Learned(plr, PB))
			{
				HWP::Commands::Reply("gen: the local player is not a Paladin of Generosity");
				return;
			}
			string sub = args.length() > 0 ? args[0] : "status";
			if (sub == "stacks" && args.length() > 1)
			{
				SetBlessing(plr, int(parseInt(args[1])), "command");
				HWP::Commands::Reply("gen: blessing " + Blessing(plr));
				return;
			}
			if (sub == "cd")
			{
				auto sk = FindSkill(plr, PF);
				if (sk !is null)
					sk.ResetCooldown();
				g_gainC = 0;
				g_convC = 0;
				HWP::Commands::Reply("gen: cooldowns reset");
				return;
			}
			if (sub == "solo")
			{
				string v = args.length() > 1 ? args[1] : "auto";
				g_soloForce = v == "on" ? 1 : (v == "off" ? 0 : -1);
				HWP::Commands::Reply("gen: solo " + (Solo() ? "yes" : "no") + " (" + v + ")");
				return;
			}
			if (sub == "pick")
			{
				// hwp gen pick [dx dy]: what a cast aimed at the player + (dx, dy) would pick and
				// why it would be refused (no cast, no cost)
				vec2 aim = xy(plr.m_unit.GetPosition());
				if (args.length() >= 3)
					aim += vec2(float(parseFloat(args[1])), float(parseFloat(args[2])));
				auto a = PickFuryTarget(plr, aim);
				string why = FuryRefusal(plr, a);
				HWP::Commands::Reply("gen: pick " + (a is null ? "none" : a.m_unit.GetId() + " " + a.m_unit.GetDebugName()
					+ " " + Reflect::GetTypeName(a)) + "; " + (why.isEmpty() ? "holds" : "refused: " + why)
					+ (g_furyPickVia.isEmpty() ? "" : "; via " + g_furyPickVia));
				return;
			}
			if (sub == "fury")
			{
				// hwp gen fury [now] [dx dy]: the cast through the skill (its checks and costs), aimed at
				// the nearest enemy, or at the player + (dx, dy); "now": the hold at once, no cast
				auto sk = cast<HWPGenFury>(FindSkill(plr, PF));
				if (sk is null)
				{
					HWP::Commands::Reply("gen: no pelor's fury");
					return;
				}
				bool now = args.length() > 1 && args[1] == "now";
				uint at = now ? 2 : 1;
				vec2 me = xy(plr.m_unit.GetPosition());
				vec2 aim = me;
				if (args.length() >= at + 2)
					aim = me + vec2(float(parseFloat(args[at])), float(parseFloat(args[at + 1])));
				else
				{
					auto near = EnemiesNear(me, float(sk.m_range), plr.Team);
					float best = 1e9f;
					for (uint i = 0; i < near.length(); i++)
					{
						float d = dist(xy(near[i].m_unit.GetPosition()), me);
						if (d < best)
						{
							best = d;
							aim = xy(near[i].m_unit.GetPosition());
						}
					}
				}
				if (now)
				{
					auto a = PickFuryTarget(plr, aim);
					string why = FuryRefusal(plr, a);
					if (why.isEmpty() && StartFury(plr, sk, a))
						HWP::Commands::Reply("gen: fury held " + a.m_unit.GetId());
					else
					{
						Refuse(plr, why.isEmpty() ? "the buff was refused" : why, false);
						HWP::Commands::Reply("gen: fury refused: " + why);
					}
					return;
				}
				bool ok = sk.Activate(aim, 1.0f);
				HWP::Commands::Reply("gen: fury cast " + (ok ? "started" : "refused") + " at " + Rounded(aim.x) + " " + Rounded(aim.y) + "; " + g_furyLast);
				return;
			}
			HWP::Commands::Reply(GenStatus(plr));
		}
	}
}

// Pelor's Fury: the target pick and the held-back cost (see the file comment)
class HWPGenFury : Skills::PlayerSkillPosition
{
	Actor@ m_target;
	PointCost@ m_realCost;
	int m_baseCooldown;
	bool m_bossCooldown;
	int m_refusedAt = -100000;

	HWPGenFury(UnitPtr unit, SValue& params) { super(unit, params); }

	void Initialize(Actor@ owner, UnitPtr unit, array<SValue@>@ params, uint id) override
	{
		Skills::PlayerSkillPosition::Initialize(owner, unit, params, id);
		m_baseCooldown = m_cooldown;
	}

	bool CanActivate(bool warn = true) override
	{
		auto plr = cast<PlayerBase>(m_owner);
		if (plr !is null && HWP::Specs::IsLocal(plr) && m_castingT < 0)
		{
			string why = "";
			if (HWP::Specs::g_fury !is null)
				why = "a hold is running";
			else if (HWP::Specs::Blessing(plr) < HWP::Specs::BLESSING_MAX)
				why = "blessing " + HWP::Specs::Blessing(plr) + "/" + HWP::Specs::BLESSING_MAX;
			if (!why.isEmpty())
			{
				// warn: a press (the HUD asks without one every frame). The targeting helper asks a
				// press without a warning first and warns only once its input buffer runs out
				// (CheckQueued), which a real press below 10 never reached (plan-generosity
				// 20261027-015913: no refusal, no "cant"), so the press frame itself warns too;
				// once per 300 ms, the two never both speak
				if (warn || JustPressed(plr))
				{
					int now = g_scene.GetTime();
					if (now - m_refusedAt >= 300 || now < m_refusedAt)
					{
						m_refusedAt = now;
						HWP::Specs::g_furyAsks++;
						HWP::Specs::Refuse(plr, why);
					}
				}
				return false;
			}
		}
		return Skills::PlayerSkillPosition::CanActivate(warn);
	}

	// this skill's button went down this frame
	bool JustPressed(PlayerBase@ plr)
	{
		auto p = cast<Player>(plr);
		return p !is null && p.m_targetHelper !is null && p.m_targetHelper.GetSkillInput(this).Pressed;
	}

	// the cost is paid in Deactivate, when the hold starts: nothing is spent by the castpoint
	PointCost@ GetCost() override
	{
		if (m_castingT >= 0)
			return PointCost(0, 0);
		return Skills::PlayerSkillPosition::GetCost();
	}

	bool Activate(vec2 target, float intensity) override
	{
		auto plr = cast<PlayerBase>(m_owner);
		if (plr is null || !HWP::Specs::IsLocal(plr))
			return Skills::PlayerSkillPosition::Activate(target, intensity);
		if (!CanActivate())
			return false;
		auto a = HWP::Specs::PickFuryTarget(plr, target);
		string why = HWP::Specs::FuryRefusal(plr, a, float(m_range) + 48.0f);
		if (!why.isEmpty())
		{
			HWP::Specs::Refuse(plr, why);
			return false;
		}
		@m_target = a;
		@m_realCost = Skills::PlayerSkillPosition::GetCost();
		vec2 at = xy(a.m_unit.GetPosition());
		NetActivate(at, intensity);
		(Network::Message("PlayerActiveSkillActivate") << int(m_skillId) << at << intensity).SendToAll();
		return true;
	}

	void Deactivate() override
	{
		bool passed = m_castingT >= m_castpoint;
		Skills::PlayerSkillPosition::Deactivate();
		auto plr = cast<PlayerBase>(m_owner);
		if (plr is null || !HWP::Specs::IsLocal(plr) || m_target is null)
			return;
		auto a = m_target;
		@m_target = null;
		if (!passed)
		{
			HWP::Specs::g_furyLast = "cast cut before the castpoint";
			return;
		}
		string why = HWP::Specs::FuryRefusal(plr, a);
		float mana = plr.m_record.mana;
		if (why.isEmpty() && (m_realCost !is null && !plr.UsePoints(true, true, m_realCost)))
			why = "not enough mana";
		if (why.isEmpty() && !HWP::Specs::StartFury(plr, this, a))
		{
			why = "the buff was refused";
			plr.m_record.mana = mana;
		}
		if (!why.isEmpty())
		{
			m_cooldownC = 0;
			HWP::Specs::g_furyFailed++;
			HWP::Specs::Refuse(plr, why);
			return;
		}
		if (HWP::Specs::IsBossActor(a))
		{
			m_cooldown = HWP::Specs::FURY_BOSS_CD;
			m_cooldownC = int(m_cooldown * m_modCooldownMul);
			m_bossCooldown = true;
		}
	}

	// the boss cooldown shows as a full sweep (m_cooldown 60 s) until it runs out
	void RestoreCooldown()
	{
		if (m_bossCooldown && m_cooldownC <= 0)
		{
			m_cooldown = m_baseCooldown;
			m_bossCooldown = false;
		}
	}
}

// Lay on Hands (this spec's copy): healing x the Blessing multiplier; notes who it heals
class HWPGenHeal : Heal
{
	HWPGenHeal(UnitPtr unit, SValue& params) { super(unit, params); }

	bool Apply(Actor@ owner, UnitPtr target, vec2 pos, vec2 dir, float intensity, bool husk) override
	{
		float mul = HWP::Specs::BlessingMul(owner);
		if (HWP::Specs::IsLocal(owner) && CanApply(owner, target, pos, dir, intensity))
			HWP::Specs::NoteLoH(owner, cast<Actor>(target.GetScriptBehavior()));
		bool ok = Heal::Apply(owner, target, pos, dir, intensity * mul, husk);
		if (ok && mul > 1.0f)
			HWP::Specs::g_lohScaled++;
		return ok;
	}
}

class HWPGenHPHeal : HPBasedHeal
{
	HWPGenHPHeal(UnitPtr unit, SValue& params) { super(unit, params); }

	bool Apply(Actor@ owner, UnitPtr target, vec2 pos, vec2 dir, float intensity, bool husk) override
	{
		return HPBasedHeal::Apply(owner, target, pos, dir, intensity * HWP::Specs::BlessingMul(owner), husk);
	}
}

// Conviction (this spec's copy): mana x the Blessing multiplier, a Blessing stack per 6 s
class HWPGenConvictionMana : GivePercentageMana
{
	HWPGenConvictionMana(UnitPtr unit, SValue& params) { super(unit, params); }

	bool Apply(Actor@ owner, UnitPtr target, vec2 pos, vec2 dir, float intensity, bool husk) override
	{
		float mul = HWP::Specs::BlessingMul(owner);
		bool ok = GivePercentageMana::Apply(owner, target, pos, dir, intensity * mul, husk);
		if (ok)
		{
			if (mul > 1.0f)
				HWP::Specs::g_convScaled++;
			HWP::Specs::OnConvictionMana(owner);
		}
		return ok;
	}
}

// Descendent of Pentival, on the Blessing stack's buff (intensity: the stack count). At the
// ArmorAdd step (attributes worked out, CalcAttributes) every equipped dragon trinket's stat
// modifiers and the Dragon Lord set bonus for the pieces worn are run again on a scratch copy of
// the attributes, and what they add, times stacks x pb-pct, is added to the real stats. The
// values come from the loaded trinkets (attuned ones too), so a game patch's numbers carry over.
namespace HWP
{
	namespace Specs
	{
		bool IsDragonTrinket(Item::Trinket@ t)
		{
			return t !is null && (t.m_id.findFirst("dragon_") == 0 || (t.m_set !is null && t.m_set.m_id == "dragon_lord"));
		}

		// stacks x pb-pct when Descendent of Pentival is on the record's player, else 0
		float PentivalK(PlayerRecord@ record, float stacks)
		{
			if (record is null || stacks <= 0)
				return 0;
			auto plr = cast<PlayerBase>(record.actor);
			if (plr is null || BindI(plr, PB, "dp-on", 0) <= 0)
				return 0;
			return stacks * BindF(plr, PB, "pb-pct", 0.005f);
		}

		// the dragon trinkets' modifiers and the set bonus the record wears now
		array<Modifiers::IModifier@>@ DragonModifiers(PlayerRecord@ record)
		{
			array<Modifiers::IModifier@> ret;
			Item::TrinketSet@ set = null;
			int pieces = 0;
			for (uint i = 0; i < record.trinketInventory.m_items.length(); i++)
			{
				auto t = record.trinketInventory.m_items[i];
				if (!IsDragonTrinket(t))
					continue;
				auto mods = t.GetModifiers(record);
				for (uint j = 0; mods !is null && j < mods.length(); j++)
					ret.insertLast(mods[j]);
				if (t.m_set !is null && t.m_set.m_id == "dragon_lord")
				{
					@set = t.m_set;
					pieces++;
				}
			}
			if (set !is null)
			{
				auto bonus = set.GetModifiers(pieces);
				for (uint j = 0; bonus !is null && j < bonus.length(); j++)
					ret.insertLast(bonus[j]);
			}
			return ret;
		}

		int g_pentivalRuns = 0;
		string g_pentivalLast = "";
	}
}

class HWPGenPentival : Modifiers::StatModifier
{
	HWPGenPentival(UnitPtr unit, SValue& params)
	{
		super(unit, params);
		Ordering = int(Modifiers::ModifierOrdering::ArmorAdd);
	}

	void Modify(PlayerRecord@ player, PlayerStats@ stats, float intensity) override
	{
		float k = HWP::Specs::PentivalK(player, intensity);
		if (k <= 0)
			return;
		auto mods = HWP::Specs::DragonModifiers(player);
		if (mods.length() == 0)
			return;
		PlayerStats s;
		s.Str = int(stats.Str); s.Dex = int(stats.Dex); s.Int = int(stats.Int); s.Foc = int(stats.Foc); s.Vit = int(stats.Vit);
		s.AttackPower = int(stats.AttackPower); s.SpellPower = int(stats.SpellPower);
		s.Health = int(stats.Health); s.Mana = int(stats.Mana);
		PlayerStats b;
		b.Str = int(s.Str); b.Dex = int(s.Dex); b.Int = int(s.Int); b.Foc = int(s.Foc); b.Vit = int(s.Vit);
		b.AttackPower = int(s.AttackPower); b.SpellPower = int(s.SpellPower); b.Health = int(s.Health); b.Mana = int(s.Mana);
		for (uint i = 0; i < mods.length(); i++)
		{
			auto sm = cast<Modifiers::StatModifier>(mods[i]);
			if (sm is null || !CheckConditionals(sm.m_conditionals, player.actor))
				continue;
			sm.Modify(player, s, 1.0f);
		}
		stats.Armor += int(round((int(s.Armor) - int(b.Armor)) * k));
		stats.ResistanceFire += int(round((int(s.ResistanceFire) - int(b.ResistanceFire)) * k));
		stats.ResistanceIce += int(round((int(s.ResistanceIce) - int(b.ResistanceIce)) * k));
		stats.ResistanceLightning += int(round((int(s.ResistanceLightning) - int(b.ResistanceLightning)) * k));
		stats.ResistancePoison += int(round((int(s.ResistancePoison) - int(b.ResistancePoison)) * k));
		stats.Health += int(round((int(s.Health) - int(b.Health)) * k));
		stats.Mana += int(round((int(s.Mana) - int(b.Mana)) * k));
		stats.HealthRegen += (float(s.HealthRegen) - float(b.HealthRegen)) * k;
		stats.ManaRegen += (float(s.ManaRegen) - float(b.ManaRegen)) * k;
		stats.SpellPower += int(round((int(s.SpellPower) - int(b.SpellPower)) * k));
		stats.AttackPower += int(round((int(s.AttackPower) - int(b.AttackPower)) * k));
		stats.SpellCritDamage += (float(s.SpellCritDamage) - float(b.SpellCritDamage)) * k;
		stats.MainHand.CritDamage += (float(s.MainHand.CritDamage) - float(b.MainHand.CritDamage)) * k;
		stats.OffHand.CritDamage += (float(s.OffHand.CritDamage) - float(b.OffHand.CritDamage)) * k;
		HWP::Specs::g_pentivalRuns++;
		HWP::Specs::g_pentivalLast = "k " + HWP::Specs::Rounded(k * 1000) + " armor +" + int(round((int(s.Armor) - int(b.Armor)) * k))
			+ " health +" + int(round((int(s.Health) - int(b.Health)) * k)) + " spellpwr +" + int(round((int(s.SpellPower) - int(b.SpellPower)) * k))
			+ " critdmg +" + HWP::Specs::Rounded((float(s.SpellCritDamage) - float(b.SpellCritDamage)) * k * 1000);
	}
}

// Descendent of Pentival's share of the Dragon Lord set's leech (a dynamic DamageLeech)
class HWPGenPentivalLeech : Modifiers::Modifier
{
	HWPGenPentivalLeech(UnitPtr unit, SValue& params) { }

	Modifiers::ModDynamism HasDamageLeech() override { return Modifiers::ModDynamism::Dynamic; }

	vec2 DamageLeech(PlayerBase@ player, Actor@ enemy, bool spell, int crit, float intensity) override
	{
		if (player is null)
			return vec2();
		float k = HWP::Specs::PentivalK(player.m_record, intensity);
		if (k <= 0)
			return vec2();
		vec2 sum;
		auto mods = HWP::Specs::DragonModifiers(player.m_record);
		for (uint i = 0; i < mods.length(); i++)
		{
			auto m = cast<Modifiers::Modifier>(mods[i]);
			if (m is null)
				continue;
			sum += m.DamageLeech(player, enemy, spell, crit, 1.0f);
		}
		return sum * k;
	}
}

namespace HWPSpecsGenerosity
{
	// Blessed Strike damage x the Blessing multiplier (before the damage is worked out)
	[Hook]
	void PlayerDamageActor(PlayerBase@ player, Actor@ actor, DamageInfo@ di, Skills::Skill@ weapon)
	{
		if (weapon is null || di is null || weapon.m_skillId != HWP::Specs::BLESSED_STRIKES)
			return;
		float mul = HWP::Specs::BlessingMul(player);
		if (mul <= 1.0f)
			return;
		di.PhysicalDamage = uint32(di.PhysicalDamage * mul + 0.5f);
		di.FireDamage = uint32(di.FireDamage * mul + 0.5f);
		di.IceDamage = uint32(di.IceDamage * mul + 0.5f);
		di.LightningDamage = uint32(di.LightningDamage * mul + 0.5f);
		di.PoisonDamage = uint32(di.PoisonDamage * mul + 0.5f);
		di.PureDamage = uint32(di.PureDamage * mul + 0.5f);
		HWP::Specs::g_bsScaled++;
	}

	// a Blessed Strike kill (the killer's client)
	[Hook]
	void PlayerKilledActor(Player@ player, Actor@ killed, DamageInfo@ di)
	{
		if (player is null || di is null || di.Weapon != HWP::Specs::BLESSED_STRIKES)
			return;
		HWP::Specs::OnBlessedKill(player);
	}
}
