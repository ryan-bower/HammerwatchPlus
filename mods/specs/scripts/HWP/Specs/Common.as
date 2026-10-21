// Shared helpers for the six 4th specializations (mods/specs).
// - Bind*: a learned skill's current bind (its level's binds plus its orbs'), read at any time
//   through PlayerBase.PrepareSkillFetchData, the way a summon reads its skill's binds
//   (PlayerOwnedActor.Initialize). A buff def is global and never sees binds, so the scripts
//   read the numbers from the skill when they need them.
// - Give: ApplyBuff's authority rule (FilterHuskDamage): a player is buffed on its own
//   client, anything else where the owner is not a husk; the buff list then sends it on.
// - PlayersNear / EnemiesNear: the actors around a point.
namespace HWP
{
	namespace Specs
	{
		const string BUFFS = "players/hwp/specs/buffs_specs.sval:";
		const string STACKS = "players/hwp/specs/stacks_specs.sval:";
		const string FX = "players/hwp/specs/effects/";

		Skills::Skill@ FindSkill(PlayerBase@ plr, uint id)
		{
			if (plr is null)
				return null;
			for (uint i = 0; i < plr.m_skills.length(); i++)
			{
				if (plr.m_skills[i] !is null && plr.m_skills[i].m_skillId == id)
					return plr.m_skills[i];
			}
			return null;
		}

		bool Learned(PlayerBase@ plr, uint id)
		{
			return FindSkill(plr, id) !is null;
		}

		SValue@ Bind(PlayerBase@ plr, uint skill, const string &in name)
		{
			if (plr is null || !Learned(plr, skill))
				return null;
			plr.PrepareSkillFetchData(skill);
			return plr.FetchData(name);
		}

		float BindF(PlayerBase@ plr, uint skill, const string &in name, float def = 0)
		{
			auto sv = Bind(plr, skill, name);
			if (sv is null)
				return def;
			if (sv.GetType() == SValueType::Integer)
				return float(sv.GetInteger());
			if (sv.GetType() == SValueType::Float)
				return sv.GetFloat();
			return def;
		}

		int BindI(PlayerBase@ plr, uint skill, const string &in name, int def = 0)
		{
			auto sv = Bind(plr, skill, name);
			if (sv is null)
				return def;
			if (sv.GetType() == SValueType::Integer)
				return sv.GetInteger();
			if (sv.GetType() == SValueType::Float)
				return int(sv.GetFloat() + 0.5f);
			return def;
		}

		string BindS(PlayerBase@ plr, uint skill, const string &in name, const string &in def = "")
		{
			auto sv = Bind(plr, skill, name);
			if (sv is null || sv.GetType() != SValueType::String)
				return def;
			return sv.GetString();
		}

		ActorBuffDef@ Buff(const string &in name)
		{
			return LoadActorBuff(name.findFirst(":") >= 0 ? name : BUFFS + name);
		}

		ActorBuffStackDef@ Stack(const string &in name)
		{
			return ActorBuffStackDef::Get(name.findFirst(":") >= 0 ? name : STACKS + name);
		}

		bool IsLocal(Actor@ a)
		{
			return a !is null && a is cast<Actor>(GetLocalPlayer());
		}

		// owner gives target the buff (duration -1: the def's own)
		bool Give(Actor@ owner, Actor@ target, ActorBuffDef@ def, float intensity = 1.0f, int duration = -1)
		{
			if (target is null || def is null || intensity <= 0 || target.IsDead())
				return false;
			if (!FilterHuskDamage(owner, target.m_unit, false))
				return false;
			return target.ApplyBuff(ActorBuff(owner, def, intensity, false, 0, duration));
		}

		array<PlayerBase@>@ PlayersNear(vec2 pos, float radius)
		{
			array<PlayerBase@> ret;
			for (uint i = 0; i < g_players.length(); i++)
			{
				if (g_players[i].peer == 255 || g_players[i].actor is null)
					continue;
				auto p = cast<PlayerBase>(g_players[i].actor);
				if (p is null || p.IsDead())
					continue;
				if (dist(xy(p.m_unit.GetPosition()), pos) <= radius)
					ret.insertLast(p);
			}
			return ret;
		}

		array<Actor@>@ EnemiesNear(vec2 pos, float radius, uint team)
		{
			array<Actor@> ret;
			auto results = g_scene.QueryCircle(pos, int(radius), ~0, RaycastType::Any, true);
			for (uint i = 0; i < results.length(); i++)
			{
				auto a = cast<Actor>(results[i].GetScriptBehavior());
				if (a is null || a.IsDead() || a.Team == team || !a.IsTargetable())
					continue;
				ret.insertLast(a);
			}
			return ret;
		}

		bool IsEliteOrBoss(Actor@ a)
		{
			if (a is null)
				return false;
			uint64 mask = ApplyTag(ApplyTag(0, g_actorTags.GetTag("boss")), g_actorTags.GetTag("elite"));
			return (a.Tags & mask) != 0;
		}

		// a looping effect that the caller moves and destroys
		UnitPtr Loop(const string &in effect, vec2 pos, dictionary@ params = null)
		{
			if (params is null)
				return PlayEffect(effect, pos);
			return PlayEffect(effect, pos, params);
		}

		// destroys a looping effect; returns the empty UnitPtr to store back
		UnitPtr Kill(UnitPtr u)
		{
			if (u.IsValid() && !u.IsDestroyed())
				u.Destroy();
			return UnitPtr();
		}
	}
}
