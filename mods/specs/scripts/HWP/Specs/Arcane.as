// Arcane (Sorcerer): Blink and Living Mana.
// - Blink (arcane/blink.sval, HWPSpecsBlink): a teleport of the dodge's distance (BLINK_DIST,
//   + bl-far with Far Step) along the aim, then bl-dmg pure on every enemy within bl-radius of
//   where the sorcerer lands (through the skill's weapon info: spell crit applies). With a
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

		const float BLINK_DIST = 90;            // the dodge's (players/attacks/dash.sval dist)
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
			g_blinks = g_blinkHits = g_lastBlink = g_recasts = g_drained = g_converted = g_barrierSaves = g_fbUsed = g_conduitSent = g_floored = 0;
			g_lastRecast = "";
		}

		bool IsElemental(Skills::Skill@ sk)
		{
			if (sk is null || sk.m_skillId == BLINK)
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
			auto sk = cast<Skills::PlayerSkillDirectional>(FindSkill(plr, g_lastSpell));
			auto me = cast<Player>(plr);
			if (sk is null || me is null || sk.m_timeline is null || plr.m_record.dashCharges < 1)
				return;
			me.GiveDashCharges(-1);
			(Network::Message("PlayerSyncDashes") << plr.m_record.dashCharges).SendToAll();
			auto tl = sk.m_timeline.m_timeline;
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
			auto cost = sk.GetCost();
			float mana = cost.flatCost.y * cost.multiplier.y;
			if (ManaPts(plr) - mana < 1)
				g_floored++;
			SetManaPts(plr, max(1.0f, ManaPts(plr) - mana));
			sk.m_cooldownC = int(sk.m_cooldown * sk.m_modCooldownMul);
			g_recasts++;
			g_lastRecast = sk.m_id;
		}

		// Mana Conduit: a share of the mana lost goes to the teammates, through the host
		void Conduit(PlayerBase@ plr, float amount)
		{
			int mates = 0;
			for (uint i = 0; i < g_players.length(); i++)
			{
				if (g_players[i].peer != 255 && g_players[i].actor !is null && g_players[i].actor !is plr && !g_players[i].actor.IsDead())
					mates++;
			}
			if (mates == 0 || amount < 1)
				return;
			SValueBuilder b;
			b.PushDictionary();
			b.PushFloat("amount", amount);
			b.PopDictionary();
			HWP::Net::Request("specs.conduit", b.Build());
			g_conduitSent += int(amount + 0.5f);
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
				b.PushInteger("mana", int(amount / to.length() + 0.5f));
				b.PopDictionary();
				HWP::Net::Send(to[i], "specs.conduit_mana", b.Build());
			}
		}

		void OnConduitMana(SValue@ data)
		{
			auto me = cast<Player>(GetLocalPlayer());
			int mana = GetParamInt(UnitPtr(), data, "mana", false, 0);
			if (me !is null && !me.IsDead() && mana > 0)
				me.GiveMana(mana);
		}

		// mana lost to damage (attacker null: damage over time from a buff)
		void Drain(PlayerBase@ plr, Actor@ attacker, float lost)
		{
			if (lost <= 0)
				return;
			g_drained += int(lost + 0.5f);
			int cap = BindI(plr, LIVING_MANA, "lm-feedback");
			if (cap > 0 && attacker !is plr)
				g_feedback = min(float(cap), g_feedback + lost);
			float share = BindF(plr, LIVING_MANA, "lm-conduit");
			if (share > 0)
				Conduit(plr, lost * share);
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
			if (IsElemental(sk))
				g_lastSpell = sk.m_skillId;
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
			float bonus = BindF(plr, LIVING_MANA, "lm-regen");
			if (bonus > 0 && missing > 0)
				SetManaPts(plr, ManaPts(plr) + ms / 1000.0f * st.ManaRegen * st.ManaGain * bonus * missing);

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
	Teleport@ m_tele;

	HWPSpecsBlink(UnitPtr unit, SValue& params)
	{
		@m_hit = LoadEffects(unit, params, "hit-");
		@m_tele = Teleport(unit, params);
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
		m_tele.DoTeleport(plr, from + dir * HWP::Specs::BLINK_DIST * (1.0f + far));
		vec2 at = xy(plr.m_unit.GetPosition());
		float radius = HWP::Specs::BindF(plr, HWP::Specs::BLINK, "bl-radius", 20);
		// placeholders until the audio picker (art/specs/AUDIO.md)
		PlayEffect("effects/generic/other/arcane/magic_blink.effect", from);
		PlaySound3D(Resources::GetSoundEvent("event:/sfx/actors/bosses/boss_avatar/boss_avatar_blink_out"), xyz(from));
		PlayEffect("effects/generic/other/arcane/magic_blink.effect", at);
		dictionary ps = { { "radius", radius } };
		PlayEffect("effects/generic/explosions/arcane_explosion_1.effect", at, ps);
		PlaySound3D(Resources::GetSoundEvent("event:/sfx/actors/bosses/boss_avatar/boss_avatar_blink_in"), xyz(at));

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
		HWP::Log("specs", "blink: " + HWP::Specs::g_lastBlink + " px, " + enemies.length() + " hit" + recast);
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
