// Bannerlord: 3-second shield/rally pulses, with 250 ms Crusade coverage refresh.
// Free recast throws the Standard; both origins persist for its remaining lifetime.
// Support.as owns recipient-authoritative shields and inherited native Killing Spree.
// Legacy perk IDs are intentionally retained for existing purchased ranks.
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
			int m_pulseC;
			float m_dr;
			int m_radius;
			float m_allyMul;
			float m_selfMul;
			int m_crusadeLvl;
			UnitPtr m_fx;
			UnitPtr m_carriedFx;

			vec2 Pos()
			{
				return m_planted || m_owner is null || !m_owner.m_unit.IsValid() ? m_pos : xy(m_owner.m_unit.GetPosition());
			}
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
			g_standards[i].m_carriedFx = Kill(g_standards[i].m_carriedFx);
			g_standards.removeAt(i);
		}

		// the skill's cast, on every peer
		void StandardCast(Actor@ owner, vec2 dir)
		{
			auto plr = cast<PlayerBase>(owner);
			if (plr is null)
				return;
			auto s = FindStandard(owner);
			if (s !is null && !s.m_planted)
			{
				s.m_planted = true;
				if (length(dir) < 0.01f) dir = owner.GetDirection();
				s.m_pos = xy(owner.m_unit.GetPosition()) + normalize(dir) * 180;
				s.m_tickC = 0;
				StandardFx(s);
				dictionary ps = { { "radius", s.m_radius }, { "planted", 0 } };
				s.m_carriedFx = Loop(FX + "standard.effect", xy(owner.m_unit.GetPosition()), ps);
				StandardPulse(s, true, false);
				PlaySound3D(Resources::GetSoundEvent("event:/sfx/player/classes/priest/holy_banner/holy_banner"), xyz(s.m_pos));
				Log("specs", "standard: thrown, " + s.m_left + " ms left");
			}
			else
			{
				if (s !is null)
					RemoveStandard(g_standards.findByRef(s));
				@s = Standard();
				@s.m_owner = owner;
				s.m_pos = xy(owner.m_unit.GetPosition());
				s.m_left = BindI(plr, STANDARD, "std-ttl", 10000);
				s.m_dr = BindF(plr, STANDARD, "std-shield", 0.03f);
				s.m_radius = BindI(plr, STANDARD, "std-radius", 120);
				s.m_allyMul = BindF(plr, STANDARD, "std-ally-mul", 1);
				s.m_selfMul = BindF(plr, STANDARD, "std-self-mul", 1);
				s.m_crusadeLvl = Learned(plr, CRUSADE) ? BindI(plr, CRUSADE, "crusade-lvl", 0) : 0;
				g_standards.insertLast(s);
				StandardFx(s);
				WarDrum(owner, s.Pos(), s.m_radius);
				StandardPulse(s, true);
				s.m_pulseC = 3000;
				s.m_tickC = STANDARD_TICK;
				PlaySound3D(Resources::GetSoundEvent("event:/sfx/player/classes/warrior/war_cry/war_cry"), owner.m_unit.GetPosition());
				Log("specs", "standard: raised for " + s.m_left + " ms, shield " + s.m_dr + " radius " + s.m_radius
					+ " ally x" + s.m_allyMul + " self x" + s.m_selfMul
					+ (s.m_crusadeLvl > 0 ? ", crusade " + s.m_crusadeLvl : ""));
			}
		}

		void StandardPulse(Standard@ s, bool pulse, bool rally = true)
		{
			vec2 pos = s.Pos();
			auto crusade = s.m_crusadeLvl > 0 ? Buff("crusade_" + s.m_crusadeLvl) : null;
			auto players = PlayersNear(pos, s.m_radius);
			if (s.m_planted)
			{
				auto carried = PlayersNear(xy(s.m_owner.m_unit.GetPosition()), s.m_radius);
				for (uint i = 0; i < carried.length(); i++)
					if (players.findByRef(carried[i]) < 0) players.insertLast(carried[i]);
			}
			auto source = cast<PlayerBase>(s.m_owner);
			for (uint i = 0; i < players.length(); i++)
			{
				if (players[i].Team != s.m_owner.Team) continue;
				bool self = players[i] is s.m_owner;
				if (!self && crusade !is null)
					Give(s.m_owner, players[i], crusade, 1, 600);
				if (!pulse || !IsLocal(players[i])) continue;
				float shield = s.m_dr * (self ? s.m_selfMul : s.m_allyMul);
				if (shield > 0) Shield(players[i], shield, shield, 4000, false, source.GetMaxHp());
				if (rally) Rally(source, players[i], BindI(source, STANDARD, "std-rally"));
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
				{
					s.m_pos = xy(s.m_owner.m_unit.GetPosition());
					s.m_fx.SetPosition(s.m_owner.m_unit.GetPosition());
				}
				if (s.m_carriedFx.IsValid()) s.m_carriedFx.SetPosition(s.m_owner.m_unit.GetPosition());
				s.m_pulseC -= ms;
				s.m_tickC -= ms;
				if (s.m_tickC <= 0)
				{
					s.m_tickC += STANDARD_TICK;
					bool pulse = s.m_pulseC <= 0;
					StandardPulse(s, pulse);
					if (pulse) s.m_pulseC = 3000;
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

	// A carried Standard is thrown for free, whatever the cooldown.
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
		HWP::Specs::StandardCast(owner, dir);
		return true;
	}

	bool NetDoAction(SValue@ param, Actor@ owner, vec2 pos, vec2 dir)
	{
		HWP::Specs::StandardCast(owner, dir);
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
