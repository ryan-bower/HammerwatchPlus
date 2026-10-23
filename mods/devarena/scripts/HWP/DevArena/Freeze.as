// Dev Arena mob freeze (Arena tab: "freeze"). Three locks, because none alone holds:
// CompositeActorBehavior.m_frozen gates only the skill loop (CompositeActorBehavior.as:1199),
// movement still updates (:1245); a buff with lock-movement, speed-mul 0, disarm and
// silence covers movement (Movements/*.as multiply by m_buffs.MoveSpeedMul()) and cancels
// a cast in progress (:531-547); and the body itself is made static and pinned (TickFreeze).
// Re-applied every second while on, so the buff's duration and newly spawned mobs are covered. Actors with no-buffs keep only m_frozen.
namespace HWP
{
namespace DevArena
{
	bool g_freeze;
	int g_freezeReapplyC;
	ActorBuffDef@ g_freezeDef;

	// measurement for the freeze spike: positions at freeze time, the player's hp lost since
	dictionary g_freezePos;   // unit id -> vec2
	float g_lastHp = -1;
	float g_hpLost;

	ActorBuffDef@ FreezeDef()
	{
		if (g_freezeDef !is null)
			return g_freezeDef;
		SValueBuilder b;
		b.PushDictionary();
		b.PushString("name", "hwp.devarena.freeze");
		b.PushInteger("duration", 2000);
		b.PushBoolean("debuff", true);
		b.PushBoolean("ignore-buff-scaling", true);
		b.PushBoolean("lock-movement", true);
		b.PushBoolean("lock-rotation", true);
		b.PushBoolean("disarm", true);
		b.PushBoolean("silence", true);
		b.PushVector2("speed-mul", vec2(0, 0));
		b.PopDictionary();
		@g_freezeDef = ActorBuffDef(HashString("hwp_devarena_freeze"), b.Build());
		return g_freezeDef;
	}

	array<CompositeActorBehavior@>@ Mobs()
	{
		array<CompositeActorBehavior@> res;
		auto units = g_scene.FetchAllActorsWithOtherTeam(g_team_player);
		for (uint i = 0; i < units.length(); i++)
		{
			auto c = cast<CompositeActorBehavior>(units[i].GetScriptBehavior());
			if (c !is null && !c.IsDead())
				res.insertLast(c);
		}
		return res;
	}

	int ApplyFreeze(bool on)
	{
		auto mobs = Mobs();
		auto def = FreezeDef();
		for (uint i = 0; i < mobs.length(); i++)
		{
			mobs[i].m_frozen = on;
			if (!on)
			{
				auto body = mobs[i].m_unit.GetPhysicsBody();
				if (body !is null)
					body.SetStatic(false);
			}
			if (on)
			{
				mobs[i].ApplyBuff(ActorBuff(null, def, 1.0f, false));
				@mobs[i].m_target = null;
			}
		}
		return mobs.length();
	}

	int SetFreeze(bool on)
	{
		g_freeze = on;
		g_freezeReapplyC = 1000;
		int n = ApplyFreeze(on);
		// measurement restarts on "on" only, so movement after "off" stays measurable
		if (on)
		{
			g_freezePos.deleteAll();
			g_hpLost = 0;
			auto mobs = Mobs();
			for (uint i = 0; i < mobs.length(); i++)
				g_freezePos.set("" + mobs[i].m_unit.GetId(), xy(mobs[i].m_unit.GetPosition()));
		}
		HWP::Log("devarena", "freeze " + (on ? "on" : "off") + ": " + n + " mobs");
		return n;
	}

	void TickFreeze(int ms)
	{
		auto plr = LocalPlayer();
		if (plr !is null && plr.m_record !is null)
		{
			float hp = plr.m_record.CurrentHealth();
			if (g_lastHp >= 0 && hp < g_lastHp)
				g_hpLost += g_lastHp - hp;
			g_lastHp = hp;
		}
		if (!g_freeze)
			return;
		// the buff stops the movement code, not the body: a mob moving at freeze time slid
		// 3.8-3.9 units over 10 s even with its velocity zeroed every frame (spike-freeze
		// 20261020-222234, -222411), so the bodies go static and are pinned where they froze
		auto mobs = Mobs();
		for (uint i = 0; i < mobs.length(); i++)
		{
			auto body = mobs[i].m_unit.GetPhysicsBody();
			if (body !is null)
			{
				body.SetLinearVelocity(0, 0);
				body.SetStatic(true);
			}
			string key = "" + mobs[i].m_unit.GetId();
			vec2 p0;
			if (!g_freezePos.get(key, p0))
				g_freezePos.set(key, xy(mobs[i].m_unit.GetPosition()));
			else if (dist(p0, xy(mobs[i].m_unit.GetPosition())) > 0.01f)
				mobs[i].m_unit.SetPosition(p0.x, p0.y, mobs[i].m_unit.GetPosition().z, true);
		}
		g_freezeReapplyC -= ms;
		if (g_freezeReapplyC <= 0)
		{
			g_freezeReapplyC = 1000;
			ApplyFreeze(true);
		}
	}

	// the largest distance a mob present at freeze time has moved since
	float MaxMoved(int &out tracked)
	{
		float best = 0;
		tracked = 0;
		auto mobs = Mobs();
		for (uint i = 0; i < mobs.length(); i++)
		{
			vec2 p0;
			if (!g_freezePos.get("" + mobs[i].m_unit.GetId(), p0))
				continue;
			tracked++;
			best = max(best, dist(p0, xy(mobs[i].m_unit.GetPosition())));
		}
		return best;
	}
}
}
