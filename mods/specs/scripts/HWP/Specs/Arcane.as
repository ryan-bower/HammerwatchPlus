// Arcane (Sorcerer): Blink and Living Mana.
// - Blink (arcane/blink.sval, HWPSpecsBlink): a teleport of BLINK_DIST px (112, + bl-far with
//   Far Step) along the aim, then bl-dmg pure on every enemy within bl-radius of where the
//   sorcerer lands (through the skill's weapon info: spell crit applies). The teleport is its
//   own (BlinkPath), not the vanilla Teleport action: that one raycasts with RaycastType::Any,
//   which a ledge's or stair's shoot-through rail stops, so Blink could not cross the stairs the
//   dash can't either (the user, 2026-10-25). BlinkPath asks the ray the projectiles ask
//   (RaycastType::Shot: shoot-through fixtures don't count), so walls still stop it short (x
//   BLINK_WALL_MARGIN, like the vanilla one) and ledges and stairs are crossed; the landing is
//   checked for room with the Any query (past a rail, over a floor tileset too) and nudged along
//   the aim (then back) up to BLINK_NUDGE.
//   Effects: blink_out at the start, blink_trail beads along the path, blink_in and the arcane
//   explosion where it lands (players/hwp/specs/effects/). With a
//   dash charge it spends one to replay the last elemental spell's timeline actions at the
//   start point, whatever its cooldown; that spell's cost is paid down to 1 mana and its
//   cooldown starts over. Void Barrier (bl-barrier ms): no lethal damage after a Blink.
// - Living Mana (arcane/living_mana.sval): max health is added to max mana (ConvertStat). Each
//   frame UpdateArcane turns the health the game moved since the last frame into mana (heals,
//   potions, regeneration, leech; and buff damage over time as a loss) and sets health to the
//   mana fraction, so the health bar shows the pool and a heal is refused only at full mana
//   (Heal.CanApply). A hit (HWPSpecsLivingMana, DamageTaken) drains the mana instead: the
//   health it is about to take is given back first, and a drain past the pool zeroes both, so
//   the hit kills. Casting leaves at least 1 mana. Regeneration + lm-regen x the missing mana
//   fraction. Arcane Feedback (lm-feedback, a cap): mana lost to damage is banked; the next
//   spell cast gets + FEEDBACK_PER_MANA damage per banked mana for FEEDBACK_TIME
//   (HWPSpecsFeedbackMul, a skill modifier). Mana Conduit (lm-conduit): that share of the mana
//   lost to damage goes to the teammates, split evenly (through the host: HWP::Net).
// Everything runs on the sorcerer's own client.
namespace HWP
{
	namespace Specs
	{
		const uint BLINK = HashString("hwp_sor_blink");
		const uint LIVING_MANA = HashString("hwp_sor_living_mana");
		const uint ELEMENTAL_ORB = HashString("elemental_orb");

		const float BLINK_DIST = 112;           // 2026-10-25: 90 (the dodge's) x 1.25, rounded (the user: "a little longer")
		const int BLINK_RAY_N = 3;              // the vanilla Teleport's ray-amount / ray-width
		const int BLINK_RAY_W = 9;
		const float BLINK_WALL_MARGIN = 0.95f;  // the vanilla ray-distance-mul, only when a wall cuts the blink
		const float BLINK_NUDGE = 24;           // the farthest a cramped landing is moved along the aim, then back
		const float BLINK_NUDGE_STEP = 4;
		const float BLINK_TRAIL_STEP = 16;      // a trail bead every this many px
		// assumed numbers (not in the design)
		const int FEEDBACK_TIME = 3000;         // the empowered spell's hits count this long
		const float FEEDBACK_PER_MANA = 0.005f; // + 0.5% damage per banked mana

		uint g_lastSpell = 0;      // the last elemental spell cast
		array<uint> g_castIds;     // the skills seen casting last frame
		float g_lastHp = -1;       // the health UpdateArcane set (-1: not yet)
		int g_barrierC = 0;
		float g_feedback = 0;      // banked mana for Arcane Feedback
		uint g_fbSkill = 0;        // the empowered spell
		float g_fbMul = 1;
		int g_fbC = 0;
		float g_conduitPend = 0;   // Mana Conduit shares not sent yet
		float g_conduitIn = 0;     // a teammate's shares not given yet (under 1 mana)
		int g_conduitSendC = 0;
		int g_bindsC = 0;
		int g_lmFeedback = 0;      // Living Mana's binds, read every BINDS_EVERY ms
		float g_lmConduit = 0;
		float g_lmRegen = 0;
		const int CONDUIT_SEND = 250;
		const int BINDS_EVERY = 250;

		// counters for `hwp specs`
		int g_blinks = 0;
		int g_blinkHits = 0;
		int g_lastBlink = 0;
		int g_recasts = 0;
		string g_lastRecast = "";
		int g_drained = 0;
		int g_converted = 0;
		int g_barrierSaves = 0;
		int g_fbUsed = 0;
		int g_conduitSent = 0;
		int g_floored = 0;
		int g_blinkLedges = 0;     // blinks that crossed what the vanilla Teleport's ray would have stopped at
		int g_blinkWalls = 0;      // blinks a wall cut short
		int g_blinkNudged = 0;     // landings moved for room
		int g_lastBlinkWant = 0;   // the distance the last Blink asked for
		int g_blinkFx = 0;         // effects the last Blink played
		bool g_poolBar = false;    // the one blue bar is up (HWPSpecsPoolHUD, ArcaneHUD.as)

		void ClearArcane()
		{
			g_lastSpell = 0;
			g_castIds.removeRange(0, g_castIds.length());
			g_lastHp = -1;
			g_barrierC = 0;
			g_feedback = 0;
			g_fbSkill = 0;
			g_fbMul = 1;
			g_fbC = 0;
			g_conduitPend = g_conduitIn = 0;
			g_conduitSendC = g_bindsC = 0;
			g_lmFeedback = 0;
			g_lmConduit = g_lmRegen = 0;
			g_blinks =g_blinkHits = g_lastBlink = g_recasts = g_drained = g_converted = g_barrierSaves = g_fbUsed = g_conduitSent = g_floored = 0;
			g_blinkLedges = g_blinkWalls = g_blinkNudged = g_lastBlinkWant = g_blinkFx = 0;
			g_lastRecast = "";
		}

		// Where a Blink from `from` toward `want` lands. The Shot ray (what NewProjectile moves
		// by) stops at walls and impenetrable actors, never at a shoot-through fixture (a ledge's
		// or stair's rail), so those are crossed; sensors, passable actors and damage takers are
		// skipped as the vanilla Teleport skips them. Then the landing needs room for the body:
		// the Any query (rails count, the sorcerer must not stand in one) with actors ignored,
		// nudged on along the aim up to BLINK_NUDGE, then back toward the start. A landing past
		// a rail (beyond where the Any ray stopped) must also be over a floor tileset: the Shot ray
		// ignores every shoot-through fixture, so without that a rail on the level's edge could be
		// crossed into the void. With no such spot the Blink stops where the vanilla Teleport would.
		class BlinkPath
		{
			vec2 m_at;
			bool m_ledge = false;   // the Any ray stopped earlier than the Shot ray: a rail was crossed
			bool m_wall = false;    // a wall cut it short
			bool m_nudged = false;

			BlinkPath(vec2 from, vec2 want)
			{
				m_at = from;
				vec2 dir = want - from;
				float dist = length(dir);
				if (dist < 0.01f)
					return;
				dir /= dist;
				float shotFrac = RayFraction(from, want, RaycastType::Shot);
				float anyFrac = RayFraction(from, want, RaycastType::Any);
				m_wall = shotFrac < 1;
				m_ledge = anyFrac < shotFrac - 0.01f;
				float d = m_wall ? dist * shotFrac * BLINK_WALL_MARGIN : dist;
				float railAt = m_ledge ? dist * anyFrac : dist + BLINK_NUDGE + 1;
				vec2 at = from + dir * d;
				if (!HasRoom(at, d > railAt))
				{
					bool found = false;
					for (float n = BLINK_NUDGE_STEP; n <= BLINK_NUDGE && !found; n += BLINK_NUDGE_STEP)
					{
						if (!m_wall && HasRoom(from + dir * (d + n), d + n > railAt))
						{
							at = from + dir * (d + n);
							found = true;
						}
						else if (d - n > 0 && HasRoom(from + dir * (d - n), d - n > railAt))
						{
							at = from + dir * (d - n);
							found = true;
						}
					}
					if (!found)
						at = from + dir * (dist * min(shotFrac, anyFrac) * BLINK_WALL_MARGIN);
					m_nudged = true;
				}
				m_at = at;
			}

			// the fraction of from -> to the first blocking hit stands at (1: nothing)
			float RayFraction(vec2 from, vec2 to, RaycastType type)
			{
				auto ray = g_scene.RaycastWide(BLINK_RAY_N, BLINK_RAY_W, from, to, ~0, type);
				for (uint i = 0; i < ray.length(); i++)
				{
					if (ray[i].fixture.IsSensor())
						continue;
					UnitPtr unit = ray[i].FetchUnit(g_scene);
					auto actor = cast<Actor>(unit.GetScriptBehavior());
					if (actor !is null && !actor.Impenetrable())
						continue;
					if (cast<IDamageTaker>(unit.GetScriptBehavior()) !is null)
						continue;
					return ray[i].fraction;
				}
				return 1.0f;
			}

			bool HasRoom(vec2 at, bool pastRail)
			{
				if (pastRail && g_scene.FetchTilesets(at).length() == 0)
					return false;
				auto hits = g_scene.QueryCircle(at, BLINK_RAY_W, ~0, RaycastType::Any, false);
				for (uint i = 0; i < hits.length(); i++)
				{
					UnitPtr unit = hits[i];
					if (cast<Actor>(unit.GetScriptBehavior()) !is null)
						continue;
					return false;
				}
				return true;
			}
		}

		// `hwp specs arcane`: the pool, the bar and the last Blink
		string ArcaneStatus(PlayerBase@ plr)
		{
			string ret = "specs arcane:";
			if (plr !is null)
			{
				int maxMana = max(1, plr.m_record.MaxMana());
				ret += " pool " + int(ManaPts(plr) + 0.5f) + "/" + maxMana
					+ " hp " + int(float(plr.m_record.hp) * 1000 + 0.5f) + " mana " + int(float(plr.m_record.mana) * 1000 + 0.5f)
					+ " living " + (Learned(plr, LIVING_MANA) ? 1 : 0) + " bar " + (g_poolBar ? "on" : "off")
					+ " dist " + int(BLINK_DIST * (1.0f + BindF(plr, BLINK, "bl-far")) + 0.5f);
			}
			ret += "; blinks " + g_blinks + " last " + g_lastBlink + " want " + g_lastBlinkWant + " ledges " + g_blinkLedges
				+ " walls " + g_blinkWalls + " nudged " + g_blinkNudged + " fx " + g_blinkFx;
			return ret;
		}

		// a skill's timeline, for the classes that have one (Lightning Ball is DirectionalCharged,
		// Flame Step Position); null for the rest (channelled spells), which Blink can't replay
		Skills::PlayerSkillTimeline@ Timeline(Skills::Skill@ sk)
		{
			auto d = cast<Skills::PlayerSkillDirectional>(sk);
			if (d !is null)
				return d.m_timeline;
			auto c = cast<Skills::PlayerSkillDirectionalCharged>(sk);
			if (c !is null)
				return c.m_timeline;
			auto p = cast<Skills::PlayerSkillPosition>(sk);
			if (p !is null)
				return p.m_timeline;
			auto a = cast<Skills::PlayerSkillAutomatic>(sk);
			if (a !is null)
				return a.m_timeline;
			return null;
		}

		// an elemental spell Blink can replay (Blink itself never)
		bool IsElemental(Skills::Skill@ sk)
		{
			if (sk is null || sk.m_skillId == BLINK || Timeline(sk) is null)
				return false;
			if (sk.m_skillId == ELEMENTAL_ORB)
				return true;
			uint64 mask = ApplyTag(ApplyTag(ApplyTag(0, g_skillTags.GetTag("fire")), g_skillTags.GetTag("ice")), g_skillTags.GetTag("lightning"));
			return (sk.m_tags & mask) != 0;
		}

		string LastSpellName(PlayerBase@ plr)
		{
			Skills::Skill@ sk = null;
			if (g_lastSpell != 0)
				@sk = FindSkill(plr, g_lastSpell);
			return sk !is null ? sk.m_id : "none";
		}

		float ManaPts(PlayerBase@ plr)
		{
			return plr.m_record.mana * max(1, plr.m_record.MaxMana());
		}

		void SetManaPts(PlayerBase@ plr, float pts)
		{
			plr.m_record.mana = clamp(pts / float(max(1, plr.m_record.MaxMana())), 0.0f, 1.0f);
		}

		// The last elemental spell again at the start point: its timeline's action lists, run the
		// way PlayerSkillTimeline.ExecuteEntry runs them (and sent on the same way)
		void Recast(PlayerBase@ plr, vec2 from, vec2 dir)
		{
			auto sk = cast<Skills::PlayerSkill>(FindSkill(plr, g_lastSpell));
			auto timeline = Timeline(sk);
			auto me = cast<Player>(plr);
			if (sk is null || me is null || timeline is null || plr.m_record.dashCharges < 1)
				return;
			float mana = ManaCost(plr, sk);
			me.GiveDashCharges(-1);
			(Network::Message("PlayerSyncDashes") << plr.m_record.dashCharges).SendToAll();
			auto tl = timeline.m_timeline;
			for (uint i = 0; i < tl.length(); i++)
			{
				if (tl[i].actions is null)
					continue;
				auto params = DoActions(tl[i].actions.actions, plr, null, from, dir, 1.0f);
				if (params is null)
					(Network::Message("PlayerSkillExecuteActions") << int(sk.m_skillId) << tl[i].actions.index << from << dir).SendToAll();
				else
					(Network::Message("PlayerSkillExecuteActionsP") << int(sk.m_skillId) << tl[i].actions.index << from << dir << params).SendToAll();
			}
			if (ManaPts(plr) - mana < 1)
				g_floored++;
			SetManaPts(plr, max(1.0f, ManaPts(plr) - mana));
			sk.m_cooldownC = int(sk.m_cooldown * sk.m_modCooldownMul);
			g_recasts++;
			g_lastRecast = sk.m_id;
		}

		// Mana Conduit: a share of the mana lost goes to the teammates, through the host. Shares
		// add up in g_conduitPend and go out every CONDUIT_SEND ms (UpdateArcane), so a drain of a
		// fraction a frame still arrives and one request carries many hits
		void Conduit(PlayerBase@ plr, float amount)
		{
			int mates = 0;
			for (uint i = 0; i < g_players.length(); i++)
			{
				if (g_players[i].peer != 255 && g_players[i].actor !is null && g_players[i].actor !is plr && !g_players[i].actor.IsDead())
					mates++;
			}
			if (mates > 0 && amount > 0)
				g_conduitPend += amount;
		}

		void FlushConduit()
		{
			if (g_conduitPend < 1)
				return;
			SValueBuilder b;
			b.PushDictionary();
			b.PushFloat("amount", g_conduitPend);
			b.PopDictionary();
			HWP::Net::Request("specs.conduit", b.Build());
			g_conduitSent += int(g_conduitPend + 0.5f);
			g_conduitPend = 0;
		}

		// host: split it between every live player but the sender
		void OnConduit(uint8 peer, SValue@ data)
		{
			float amount = GetParamFloat(UnitPtr(), data, "amount", false, 0);
			array<uint8> to;
			for (uint i = 0; i < g_players.length(); i++)
			{
				if (g_players[i].peer != 255 && g_players[i].peer != peer && g_players[i].actor !is null && !g_players[i].actor.IsDead())
					to.insertLast(g_players[i].peer);
			}
			for (uint i = 0; i < to.length(); i++)
			{
				SValueBuilder b;
				b.PushDictionary();
				b.PushFloat("mana", amount / to.length());
				b.PopDictionary();
				HWP::Net::Send(to[i], "specs.conduit_mana", b.Build());
			}
		}

		// a teammate's share; fractions are kept until they make a whole point
		void OnConduitMana(SValue@ data)
		{
			auto me = cast<Player>(GetLocalPlayer());
			if (me is null || me.IsDead())
				return;
			g_conduitIn += GetParamFloat(UnitPtr(), data, "mana", false, 0);
			int mana = int(g_conduitIn);
			if (mana > 0)
			{
				me.GiveMana(mana);
				g_conduitIn -= mana;
			}
		}

		// mana lost to damage (attacker null: damage over time from a buff)
		void Drain(PlayerBase@ plr, Actor@ attacker, float lost)
		{
			if (lost <= 0)
				return;
			g_drained += int(lost + 0.5f);
			if (g_lmFeedback > 0 && attacker !is plr)
				g_feedback = min(float(g_lmFeedback), g_feedback + lost);
			if (g_lmConduit > 0)
				Conduit(plr, lost * g_lmConduit);
		}

		// Living Mana's binds: they change only with skills and orbs, so read every BINDS_EVERY ms
		void ReadLivingBinds(PlayerBase@ plr)
		{
			g_lmFeedback = BindI(plr, LIVING_MANA, "lm-feedback");
			g_lmConduit = BindF(plr, LIVING_MANA, "lm-conduit");
			g_lmRegen = BindF(plr, LIVING_MANA, "lm-regen");
		}

		// a hit (Player.Damage, through DamageTaken just before it takes the health)
		void LivingHit(PlayerBase@ plr, Actor@ attacker, int dmg)
		{
			if (!IsLocal(plr) || dmg <= 0 || plr.IsDead() || !Learned(plr, LIVING_MANA))
				return;
			float have = ManaPts(plr);
			float drain = dmg;
			if (g_barrierC > 0 && drain >= have)
			{
				drain = max(0.0f, have - 1);
				g_barrierSaves++;
			}
			if (drain >= have)
			{
				// the pool is gone: the hit takes the health below 0 and Damage calls OnDeath
				plr.m_record.mana = 0;
				plr.m_record.hp = 0;
				g_lastHp = -1;
				Drain(plr, attacker, have);
				return;
			}
			SetManaPts(plr, have - drain);
			plr.m_record.hp = float(plr.m_record.hp) + float(dmg) / float(max(1, plr.GetMaxHp()));
			Drain(plr, attacker, drain);
		}

		void OnSpellCast(PlayerBase@ plr, Skills::Skill@ sk)
		{
			if (!IsElemental(sk))
				return;
			g_lastSpell = sk.m_skillId;
			// the bank goes on the next elemental spell, never on Blink
			if (g_feedback >= 1)
			{
				g_fbSkill = sk.m_skillId;
				g_fbMul = 1.0f + g_feedback * FEEDBACK_PER_MANA;
				g_fbC = FEEDBACK_TIME;
				Log("specs", "arcane feedback: " + int(g_feedback + 0.5f) + " mana, " + sk.m_id + " x" + formatFloat(g_fbMul, "", 0, 3));
				g_feedback = 0;
				g_fbUsed++;
				plr.m_record.RefreshModifiers();
			}
		}

		void UpdateArcane(int ms)
		{
			auto plr = cast<PlayerBase>(GetLocalPlayer());
			g_barrierC -= ms;
			if (g_fbC > 0)
			{
				g_fbC -= ms;
				if (g_fbC <= 0)
				{
					g_fbSkill = 0;
					g_fbMul = 1;
					if (plr !is null)
						plr.m_record.RefreshModifiers();
				}
			}
			if (plr is null || plr.IsDead() || (!Learned(plr, LIVING_MANA) && !Learned(plr, BLINK)))
			{
				g_lastHp = -1;
				return;
			}

			// a spell's cast starting (m_castingT leaving -1), whichever way it was cast
			array<uint> casting;
			for (uint i = 0; i < plr.m_skills.length(); i++)
			{
				auto sk = cast<Skills::PlayerSkill>(plr.m_skills[i]);
				if (sk is null || sk.m_type != PlayerSkillType::Spell || sk.m_castingT < 0)
					continue;
				casting.insertLast(sk.m_skillId);
				if (g_castIds.find(sk.m_skillId) < 0)
					OnSpellCast(plr, sk);
			}
			g_castIds = casting;

			if (!Learned(plr, LIVING_MANA))
				return;
			g_bindsC -= ms;
			if (g_bindsC <= 0)
			{
				g_bindsC = BINDS_EVERY;
				ReadLivingBinds(plr);
			}
			g_conduitSendC -= ms;
			if (g_conduitSendC <= 0)
			{
				g_conduitSendC = CONDUIT_SEND;
				FlushConduit();
			}
			float maxHp = max(1, plr.GetMaxHp());
			float hp = plr.m_record.hp;
			if (g_lastHp >= 0 && abs(hp - g_lastHp) > 0.00001f)
			{
				float pts = (hp - g_lastHp) * maxHp;
				if (pts > 0)
				{
					SetManaPts(plr, ManaPts(plr) + pts);
					g_converted += int(pts + 0.5f);
				}
				else
				{
					float have = ManaPts(plr);
					SetManaPts(plr, have + pts);
					Drain(plr, null, min(-pts, have));
				}
			}

			// regeneration: + lm-regen x the missing fraction of the vanilla rate
			auto st = plr.m_record.currStats;
			float missing = 1.0f - plr.m_record.mana;
			if (g_lmRegen > 0 && missing > 0)
				SetManaPts(plr, ManaPts(plr) + ms / 1000.0f * st.ManaRegen * st.ManaGain * g_lmRegen * missing);

			// casting stops at 1 mana
			if (ManaPts(plr) < 1)
			{
				SetManaPts(plr, 1);
				g_floored++;
			}

			plr.m_record.hp = max(plr.m_record.mana, 1.0f / maxHp);
			g_lastHp = plr.m_record.hp;
		}
	}
}

// Blink's cast: the recast at the start point, the teleport, the pure damage where it lands.
// The child "hit" effects at intensity bl-dmg / 100.
class HWPSpecsBlink : IEffect
{
	EffectList@ m_hit;

	HWPSpecsBlink(UnitPtr unit, SValue& params)
	{
		@m_hit = LoadEffects(unit, params, "hit-");
	}

	CanEvade IsEvadable(Actor@ attacker) { return CanEvade::Neither; }
	void SetWeaponInformation(uint weapon) { PropagateWeaponInformation(m_hit, weapon); }
	bool CanApply(Actor@ owner, UnitPtr target, vec2 pos, vec2 dir, float intensity) override { return owner !is null; }

	bool Apply(Actor@ owner, UnitPtr target, vec2 pos, vec2 dir, float intensity, bool husk)
	{
		auto plr = cast<PlayerBase>(owner);
		if (plr is null || husk || !HWP::Specs::IsLocal(owner))
			return true;
		vec2 from = xy(plr.m_unit.GetPosition());
		if (length(dir) < 0.01f)
			dir = vec2(cos(plr.m_dirAngle), sin(plr.m_dirAngle));
		dir = normalize(dir);

		string recast = "";
		if (plr.m_record.dashCharges >= 1 && HWP::Specs::g_lastSpell != 0)
		{
			int before = HWP::Specs::g_recasts;
			HWP::Specs::Recast(plr, from, dir);
			if (HWP::Specs::g_recasts > before)
				recast = ", recast " + HWP::Specs::g_lastRecast;
		}

		float far = HWP::Specs::BindF(plr, HWP::Specs::BLINK, "bl-far");
		float want = HWP::Specs::BLINK_DIST * (1.0f + far);
		HWP::Specs::BlinkPath@ path = HWP::Specs::BlinkPath(from, from + dir * want);
		vec3 was = plr.m_unit.GetPosition();
		plr.m_unit.SetPosition(xyz(path.m_at, was.z));
		vec2 at = xy(plr.m_unit.GetPosition());
		float radius = HWP::Specs::BindF(plr, HWP::Specs::BLINK, "bl-radius", 20);
		// the look (2026-10-25): the vanish, a bead trail along the skipped path, the arrival
		int fx = 0;
		PlayEffect(HWP::Specs::FX + "blink_out.effect", from);
		fx++;
		float gone = dist(from, at);
		for (float d = HWP::Specs::BLINK_TRAIL_STEP; d < gone; d += HWP::Specs::BLINK_TRAIL_STEP)
		{
			PlayEffect(HWP::Specs::FX + "blink_trail.effect", from + dir * d);
			fx++;
		}
		PlayEffect(HWP::Specs::FX + "blink_in.effect", at);
		fx++;
		// sounds picked in the audio picker (art/specs/AUDIO.md); the vanish at twice the volume, as asked
		PlayEffect("effects/generic/other/arcane/magic_blink.effect", from);
		auto vanish = Resources::GetSoundEvent("event:/sfx/actors/undead/shade/shade/shade_blink_out");
		if (vanish !is null)
		{
			SoundInstance@ si = vanish.PlayTracked(xyz(from));
			si.SetVolume(2.0f);
			si.SetPaused(false);
		}
		PlayEffect("effects/generic/other/arcane/magic_blink.effect", at);
		dictionary ps = { { "radius", radius } };
		PlayEffect("effects/generic/explosions/arcane_explosion_1.effect", at, ps);
		PlaySound3D(Resources::GetSoundEvent("event:/sfx/actors/undead/shade/shade/shade_blink_in"), xyz(at));

		float dmg = HWP::Specs::BindF(plr, HWP::Specs::BLINK, "bl-dmg", 25);
		auto enemies = HWP::Specs::EnemiesNear(at, radius, plr.Team);
		for (uint i = 0; i < enemies.length(); i++)
		{
			auto a = enemies[i];
			ApplyEffects(m_hit, plr, a.m_unit, xy(a.m_unit.GetPosition()), dir, dmg / 100.0f, false);
		}
		int barrier = HWP::Specs::BindI(plr, HWP::Specs::BLINK, "bl-barrier");
		if (barrier > 0)
			HWP::Specs::g_barrierC = barrier;

		HWP::Specs::g_blinks++;
		HWP::Specs::g_blinkHits += enemies.length();
		HWP::Specs::g_lastBlink = int(dist(from, at) + 0.5f);
		HWP::Specs::g_lastBlinkWant = int(want + 0.5f);
		HWP::Specs::g_blinkFx = fx + 1;
		string how = "";
		if (path.m_ledge)
		{
			HWP::Specs::g_blinkLedges++;
			how += ", over ledge";
		}
		if (path.m_wall)
		{
			HWP::Specs::g_blinkWalls++;
			how += ", wall";
		}
		if (path.m_nudged)
		{
			HWP::Specs::g_blinkNudged++;
			how += ", nudged";
		}
		HWP::Log("specs", "blink: " + HWP::Specs::g_lastBlink + " px of " + HWP::Specs::g_lastBlinkWant + ", " + enemies.length() + " hit" + recast + how
			+ ", fx " + HWP::Specs::g_blinkFx);
		return true;
	}
}

// Living Mana: a hit drains the mana instead of the health (HWP::Specs::LivingHit)
class HWPSpecsLivingMana : Modifiers::Modifier
{
	HWPSpecsLivingMana(UnitPtr unit, SValue& params) { }

	Modifiers::ModDynamism HasDamageTaken() override { return Modifiers::ModDynamism::Dynamic; }
	void DamageTaken(PlayerBase@ player, Actor@ attacker, int dmg, float intensity) override
	{
		HWP::Specs::LivingHit(player, attacker, dmg);
	}
}

// Arcane Feedback: the empowered spell's damage, while its window lasts
class HWPSpecsFeedbackMul : Modifiers::SkillModifier
{
	HWPSpecsFeedbackMul(UnitPtr unit, SValue& params) { super(unit, params); }

	void Modify(Skills::Skill@ skill, float intensity) override
	{
		if (HWP::Specs::g_fbSkill != 0 && skill.m_skillId == HWP::Specs::g_fbSkill)
			skill.m_modDamageMul *= HWP::Specs::g_fbMul;
	}
}
