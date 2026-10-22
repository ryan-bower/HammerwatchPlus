// QA only: read-only native outgoing/target damage fields at nine decimals.
// PlayerBase.as788-938 and CompositeActorBehavior.as706-726 are the model.
// Explicit target identity; no RNG, damage, refresh, hooks, or input changes.
namespace GameLab
{
    // damagefields <skillId> <targetUnitId>: exact live owned skill and Composite
    // target fields. No modifier.Crit sampling. Max128 owned skills, radius1000.
    void VerbQADamageFields(const string &in id, array<string>@ args)
    {
        auto player = cast<Player>(GetLocalPlayer());
        if (player is null || args.length() != 2)
        {
            Fail(id, "usage: damagefields <skillId> <targetUnitId>; live Player required");
            return;
        }
        if (player.m_record is null || player.m_record.playerClass is null || player.IsDead()
            || player.m_skills.length() > 128)
        {
            Fail(id, "invalid live player/class or more than128 skills");
            return;
        }
        int targetId = int(parseInt(args[1]));
        UnitPtr unit = g_scene.GetUnit(targetId);
        if (targetId == 0 || !unit.IsValid() || unit.IsDestroyed() || unit == player.m_unit)
        {
            Fail(id, "target must be an explicit distinct live unit");
            return;
        }
        auto target = cast<CompositeActorBehavior>(unit.GetScriptBehavior());
        if (target is null || target.IsDead() || target.m_props is null
            || dist(xy(unit.GetPosition()), xy(player.m_unit.GetPosition())) > 1000)
        {
            Fail(id, "target must be a live CompositeActor within1000px");
            return;
        }
        Skills::Skill@ skill = null;
        int matches = 0;
        uint skillId = HashString(args[0]);
        for (uint i = 0; i < player.m_skills.length(); i++)
        {
            auto candidate = player.m_skills[i];
            if (candidate !is null && candidate.m_skillId == skillId && candidate.m_id == args[0])
            {
                @skill = candidate;
                matches++;
            }
        }
        if (matches != 1 || skill is null)
        {
            Fail(id, "exactly one matching owned live skill is required");
            return;
        }
        auto targetBuffs = target.GetBuffList();
        if (targetBuffs is null)
        {
            Fail(id, "target native buff list is required");
            return;
        }
        auto st = player.m_record.currStats;
        auto mh = st.MainHand;
        auto oh = st.OffHand;
        vec2 damageMod = player.m_record.GetModifiers().DamageMul(player, target);
        vec2 armorMod = targetBuffs.ArmorMul();
        auto props = target.m_props;
        Json owner;
        owner.Int("unit", player.m_unit.GetId()).Str("class", player.m_record.playerClass.m_id)
            .Int("level", player.m_record.level)
            .Raw("x", formatFloat(player.m_unit.GetPosition().x, "", 0, 9))
            .Raw("y", formatFloat(player.m_unit.GetPosition().y, "", 0, 9))
            .Raw("buffDamageMul", formatFloat(player.m_buffs.DamageMul(), "", 0, 9))
            .Raw("damageMul", formatFloat(float(st.DamageMul), "", 0, 9))
            .Raw("summonDamageMul", formatFloat(float(st.SummonDamageMul), "", 0, 9))
            .Raw("attackPower", formatFloat(float(st.AttackPower), "", 0, 9))
            .Raw("spellPower", formatFloat(float(st.SpellPower), "", 0, 9))
            .Raw("damagePowerDivisor", formatFloat(Tweak::DamagePowerDivisor, "", 0, 9))
            .Raw("modifierAttack", formatFloat(damageMod.x, "", 0, 9))
            .Raw("modifierSpell", formatFloat(damageMod.y, "", 0, 9))
            .Raw("spellCritChance", formatFloat(float(st.SpellCritChance), "", 0, 9))
            .Raw("spellCritDamage", formatFloat(float(st.SpellCritDamage), "", 0, 9))
            .Raw("physicalMul", formatFloat(float(st.PhysicalDamageMul), "", 0, 9))
            .Raw("fireMul", formatFloat(float(st.FireDamageMul), "", 0, 9))
            .Raw("iceMul", formatFloat(float(st.IceDamageMul), "", 0, 9))
            .Raw("lightningMul", formatFloat(float(st.LightningDamageMul), "", 0, 9))
            .Raw("poisonMul", formatFloat(float(st.PoisonDamageMul), "", 0, 9))
            .Raw("pureMul", formatFloat(float(st.PureDamageMul), "", 0, 9))
            .Raw("armorPen", formatFloat(float(st.ArmorPenetration), "", 0, 9))
            .Raw("firePen", formatFloat(float(st.ResistanceFirePenetration), "", 0, 9))
            .Raw("icePen", formatFloat(float(st.ResistanceIcePenetration), "", 0, 9))
            .Raw("lightningPen", formatFloat(float(st.ResistanceLightningPenetration), "", 0, 9))
            .Raw("poisonPen", formatFloat(float(st.ResistancePoisonPenetration), "", 0, 9));
        Json main;
        main.Int("physical", int(mh.DamagePhysical)).Int("fire", int(mh.DamageFire))
            .Int("ice", int(mh.DamageIce)).Int("lightning", int(mh.DamageLightning)).Int("poison", int(mh.DamagePoison))
            .Raw("critChance", formatFloat(float(mh.CritChance), "", 0, 9))
            .Raw("critDamage", formatFloat(float(mh.CritDamage), "", 0, 9))
            .Raw("attackSpeed", formatFloat(float(mh.AttackSpeed), "", 0, 9));
        Json off;
        off.Int("physical", int(oh.DamagePhysical)).Int("fire", int(oh.DamageFire))
            .Int("ice", int(oh.DamageIce)).Int("lightning", int(oh.DamageLightning)).Int("poison", int(oh.DamagePoison))
            .Raw("critChance", formatFloat(float(oh.CritChance), "", 0, 9))
            .Raw("critDamage", formatFloat(float(oh.CritDamage), "", 0, 9))
            .Raw("attackSpeed", formatFloat(float(oh.AttackSpeed), "", 0, 9));
        Json selected;
        selected.Str("id", skill.m_id).Int("type", int(skill.m_type)).Int("matches", matches)
            .Raw("damageMul", formatFloat(skill.m_modDamageMul, "", 0, 9))
            .Raw("critChance", formatFloat(skill.m_modCritChance, "", 0, 9))
            .Raw("critDamage", formatFloat(skill.m_modCritDamage, "", 0, 9));
        Json enemy;
        enemy.Int("unit", targetId).Str("name", unit.GetDebugName()).Str("type", Reflect::GetTypeName(target))
            .Raw("x", formatFloat(unit.GetPosition().x, "", 0, 9))
            .Raw("y", formatFloat(unit.GetPosition().y, "", 0, 9))
            .Int("hpMax", target.GetMaxHp()).Raw("hpFraction", formatFloat(target.GetHealth(), "", 0, 9))
            .Int("armor", props.m_armor).Int("fireRes", props.m_resistanceFire).Int("iceRes", props.m_resistanceIce)
            .Int("lightningRes", props.m_resistanceLightning).Int("poisonRes", props.m_resistancePoison)
            .Raw("armorMul", formatFloat(armorMod.x, "", 0, 9))
            .Raw("resistanceMul", formatFloat(armorMod.y, "", 0, 9))
            .Raw("damageTakenMul", formatFloat(targetBuffs.DamageTakenMul(), "", 0, 9))
            .Raw("afflictionDamageTakenMul", formatFloat(targetBuffs.AfflictionDamageTakenMul(), "", 0, 9))
            .Raw("receiveCritChance", formatFloat(targetBuffs.ReceiveCritChance(), "", 0, 9))
            .Raw("afflictionPhysicalMul", formatFloat(props.m_afflPhysMul, "", 0, 9))
            .Raw("afflictionFireMul", formatFloat(props.m_afflFireMul, "", 0, 9))
            .Raw("afflictionIceMul", formatFloat(props.m_afflIceMul, "", 0, 9))
            .Raw("afflictionLightningMul", formatFloat(props.m_afflLightnMul, "", 0, 9))
            .Raw("afflictionPoisonMul", formatFloat(props.m_afflPoisonMul, "", 0, 9))
            .Int("firePool", targetBuffs.m_fireDmgPool).Int("icePool", targetBuffs.m_iceDmgPool)
            .Int("poisonPool", targetBuffs.m_poisonDmgPool).Int("lightningPool", targetBuffs.m_lightningDmgPool)
            .Int("physicalPool", targetBuffs.m_physicalDmgPool);
        Emit(Reply(id, true).Int("now", int(g_scene.GetTime())).Int("ngp", g_ngp)
            .Int("precision", 9).Bool("sampledCritRng", false)
            .Raw("owner", owner.Close()).Raw("main", main.Close()).Raw("off", off.Close())
            .Raw("skill", selected.Close()).Raw("target", enemy.Close()));
    }

    void Register_qa_damage_fields()
    {
        RegisterVerb("damagefields", "<skillId> <targetUnitId>", Verb(VerbQADamageFields));
    }
}
