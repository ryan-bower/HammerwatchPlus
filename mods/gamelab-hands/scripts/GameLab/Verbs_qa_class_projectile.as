// Bounded read-only native projectile/collision observation. The caller posts
// ordinary input separately; this task never triggers a hit or changes payloads.
namespace GameLab
{
	bool g_qaClassProjectileBusy = false;
	class QAClassProjectileTask : QueuedTasks::UpdatingTask
	{
		PlayerBase@ player;
		UnitProducer@ producer;
		array<Actor@> targets;
		array<double> previousHp;
		array<int> units, collisions, penetrations;
		string tag, path;
		vec2 origin;
		int limit, elapsed = 0, frames = 0, seen = 0, emitted = 0, live = 0;
		bool scanTruncated = false;

		string Targets()
		{
			array<string> rows;
			for (uint i = 0; i < targets.length(); i++)
			{
				auto actor = targets[i];
				bool valid = actor !is null && actor.m_unit.IsValid() && !actor.m_unit.IsDestroyed();
				Json row;
				row.Int("unit", actor is null ? 0 : actor.m_unit.GetId()).Bool("valid", valid);
				if (valid)
					row.Int("hpMax", actor.GetMaxHp()).Raw("hpExact", formatFloat(double(actor.GetHealth()) * double(actor.GetMaxHp()), "", 0, 9))
						.Num("x", actor.m_unit.GetPosition().x).Num("y", actor.m_unit.GetPosition().y).Bool("dead", actor.IsDead());
				auto composite = cast<CompositeActorBehavior>(actor);
                ActorBuffList@ buffs;
                if (actor !is null) @buffs = actor.GetBuffList();
                row.Bool("native_props", composite !is null && buffs !is null);
                if (composite !is null && buffs !is null)
                    row.Int("armor", composite.m_props.m_armor)
                        .Int("resFire", composite.m_props.m_resistanceFire).Int("resIce", composite.m_props.m_resistanceIce)
                        .Int("resLightning", composite.m_props.m_resistanceLightning).Int("resPoison", composite.m_props.m_resistancePoison)
                        .Raw("damageTakenMul", formatFloat(buffs.DamageTakenMul(), "", 0, 9))
                        .Raw("receiveCritChance", formatFloat(buffs.ReceiveCritChance(), "", 0, 9))
                        .Raw("armorMulPhysical", formatFloat(buffs.ArmorMul().x, "", 0, 9))
                        .Raw("modifierSpell", formatFloat(player.m_record.GetModifiers().DamageMul(player, actor).y, "", 0, 9));
				rows.insertLast(row.Close());
			}
			return RawArray(rows);
		}

        string DamagePayload(NewProjectile@ projectile)
        {
            Json result;
            auto list = projectile.m_hitEffects;
            result.Bool("present", list !is null);
            if (list is null) return result.Close();
            array<string> rows;
            for (uint i = 0; i < list.m_effects.length() && i < 8; i++)
            {
                if (list.m_effects[i] is null) continue;
                auto fixedDamage = cast<Damage>(list.m_effects[i].m_effect);
                auto weaponDamage = cast<PlayerDamage>(list.m_effects[i].m_effect);
                if (fixedDamage is null && weaponDamage is null) continue;
                Json row;
                if (fixedDamage !is null)
                    row.Str("kind", "Damage").Int("physical", fixedDamage.m_PhysicalDamage).Int("fire", fixedDamage.m_FireDamage)
                        .Int("ice", fixedDamage.m_IceDamage).Int("lightning", fixedDamage.m_LightningDamage)
                        .Int("poison", fixedDamage.m_PoisonDamage).Int("pure", fixedDamage.m_PureDamage)
                        .Int("merged", fixedDamage.m_merged.length()).Int("weapon_info", fixedDamage.m_weaponInfo);
                if (weaponDamage !is null)
                {
                    auto st = player.m_record.currStats;
                    auto hand = weaponDamage.m_primary ? st.MainHand : st.OffHand;
                    auto skill = player.GetSkill(weaponDamage.m_weaponInfo);
                    Json components, model;
                    components.Raw("physical", formatFloat(hand.DamagePhysical, "", 0, 9))
                        .Raw("fire", formatFloat(hand.DamageFire, "", 0, 9)).Raw("ice", formatFloat(hand.DamageIce, "", 0, 9))
                        .Raw("lightning", formatFloat(hand.DamageLightning, "", 0, 9))
                        .Raw("poison", formatFloat(hand.DamagePoison, "", 0, 9)).Raw("pure", formatFloat(hand.DamagePure, "", 0, 9));
                    model.Bool("skill_valid", skill !is null).Int("skill_type", skill is null ? -1 : int(skill.m_type))
                        .Raw("spellPower", formatFloat(st.SpellPower, "", 0, 9))
                        .Raw("powerDivisor", formatFloat(Tweak::DamagePowerDivisor, "", 0, 9))
                        .Raw("globalDamageMul", formatFloat(st.DamageMul, "", 0, 9))
                        .Raw("summonDamageMul", formatFloat(st.SummonDamageMul, "", 0, 9))
                        .Raw("buffDamageMul", formatFloat(player.m_buffs.DamageMul(), "", 0, 9))
                        .Raw("physicalDamageMul", formatFloat(st.PhysicalDamageMul, "", 0, 9))
                        .Raw("spellCritChance", formatFloat(st.SpellCritChance, "", 0, 9));
                    if (skill !is null)
                        model.Raw("skillDamageMul", formatFloat(skill.m_modDamageMul, "", 0, 9))
                            .Raw("skillCritChance", formatFloat(skill.m_modCritChance, "", 0, 9))
                            .Bool("spell", skill.m_type == PlayerSkillType::Spell);
                    row.Str("kind", "PlayerDamage").Raw("mul", formatFloat(weaponDamage.m_mul, "", 0, 9))
                        .Bool("primary", weaponDamage.m_primary).Int("merged", weaponDamage.m_merged.length())
                        .Int("weapon_info", weaponDamage.m_weaponInfo).Raw("hand", components.Close()).Raw("model", model.Close());
                }
                rows.insertLast(row.Close());
            }
            return result.Int("effect_count", list.m_effects.length()).Int("damage_count", rows.length())
                .Int("truncated", list.m_effects.length() > 8 ? list.m_effects.length() - 8 : 0)
                .Raw("damage", RawArray(rows)).Close();
        }

		void Sample(const string &in reason, NewProjectile@ projectile = null)
		{
			seen++;
			if (emitted >= 64) return;
			Json row;
			row.Str("ev", "qa_class_projectile").Str("tag", tag).Str("phase", "sample")
				.Int("index", emitted++).Int("now", int(g_scene.GetTime())).Int("elapsed", elapsed)
				.Str("reason", reason).Raw("targets", Targets()).Bool("projectile", projectile !is null);
			if (projectile !is null)
			{
				auto collision = projectile.m_lastCollision;
				bool valid = collision.IsValid() && !collision.IsDestroyed();
				row.Int("unit", projectile.m_unit.GetId()).Int("owner", projectile.m_owner.m_unit.GetId())
                    .Bool("owner_is_player", projectile.m_owner is player)
					.Num("x", projectile.m_pos.x).Num("y", projectile.m_pos.y)
					.Num("direction_x", projectile.m_dir.x).Num("direction_y", projectile.m_dir.y)
					.Num("intensity", projectile.m_intensity).Int("ttl", projectile.m_ttl)
					.Int("penetration", projectile.m_penetration).Int("ray_width", projectile.m_rayWidth)
					.Int("ray_count", projectile.m_rayNum).Bool("collision_valid", valid)
					.Int("collision_unit", valid ? collision.GetId() : 0)
					.Str("collision_name", valid ? collision.GetDebugName() : "")
					.Bool("collision_actor", valid && cast<Actor>(collision.GetScriptBehavior()) !is null)
					.Raw("payload", DamagePayload(projectile));
			}
			Emit(row);
		}

		void Finish(bool complete, const string &in error)
		{
			g_qaClassProjectileBusy = false;
			Json row;
			Emit(row.Str("ev", "qa_class_projectile").Str("tag", tag).Str("phase", "done")
				.Bool("complete", complete).Str("error", error).Bool("truncated", scanTruncated || seen > emitted)
				.Int("seen", seen).Int("count", emitted).Int("projectiles", units.length()).Int("live", live)
				.Int("ms", elapsed).Int("frames", frames).Str("producer", path).Raw("targets", Targets()));
		}

		bool UpdateFrame(int ms) override
		{
			elapsed += ms; frames++;
			if (player is null || GetLocalPlayer() !is player || player.IsDead()
				|| !player.m_unit.IsValid() || dist(origin, xy(player.m_unit.GetPosition())) > 1)
			{ Finish(false, "local actor changed, died, or moved"); return true; }
			for (uint i = 0; i < targets.length(); i++)
			{
				auto actor = targets[i];
				if (!actor.m_unit.IsValid() || actor.m_unit.IsDestroyed() || actor.IsDead())
				{ Finish(false, "measurement target lost or died"); return true; }
				double hp = double(actor.GetHealth()) * double(actor.GetMaxHp());
				if (abs(hp - previousHp[i]) > 0.00001) { previousHp[i] = hp; Sample("target_hp"); }
			}
			auto all = g_scene.FetchAllUnitsOfType(producer);
			if (all.length() > 16) scanTruncated = true;
			live = 0;
			for (uint i = 0; i < all.length() && i < 16; i++)
			{
				if (!all[i].IsValid() || all[i].IsDestroyed()) continue;
				auto projectile = cast<NewProjectile>(all[i].GetScriptBehavior());
				if (projectile is null || projectile.m_owner !is player) continue;
				live++;
				int uid = all[i].GetId();
				int collision = projectile.m_lastCollision.IsValid() ? projectile.m_lastCollision.GetId() : 0;
				int index = units.find(uid);
				if (index < 0)
				{
					if (units.length() >= 8) { scanTruncated = true; continue; }
					units.insertLast(uid); collisions.insertLast(collision); penetrations.insertLast(projectile.m_penetration);
					Sample("birth", projectile);
				}
				else if (collisions[index] != collision || penetrations[index] != projectile.m_penetration)
				{
					collisions[index] = collision; penetrations[index] = projectile.m_penetration;
					Sample("collision_or_penetration", projectile);
				}
			}
			if (elapsed < limit) return false;
			Finish(true, ""); return true;
		}
	}

	void VerbQAClassProjectile(const string &in id, array<string>@ args)
	{
		auto player = cast<PlayerBase>(GetLocalPlayer());
		if (args.length() < 4 || args.length() > 7 || player is null || player.IsDead()
			|| QueuedTasks::g_instance is null || g_qaClassProjectileBusy)
		{ Fail(id, "usage: qa_class_projectile <tag> <500..5000ms> <producer> <1..4 targetUnitIDs>"); return; }
		int ms = int(parseInt(args[1]));
		auto producer = Resources::GetUnitProducer(args[2]);
		if (ms < 500 || ms > 5000 || producer is null || g_scene.FetchAllUnitsOfType(producer).length() != 0)
		{ Fail(id, "needs bounded window, actual producer, and no old matching projectiles"); return; }
		QAClassProjectileTask task;
		@task.player = player; @task.producer = producer;
		task.tag = args[0]; task.path = args[2]; task.limit = ms;
		task.origin = xy(player.m_unit.GetPosition());
		for (uint i = 3; i < args.length(); i++)
		{
			auto unit = g_scene.GetUnit(int(parseInt(args[i])));
			Actor@ actor;
			if (unit.IsValid() && !unit.IsDestroyed()) @actor = cast<Actor>(unit.GetScriptBehavior());
			if (actor is null || actor.IsDead() || actor.Team == player.Team || dist(task.origin, xy(unit.GetPosition())) > 256
				|| task.targets.findByRef(actor) >= 0)
			{ Fail(id, "needs1..4 distinct live nearby hostile actor targets"); return; }
			task.targets.insertLast(actor);
			task.previousHp.insertLast(double(actor.GetHealth()) * double(actor.GetMaxHp()));
		}
		task.Sample("initial");
		g_qaClassProjectileBusy = true; QueuedTasks::Queue(task);
		Emit(Reply(id, true).Str("tag", task.tag).Int("ms", ms).Int("targets", task.targets.length()));
	}

	void Register_qa_class_projectile()
	{
		RegisterVerb("qa_class_projectile", "<tag> <500..5000ms> <producer> <1..4 targetUnitIDs>", Verb(VerbQAClassProjectile));
	}
}
