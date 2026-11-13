// Catch-up experience (issue #73): in a New Game+ run, a player below the level cap of the
// NG+ level before the run's gets +50% experience, shown as the "Late Bloomer" buff.
//
// Threshold: vanilla's level cap is PlayerRecord.GetLevelCap() = Tweak::LevelCap (20) +
// ngp * Tweak::LevelCapNGPAdd (5) (Data/Player.as), so NG+ n caps at 20 + 5n. In a run at
// NG+ n (n >= 1) the threshold is the cap of NG+ (n - 1): 20 at NG+1, 25 at NG+2, 30 at
// NG+3. NG+0 has none. The run's NG+ is g_ngp (HWR2GameMode, loaded from the level save on
// every machine, the value the tab overlay shows), not the character's own unlocked ngp.
// A player already at their own character's cap gets nothing either: GiveExperience stops
// there, so the buff would promise experience they cannot gain.
//
// The bonus: one buff, tweak/hwp/buffs_catchup.sval, with experience-mul 1.5.
// PlayerRecord.GiveExperience multiplies every non-skipGainMod gain by
// ActorBuffList.ExperienceMul() (the vanilla shrine experience blessing's path), which covers
// kill experience (Player.NetShareExperience on every machine, from PlayerShareExperience)
// and mission rewards (MissionManager.NetSetMissionState, booked before the level change).
// Each machine books its own local player's experience, so the buff is added locally (husk,
// not networked), as outofcombat's and legacy's are.
//
// The timer: reset to KEEP_MS every frame while the bonus applies, set to 0 when it stops
// (the buff list drops it on its next update). It stays short because a player's buffs are
// saved with the record (PlayerRecord.Save, actor-save) and carry over a level change, into
// a saved character and onto the host's networked copy (ActorBuffList.Load); a long one
// would outlive the condition (outofcombat README, cc01a6a5). The HUD and bufftips read the
// def's duration (display-timer-radius off), so no countdown shows.
//
// Setting: catchup.enabled (host). Command: hwp catchup [ngp <n> | ngp off].
namespace HWP
{
	namespace CatchUp
	{
		const string BUFF = "tweak/hwp/buffs_catchup.sval:hwp_catchup";
		const int KEEP_MS = 5000; // the buff's timer, reset every frame; outlasts a long frame
		const int NO_FORCE = -1;
		const string PCT = "+50%"; // the bonus, as the buff def's experience-mul 1.5 gives it

		ActorBuffDef@ g_def;
		int g_forceNgp = NO_FORCE; // hwp catchup ngp <n>: this level's NG+ for the check only
		bool g_on = false;         // the last state logged
		string g_descKey = "";     // the threshold and NG+ the buff's description was written for

		bool Enabled() { return HWP::Settings::GetBool("catchup.enabled", true); }

		// the run's NG+ level (g_ngp is a float; the game rounds it the same way)
		int RunNgp()
		{
			if (g_forceNgp != NO_FORCE)
				return g_forceNgp;
			return max(0, int(g_ngp + 0.5f));
		}

		// the cap of NG+ (n - 1): below it a player gets the bonus; 0 at NG+0 (no bonus)
		int Threshold(int ngp)
		{
			if (ngp <= 0)
				return 0;
			return int(Tweak::LevelCap + float(ngp - 1) * Tweak::LevelCapNGPAdd + 0.5f);
		}

		// why the bonus is off, or "" when it applies
		string Why(PlayerRecord@ rec)
		{
			if (!Enabled())
				return "switched off";
			if (rec is null)
				return "no player";
			if (g_inTown)
				return "in town";
			if (rec.IsDead())
				return "dead";
			int ngp = RunNgp();
			if (ngp <= 0)
				return "NG+0";
			if (rec.level >= Threshold(ngp))
				return "level " + rec.level + " >= " + Threshold(ngp);
			if (rec.level >= rec.GetLevelCap())
				return "at the character's cap " + rec.GetLevelCap();
			return "";
		}

		bool Active(PlayerRecord@ rec) { return Why(rec) == ""; }

		ActorBuff@ Find(PlayerBase@ pb)
		{
			if (pb is null || g_def is null)
				return null;
			auto@ buffs = pb.m_buffs.m_buffs;
			for (uint i = 0; i < buffs.length(); i++)
				if (buffs[i].m_def is g_def)
					return buffs[i];
			return null;
		}

		// hides every one of our HUD icons except keep's (outofcombat's PruneHUD): HUDBuffs.Update
		// removes hidden icons
		void PruneHUD(ActorBuff@ keep)
		{
			auto hud = GetHUD();
			if (hud is null || g_def is null)
				return;
			for (uint c = 0; c < hud.m_components.length(); c++)
			{
				auto comp = cast<HUDBuffs>(hud.m_components[c]);
				if (comp is null || comp.m_wBuffList is null)
					continue;
				bool kept = false;
				auto@ list = comp.m_wBuffList.m_children;
				for (uint i = 0; i < list.length(); i++)
				{
					auto w = cast<BuffWidget>(list[i]);
					if (w is null || !w.m_visible)
						continue;
					auto b = cast<ActorBuff>(w.m_buff);
					if (b is null || b.m_def !is g_def)
						continue;
					if (b is keep && !kept)
					{
						kept = true;
						continue;
					}
					w.m_visible = false;
					@w.m_buff = null;
				}
			}
		}

		void End(PlayerBase@ pb)
		{
			auto buff = Find(pb);
			if (buff !is null)
				buff.m_duration = 0; // the buff list drops it on its next update
			PruneHUD(null);
		}

		void Tick()
		{
			if (g_def is null)
				return;
			auto rec = GetLocalPlayerRecord();
			if (rec is null)
				return;
			auto pb = cast<PlayerBase>(rec.actor);

			string why = Why(rec);
			if (why != "")
			{
				if (pb !is null && Find(pb) !is null)
					End(pb);
				if (g_on)
				{
					g_on = false;
					HWP::Log("catchup", "bonus off: " + why);
				}
				return;
			}
			if (pb is null)
				return;

			int ngp = RunNgp();
			int lvl = Threshold(ngp);
			string key = ngp + "/" + lvl;
			if (key != g_descKey)
			{
				g_descKey = key;
				g_def.m_description = Resources::GetString(".hwp.catchup.desc", { { "pct", PCT }, { "lvl", "" + lvl }, { "ngp", "" + ngp } });
			}

			auto buff = Find(pb);
			if (buff is null)
			{
				@buff = ActorBuff(pb, g_def, 1.0f, true, 0, KEEP_MS);
				pb.m_buffs.Add(buff);
			}
			else
				buff.m_duration = KEEP_MS;
			PruneHUD(buff);
			if (!g_on)
			{
				g_on = true;
				HWP::Log("catchup", "bonus on: level " + rec.level + " < " + lvl + " at NG+" + ngp);
			}
		}

		void Cmd(array<string>@ args)
		{
			// ngp <n> | ngp off: check against this NG+ instead of the run's, until the level ends
			if (args.length() >= 2 && args[0] == "ngp")
			{
				if (args[1] == "off")
					g_forceNgp = NO_FORCE;
				else
					g_forceNgp = max(0, int(parseInt(args[1])));
				HWP::Log("catchup", "ngp forced: " + (g_forceNgp == NO_FORCE ? "off" : "" + g_forceNgp));
			}
			auto rec = GetLocalPlayerRecord();
			int ngp = RunNgp();
			string why = Why(rec);
			HWP::Commands::Reply(Resources::GetString(".hwp.catchup.status", {
				{ "state", Resources::GetString(Enabled() ? ".hwp.catchup.state.on" : ".hwp.catchup.state.off") },
				{ "ngp", "" + ngp },
				{ "lvl", ngp <= 0 ? "-" : "" + Threshold(ngp) },
				{ "level", rec is null ? "-" : "" + rec.level },
				{ "active", why == "" ? Resources::GetString(".hwp.catchup.active.yes", { { "pct", PCT } }) : Resources::GetString(".hwp.catchup.active.no", { { "why", why } }) } }));
		}
	}
}

namespace Modules
{
	class HWPCatchUpModule : Module, HWP::ModuleStart
	{
		HWPCatchUpModule()
		{
			super("hwp-catchup");
			@HWP::CatchUp::g_def = LoadActorBuff(HWP::CatchUp::BUFF);
			HWP::Commands::Register("catchup", " the NG+ catch-up experience bonus; 'ngp <n>|off' checks against another NG+ this level", HWP::Commands::Handler(HWP::CatchUp::Cmd));
			HWP::Log("catchup", "ready: buff " + (HWP::CatchUp::g_def is null ? "MISSING" : "loaded")
				+ ", thresholds NG+1 " + HWP::CatchUp::Threshold(1) + ", NG+2 " + HWP::CatchUp::Threshold(2));
		}

		void Start(StartMode sMode)
		{
			HWP::CatchUp::g_forceNgp = HWP::CatchUp::NO_FORCE;
			HWP::CatchUp::g_on = false;
		}

		// HWP::Guard (tools/guard_modules.py): a script error here turns this off, not the game
		HWP::Guard m_guardUpdateFrame;
		void UpdateFrame(int ms, GameInput& gameInput, MenuInput& menuInput, bool paused) override
		{
			if (m_guardUpdateFrame.Skip("catchup", "HWPCatchUpModule.UpdateFrame"))
				return;
			if (m_guardUpdateFrame.Raw())
			{
				GuardedUpdateFrame(ms, gameInput, menuInput, paused);
				m_guardUpdateFrame.Ok();
				return;
			}
			try { GuardedUpdateFrame(ms, gameInput, menuInput, paused); m_guardUpdateFrame.Ok(); }
			catch { m_guardUpdateFrame.Failed(); }
		}

		void GuardedUpdateFrame(int ms, GameInput& gameInput, MenuInput& menuInput, bool paused)
		{
			if (paused)
				return;
			HWP::CatchUp::Tick();
		}
	}
}
