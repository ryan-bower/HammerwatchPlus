// Bannerlord (Warrior): Battlefield Standard and Righteous Crusade.
// - Battlefield Standard (bannerlord/battlefield_standard.sval): the first cast raises the
//   standard over the warrior for std-ttl. Every 250 ms, players within std-radius get
//   standard_dr (damage taken x (1 - std-dr)) for 600 ms. A second cast while it is carried
//   plants it where the warrior stands: free, even while the skill cools down, the effect
//   doubled and the time left halved. The cooldown runs from the raise.
//   Orbs: Feared Crest (std-enemy-debuff, an area Vulnerability on enemies in the radius),
//   Martyr's Banner (std-ally-mul on the others, std-self-mul 0 on the warrior).
// - Righteous Crusade (bannerlord/righteous_crusade.sval): the warrior's buffs last
//   crusade longer (BuffScaling), and allies within the standard get the same (crusade_<lvl>).
//   Orbs: War Drum (drum-tier: each Warcry or standard cast raises the Weakness of enemies
//   around by one step, up to the orb's step), Shared Provisions (prov-cdr: cooldown
//   reduction per buff on the party, the provisions stack).
// The standard runs on every peer: the cast action is sent with the skill's timeline
// (PlayerSkillExecuteActions), and Give applies each buff only where it has authority.
namespace HWP
{
	namespace Specs
	{
		const uint STANDARD = HashString("hwp_war_battlefield_standard");
		const uint CRUSADE = HashString("hwp_war_righteous_crusade");
		const int STANDARD_TICK = 250;
		const int PROVISIONS_CAP = 30;   // % (assumed)

		class Standard
		{
			Actor@ m_owner;
			bool m_planted;
			vec2 m_pos;
			int m_left;
			int m_tickC;
			float m_dr;
			int m_radius;
			float m_allyMul;
			float m_selfMul;
			string m_enemyDebuff;
			int m_crusadeLvl;
			UnitPtr m_fx;

			vec2 Pos() { return m_planted ? m_pos : xy(m_owner.m_unit.GetPosition()); }
		}

		array<Standard@> g_standards;

		Standard@ FindStandard(Actor@ owner)
		{
			for (uint i = 0; i < g_standards.length(); i++)
			{
				if (g_standards[i].m_owner is owner)
					return g_standards[i];
			}
			return null;
		}

		bool StandardCarried(Actor@ owner)
		{
			auto s = FindStandard(owner);
			return s !is null && !s.m_planted;
		}

		void StandardFx(Standard@ s)
		{
			s.m_fx = Kill(s.m_fx);
			dictionary ps = { { "radius", s.m_radius }, { "planted", s.m_planted ? 1 : 0 } };
			s.m_fx = Loop(FX + "standard.effect", s.Pos(), ps);
		}

		void RemoveStandard(uint i)
		{
			g_standards[i].m_fx = Kill(g_standards[i].m_fx);
			g_standards.removeAt(i);
		}

		// the skill's cast, on every peer
		void StandardCast(Actor@ owner)
		{
			auto plr = cast<PlayerBase>(owner);
			if (plr is null)
				return;
			auto s = FindStandard(owner);
			if (s !is null && !s.m_planted)
			{
				s.m_planted = true;
				s.m_pos = xy(owner.m_unit.GetPosition());
				s.m_left /= 2;
				s.m_tickC = 0;
				StandardFx(s);
				PlaySound3D(Resources::GetSoundEvent("event:/sfx/player/classes/priest/holy_banner/holy_banner"), xyz(s.m_pos));
				Log("specs", "standard: planted, " + s.m_left + " ms left, dr " + s.m_dr * 2);
			}
			else
			{
				if (s !is null)
					RemoveStandard(g_standards.findByRef(s));
				@s = Standard();
				@s.m_owner = owner;
				s.m_left = BindI(plr, STANDARD, "std-ttl", 10000);
				s.m_dr = BindF(plr, STANDARD, "std-dr", 0.02f);
				s.m_radius = BindI(plr, STANDARD, "std-radius", 75);
				s.m_allyMul = BindF(plr, STANDARD, "std-ally-mul", 1);
				s.m_selfMul = BindF(plr, STANDARD, "std-self-mul", 1);
				s.m_enemyDebuff = BindS(plr, STANDARD, "std-enemy-debuff");
				s.m_crusadeLvl = Learned(plr, CRUSADE) ? BindI(plr, CRUSADE, "crusade-lvl", 0) : 0;
				g_standards.insertLast(s);
				StandardFx(s);
				PlaySound3D(Resources::GetSoundEvent("event:/sfx/player/classes/warrior/war_cry/war_cry"), owner.m_unit.GetPosition());
				Log("specs", "standard: raised for " + s.m_left + " ms, dr " + s.m_dr + " radius " + s.m_radius
					+ " ally x" + s.m_allyMul + " self x" + s.m_selfMul
					+ (s.m_enemyDebuff != "" ? ", enemies " + s.m_enemyDebuff : "")
					+ (s.m_crusadeLvl > 0 ? ", crusade " + s.m_crusadeLvl : ""));
			}
			WarDrum(owner, s.Pos(), s.m_radius);
		}

		void StandardPulse(Standard@ s)
		{
			vec2 pos = s.Pos();
			float mul = s.m_planted ? 2.0f : 1.0f;
			auto dr = Buff(s.m_planted ? "standard_dr_planted" : "standard_dr");
			auto crusade = s.m_crusadeLvl > 0 ? Buff("crusade_" + s.m_crusadeLvl) : null;
			auto players = PlayersNear(pos, s.m_radius);
			for (uint i = 0; i < players.length(); i++)
			{
				bool self = players[i] is s.m_owner;
				Give(s.m_owner, players[i], dr, s.m_dr * mul * (self ? s.m_selfMul : s.m_allyMul), 600);
				if (!self && crusade !is null)
					Give(s.m_owner, players[i], crusade, 1, 600);
			}
			if (s.m_enemyDebuff != "")
			{
				auto debuff = Buff(s.m_enemyDebuff);
				auto enemies = EnemiesNear(pos, s.m_radius, s.m_owner.Team);
				for (uint i = 0; i < enemies.length(); i++)
					Give(s.m_owner, enemies[i], debuff);
			}
		}

		void UpdateStandards(int ms)
		{
			for (int i = int(g_standards.length()) - 1; i >= 0; i--)
			{
				auto s = g_standards[i];
				s.m_left -= ms;
				if (s.m_owner is null || s.m_owner.m_unit.IsDestroyed() || s.m_owner.IsDead() || s.m_left <= 0)
				{
					Log("specs", "standard: ended" + (s.m_left <= 0 ? "" : " (bearer gone)"));
					PlaySound3D(Resources::GetSoundEvent("event:/sfx/player/classes/priest/holy_banner/holy_banner_end"), xyz(s.Pos()));
					RemoveStandard(i);
					continue;
				}
				if (!s.m_planted && s.m_fx.IsValid())
					s.m_fx.SetPosition(s.m_owner.m_unit.GetPosition());
				s.m_tickC -= ms;
				if (s.m_tickC <= 0)
				{
					s.m_tickC += STANDARD_TICK;
					StandardPulse(s);
				}
			}
		}

		void ClearStandards()
		{
			for (int i = int(g_standards.length()) - 1; i >= 0; i--)
				RemoveStandard(i);
		}

		// War Drum: each AoE buff cast steps the Weakness of the enemies around one tier up,
		// to the orb's tier (1 minor, 2 normal, 3 greater)
		const array<string> WEAKNESS = { "", "tweak/buffs/status_effects.sval:weakness_minor",
			"tweak/buffs/status_effects.sval:weakness", "tweak/buffs/status_effects.sval:weakness_greater" };

		int WeaknessTier(Actor@ a)
		{
			for (int t = 3; t >= 1; t--)
			{
				if (a.HasBuff(HashString(WEAKNESS[t])))
					return t;
			}
			return 0;
		}

		void WarDrum(Actor@ owner, vec2 pos, int radius)
		{
			auto plr = cast<PlayerBase>(owner);
			int cap = min(3, BindI(plr, CRUSADE, "drum-tier", 0));
			if (cap <= 0)
				return;
			auto enemies = EnemiesNear(pos, radius, owner.Team);
			int hit = 0;
			for (uint i = 0; i < enemies.length(); i++)
			{
				int t = min(cap, WeaknessTier(enemies[i]) + 1);
				if (Give(owner, enemies[i], Buff(WEAKNESS[t])))
					hit++;
			}
			if (!owner.IsHusk())
				Log("specs", "war drum: " + hit + " enemies, tier cap " + cap);
		}

		// Shared Provisions, the local player: prov-cdr cooldown reduction per buff on the
		// party (every player's buffs, debuffs left out), as provisions stacks of 1% each
		int g_provisionsC = 0;
		void UpdateProvisions(int ms)
		{
			g_provisionsC -= ms;
			if (g_provisionsC > 0)
				return;
			g_provisionsC = 500;
			auto plr = cast<PlayerBase>(GetLocalPlayer());
			auto def = Stack("provisions");
			if (plr is null || def is null)
				return;
			float pct = BindF(plr, CRUSADE, "prov-cdr", 0);
			int want = 0;
			if (pct > 0)
			{
				int buffs = 0;
				for (uint i = 0; i < g_players.length(); i++)
				{
					auto p = cast<PlayerBase>(g_players[i].actor);
					if (g_players[i].peer == 255 || p is null || p.IsDead())
						continue;
					for (uint j = 0; j < p.m_buffs.m_buffs.length(); j++)
					{
						auto b = p.m_buffs.m_buffs[j];
						if (!b.m_def.m_debuff && b.m_def.m_hud !is null)
							buffs++;
					}
				}
				want = min(PROVISIONS_CAP, int(buffs * pct * 100 + 0.5f));
			}
			int have = plr.GetStacks(def);
			if (want != have)
				plr.AddStacks(plr, def, want - have);
		}
	}
}

class HWPSpecsStandard : Skills::PlayerSkillDirectional
{
	bool m_plantCast;

	HWPSpecsStandard(UnitPtr unit, SValue& params) { super(unit, params); }

	// a carried standard is planted for free, whatever the cooldown (the conditionals still hold)
	bool CanActivate(bool warn = true) override
	{
		if (HWP::Specs::StandardCarried(m_owner))
		{
			if (CheckConditionals(m_conditionals, m_owner))
				return true;
			auto plr = cast<PlayerBase>(m_owner);
			if (plr !is null && warn)
				plr.m_record.PlayVoice("cant");
			return false;
		}
		return Skills::PlayerSkillDirectional::CanActivate(warn);
	}

	PointCost@ GetCost() override
	{
		if (m_plantCast || (m_castingT < 0 && HWP::Specs::StandardCarried(m_owner)))
			return PointCost();
		return Skills::PlayerSkillDirectional::GetCost();
	}

	void NetActivate(vec2 target, float intensity) override
	{
		m_plantCast = HWP::Specs::StandardCarried(m_owner);
		Skills::PlayerSkillDirectional::NetActivate(target, intensity);
	}

	void Deactivate() override
	{
		int cd = m_cooldownC;
		Skills::PlayerSkillDirectional::Deactivate();
		if (m_plantCast)
			m_cooldownC = cd;
		m_plantCast = false;
	}
}

class HWPSpecsStandardCast : IAction
{
	HWPSpecsStandardCast(UnitPtr unit, SValue& params) {}

	void Update(int dt, int cooldown) {}
	bool NeedNetParams() { return false; }
	void SetWeaponInformation(uint weapon) {}
	void CancelAction() {}

	bool DoAction(SValueBuilder@ builder, Actor@ owner, Actor@ target, vec2 pos, vec2 dir, float intensity)
	{
		HWP::Specs::StandardCast(owner);
		return true;
	}

	bool NetDoAction(SValue@ param, Actor@ owner, vec2 pos, vec2 dir)
	{
		HWP::Specs::StandardCast(owner);
		return true;
	}
}

// War Drum on the Warcry (righteous_crusade.sval, a castspell trigger on warcry): runs where
// the trigger fires and where it is sent on, Give keeps the owner's peer the only one to apply
class HWPSpecsWarDrum : IEffect
{
	int m_radius;

	HWPSpecsWarDrum(UnitPtr unit, SValue& params)
	{
		m_radius = GetParamInt(unit, params, "radius", false, 100);
	}

	CanEvade IsEvadable(Actor@ attacker) { return CanEvade::Neither; }
	void SetWeaponInformation(uint weapon) {}
	bool CanApply(Actor@ owner, UnitPtr target, vec2 pos, vec2 dir, float intensity) override { return owner !is null; }

	bool Apply(Actor@ owner, UnitPtr target, vec2 pos, vec2 dir, float intensity, bool husk)
	{
		if (owner is null)
			return false;
		HWP::Specs::WarDrum(owner, xy(owner.m_unit.GetPosition()), m_radius);
		return true;
	}
}
