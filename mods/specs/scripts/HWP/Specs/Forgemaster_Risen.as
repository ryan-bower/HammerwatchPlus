// The Devil Forgemaster's risen and body unit classes: the generated units (tools/
// make_forgemaster_risen.py, players/hwp/specs/forgemaster/{risen,bodies}/) name these.
// Forgemaster.as holds the skills and the base classes (HWPSpecsRisen, HWPSpecsRisenState,
// HWPSpecsBody); this file only changes how a risen moves and how a body looks (2026-10-25).
//
// - A risen runs. Forgemaster.as's FollowerFor builds the follower movement with roaming 0.5 (an
//   idle risen ambled about at half speed, the "not aggroed" pace) and the enemy's own speed (a
//   slow enemy never ran). RisenRun sets roaming 1.0 (idle moves go at full speed; MeleeFollower
//   Movement.as:63-85 scale the idle walk by m_roaming), speed at least RISEN_RUN_SPEED (the
//   Priest's crusader pikeman: 4.5) and a run-back speed RISEN_RUNBACK_MUL above it, on every
//   movement a state actor has. The target search runs twice as often (target-find-cooldown-mul
//   RISEN_SEARCH_MUL, also in the unit file: CompositeActorBehavior.as:1037/1070/1130 scale the
//   search cooldown by it), so a risen engages what comes into its 300 aggro range the way the
//   vanilla summons do. `[HWP:specs] risen <id> runs: speed S runback R roaming 1.0 search-mul M`.
// - A body is grey (BODY_TINT), not HWPSpecsBody's green-grey; its unit has no map dot, no ring,
//   no effects and every collision shape shoot-through (the generator). `[HWP:specs] body <id> <rel>
//   tint grey`.
// - `hwp risen`: every living risen's movement class, speed, run-back speed, roaming, search
//   multiplier and whether it has a target, for the fix-specs-risen-* scenarios.
namespace HWP
{
	namespace Specs
	{
		const float RISEN_RUN_SPEED = 4.5f;
		const float RISEN_RUNBACK_MUL = 1.4f;
		const float RISEN_SEARCH_MUL = 0.5f;
		const vec4 BODY_TINT = vec4(0.45f, 0.45f, 0.45f, 1.0f);
		int g_risenRuns = 0;    // movements set to the chase pace this level
		int g_risenKeeps = 0;   // movements left alone (not a follower: a PassiveMovement ballista)

		// the follower movement at a chase pace; false when m is not a follower movement
		bool RisenRun(ActorMovement@ m)
		{
			auto mm = cast<MeleeMovement>(m);
			if (mm is null)
				return false;
			auto mf = cast<MeleeFollowerMovement>(m);
			auto rf = cast<RangedFollowerMovement>(m);
			if (mf is null && rf is null)
				return false;
			mm.m_roaming = 1.0f;
			mm.m_speed = max(mm.m_speed, RISEN_RUN_SPEED);
			if (mf !is null)
				mf.m_runBackSpeed = max(mf.m_runBackSpeed, mm.m_speed * RISEN_RUNBACK_MUL);
			if (rf !is null)
				rf.m_runBackSpeed = max(rf.m_runBackSpeed, mm.m_speed * RISEN_RUNBACK_MUL);
			return true;
		}

		float RunBackSpeed(ActorMovement@ m)
		{
			auto mf = cast<MeleeFollowerMovement>(m);
			if (mf !is null)
				return mf.m_runBackSpeed;
			auto rf = cast<RangedFollowerMovement>(m);
			if (rf !is null)
				return rf.m_runBackSpeed;
			return 0;
		}

		string F1(float v) { return formatFloat(v, "", 0, 1); }

		// "speed S runback R roaming X" of a movement, or its class when it is not a melee movement
		string MoveNumbers(ActorMovement@ m)
		{
			if (m is null)
				return "move none";
			auto mm = cast<MeleeMovement>(m);
			if (mm is null)
				return "move " + Reflect::GetTypeName(m);
			return "move " + MoveName(m) + " speed " + F1(mm.m_speed) + " runback " + F1(RunBackSpeed(m)) + " roaming " + F1(mm.m_roaming);
		}

		// the chase pace on every movement of a freshly initialized risen, and the search cadence
		void RisenRunAll(CompositeActorBehavior@ b, array<ActorMovement@>@ moves)
		{
			if (b is null)
				return;
			b.m_props.m_targetFindCdMul = min(b.m_props.m_targetFindCdMul, RISEN_SEARCH_MUL);
			int runs = 0;
			for (uint i = 0; i < moves.length(); i++)
			{
				if (moves[i] is null)
					continue;
				if (RisenRun(moves[i]))
					runs++;
				else
					g_risenKeeps++;
			}
			g_risenRuns += runs;
			if (runs > 0)
				HWP::Log("specs", "risen " + b.m_unit.GetId() + " runs: " + MoveNumbers(b.m_movement).substr(5)
					+ " search-mul " + F1(b.m_props.m_targetFindCdMul) + " (" + runs + " of " + moves.length() + " movements)");
			else
				HWP::Log("specs", "risen " + b.m_unit.GetId() + " keeps its movement: " + MoveNumbers(b.m_movement)
					+ " search-mul " + F1(b.m_props.m_targetFindCdMul));
		}

		// hwp risen: the local Forgemaster's living risen and their movement numbers
		void CmdRisen(array<string>@ args)
		{
			auto plr = cast<PlayerBase>(GetLocalPlayer());
			if (plr is null)
			{
				HWP::Commands::Reply("risen: no local player");
				return;
			}
			auto risen = RisenUnits(plr);
			string ret = "risen " + risen.length() + " (runs set " + g_risenRuns + ", kept " + g_risenKeeps + ", run speed >= "
				+ F1(RISEN_RUN_SPEED) + ", search-mul " + F1(RISEN_SEARCH_MUL) + "):";
			for (uint i = 0; i < risen.length(); i++)
			{
				auto b = cast<CompositeActorBehavior>(risen[i]);
				if (b is null)
					continue;
				string tgt = "0";
				if (b.m_target !is null)
					tgt = "" + b.m_target.m_unit.GetId();
				ret += " | id " + b.m_unit.GetId() + " " + MoveNumbers(b.m_movement) + " search " + F1(b.m_props.m_targetFindCdMul)
					+ " target " + tgt + " dist " + int(dist(xy(b.m_unit.GetPosition()), xy(plr.m_unit.GetPosition())));
			}
			HWP::Commands::Reply(ret);
		}
	}
}

class HWPSpecsRisenUnit : HWPSpecsRisen
{
	HWPSpecsRisenUnit(UnitPtr unit, SValue& params) { super(unit, params); }

	void Initialize(Actor@ owner, float intensity, bool husk, uint weaponInfo = 0) override
	{
		HWPSpecsRisen::Initialize(owner, intensity, husk, weaponInfo);
		array<ActorMovement@> moves = { m_movement };
		HWP::Specs::RisenRunAll(this, moves);
	}
}

class HWPSpecsRisenStateUnit : HWPSpecsRisenState
{
	HWPSpecsRisenStateUnit(UnitPtr unit, SValue& params) { super(unit, params); }

	void Initialize(Actor@ owner, float intensity, bool husk, uint weaponInfo = 0) override
	{
		HWPSpecsRisenState::Initialize(owner, intensity, husk, weaponInfo);
		// every state's movement once (states share movements; the base swapped them in place)
		array<ActorMovement@> moves;
		for (uint i = 0; i < m_states.length(); i++)
		{
			auto m = m_states[i].m_movement;
			if (m !is null && moves.findByRef(m) < 0)
				moves.insertLast(m);
		}
		if (m_movement !is null && moves.findByRef(m_movement) < 0)
			moves.insertLast(m_movement);
		HWP::Specs::RisenRunAll(this, moves);
	}
}

// an intact body: HWPSpecsBody (Forgemaster.as) in grey
class HWPSpecsBodyUnit : HWPSpecsBody
{
	HWPSpecsBodyUnit(UnitPtr unit, SValue& params)
	{
		super(unit, params);
		m_unit.SetMultiplyColor(HWP::Specs::BODY_TINT);
		HWP::Log("specs", "body " + m_unit.GetId() + " " + m_source + " tint grey");
	}
}

namespace Modules
{
	class HWPSpecsRisenModule : Module
	{
		HWPSpecsRisenModule()
		{
			super("hwp-specs-risen");
			HWP::Commands::Register("risen", "  Devil Forgemaster risen: each one's movement, speed, run-back, roaming, target search", HWP::Commands::Handler(HWP::Specs::CmdRisen));
		}
	}
}
