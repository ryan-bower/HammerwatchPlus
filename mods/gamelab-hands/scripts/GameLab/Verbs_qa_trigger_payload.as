// Read-only instantiated native modifier payloads. No RNG, refresh, trigger,
// skill/stack setter, damage call, input, or per-frame hook is installed here.
namespace GameLab
{
	const uint QA_TRIGGER_SCAN_CAP = 256;
	const uint QA_TRIGGER_RECORD_CAP = 8;
	const uint QA_TRIGGER_EFFECT_CAP = 2;
	const uint QA_TRIGGER_TEXT_CAP = 11000;

	string QATriggerEffectPayload(EffectList@ list)
	{
		Json result;
		result.Bool("present", list !is null);
		if (list is null)
			return result.Close();
		array<string> effects;
		for (uint i = 0; i < list.m_effects.length() && i < QA_TRIGGER_EFFECT_CAP; i++)
		{
			auto entry = list.m_effects[i];
			Json row;
			row.Bool("entry", entry !is null);
			if (entry !is null)
			{
				row.Bool("present", entry.m_effect !is null)
					.Str("class", entry.m_effect is null ? "" : Reflect::GetTypeName(entry.m_effect));
				auto damage = cast<Damage>(entry.m_effect);
				row.Bool("damage", damage !is null);
				if (damage !is null)
					row.Int("physical", damage.m_PhysicalDamage).Int("fire", damage.m_FireDamage)
						.Int("ice", damage.m_IceDamage).Int("lightning", damage.m_LightningDamage)
						.Int("poison", damage.m_PoisonDamage).Int("pure", damage.m_PureDamage)
						.Int("weapon_info", damage.m_weaponInfo).Int("merged", damage.m_merged.length())
						.Bool("dot", damage.m_dot).Bool("melee", damage.m_melee);
				auto mod = entry.m_effectMod;
				row.Bool("modifier", mod !is null);
				if (mod !is null)
					row.Num("intensity_set0", mod.m_intensitySet.x).Num("intensity_set1", mod.m_intensitySet.y)
						.Num("intensity_mul0", mod.m_intensityMul.x).Num("intensity_mul1", mod.m_intensityMul.y)
						.Bool("target_self", mod.m_targetSelf).Int("modifier_weapon_info", mod.m_weaponInfo);
			}
			effects.insertLast(row.Close());
		}
		return result.Num("self_damage", list.m_selfDmg).Num("team_damage", list.m_teamDmg)
			.Num("enemy_damage", list.m_enemyDmg).Int("count", list.m_effects.length())
			.Int("truncated", list.m_effects.length() > QA_TRIGGER_EFFECT_CAP ? list.m_effects.length() - QA_TRIGGER_EFFECT_CAP : 0)
			.Raw("effects", RawArray(effects)).Close();
	}

	void VerbQATriggerPayload(const string &in id, array<string>@ args)
	{
		auto player = cast<PlayerBase>(GetLocalPlayer());
		if (args.length() > 1 || player is null || player.m_record is null || player.IsDead())
		{
			Fail(id, "requires a live local player; usage: qa_trigger_payload [native source id]");
			return;
		}
		uint source = args.length() == 1 ? HashString(args[0]) : 0;
		bool filtered = args.length() == 1;
		auto rec = player.m_record;
		array<string> records;
		uint total = rec.modifiers.m_triggerModifiers.length();
		uint scanned = min(total, QA_TRIGGER_SCAN_CAP);
		int matches = 0;
		uint textSize = 0;
		for (uint i = 0; i < scanned; i++)
		{
			auto state = rec.modifiers.m_triggerModifiers[i];
			if (state is null || state.m_trigg is null)
				continue; // Native Clear deliberately retains inactive state shells.
			auto base = state.m_trigg;
			if (filtered && base.m_verbId != source)
				continue;
			matches++;
			if (records.length() >= QA_TRIGGER_RECORD_CAP)
				continue;
			Json row;
			row.Int("index", i).Str("class", Reflect::GetTypeName(base))
				.Int("verb", int(base.m_verb)).Int("source_id", base.m_verbId).Int("modifier_id", base.m_modId)
				.Int("trigger", int(base.m_trigger)).Int("quantity_trigger", int(base.m_quantityTrigger))
				.Num("intensity", state.m_intensity).Int("timeout_until", state.m_timeoutC)
				.Int("counter_remaining", state.m_counterC).Bool("update", state.m_hasUpdate)
				.Bool("conditionals", base.m_conditionals !is null).Bool("conditional_target_other", base.m_condTargetOther);
			auto trigger = cast<Modifiers::TriggerEffect>(base);
			row.Bool("effect_trigger", trigger !is null);
			if (trigger !is null)
				row.Num("chance0", trigger.m_chance.x).Num("chance1", trigger.m_chance.y)
					.Num("nominal_chance", Modifiers::lerp(trigger.m_chance, state.m_intensity))
					.Int("timeout0", trigger.m_timeout.x).Int("timeout1", trigger.m_timeout.y)
					.Bool("target_self", trigger.m_targetSelf).Int("counter", trigger.m_counter)
					.Raw("payload", QATriggerEffectPayload(trigger.m_effectList));
			auto timed = cast<Modifiers::TimedTriggerEffect>(base);
			row.Bool("timed", timed !is null);
			if (timed !is null)
			{
				row.Int("frequency0", timed.m_freq.x).Int("frequency1", timed.m_freq.y);
				auto timer = cast<Modifiers::TimedTriggerEffectState>(state);
				row.Bool("timer_state", timer !is null);
				if (timer !is null) row.Int("timer_remaining", timer.m_timer);
			}
			string serialized = row.Close();
			if (textSize + serialized.length() > QA_TRIGGER_TEXT_CAP) continue;
			textSize += serialized.length();
			records.insertLast(serialized);
		}
		Emit(Reply(id, true).Int("now", int(g_scene.GetTime())).Int("player", player.m_unit.GetId())
			.Str("filter", filtered ? args[0] : "").Int("filter_hash", source).Num("luck", player.m_currLuck)
			.Int("state_count", total).Int("scanned", scanned).Int("scan_truncated", total - scanned)
			.Int("matches", matches).Int("count", records.length()).Int("truncated", matches - records.length())
			.Raw("records", RawArray(records)));
	}

	void Register_qa_trigger_payload()
	{
		RegisterVerb("qa_trigger_payload", "[native source id]", Verb(VerbQATriggerPayload));
	}
}
