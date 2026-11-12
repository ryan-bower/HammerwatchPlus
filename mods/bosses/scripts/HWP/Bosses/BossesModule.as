// Tougher bosses (issue #96): every boss gets bosses.toughness % (default 25) more armor and
// more of each resistance (fire, ice, lightning, poison). Health is untouched.
//
// What a boss is: an actor with the "boss" actor tag, the flag vanilla, Pelor's Fury, the boss
// recap and the Wave Arena use (every unit with a HUD boss bar has it, but the Serpents' and
// Harbingers' shared health units, which have no armor of their own: their visible bodies are
// TransferDamageActors that apply their own armor first).
//
// How: armor and resistances are flat numbers on the unit's own ActorProperties (one object
// per spawned unit, one per state of a StateActorBehavior), read by
// CompositeActorBehavior.Damage as ApplyArmor(dmg, buffArmorMul * m_props.m_armor, pen), and
// so by whichever machine works the hit out (the attacker's). So every machine scales its own
// copy the same way, from the host's setting (scope host, HWP::Settings::Sync): the scan below
// runs on every machine, every SCAN_MS, over FetchAllActorsWithOtherTeam(g_team_player).
// A buff (armor-mul / resistance-mul) would have been networked for free, but the Avatar and
// the Face are no-buffs bosses that ApplyBuff refuses.
//
// The numbers: base > 0 becomes round(base * (100 + pct) / 100); 0 and below stay as they are
// (no boss in the game has negative armor or resistance; a weakness never gets deeper). The
// game has no cap to pass: ApplyArmor's reduction is a / (1 + a), under 100 % at any value.
// The base values are kept per properties object, so a setting change re-applies from them
// and 0 (or the module off) puts the vanilla values back.
//
// Pelor's Fury (specs, Generosity.as) still wins: its pelors_fury buff has armor-mul and
// resistance-mul 0, and the buffs' ArmorMul multiplies the scaled value, so it is 0. The NG+
// armor and resistance multipliers apply on top, as in vanilla.
//
// A boss that turns to the player's team (the Forgemaster raises a new unit, but a team swap
// would do it too) gets its vanilla values back on the next scan.
namespace HWP
{
	namespace Bosses
	{
		const int SCAN_MS = 500;

		class Scaled
		{
			CompositeActorBehavior@ actor;
			ActorProperties@ props;
			string name;
			// vanilla
			int armor;
			int fire;
			int ice;
			int lightning;
			int poison;
			int pct = 0;                             // applied now
		}

		array<Scaled@> g_scaled;
		int g_seen = 0; // properties objects scaled this level

		bool Enabled() { return HWP::Settings::GetBool("bosses.enabled", true); }

		int Percent()
		{
			if (!Enabled())
				return 0;
			return clamp(HWP::Settings::GetInt("bosses.toughness", 25), 0, 500);
		}

		bool IsBoss(Actor@ a)
		{
			return a !is null && (a.Tags & ApplyTag(0, g_actorTags.GetTag("boss"))) != 0;
		}

		int Up(int base, int pct)
		{
			if (base <= 0 || pct <= 0)
				return base;
			return int(float(base) * float(100 + pct) / 100.0f + 0.5f);
		}

		void Apply(Scaled@ s, int pct)
		{
			if (s.pct == pct)
				return;
			s.props.m_armor = Up(s.armor, pct);
			s.props.m_resistanceFire = Up(s.fire, pct);
			s.props.m_resistanceIce = Up(s.ice, pct);
			s.props.m_resistanceLightning = Up(s.lightning, pct);
			s.props.m_resistancePoison = Up(s.poison, pct);
			s.pct = pct;
			HWP::Log("bosses", s.name + " +" + pct + "%: armor " + s.armor + " -> " + s.props.m_armor
				+ ", res " + s.fire + "/" + s.ice + "/" + s.lightning + "/" + s.poison + " -> "
				+ s.props.m_resistanceFire + "/" + s.props.m_resistanceIce + "/"
				+ s.props.m_resistanceLightning + "/" + s.props.m_resistancePoison);
		}

		Scaled@ Find(ActorProperties@ p)
		{
			for (uint i = 0; i < g_scaled.length(); i++)
			{
				if (g_scaled[i].props is p)
					return g_scaled[i];
			}
			return null;
		}

		bool Gone(CompositeActorBehavior@ a)
		{
			return a is null || !a.m_unit.IsValid() || a.m_unit.IsDestroyed();
		}

		void Scan()
		{
			int pct = Percent();

			// the ones already scaled: a setting change, a boss that left the enemies, a unit gone
			for (int i = int(g_scaled.length()) - 1; i >= 0; i--)
			{
				auto s = g_scaled[i];
				if (Gone(s.actor))
				{
					g_scaled.removeAt(i);
					continue;
				}
				bool foe = s.actor.Team != g_team_player && IsBoss(s.actor);
				Apply(s, foe ? pct : 0);
			}

			if (pct <= 0)
				return;

			auto foes = g_scene.FetchAllActorsWithOtherTeam(g_team_player);
			for (uint i = 0; i < foes.length(); i++)
			{
				auto a = cast<CompositeActorBehavior>(foes[i].GetScriptBehavior());
				if (a is null || a.m_props is null || !IsBoss(a) || a.IsDead())
					continue;
				// a StateActorBehavior swaps in another properties object per state: each is
				// scaled once, when it is first seen
				if (Find(a.m_props) !is null)
					continue;
				Scaled@ s = Scaled();
				@s.actor = a;
				@s.props = a.m_props;
				s.name = foes[i].GetUnitProducer().GetResourceName();
				s.armor = a.m_props.m_armor;
				s.fire = a.m_props.m_resistanceFire;
				s.ice = a.m_props.m_resistanceIce;
				s.lightning = a.m_props.m_resistanceLightning;
				s.poison = a.m_props.m_resistancePoison;
				g_scaled.insertLast(s);
				g_seen++;
				Apply(s, pct);
			}
		}

		void CmdBosses(array<string>@ args)
		{
			string ret = "bosses: +" + Percent() + "% armor and resistances"
				+ (Enabled() ? "" : " (off)") + ", " + g_scaled.length() + " boss properties scaled now, "
				+ g_seen + " this level";
			for (uint i = 0; i < g_scaled.length(); i++)
			{
				auto s = g_scaled[i];
				ret += "\n  " + s.name + " +" + s.pct + "%: armor " + s.props.m_armor + " (" + s.armor + "), res "
					+ s.props.m_resistanceFire + "/" + s.props.m_resistanceIce + "/"
					+ s.props.m_resistanceLightning + "/" + s.props.m_resistancePoison
					+ " (" + s.fire + "/" + s.ice + "/" + s.lightning + "/" + s.poison + ")";
			}
			HWP::Log("bosses", ret);
			HWP::Commands::Reply(ret);
		}
	}
}

namespace Modules
{
	class HWPBossesModule : Module, HWP::ModuleStart
	{
		int m_scanC = 0;

		HWPBossesModule()
		{
			super("hwp-bosses");
			HWP::Commands::Register("bosses", ": the boss armor and resistance bonus, and the bosses it holds now", HWP::Commands::Handler(HWP::Bosses::CmdBosses));
		}

		void Start(StartMode sMode)
		{
			HWP::Settings::Sync("bosses.");
			m_scanC = 0;
			HWP::Log("bosses", "level start: +" + HWP::Bosses::Percent() + "% boss armor and resistances");
		}

		// HWP::Guard (tools/guard_modules.py): a script error here turns this off, not the game
		HWP::Guard m_guardUpdateFrame;
		void UpdateFrame(int ms, GameInput& gameInput, MenuInput& menuInput, bool paused) override
		{
			if (m_guardUpdateFrame.Skip("bosses", "HWPBossesModule.UpdateFrame"))
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
			if (g_inTown)
				return;
			m_scanC -= ms;
			if (m_scanC > 0)
				return;
			m_scanC = HWP::Bosses::SCAN_MS;
			HWP::Bosses::Scan();
		}
	}
}
