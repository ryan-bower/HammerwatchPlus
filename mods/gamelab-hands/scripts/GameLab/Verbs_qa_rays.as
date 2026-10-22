// Bounded, read-only collision and owned-follower observations for class QA.
// No damage, movement, target selection or actor state is changed here.
namespace GameLab
{
	const uint QA_MELEE_RAY_CAP = 16;

	// meleerays <dx> <dy>: exactly the trident MeleeSwing's native Shot query:
	// 3 parallel rays across16px,40px reach, origin -Tweak::PlayerCameraHeight.
	// Unlike rayhit, actors and the owner's own fixtures remain visible.
	void VerbQAMeleeRays(const string &in id, array<string>@ args)
	{
		auto plr = GetLocalPlayer();
		if (plr is null || args.length() != 2)
		{
			Fail(id, "usage: meleerays <dx> <dy>; needs a spawned local player");
			return;
		}
		vec2 dir(parseFloat(args[0]), parseFloat(args[1]));
		float len = length(dir);
		if (len <= 0 || len > 10000)
		{
			Fail(id, "direction length must be positive and at most10000");
			return;
		}
		dir /= len;
		vec2 from = xy(plr.m_unit.GetPosition()) + vec2(0, -Tweak::PlayerCameraHeight);
		vec2 to = from + dir * 40;
		auto results = g_scene.RaycastWide(3, 16, from, to, ~0, RaycastType::Shot);
		array<string> hits;
		for (uint i = 0; i < results.length() && i < QA_MELEE_RAY_CAP; i++)
		{
			RaycastResult res = results[i];
			UnitPtr unit = res.FetchUnit(g_scene);
			ref@ behavior = null;
			if (unit.IsValid())
				@behavior = unit.GetScriptBehavior();
			auto actor = cast<Actor>(behavior);
			auto taker = cast<IDamageTaker>(behavior);
			Json row;
			row.Int("unit", unit.IsValid() ? unit.GetId() : -1).Bool("valid", unit.IsValid())
				.Str("name", unit.IsValid() ? unit.GetDebugName() : "")
				.Str("type", behavior is null ? "" : Reflect::GetTypeName(behavior))
				.Num("x", res.point.x).Num("y", res.point.y).Num("dist", dist(from, res.point))
				.Num("fraction", res.fraction).Bool("owner", unit == plr.m_unit)
				.Bool("actor", actor !is null).Bool("damageTaker", taker !is null)
				.Bool("impenetrable", taker !is null && taker.Impenetrable()).Bool("sensor", res.fixture.IsSensor());
			hits.insertLast(row.Close());
		}
		int truncated = results.length() > QA_MELEE_RAY_CAP ? int(results.length() - QA_MELEE_RAY_CAP) : 0;
		Emit(Reply(id, true).Int("now", int(g_scene.GetTime())).Int("count", results.length()).Int("truncated", truncated)
			.Int("rays", 3).Int("width", 16).Int("distance", 40).Int("headHeight", Tweak::PlayerCameraHeight)
			.Num("x0", from.x).Num("y0", from.y).Num("x1", to.x).Num("y1", to.y).Raw("hits", RawArray(hits)));
	}

	// summonmove <ownedUnitId>: only a local player's live owned actor within1200px.
	// The instantiated MeleeFollowerMovement values reveal producer overrides as well
	// as native defaults. This never orders the summon or writes movement state.
	void VerbQASummonMove(const string &in id, array<string>@ args)
	{
		auto plr = GetLocalPlayer();
		if (plr is null || args.length() != 1)
		{
			Fail(id, "usage: summonmove <ownedUnitId>; needs a spawned local player");
			return;
		}
		auto unit = g_scene.GetUnit(int(parseInt(args[0])));
		if (!unit.IsValid() || unit.IsDestroyed())
		{
			Fail(id, "owned unit is not live");
			return;
		}
		auto actor = cast<CompositeActorBehavior>(unit.GetScriptBehavior());
		auto owned = cast<IOwnedUnit>(unit.GetScriptBehavior());
		Actor@ owner = owned is null ? null : owned.GetOwner();
		if (actor is null || actor.IsDead() || owner is null || owner.m_unit != plr.m_unit
			|| dist(xy(unit.GetPosition()), xy(plr.m_unit.GetPosition())) > 1200)
		{
			Fail(id, "requires a live actor owned by the local player within1200px");
			return;
		}
		vec2 pos = xy(unit.GetPosition());
		vec2 ownerPos = xy(plr.m_unit.GetPosition());
		auto follower = cast<MeleeFollowerMovement>(actor.m_movement);
		auto reply = Reply(id, true);
		reply.Int("now", int(g_scene.GetTime())).Int("unit", unit.GetId()).Str("name", unit.GetDebugName())
			.Str("movement", actor.m_movement is null ? "" : Reflect::GetTypeName(actor.m_movement))
			.Bool("follower", follower !is null).Num("x", pos.x).Num("y", pos.y)
			.Int("owner", owner.m_unit.GetId()).Num("ownerX", ownerPos.x).Num("ownerY", ownerPos.y)
			.Num("dist", dist(pos, ownerPos)).Int("hpMax", actor.GetMaxHp())
			.Num("hpExact", double(actor.GetHealth()) * double(actor.GetMaxHp()));
		if (follower !is null)
			reply.Num("runBackDistance", sqrt(float(follower.m_runBackDistSq)))
				.Num("roamingDistance", sqrt(float(follower.m_roamingDistSq))).Bool("runningBack", follower.m_runningBack)
				.Num("idleTargetX", follower.m_idleTarget.x).Num("idleTargetY", follower.m_idleTarget.y)
				.Int("retargetMs", follower.m_newIdleTargetC);
		Emit(reply);
	}

	void Register_qa_rays()
	{
		RegisterVerb("meleerays", "<dx> <dy>", Verb(VerbQAMeleeRays));
		RegisterVerb("summonmove", "<ownedUnitId>", Verb(VerbQASummonMove));
	}
}
