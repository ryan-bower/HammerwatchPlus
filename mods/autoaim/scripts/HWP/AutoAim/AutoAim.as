// Auto aim for AOE skills: a remake of kearneyTim's "Auto Aim for controller AOE skills"
// (Steam Workshop 3732392493), on core's aim hooks (HWP/Core/Aim.as).
//
// The skills are the ones vanilla targets with a reticle (TargetingMode::TargetAOE: the
// Ranger's Marked Shot, the Warrior's Leap, the Sorcerer's Firewall and the like).
// - Auto Aim: the reticle snaps to the enemy nearest where it would have been, among the
//   enemies in the skill's range, inside the aim cone (centred on the aim direction) and
//   in plain sight (nothing solid on the line, as ShootRandomEnemy checks it).
// - Auto Fire: once the reticle has snapped, the skill fires without the attack press
//   (or the button release, with quickcast). Our Adjust hook records the snap; the next
//   frame's PreUpdate fires there, so the reticle is seen on the target first.
// - Auto Skill: with nothing being targeted, an AOE skill that is ready, with mana at or
//   over the set share, fires on its own at an enemy in range, at most once a buffer.
//
// The original is for a controller only. Here autoaim.mode picks: off, controller (the
// default) or controller and mouse. The settings are rows on the player menu's Plus tab.
namespace HWP
{
	namespace AutoAim
	{
		// cached settings (RefreshSettings)
		int g_mode = 1;            // 0 off, 1 controller, 2 controller and mouse
		int g_cone = 180;          // degrees, 0-360
		bool g_fire = true;
		bool g_skill = true;
		int g_skillMana = 60;      // percent of max mana auto skill needs
		int g_skillBuffer = 2000;  // ms between auto skill casts
		bool g_debug = false;

		const array<int> CONES = { 90, 180, 270, 360 };
		const array<int> MANAS = { 0, 40, 60, 80 };

		// the last snap (Adjust), for Auto Fire on the next frame
		Skills::Skill@ g_snapSkill;
		UnitPtr g_snapUnit;
		vec2 g_snapPos;
		int g_snapTime = -1;
		int g_snaps = 0;

		int g_lastAutoSkill = -100000;
		// what the last shot went at, for `hwp autoaim` and GameLab
		string g_lastShot = "none";
		int g_shots = 0;
		int g_skillShots = 0;

		void Debug(const string &in text)
		{
			if (g_debug)
				HWP::Log("autoaim", text);
		}

		void RefreshSettings()
		{
			g_mode = clamp(HWP::Settings::GetInt("autoaim.mode", 1), 0, 2);
			g_cone = clamp(HWP::Settings::GetInt("autoaim.cone", 180), 0, 360);
			g_fire = HWP::Settings::GetBool("autoaim.fire", true);
			g_skill = HWP::Settings::GetBool("autoaim.skill", true);
			g_skillMana = clamp(HWP::Settings::GetInt("autoaim.skill_mana", 60), 0, 100);
			g_skillBuffer = max(0, HWP::Settings::GetInt("autoaim.skill_buffer_ms", 2000));
			g_debug = HWP::Settings::GetBool("autoaim.debug", false);
		}

		void OnSettingChanged(const string &in key)
		{
			if (key.findFirst("autoaim.") == 0)
				RefreshSettings();
		}

		// on for the input in use right now
		bool Active(bool gamepad)
		{
			return g_mode == 2 || (g_mode == 1 && gamepad);
		}

		bool UsingGamepad()
		{
			return GetInput(Focus::GAMEPLAY).UsingGamepad;
		}

		// nothing solid between from and the actor (the ShootRandomEnemy check)
		bool InSight(vec2 from, Actor@ actor)
		{
			auto ray = g_scene.Raycast(from, xy(actor.m_unit.GetPosition()), ~0, RaycastType::Shot);
			for (uint j = 0; j < ray.length(); j++)
			{
				UnitPtr u = ray[j].FetchUnit(g_scene);
				if (u == actor.m_unit)
					return true;
				if (u.GetScriptBehavior() is null)
					return false;
			}
			return true;
		}

		bool InCone(vec2 aimDir, vec2 toEnemy)
		{
			if (g_cone >= 360)
				return true;
			float len = length(toEnemy);
			if (len < 1.0f || lengthsq(aimDir) <= 0.0f)
				return true;
			float cosA = dot(normalize(aimDir), toEnemy / len);
			return cosA >= cos(g_cone * 0.5f * PI / 180.0f);
		}

		// The enemy to aim at: in range (the reticle may sit up to half its size short of
		// the enemy), in the cone around aimDir, in sight; the one nearest ref. Its spot,
		// clamped into the skill's range, goes to pos.
		UnitPtr Pick(PlayerTargetingHelper@ helper, Skills::TargetingParams@ params, vec2 aimDir, vec2 ref, vec2 &out pos)
		{
			UnitPtr best;
			auto plr = helper.m_player;
			if (plr is null || plr.IsDead())
				return best;
			vec2 me = xy(plr.m_unit.GetPosition());
			float reach = params.rangeMax + params.targetSz * 0.5f;
			auto units = g_scene.FetchActorsWithOtherTeam(plr.Team, me, uint(max(1.0f, reach)));
			float bestD = -1.0f;
			for (uint i = 0; i < units.length(); i++)
			{
				auto actor = cast<Actor>(units[i].GetScriptBehavior());
				if (actor is null || !actor.IsTargetable() || actor.IsDead())
					continue;
				vec2 at = xy(units[i].GetPosition());
				vec2 to = at - me;
				float d = length(to);
				if (d < params.rangeMin || d > reach)
					continue;
				if (!InCone(aimDir, to))
					continue;
				if (!InSight(me, actor))
					continue;
				float score = dist(at, ref);
				if (bestD < 0.0f || score < bestD)
				{
					bestD = score;
					best = units[i];
					pos = d > params.rangeMax ? me + to * (params.rangeMax / d) : at;
				}
			}
			return best;
		}

		// core hook: where the reticle goes
		vec2 Adjust(PlayerTargetingHelper@ helper, Skills::TargetingParams@ params, vec2 pos, bool gamepad)
		{
			if (!Active(gamepad) || helper.m_targetingSkill is null || helper.m_player is null)
				return pos;
			vec2 me = xy(helper.m_player.m_unit.GetPosition());
			vec2 snapped;
			UnitPtr target = Pick(helper, params, pos - me, pos, snapped);
			if (!target.IsValid())
			{
				@g_snapSkill = null;
				return pos;
			}
			// the stick keeps steering from the snapped spot
			if (gamepad)
				helper.m_gamepadRelTarget = snapped - me;
			@g_snapSkill = helper.m_targetingSkill;
			g_snapUnit = target;
			g_snapPos = snapped;
			g_snapTime = g_scene.GetTime();
			g_snaps++;
			return snapped;
		}

		string Where(UnitPtr unit, vec2 pos)
		{
			string name = unit.IsValid() && unit.GetUnitProducer() !is null ? unit.GetUnitProducer().GetDebugName() : "?";
			return name + " at " + int(pos.x) + "," + int(pos.y);
		}

		// Auto Skill: the first ready AOE skill, at an enemy anywhere in its cone
		bool AutoSkill(PlayerTargetingHelper@ helper, vec2 aimDir)
		{
			auto plr = helper.m_player;
			if (!g_skill || plr is null || plr.IsDead())
				return false;
			int now = g_scene.GetTime();
			if (now - g_lastAutoSkill < g_skillBuffer)
				return false;
			if (plr.m_record.mana * 100.0f < g_skillMana)
				return false;
			for (uint i = 0; i < plr.m_uncancellableSkills.length(); i++)
			{
				if (plr.m_uncancellableSkills[i].IsUncancellableActive())
					return false;
			}
			vec2 me = xy(plr.m_unit.GetPosition());
			for (uint i = 0; i < plr.m_skills.length(); i++)
			{
				auto skill = plr.m_skills[i];
				if (skill is null || skill.m_type != PlayerSkillType::Spell)
					continue;
				Skills::TargetingParams params;
				if (skill.GetTargetingMode(params) != Skills::TargetingMode::TargetAOE)
					continue;
				if (skill.IsActive() || helper.CheckSkillBlocked(skill) || !skill.CanActivate(false))
					continue;
				vec2 pos;
				UnitPtr target = Pick(helper, params, aimDir, me + aimDir * clamp(150.0f, float(params.rangeMin), float(params.rangeMax)), pos);
				if (!target.IsValid())
					continue;
				g_lastAutoSkill = now;
				if (skill.Activate(pos, 1.0f))
				{
					helper.CancelOther(skill, aimDir);
					helper.TriggerModifierEffects(skill);
					g_skillShots++;
					g_lastShot = "auto skill " + skill.m_id + " at " + Where(target, pos);
					Debug(g_lastShot);
					return true;
				}
			}
			return false;
		}

		// core hook, before the vanilla targeting step
		bool PreUpdate(PlayerTargetingHelper@ helper, int dt, vec2 aimDir)
		{
			bool gamepad = UsingGamepad();
			if (!Active(gamepad))
				return false;
			auto skill = helper.m_targetingSkill;
			if (skill is null)
			{
				@g_snapSkill = null;
				return AutoSkill(helper, aimDir);
			}
			// Auto Fire: the snap Adjust made last frame, for this same skill
			if (!g_fire || g_snapSkill !is skill || g_scene.GetTime() - g_snapTime > 250)
				return false;
			auto actor = g_snapUnit.IsValid() ? cast<Actor>(g_snapUnit.GetScriptBehavior()) : null;
			if (actor is null || actor.IsDead())
				return false;
			@g_snapSkill = null;
			g_shots++;
			g_lastShot = "auto fire " + skill.m_id + " at " + Where(g_snapUnit, g_snapPos);
			Debug(g_lastShot);
			HWP::Aim::FireTargeted(helper, g_snapPos, aimDir);
			return true;
		}

		string ModeName(int mode) { return Resources::GetString(".hwp.autoaim.mode." + mode); }
		string OnOff(bool on) { return Resources::GetString(on ? ".hwp.autoaim.on" : ".hwp.autoaim.off"); }

		// the Plus tab rows
		class ModeOption : HWP::Options::Option
		{
			string Title() override { return Resources::GetString(".hwp.autoaim.option.mode"); }
			string Value() override { return ModeName(g_mode); }
			void Next() override { HWP::Settings::SetInt("autoaim.mode", (g_mode + 1) % 3); RefreshSettings(); }
		}

		class ConeOption : HWP::Options::Option
		{
			string Title() override { return Resources::GetString(".hwp.autoaim.option.cone"); }
			string Value() override { return Resources::GetString(".hwp.autoaim.cone", { { "deg", "" + g_cone } }); }
			void Next() override
			{
				int i = CONES.find(g_cone);
				HWP::Settings::SetInt("autoaim.cone", CONES[(i + 1) % CONES.length()]);
				RefreshSettings();
			}
		}

		class FireOption : HWP::Options::Option
		{
			string Title() override { return Resources::GetString(".hwp.autoaim.option.fire"); }
			string Value() override { return OnOff(g_fire); }
			void Next() override { HWP::Settings::SetBool("autoaim.fire", !g_fire); RefreshSettings(); }
		}

		// off, then on at each mana share in turn
		class SkillOption : HWP::Options::Option
		{
			string Title() override { return Resources::GetString(".hwp.autoaim.option.skill"); }
			string Value() override
			{
				if (!g_skill)
					return OnOff(false);
				return Resources::GetString(".hwp.autoaim.skill.mana", { { "pct", "" + g_skillMana } });
			}
			void Next() override
			{
				int i = g_skill ? MANAS.find(g_skillMana) : -1;
				if (g_skill && i < 0)
					i = MANAS.length() - 1;
				if (g_skill && i == int(MANAS.length()) - 1)
					HWP::Settings::SetBool("autoaim.skill", false);
				else
				{
					HWP::Settings::SetBool("autoaim.skill", true);
					HWP::Settings::SetInt("autoaim.skill_mana", MANAS[i + 1]);
				}
				RefreshSettings();
			}
		}

		// hwp autoaim: the settings (the original's caa_settings) and the last shot
		void CmdAutoAim(array<string>@ args)
		{
			HWP::Commands::Reply("autoaim: mode " + g_mode + " (" + ModeName(g_mode) + "), cone " + g_cone
				+ ", fire " + g_fire + ", skill " + g_skill + " at " + g_skillMana + "% mana every " + g_skillBuffer
				+ " ms, debug " + g_debug + "; gamepad " + UsingGamepad() + "; shots " + g_shots + ", skill shots "
				+ g_skillShots + "; snaps " + g_snaps + ", snap " + int(g_snapPos.x) + "," + int(g_snapPos.y) + "; last " + g_lastShot);
		}
	}
}

namespace Modules
{
	class HWPAutoAimModule : Module, HWP::ModuleStart
	{
		HWPAutoAimModule()
		{
			super("hwp-autoaim");
			HWP::Aim::OnAdjust(HWP::Aim::Adjust(HWP::AutoAim::Adjust));
			HWP::Aim::OnPreUpdate(HWP::Aim::PreUpdate(HWP::AutoAim::PreUpdate));
			HWP::Options::Register("autoaim", HWP::AutoAim::ModeOption());
			HWP::Options::Register("aimcone", HWP::AutoAim::ConeOption());
			HWP::Options::Register("autofire", HWP::AutoAim::FireOption());
			HWP::Options::Register("autoskill", HWP::AutoAim::SkillOption());
			HWP::Commands::Register("autoaim", " auto aim settings and the last auto shot", HWP::Commands::Handler(HWP::AutoAim::CmdAutoAim));
			HWP::Commands::OnSettingChanged(HWP::Commands::SettingListener(HWP::AutoAim::OnSettingChanged));
		}

		void Start(StartMode sMode)
		{
			HWP::AutoAim::RefreshSettings();
			@HWP::AutoAim::g_snapSkill = null;
			HWP::AutoAim::g_lastAutoSkill = -100000;
		}
	}
}
