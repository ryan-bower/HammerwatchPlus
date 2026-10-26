// Marksman orb script that data alone cannot express (sniper_snipe.sval):
// - HWPFirearmsSnipeRecoil: Recoil Roll. The orb's skill dict names this class in place of
//   HWPFirearmsSnipe (the orb's dict comes first in the level params, PlayerBase.AddPlayerSkill,
//   so its "class" wins), so the shot is Snipe's in every way: the laser dot, the rank's channel,
//   damage and armor penetration, Headshot and Piercing Bullet. The frame the round leaves (the
//   castpoint going by) the shooter is thrown back along the shot's line with their own dash,
//   as Rocket Jump does (Combat.as HWPFirearmsRocketJump): the first Skills::Charge started
//   directly, so no dash charge is spent and the dash's own distance (90 px, dash.sval) and roll
//   animation are used, and the others see the dash through PlayerActiveSkillDoActivate. The
//   snipe_recoil buff (buffs_firearms.sval, 400 ms, 100 % evade) is the roll's invulnerability.
//   Snipe's cast ends at the shot (Deactivate: past the castpoint, so the cooldown starts), or
//   its attack animation, set again every frame, would hide the roll.
// - hwp firearms snipe: the local player's Snipe rank, channel and armor penetration (the
//   live skill's castpoint and the rank's snipe-pen bind), whether Recoil Roll is on, and the
//   rolls so far. FirearmsModule.as CmdStatus hands "snipe" here.
namespace HWP
{
	namespace Firearms
	{
		namespace Marksman
		{
			const string SNIPE_ID = "hwp_fs_snipe";

			int g_recoils = 0;
			vec2 g_lastRecoilAway;
			// the roll under way: where it started, and how far the last one went (UpdateRecoil)
			bool g_rolling = false;
			vec2 g_rollFrom;
			float g_lastRollPx = -1;

			// Throw plr back along -shotDir with their dash and give snipe_recoil. Local player only.
			bool Recoil(Player@ plr, vec2 shotDir)
			{
				if (plr is null || plr.IsDead())
					return false;
				vec2 away = normalize(shotDir) * -1.0f;
				auto buff = LoadActorBuff(HWP::Firearms::BUFFS + "snipe_recoil");
				if (buff !is null)
					plr.ApplyBuff(ActorBuff(plr, buff, 1.0f, false));
				bool dashed = false;
				for (uint i = 0; i < plr.m_skills.length(); i++)
				{
					auto dash = cast<Skills::Charge>(plr.m_skills[i]);
					if (dash is null)
						continue;
					dash.NetDoActivate(null, away);
					dash.m_holding = false;
					// as ActiveSkill's queued DoActivate does, so the others see the dash, not a slide
					SValue@ none = null;
					(Network::Message("PlayerActiveSkillDoActivate") << int(dash.m_skillId) << away << none).SendToAll();
					dashed = true;
					break;
				}
				g_recoils++;
				g_lastRecoilAway = away;
				g_rolling = dashed;
				g_rollFrom = xy(plr.m_unit.GetPosition());
				HWP::Log("firearms", "snipe recoil: thrown back along " + int(away.x * 100) + "," + int(away.y * 100)
					+ (dashed ? " with the dash" : ", no dash skill to roll with")
					+ ", evade " + (buff !is null ? buff.m_duration : 0) + " ms, roll " + g_recoils);
				return dashed;
			}

			// Once the dash has ended (PlayerBase.m_charging off, Charge.CancelCharge), log how far
			// the roll went: the dash's 90 px on open floor, less when a wall stops it. Ticked by
			// FirearmsModule.UpdateFrame.
			void UpdateRecoil()
			{
				if (!g_rolling)
					return;
				auto plr = cast<PlayerBase>(GetLocalPlayer());
				if (plr is null || plr.IsDead())
				{
					g_rolling = false;
					return;
				}
				if (plr.m_charging)
					return;
				g_rolling = false;
				g_lastRollPx = dist(g_rollFrom, xy(plr.m_unit.GetPosition()));
				HWP::Log("firearms", "snipe recoil: rolled " + formatFloat(g_lastRollPx, "", 0, 1) + " px (a dash is 90)");
			}

			// The rank's value of a Snipe bind: the rank's dict first, then the base skill's
			// (the order PlayerBase.AddPlayerSkill reads them in).
			float SnipeBind(PlayerBase@ plr, PlayerSkillDef@ def, int lvl, const string &in name, float def_)
			{
				if (def is null || lvl <= 0 || def.m_levelParams.length() == 0)
					return def_;
				int top = min(lvl, int(def.m_levelParams.length())) - 1;
				array<SValue@>@ dicts = { @def.m_levelParams[top], @def.m_levelParams[0] };
				for (uint i = 0; i < dicts.length(); i++)
				{
					if (dicts[i] is null)
						continue;
					auto binds = dicts[i].GetDictionaryEntry("binds");
					if (binds is null)
						continue;
					auto v = binds.GetDictionaryEntry(name);
					if (v !is null)
						return v.GetFloat();
				}
				return def_;
			}

			void CmdSnipe(array<string>@ args)
			{
				auto plr = cast<PlayerBase>(GetLocalPlayer());
				if (plr is null)
				{
					HWP::Commands::Reply("snipe: no local player");
					return;
				}
				auto skill = HWP::Firearms::FindSkill(plr, HashString(SNIPE_ID));
				auto snipe = cast<HWPFirearmsSnipe>(skill);
				auto def = plr.m_record.playerClass.GetSkillDef(HashString(SNIPE_ID), true);
				int lvl = def !is null ? plr.m_record.GetSkillLevel(def) : 0;
				if (snipe is null || def is null)
				{
					HWP::Commands::Reply("snipe: not learned (rank " + lvl + ")");
					return;
				}
				float pen = SnipeBind(plr, def, lvl, "snipe-pen", -1.0f);
				float mul = SnipeBind(plr, def, lvl, "snipe-mul", -1.0f);
				bool recoil = cast<HWPFirearmsSnipeRecoil>(skill) !is null;
				HWP::Commands::Reply("snipe: rank " + lvl + ", channel " + snipe.m_castpoint + " ms, armor pen "
					+ int(pen * 100.0f + 0.5f) + "%, damage " + int(mul * 100.0f + 0.5f) + "%, cooldown " + snipe.m_cooldown
					+ " ms, recoil " + (recoil ? "orb" : "none") + ", rolls " + g_recoils
					+ ", last roll " + (g_lastRollPx >= 0 ? formatFloat(g_lastRollPx, "", 0, 1) : "none") + " px"
					+ (g_recoils > 0 ? (" (away " + int(g_lastRecoilAway.x * 100) + "," + int(g_lastRecoilAway.y * 100) + ")") : ""));
			}
		}
	}
}

class HWPFirearmsSnipeRecoil : HWPFirearmsSnipe
{
	HWPFirearmsSnipeRecoil(UnitPtr unit, SValue& params) { super(unit, params); }

	void Update(int dt, bool walking, vec2 aimDir) override
	{
		bool winding = m_castingT >= 0 && m_castingT < m_castpoint;
		HWPFirearmsSnipe::Update(dt, walking, aimDir);
		// the castpoint went by this frame and the shot was paid for (a failed UsePoints
		// deactivates: m_castingT is -1 then)
		if (!winding || m_castingT < m_castpoint)
			return;
		auto plr = cast<Player>(m_owner);
		if (plr is null)
			return;
		vec2 dir = normalize(m_timeline.m_dirTarget);
		Deactivate();
		HWP::Firearms::Marksman::Recoil(plr, dir);
	}
}
