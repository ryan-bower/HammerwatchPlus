// Out of combat speed (issue #99): a player who has not hit an enemy for
// outofcombat.delay seconds (10) moves outofcombat.speed times as fast (2x), until
// they hit one again.
//
// Speed: one buff, tweak/hwp/buffs_outofcombat.sval, whose speed-mul is set from the
// setting. Player.Update multiplies the move speed by ActorBuffList.MoveSpeedMul
// (Player.as, Moving), the path every vanilla speed buff takes (the combo's
// bursting speed, Apothecary's Tincture), so it stacks with them and goes when the
// buff does. The buff is added locally (husk, not networked, as legacy's Title
// Bonuses buff): each machine moves its own player and the others see the position,
// so each machine boosts its own local player and a client gets it as the host does.
// Its timer is reset to KEEP_MS every frame while the boost is on; when it ends, the
// timer is set to 0 and the buff list drops it on its next update. The timer stays
// short because the player's buffs go into the record's actor-save (PlayerRecord.Save):
// they carry over a level change and into a saved character, and the host reloads them
// as networked buffs (ActorBuffList.Load), so a long one would outlive the boost on the
// clients' copy of the host. The tooltip and HUD read the def's duration (display-timer-
// radius off), so the short timer shows no countdown. The HUD shows the vanilla
// shrine speed blessing's icon; every tick hides any of ours that is not the current
// actor's buff (a respawn that keeps the old actor's buffs left legacy's behind).
//
// Hits: the PlayerDamagedActor hook (Player.DamagedActor), which fires only on the
// attacker's machine (CompositeActorBehavior.Damage calls DamagedActor on the local
// attacker), for a hit that did damage, not for burn, poison or bleed ticks. It
// counts the local player's hits on an actor of another team, the player's summons'
// hits too (PlayerOwnedActor.DamagedActor goes through the owner). Breakables (pots,
// crates) are not actors and never count. Taking damage does not end the boost: the
// issue asks for attacking only.
//
// Where: dungeon runs; in town only with outofcombat.town (off by default). A new
// level starts boosted (no hit yet), and the first hit ends it.
// Settings: outofcombat.enabled, outofcombat.speed, outofcombat.delay, outofcombat.town
// (host). Command: hwp outofcombat [hit].
namespace HWP
{
	namespace OutOfCombat
	{
		const string BUFF = "tweak/hwp/buffs_outofcombat.sval:hwp_outofcombat";
		const int NEVER = 1 << 30; // ms since the last hit when there was none this level
		const int KEEP_MS = 5000;  // the buff's timer, reset every frame; outlasts a long frame

		ActorBuffDef@ g_def;
		int g_sinceHitMs = NEVER;
		int g_hits = 0;           // the local player's hits on enemies this level
		string g_descKey = "";    // the speed and delay the buff's description was written for

		bool Enabled() { return HWP::Settings::GetBool("outofcombat.enabled", true); }
		float Mult() { return clamp(HWP::Settings::GetFloat("outofcombat.speed", 2.0f), 1.0f, 5.0f); }
		int DelaySecs() { return clamp(HWP::Settings::GetInt("outofcombat.delay", 10), 0, 600); }
		bool InTown() { return HWP::Settings::GetBool("outofcombat.town", false); }

		// 2 -> "2", 1.5 -> "1.5"
		string Num(float v)
		{
			string s = formatFloat(v, "", 0, 2);
			if (s.findFirst(".") >= 0)
			{
				while (s.length() > 1 && s.substr(s.length() - 1) == "0")
					s = s.substr(0, s.length() - 1);
				if (s.substr(s.length() - 1) == ".")
					s = s.substr(0, s.length() - 1);
			}
			return s;
		}

		bool Active(PlayerRecord@ rec)
		{
			if (!Enabled() || rec is null || rec.IsDead())
				return false;
			if (g_inTown && !InTown())
				return false;
			if (Mult() <= 1.0f)
				return false;
			return g_sinceHitMs >= DelaySecs() * 1000;
		}

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

		// hides every one of our HUD icons except keep's (legacy's PruneHUD): HUDBuffs.Update
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

		void Tick(int ms)
		{
			if (g_sinceHitMs < NEVER - ms)
				g_sinceHitMs += ms;
			else
				g_sinceHitMs = NEVER;

			if (g_def is null)
				return;
			auto rec = GetLocalPlayerRecord();
			if (rec is null)
				return;
			auto pb = cast<PlayerBase>(rec.actor);
			if (pb is null)
				return;

			if (!Active(rec))
			{
				if (Find(pb) !is null)
					End(pb);
				return;
			}

			float mult = Mult();
			int delay = DelaySecs();
			g_def.m_mulSpeed = vec2(mult, mult);
			string key = Num(mult) + "/" + delay;
			if (key != g_descKey)
			{
				g_descKey = key;
				g_def.m_description = Resources::GetString(".hwp.outofcombat.desc", { { "mult", Num(mult) }, { "delay", "" + delay } });
			}

			auto buff = Find(pb);
			if (buff is null)
			{
				@buff = ActorBuff(pb, g_def, 1.0f, true, 0, KEEP_MS);
				pb.m_buffs.Add(buff);
				HWP::Log("outofcombat", "boost on: " + Num(mult) + "x");
			}
			else
				buff.m_duration = KEEP_MS;
			PruneHUD(buff);
		}

		// the local player (or their summon) hit something
		void OnHit(Player@ player, Actor@ actor)
		{
			if (player is null || actor is null || player.m_record is null || !player.m_record.local)
				return;
			if (actor.Team == player.Team)
				return;
			g_sinceHitMs = 0;
			g_hits++;
			if (Find(player) !is null)
			{
				End(player);
				HWP::Log("outofcombat", "boost off: hit an enemy");
			}
		}

		void Cmd(array<string>@ args)
		{
			auto rec = GetLocalPlayerRecord();
			// hit: as if the local player hit an enemy now (for testing)
			if (args.length() >= 1 && args[0] == "hit")
			{
				g_sinceHitMs = 0;
				g_hits++;
				if (rec !is null)
					End(cast<PlayerBase>(rec.actor));
				HWP::Log("outofcombat", "boost off: hit (command)");
			}
			string since = g_sinceHitMs >= NEVER ? "-" : Num(g_sinceHitMs / 1000.0f);
			HWP::Commands::Reply(Resources::GetString(".hwp.outofcombat.status", {
				{ "state", Resources::GetString(Enabled() ? ".hwp.outofcombat.state.on" : ".hwp.outofcombat.state.off") },
				{ "mult", Num(Mult()) }, { "delay", "" + DelaySecs() },
				{ "town", Resources::GetString(InTown() ? ".hwp.outofcombat.town.yes" : ".hwp.outofcombat.town.no") },
				{ "since", since }, { "hits", "" + g_hits },
				{ "active", Resources::GetString(Active(rec) ? ".hwp.outofcombat.active.yes" : ".hwp.outofcombat.active.no") } }));
		}
	}
}

namespace HWPOutOfCombat
{
	[Hook]
	void PlayerDamagedActor(Player@ player, Actor@ actor, DamageInfo@ di)
	{
		HWP::OutOfCombat::OnHit(player, actor);
	}
}

namespace Modules
{
	class HWPOutOfCombatModule : Module, HWP::ModuleStart
	{
		HWPOutOfCombatModule()
		{
			super("hwp-outofcombat");
			@HWP::OutOfCombat::g_def = LoadActorBuff(HWP::OutOfCombat::BUFF);
			HWP::Commands::Register("outofcombat", " the out of combat speed boost; 'hit' counts as hitting an enemy now", HWP::Commands::Handler(HWP::OutOfCombat::Cmd));
			HWP::Log("outofcombat", "ready: buff " + (HWP::OutOfCombat::g_def is null ? "MISSING" : "loaded")
				+ ", " + HWP::OutOfCombat::Num(HWP::OutOfCombat::Mult()) + "x after " + HWP::OutOfCombat::DelaySecs() + " s");
		}

		void Start(StartMode sMode)
		{
			HWP::OutOfCombat::g_sinceHitMs = HWP::OutOfCombat::NEVER;
			HWP::OutOfCombat::g_hits = 0;
		}

		// HWP::Guard (tools/guard_modules.py): a script error here turns this off, not the game
		HWP::Guard m_guardUpdateFrame;
		void UpdateFrame(int ms, GameInput& gameInput, MenuInput& menuInput, bool paused) override
		{
			if (m_guardUpdateFrame.Skip("outofcombat", "HWPOutOfCombatModule.UpdateFrame"))
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
			HWP::OutOfCombat::Tick(ms);
		}
	}
}
