class PlayerMenuModificationsTab : MenuTab
{
	string m_skillsTitle = Resources::GetString(".menu.player.mods.skills");
	string m_statsTitle = Resources::GetString(".menu.player.mods.stats");
	string m_effectsTitle = Resources::GetString(".menu.player.mods.effects");

	TextWidget@ m_title;

	CheckBoxGroupWidget@ m_checkBoxGroup;
	
	// Skills
	Widget@ m_skillsGroup;
	GroupWidget@ m_skillGroup;
	ScrollbarWidget@ m_skillsScroll;
	Widget@ m_skillList;

	SkillWidget@ m_skillIcon;
	TextWidget@ m_skillTitle;
	TextWidget@ m_skillDescription;

	// Stats
	Widget@ m_statsGroup;
	Widget@ m_statsList;

	TextWidget@ m_statsHeaderTemplate;
	Widget@ m_statsValueTemplate;
	Widget@ m_statsSeparatorTemplate;

	// Effects
	Widget@ m_effectsGroup;
	Widget@ m_effectsList;
	Widget@ m_effectsTemplate;

	BindingDisplayWidget@ m_bindingSubTabP;
	BindingDisplayWidget@ m_bindingSubTabN;

	PlayerMenuModificationsTab(GUIBuilder@ b, uint id)
	{
		super(b, id, "gui/playermenu/modifications.gui");

		@m_checkBoxGroup = cast<CheckBoxGroupWidget>(m_widget.GetWidgetById("tabs-container"));

		// Skills
		@m_skillsGroup = m_widget.GetWidgetById("skills-content");
		@m_skillsScroll = cast<ScrollbarWidget>(m_widget.GetWidgetById("skills-scroll"));
		@m_skillGroup = cast<GroupWidget>(m_widget.GetWidgetById("skill-content"));
		@m_skillList = m_widget.GetWidgetById("skill-list");

		@m_skillIcon = cast<SkillWidget>(m_widget.GetWidgetById("skill-icon"));
		@m_skillTitle = cast<TextWidget>(m_widget.GetWidgetById("skill-title"));
		@m_skillDescription = cast<TextWidget>(m_widget.GetWidgetById("skill-description"));

		// Stats
		@m_statsGroup = m_widget.GetWidgetById("stats-content");
		@m_statsList = m_widget.GetWidgetById("stats-list");
		@m_statsHeaderTemplate = cast<TextWidget>(m_widget.GetWidgetById("stat-header-template"));
		@m_statsValueTemplate = m_widget.GetWidgetById("stat-value-template");
		@m_statsSeparatorTemplate = m_widget.GetWidgetById("stat-separator-template");

		// Effects
		@m_effectsGroup = m_widget.GetWidgetById("effects-content");
		@m_effectsList = m_widget.GetWidgetById("effects-list");
		@m_effectsTemplate = m_widget.GetWidgetById("effects-template");

		@m_title = cast<TextWidget>(m_widget.GetWidgetById("title"));

		@m_bindingSubTabP = cast<BindingDisplayWidget>(m_widget.GetWidgetById("binding-subtab-p"));
		@m_bindingSubTabN = cast<BindingDisplayWidget>(m_widget.GetWidgetById("binding-subtab-n"));

		RefreshInteractableWidgets(m_widget);
		SetTab(HashString("skills-content"));
	}

	void RefreshKeybinds(ControlMap@ currMap) override
	{
		m_bindingSubTabP.SetBinding("MenuPreviousSubTab");
		m_bindingSubTabN.SetBinding("MenuNextSubTab");

		AWindowObject::RefreshKeybinds(currMap);
	}

	void RefreshSkillGroup()
	{
		for (uint i = 0; i < m_skillList.m_children.length(); i++)
		{
			auto child = cast<SkillWidget>(m_skillList.m_children[i]);
			if (child is null)
				continue;

			child.SetID("");
			child.SetSkill();
		}

		auto record = GetLocalPlayerRecord();
		if (record is null)
			return;

		array<Skills::Skill@>@ playerSkills;

		auto player = cast<PlayerBase>(record.actor);
		if (player !is null)
			@playerSkills = player.m_skills;
		else
			@playerSkills = PlayerHelper::GetDeadSkillList(record);

		auto mainHandWeapon = record.equipped.m_items[EquippedItemsSlots::MainHand];
		auto offHandWeapon = record.equipped.m_items[EquippedItemsSlots::OffHand];

		uint j = 2;
		for (uint i = 0; i < playerSkills.length(); i++)
		{
			//if (j >= m_skillList.m_children.length())
			//	break;

			auto skill = playerSkills[i];
			if (skill.m_hiddenFromPlrMenu)
				continue;

			if (skill.m_type == PlayerSkillType::Dash)
				continue;

			SkillWidget@ child = null;
			if (skill.m_type == PlayerSkillType::MainHand)
				@child = cast<SkillWidget>(m_skillList.m_children[0]);
			else if (skill.m_type == PlayerSkillType::OffHand)
				@child = cast<SkillWidget>(m_skillList.m_children[1]);
			else
			{
				if (j >= m_skillList.m_children.length())
					continue;
				
				@child = cast<SkillWidget>(m_skillList.m_children[j]);
				j++;
			}

			child.SetID(skill.m_id);

			if (skill.m_type == PlayerSkillType::MainHand)
				child.SetSkill(skill, mainHandWeapon);
			else if (skill.m_type == PlayerSkillType::OffHand)
			{
				bool twoHanded = mainHandWeapon !is null && mainHandWeapon.GetSlot() == Equipment::Slot::TwoHanded;
				child.SetSkill(skill, twoHanded ? mainHandWeapon : offHandWeapon, twoHanded);
			}
			else
				child.SetSkill(skill);
		}

		m_skillsScroll.Highlight();
	}

	string FormatDmgReduction(int armor, const string &in icon)
	{
		auto reduction = 100.0f - ((ApplyArmor(100000, float(armor)) / 100000.0f) * 100.0f);
		if (reduction == 0)
			return " (-0%\\ " + icon + ")";
		if (reduction > 0)
			return " (-" + round(reduction, 2) + "%\\ " + icon + ")";
		return " (+" + round(-reduction, 2) + "%\\ " + icon + ")";
	}

	array<string> m_statsTabIcons = {
		"splpwr",
		"armor",
		"critchance",
		"critdamage",
		"spellcritchance",
		"spellcritdamage",
		"health",
		"healthregen",
		"mana",
		"manaregen",
		"damagephysical",
		"damagefire",
		"damageice",
		"damagelightning",
		"damagepoison"
	};

	array<string>@ GetShownIcons() override
	{
		if (m_statsGroup.m_visible)
			return m_statsTabIcons;
		return array<string>();
	}


	void RefreshStatsGroup()
	{
		m_statsList.ClearChildren();

		auto record = GetLocalPlayerRecord();
		if (record is null)
			return;

		record.RefreshStats();
		auto stats = record.currStats;
		auto playerBase = cast<PlayerBase>(record.actor);
		auto@ modifiers = record.GetModifiers();


		AddHeader(".menu.player.mods.stats.attributes");

		string strExtra = "";
		string dexExtra = "";
		string intExtra = "";
		string focExtra = "";
		string vitExtra = "";

		if (record.playerClass !is null)
		{
			if (record.playerClass.str_spellpwr > 0)
				strExtra = "\\\"icn-splpwr\"+" + int(float(record.playerClass.str_spellpwr) * float(stats.Str) + 0.5f) + " ";
			if (record.playerClass.dex_spellpwr > 0)
				dexExtra = "\\\"icn-splpwr\"+" + int(float(record.playerClass.dex_spellpwr) * float(stats.Dex) + 0.5f) + " ";
			if (record.playerClass.int_spellpwr > 0)
				intExtra = "\\\"icn-splpwr\"+" + int(float(record.playerClass.int_spellpwr) * float(stats.Int) + 0.5f) + " ";
			if (record.playerClass.foc_spellpwr > 0)
				focExtra = "\\\"icn-splpwr\"+" + int(float(record.playerClass.foc_spellpwr) * float(stats.Foc) + 0.5f) + " ";
			if (record.playerClass.vit_spellpwr > 0)
				vitExtra = "\\\"icn-splpwr\"+" + int(float(record.playerClass.vit_spellpwr) * float(stats.Vit) + 0.5f) + " ";
		}


		//AddStat("strength", "str", stats.Str, " ("+strExtra+"\\\"icn-res-phys\"+" + int(float(stats.Str) * Tweak::ArmorPerStr + 0.5f) + ")");
		AddStat(Modifiers::ConvertableStat::Str, stats.Str, " ("+strExtra
			+"\\\"icn-res-phys\"+" + int(float(stats.Str) * Tweak::ArmorPerStr + 0.5f) + " "
			+"\\\"icn-respen-phys\"+" + StatsText::FloatStr(Tweak::GetStrBasedArmorPen(stats.Str) * 100.0f) + "%)"
		);
		
		AddStat(Modifiers::ConvertableStat::Dex, stats.Dex, " ("+dexExtra
			+"\\\"icn-crit-atkdmg\"+" + int(Tweak::GetDexBasedCritDamage(stats.Dex) * 100.0f + 0.5f) + "% "
			+"\\\"icn-crit-atkchance\"+" + StatsText::FloatStr(Tweak::GetDexBasedCritChance(stats.Dex) * 100.0f) + "%)"
		);
		
		AddStat(Modifiers::ConvertableStat::Int, stats.Int, " ("+intExtra
			+"\\\"icn-crit-spelldmg\"+" + int(Tweak::GetIntBasedCritDamage(stats.Int) * 100.0f + 0.5f) + "% "
			+"\\\"icn-crit-spellchance\"+" + StatsText::FloatStr(Tweak::GetIntBasedCritChance(stats.Int) * 100.0f) + "%)"
		);
		
		AddStat(Modifiers::ConvertableStat::Foc, stats.Foc, " ("+focExtra+"\\\"icn-mp\"+" + int(float(stats.Foc) * Tweak::ManaPerFoc) + " \\\"icn-mp-rgn\"+" + round(float(stats.Foc) * Tweak::ManaRegenPerFoc, 2) + ")");
		AddStat(Modifiers::ConvertableStat::Vit, stats.Vit, " ("+vitExtra+"\\\"icn-hp\"+" + int(float(stats.Vit) * Tweak::HealthPerVit) + " \\\"icn-hp-rgn\"+" + round(float(stats.Vit) * Tweak::HealthRegenPerVit, 2) + ")");

		AddSeparator();

		AddHeader(".menu.player.mods.stats.pools");
		AddStat(Modifiers::ConvertableStat::Health, record.CurrentHealth() + " / " + stats.Health);
		AddStat(Modifiers::ConvertableStat::HealthRegen, round(stats.HealthRegen, 2));
		AddStat(Modifiers::ConvertableStat::Mana, record.CurrentMana() + " / " + stats.Mana);
		AddStat(Modifiers::ConvertableStat::ManaRegen, round(stats.ManaRegen, 2));

		AddSeparator();

		AddHeader(".menu.player.mods.stats.protection");
		AddStat(Modifiers::ConvertableStat::Armor, stats.Armor, FormatDmgReduction(stats.Armor, "\\\"icn-dmg-phys\""));
		AddStat(Modifiers::ConvertableStat::ResistanceFire, stats.ResistanceFire, FormatDmgReduction(stats.ResistanceFire, "\\\"icn-dmg-fire\""));
		AddStat(Modifiers::ConvertableStat::ResistanceIce, stats.ResistanceIce, FormatDmgReduction(stats.ResistanceIce, "\\\"icn-dmg-ice\""));
		AddStat(Modifiers::ConvertableStat::ResistanceLightning, stats.ResistanceLightning, FormatDmgReduction(stats.ResistanceLightning, "\\\"icn-dmg-lightn\""));
		AddStat(Modifiers::ConvertableStat::ResistancePoison, stats.ResistancePoison, FormatDmgReduction(stats.ResistancePoison, "\\\"icn-dmg-poison\""));

		AddSeparator();

		AddHeader(".menu.player.mods.stats.utility");
		AddStat(Modifiers::ConvertableStat::MoveSpeed, StatsText::FloatStr(stats.MoveSpeed * 100.0f) + "%");
		AddStat(Modifiers::ConvertableStat::EvadeChance, StatsText::FloatStr(stats.EvadeChance * 100.0f) + "%");
		AddStat(Modifiers::ConvertableStat::ParryChance, StatsText::FloatStr(stats.ParryChance * 100.0f) + "%");
		AddStat(Modifiers::ConvertableStat::ExperienceMul, StatsText::FloatStr(stats.ExperienceMul * 100.0f) + "%");
		AddStat("scursegain", "", StatsText::FloatStr((record.ScaleShadowCurse(1.0f)) * 100.0f) + "%");
		AddStat(Modifiers::ConvertableStat::Thorns, stats.Thorns);
		// HWP: the Luck stat (core HWP::Luck, a custom stat): its own widget id so the lab
		// can read the row (gl menu mods - hwp-luck); AddStat clears the clone's id
		{
			auto luckRow = m_statsValueTemplate.Clone();
			luckRow.m_visible = true;
			luckRow.SetID("hwp-luck");
			auto luckIcon = cast<TextWidget>(luckRow.GetWidgetById("icon"));
			luckIcon.SetText("\\\"icn-luck\"");
			float luckVal = HWP::Luck::OfRecord(record);
			auto luckValue = cast<TextWidget>(luckIcon.GetWidgetById("value"));
			luckValue.SetText("" + int(luckVal + (luckVal < 0 ? -0.5f : 0.5f)) + " " + Resources::GetString(".stat.custom.hwpluck"));
			auto luckTip = WidgetTooltip();
			luckTip.m_tooltipTitle = Resources::GetString(".stat.custom.hwpluck");
			luckTip.m_tooltipText = HWP::Luck::TooltipText(luckVal);
			@luckRow.m_tooltip = luckTip;
			@luckValue.m_tooltip = luckTip;
			m_statsList.AddChild(luckRow);
		}
		//AddStat(Modifiers::ConvertableStat::BloodyBullionStat, StatsText::FloatStr(stats.BloodyBullionStat * 100.0f) + "%");

		AddSeparator();

		AddStat(Modifiers::ConvertableStat::Valor, record.valor);
		AddStat(Modifiers::ConvertableStat::Hunt, record.hunt);
		AddStat(Modifiers::ConvertableStat::Arcane, record.arcane);
		AddStat(Modifiers::ConvertableStat::Avarice, record.avarice);
		AddStat(Modifiers::ConvertableStat::Benevolence, record.benevolence);

		AddSeparator();

		AddStat(Modifiers::ConvertableStat::AttackPower, stats.AttackPower, " (" + (stats.AttackPower > 0 ? "+" : "") + round(((Tweak::DamagePowerDivisor + stats.AttackPower) / Tweak::DamagePowerDivisor - 1.0f) * 100.0f, 2) + "%)");
		AddStat(Modifiers::ConvertableStat::SpellPower, stats.SpellPower, " (" + (stats.SpellPower > 0 ? "+" : "") + round(((Tweak::DamagePowerDivisor + stats.SpellPower) / Tweak::DamagePowerDivisor - 1.0f) * 100.0f, 2) + "%)");
		AddStat(Modifiers::ConvertableStat::SummonDamageMul, StatsText::FloatStr(stats.SummonDamageMul * 100.0f) + "%");
		AddStat(Modifiers::ConvertableStat::SummonHealthMul, StatsText::FloatStr(stats.SummonHealthMul * 100.0f) + "%");

		AddSeparator();

		AddHeader(".menu.player.mods.stats.attack");

		AddStat(Modifiers::ConvertableStat::MainHandAttackSpeed, StatsText::FloatStr(stats.MainHand.AttackSpeed * 100.0f) + "%");
		AddStat(Modifiers::ConvertableStat::MainHandCritChance, StatsText::FloatStr(stats.MainHand.CritChance * 100.0f) + "%");
		AddStat(Modifiers::ConvertableStat::MainHandCritDamage, StatsText::FloatStr(stats.MainHand.CritDamage * 100.0f) + "%");

		AddStat("mainhanddamage", "mainhand", stats.MainHand.DamagePhysical + stats.MainHand.DamageFire + stats.MainHand.DamageIce + stats.MainHand.DamageLightning + stats.MainHand.DamagePoison + stats.MainHand.DamagePure);
		AddStat("offhanddamage", "offhand", stats.OffHand.DamagePhysical + stats.OffHand.DamageFire + stats.OffHand.DamageIce + stats.OffHand.DamageLightning + stats.OffHand.DamagePoison + stats.OffHand.DamagePure);


		AddSeparator();


		AddHeader(".menu.player.mods.stats.spell");
		AddStat(Modifiers::ConvertableStat::CastSpeed, StatsText::FloatStr(stats.CastSpeed * 100.0f) + "%");
		AddStat(Modifiers::ConvertableStat::SpellCritChance, StatsText::FloatStr(stats.SpellCritChance * 100.0f) + "%");
		AddStat(Modifiers::ConvertableStat::SpellCritDamage, StatsText::FloatStr(stats.SpellCritDamage * 100.0f) + "%");

		AddSeparator();

		if (stats.ArmorPenetration != 0 || stats.ResistanceFirePenetration != 0 || stats.ResistanceIcePenetration != 0 || stats.ResistanceLightningPenetration != 0 || stats.ResistancePoisonPenetration != 0)
		{
			AddHeader(".menu.player.mods.stats.penetration");
			
			if (stats.ArmorPenetration != 0)
				AddStat(Modifiers::ConvertableStat::ArmorPenetration, StatsText::FloatStr(stats.ArmorPenetration * 100.0f) + "%");
			if (stats.ResistanceFirePenetration != 0)
				AddStat(Modifiers::ConvertableStat::ResistanceFirePenetration, StatsText::FloatStr(stats.ResistanceFirePenetration * 100.0f) + "%");
			if (stats.ResistanceIcePenetration != 0)
				AddStat(Modifiers::ConvertableStat::ResistanceIcePenetration, StatsText::FloatStr(stats.ResistanceIcePenetration * 100.0f) + "%");
			if (stats.ResistanceLightningPenetration != 0)
				AddStat(Modifiers::ConvertableStat::ResistanceLightningPenetration, StatsText::FloatStr(stats.ResistanceLightningPenetration * 100.0f) + "%");
			if (stats.ResistancePoisonPenetration != 0)
				AddStat(Modifiers::ConvertableStat::ResistancePoisonPenetration, StatsText::FloatStr(stats.ResistancePoisonPenetration * 100.0f) + "%");
			
			AddSeparator();
		}
		
		AddHeader(".menu.player.mods.stats.multiplier");
		
		float dmgMul = stats.DamageMul;
		if (playerBase !is null)
			dmgMul *= playerBase.m_buffs.DamageMul();
		
		AddStat("damage", "", StatsText::FloatStr(dmgMul * 100.0f) + "%");
		
		if (stats.PhysicalDamageMul != 1.0f)
			AddStat(Modifiers::ConvertableStat::PhysicalDamageMul, StatsText::FloatStr(stats.PhysicalDamageMul * 100.0f) + "%");
		if (stats.FireDamageMul != 1.0f)
			AddStat(Modifiers::ConvertableStat::FireDamageMul, StatsText::FloatStr(stats.FireDamageMul * 100.0f) + "%");
		if (stats.IceDamageMul != 1.0f)
			AddStat(Modifiers::ConvertableStat::IceDamageMul, StatsText::FloatStr(stats.IceDamageMul * 100.0f) + "%");
		if (stats.LightningDamageMul != 1.0f)
			AddStat(Modifiers::ConvertableStat::LightningDamageMul, StatsText::FloatStr(stats.LightningDamageMul * 100.0f) + "%");
		if (stats.PoisonDamageMul != 1.0f)
			AddStat(Modifiers::ConvertableStat::PoisonDamageMul, StatsText::FloatStr(stats.PoisonDamageMul * 100.0f) + "%");
		if (stats.PureDamageMul != 1.0f)
			AddStat(Modifiers::ConvertableStat::PureDamageMul, StatsText::FloatStr(stats.PureDamageMul * 100.0f) + "%");
		
		
		float goldGain = record.GetMaterialModifier(MaterialType::Gold);
		float woodGain = record.GetMaterialModifier(MaterialType::Wood);
		float stonGain = record.GetMaterialModifier(MaterialType::Stone);
		float ironGain = record.GetMaterialModifier(MaterialType::Iron);
		float crysGain = record.GetMaterialModifier(MaterialType::Crystals);
		float dustGain = record.GetMaterialModifier(MaterialType::Dust);
		float oreGain =  record.GetMaterialModifier(MaterialType::Ore);
		
		if (goldGain != 1.0f || woodGain != 1.0f || stonGain != 1.0f || ironGain != 1.0f || crysGain != 1.0f || dustGain != 1.0f || oreGain != 1.0f)
		{
			AddSeparator();
			AddHeader(".menu.player.mods.stats.resources");
			
			if (goldGain != 1.0f)
				AddStat("goldgain", "gold", StatsText::FloatStr(goldGain * 100.0f) + "%");
			if (woodGain != 1.0f)
				AddStat("woodgain", "wood", StatsText::FloatStr(woodGain * 100.0f) + "%");
			if (stonGain != 1.0f)
				AddStat("stonegain", "stone", StatsText::FloatStr(stonGain * 100.0f) + "%");
			if (ironGain != 1.0f)
				AddStat("irongain", "iron", StatsText::FloatStr(ironGain * 100.0f) + "%");
			if (crysGain != 1.0f)
				AddStat("crysgain", "crys", StatsText::FloatStr(crysGain * 100.0f) + "%");
			if (dustGain != 1.0f)
				AddStat("dustgain", "dust", StatsText::FloatStr(dustGain * 100.0f) + "%");
			if (oreGain != 1.0f)
				AddStat("oregain", "ore", StatsText::FloatStr(oreGain * 100.0f) + "%");
		}
	}

	void AddHeader(const string &in title)
	{
		auto header = cast<TextWidget>(m_statsHeaderTemplate.Clone());
		header.m_visible = true;
		header.SetID("");
		header.SetText(Resources::GetString(title));

		m_statsList.AddChild(header);
	}



	void AddStat(Modifiers::ConvertableStat stat, const string &in val, const string &in extra = "")
	{
		auto widget = m_statsValueTemplate.Clone();
		widget.m_visible = true;
		widget.SetID("");
		
		string statStr = Modifiers::GetIconString(stat);
		
		auto statIcon = cast<TextWidget>(widget.GetWidgetById("icon"));
		if (Resources::HasString(".stat.icon." + statStr))
			statIcon.SetText(Resources::GetString(".stat.icon." + statStr));
		else
			statIcon.SetText("  ");
		
		auto value = cast<TextWidget>(statIcon.GetWidgetById("value"));
		value.SetText(val + " " + Resources::GetString(".stat.name." + statStr) + extra);
		
		auto tooltipMaker = StatBreakdownTooltip(stat);
		@widget.m_tooltip = tooltipMaker;
		@value.m_tooltip = tooltipMaker;
		
		m_statsList.AddChild(widget);
	}

	void AddStat(const string &in title, const string &in icon, const string &in val)
	{
		auto widget = m_statsValueTemplate.Clone();
		widget.m_visible = true;
		widget.SetID("");

		auto statIcon = cast<TextWidget>(widget.GetWidgetById("icon"));
		if (!icon.isEmpty())
			statIcon.SetText("\\\"icn-" + icon + "\"");
		else
			statIcon.SetText("  ");

		auto value = cast<TextWidget>(statIcon.GetWidgetById("value"));
		value.SetText(val + " " + Resources::GetString(".stat.custom." + title));

		m_statsList.AddChild(widget);
	}

	void AddSeparator()
	{
		auto separator = m_statsSeparatorTemplate.Clone();
		separator.m_visible = true;
		separator.SetID("");

		m_statsList.AddChild(separator);
	}

	bool ValidName(const string &in name)
	{
		if (name.isEmpty())
			return false;
		if (name == "title")
			return false;
		return true;
	}

	void RefreshEffectsGroup()
	{
		m_effectsList.ClearChildren();
/*
		for (uint i = 0; i < g_myTownRecord.m_heroTitles.length(); i++)
		{
			auto title = g_myTownRecord.m_heroTitles[i];
			if (title.m_title.m_name.isEmpty())
				continue;
			
			auto newEffect = m_effectsTemplate.Clone();
			newEffect.SetID("");
			newEffect.m_visible = true;
			
			cast<SpriteWidget>(newEffect.GetWidgetById("effect-icon")).SetSprite(title.m_title.m_icon);
			cast<TextWidget>(newEffect.GetWidgetById("effect-title")).SetText(title.m_title.m_name);
			cast<TextWidget>(newEffect.GetWidgetById("effect-description")).SetText(title.m_title.m_description);
			newEffect.m_height = max(newEffect.m_height, cast<TextWidget>(newEffect.GetWidgetById("effect-title")).m_height + cast<TextWidget>(newEffect.GetWidgetById("effect-description")).m_height);
			
			m_effectsList.AddChild(newEffect);
		}
*/
		auto record = GetLocalPlayerRecord();
		if (record is null)
			return;

		if (record.shadowCurses > 0)
		{
			auto newEffect = m_effectsTemplate.Clone();
			newEffect.SetID("");
			newEffect.m_visible = true;
			cast<SpriteWidget>(newEffect.GetWidgetById("effect-icon")).SetSprite(ScriptSprite(Resources::GetTexture2D("gui/hud.png"), vec4(168, 120, 24, 24)));
			cast<TextWidget>(newEffect.GetWidgetById("effect-title")).SetText(Resources::GetString(".menu.player.mods.effects.shadow_curse.name"));
			float remPerStack = float(Tweak::SCurseArmorPenalty) + g_ngp * Tweak::SCurseArmorNGPPenalty;
			cast<TextWidget>(newEffect.GetWidgetById("effect-description")).SetText(Resources::GetString(".menu.player.mods.effects.shadow_curse.desc", {
				{ "amnt-total", "" + int(float(record.shadowCurses) * remPerStack) }, 
				{ "amnt-stack", StatsText::FloatStr(remPerStack) }
			}));
			newEffect.m_height = max(newEffect.m_height, cast<TextWidget>(newEffect.GetWidgetById("effect-title")).m_height + cast<TextWidget>(newEffect.GetWidgetById("effect-description")).m_height);
			
			m_effectsList.AddChild(newEffect);
		}

		for (uint i = 0; i < record.missionBuffs.length(); i++)
		{
			if (!ValidName(record.missionBuffs[i].m_buff.m_name))
				continue;
			
			auto newEffect = m_effectsTemplate.Clone();
			newEffect.SetID("");
			newEffect.m_visible = true;
			cast<SpriteWidget>(newEffect.GetWidgetById("effect-icon")).SetSprite(record.missionBuffs[i].m_buff.m_icon);
			cast<TextWidget>(newEffect.GetWidgetById("effect-title")).SetText(record.missionBuffs[i].m_buff.m_name);
			cast<TextWidget>(newEffect.GetWidgetById("effect-description")).SetText(record.missionBuffs[i].m_buff.m_description);
			newEffect.m_height = max(newEffect.m_height, cast<TextWidget>(newEffect.GetWidgetById("effect-title")).m_height + cast<TextWidget>(newEffect.GetWidgetById("effect-description")).m_height);
			
			m_effectsList.AddChild(newEffect);
		}

		auto player = cast<PlayerBase>(record.actor);
		if (player !is null)
		{
			auto@ buffs = player.m_buffs.m_buffs;
			for (uint i = 0; i < buffs.length(); i++)
			{
				if (!ValidName(buffs[i].m_def.m_name))
					continue;
				
				auto newEffect = m_effectsTemplate.Clone();
				newEffect.SetID("");
				newEffect.m_visible = true;
				
				cast<SpriteWidget>(newEffect.GetWidgetById("effect-icon")).SetSprite(buffs[i].GetBuffIcon());
				cast<TextWidget>(newEffect.GetWidgetById("effect-title")).SetText(Resources::GetString(buffs[i].m_def.m_name));
				cast<TextWidget>(newEffect.GetWidgetById("effect-description")).SetText(Resources::GetString(buffs[i].m_def.m_description));
				newEffect.m_height = max(newEffect.m_height, cast<TextWidget>(newEffect.GetWidgetById("effect-title")).m_height + cast<TextWidget>(newEffect.GetWidgetById("effect-description")).m_height);
				
				m_effectsList.AddChild(newEffect);
			}

			auto@ stacks = player.m_buffs.m_stacks;
			for (uint i = 0; i < stacks.length(); i++)
			{
				auto stackDef = stacks[i].m_def;
				if (stackDef is null)
					continue;
				
				auto newEffect = m_effectsTemplate.Clone();
				newEffect.SetID("");
				newEffect.m_visible = true;
				
				if (ValidName(stackDef.m_name))
				{
					cast<TextWidget>(newEffect.GetWidgetById("effect-title")).SetText(Resources::GetString(stackDef.m_name));
					cast<TextWidget>(newEffect.GetWidgetById("effect-description")).SetText(Resources::GetString(stackDef.m_desc));
				}
				else if (stackDef.m_buffDef !is null)
				{
					if (ValidName(stackDef.m_buffDef.m_name))
					{
						cast<TextWidget>(newEffect.GetWidgetById("effect-title")).SetText(Resources::GetString(stackDef.m_buffDef.m_name));
						cast<TextWidget>(newEffect.GetWidgetById("effect-description")).SetText(Resources::GetString(stackDef.m_buffDef.m_description));
					}
					else
						continue;
				}
				
				cast<SpriteWidget>(newEffect.GetWidgetById("effect-icon")).SetSprite(stacks[i].GetBuffIcon());
				newEffect.m_height = max(newEffect.m_height, cast<TextWidget>(newEffect.GetWidgetById("effect-title")).m_height + cast<TextWidget>(newEffect.GetWidgetById("effect-description")).m_height);
				
				m_effectsList.AddChild(newEffect);
			}
		}
	}

	void ShowSkillInfo(uint id, Widget@ sender)
	{
		auto record = GetLocalPlayerRecord();
		if (record is null)
			return;

		array<Skills::Skill@>@ playerSkills;

		auto player = cast<PlayerBase>(record.actor);
		if (player !is null)
			@playerSkills = player.m_skills;
		else
			@playerSkills = PlayerHelper::GetDeadSkillList(record);

		Skills::Skill@ skill;
		for (uint i = 0; i < playerSkills.length(); i++)
		{
			if (playerSkills[i].m_skillId == id)
			{
				@skill = playerSkills[i];
				break;
			}
		}

		if (skill is null)
		{
			if (m_skillIcon !is null && m_skillIcon.m_skill is null && m_skillIcon.m_plrSkill is null && m_skillIcon.m_passiveSkill is null)
				m_skillIcon.m_visible = false;

			return;
		}

		m_skillIcon.m_visible = true;

		auto skillWidget = cast<SkillWidget>(sender);
		if (skillWidget !is null && skillWidget.m_item !is null && (skill.m_type == PlayerSkillType::MainHand || skill.m_type == PlayerSkillType::OffHand))
			m_skillIcon.SetSkill(skill, skillWidget.m_item);
		else
		{
			@m_skillIcon.m_item = null;
			m_skillIcon.SetSkill(skill);
		}

		m_skillTitle.SetText(Resources::GetString(skill.m_name));

		StringBuilder desc;

		Item::ItemSkillDef@ itemDef = Item::ItemSkillDef::Get(skill.m_skillId);
		if (itemDef !is null)
		{
			AppendTagsList(desc, itemDef.m_tags);
			desc.Append(Resources::GetString(itemDef.m_description));
		}
		else
		{
			auto skillDef = record.playerClass.GetSkillDef(skill.m_skillId);
			if (skillDef is null)
				return;
			
			AppendTagsList(desc, skillDef.m_tags);
			AppendSkillDesc(record, desc, skillDef);
			desc.Append("\n");
			
			for (uint i = 0; i < skillDef.m_modSkills.length(); i++)
			{
				if (record.GetSkillLevel(skillDef.m_modSkills[i]) <= 0)
					continue;
				
				desc.Append("\n\n\n\n");
				desc.Append(Resources::GetString(skillDef.m_modSkills[i].m_name));
				desc.Append("\n\n");
				AppendSkillDesc(record, desc, skillDef.m_modSkills[i]);
			}
		}

		m_skillDescription.SetText(desc.String());
		//m_skillGroup.RefreshAutoSize();
		//m_skillsScroll.Invalidate();
	}



	void Invalidate() override
	{
		AWindowObject::Invalidate();

		RefreshSkillGroup();
		RefreshStatsGroup();
		RefreshEffectsGroup();
	}

	void SetTab(uint i)
	{
		BaseGameMode@ gm = cast<BaseGameMode>(g_gameMode);
		if (gm !is null)
			gm.m_windowManager.CloseTooltip();

		m_statsList.ClearChildren();

		if (m_skillsGroup.m_idHash == i)
		{
			m_skillsGroup.m_visible = true;
			m_statsGroup.m_visible = false;
			m_effectsGroup.m_visible = false;
			m_checkBoxGroup.SetChecked("skills-content");
			m_title.SetText(m_skillsTitle);
			RefreshSkillGroup();
		}
		else if (m_statsGroup.m_idHash == i)
		{
			m_skillsGroup.m_visible = false;
			m_statsGroup.m_visible = true;
			m_effectsGroup.m_visible = false;
			m_checkBoxGroup.SetChecked("stats-content");
			m_title.SetText(m_statsTitle);
			RefreshStatsGroup();
		}
		else if (m_effectsGroup.m_idHash == i)
		{
			m_skillsGroup.m_visible = false;
			m_statsGroup.m_visible = false;
			m_effectsGroup.m_visible = true;
			m_checkBoxGroup.SetChecked("effects-content");
			m_title.SetText(m_effectsTitle);
			RefreshEffectsGroup();
		}

		m_input.RefreshInteractableWidgets(m_widget);
	}

	void StepTab(int i)
	{
		BaseGameMode@ gm = cast<BaseGameMode>(g_gameMode);
		if (gm !is null)
			gm.m_windowManager.CloseTooltip();

		m_checkBoxGroup.StepChecked(i > 0);
		SetTab(HashString(m_checkBoxGroup.GetChecked().GetValue()));
	}

	bool Update(int ms, GameInput& gameInput, MenuInput& menuInput) override
	{
		auto record = GetLocalPlayerRecord();

		if (record is null)
			return AWindowObject::Update(ms, gameInput, menuInput);

%if GAME
		if (menuInput.MenuPreviousSubTab.Pressed)
			StepTab(-1);
		if (menuInput.MenuNextSubTab.Pressed)
			StepTab(1);
%endif

		return AWindowObject::Update(ms, gameInput, menuInput);
	}

	void OnFunc(Widget@ sender, const string &in name) override
	{
		//print("Modifications::" + name);

		auto parse = name.split(" ");
		if (parse[0] == "set-tab")
			SetTab(HashString(parse[1]));
		else if (parse[0] == "next-tab")
			StepTab(1);
		else if (parse[0] == "prev-tab")
			StepTab(-1);
		else if (parse[0] == "show-skill")
			ShowSkillInfo(sender.m_idHash, sender);
		
		else if (parse[0] == "tooltip")
			sender.ShowTooltip();
		else if (parse[0] == "untooltip")
		{
			BaseGameMode@ gm = cast<BaseGameMode>(g_gameMode);
			if (gm !is null)
				gm.m_windowManager.CloseTooltip();
		}
	}
}


class StatBreakdownTooltip : WidgetTooltip
{
	Modifiers::ConvertableStat m_stat;

	StatBreakdownTooltip(Modifiers::ConvertableStat stat)
	{
		m_stat = stat;
	}

	ITooltip@ MakeTooltip() override
	{
		if (m_builtTooltip !is null)
			return m_builtTooltip;

		return CreateStatBreakdownTooltip(m_stat);
	}
}

interface IModifierProvider
{
	string GetModifierProviderName();
}

class ModifierProvider : IModifierProvider
{
	string m_name;
	ModifierProvider(const string &in name) { m_name = name; }
	string GetModifierProviderName() { return m_name; }
}


double AddBreakdownTooltipStep(array<ScalableBlocks::Block@>@ blocks, IModifierProvider@ modProv, double lastValue, double currValue, Modifiers::ConvertableStat stat, const string &in append = "")
{
	double diff = currValue - lastValue;
	if (abs(diff) < 0.0001f)
		return currValue;
	
	vec4 col = vec4(0);
	vec2 offset = vec2(0, 0);
	vec2 padding = vec2(8, 2);
	
	string text;
	if (modProv !is null)
		text = modProv.GetModifierProviderName() + ": ";
	else
		text = "???: ";
	
	if (diff > 0)
		text += "+";
	
	switch(Modifiers::GetStatFormatting(stat))
	{
	case Modifiers::StatFormatting::Integer: text += int64(diff + 0.001f); break;
	case Modifiers::StatFormatting::Float: text += StatsText::FloatStr(diff); break;
	case Modifiers::StatFormatting::Percentage: text += StatsText::FloatStr(diff * 100.0f) + "%"; break;
	}
	
	blocks.insertLast(ScalableBlocks::TextBlock(text + append, col, vec2(0, 0), offset, padding));
	return currValue;
}

ToolTip@ CreateStatBreakdownTooltip(Modifiers::ConvertableStat stat)
{
	array<ScalableBlocks::Block@> blocks;
	auto iconFrame = ScriptSprite(Resources::GetTexture2D("gui/gui.png"), vec4(76, 210, 28, 28));

	auto sepLeft = ScriptSprite(Resources::GetTexture2D("gui/gui.png"), vec4(124, 417, 9, 1));
	auto sepMid = ScriptSprite(Resources::GetTexture2D("gui/gui.png"), vec4(133, 417, 1, 1));
	auto sepRight = ScriptSprite(Resources::GetTexture2D("gui/gui.png"), vec4(124, 418, 9, 1));

	vec4 col = vec4(0);
	vec2 offset = vec2(0, 0);
	vec2 padding = vec2(8, 2);

	blocks.insertLast(ScalableBlocks::PaddingBlock(10));

/*
	// Title
	blocks.insertLast(ScalableBlocks::TitleBlock("\\c" + Item::QualityColorString(item.GetQuality()) + item.GetName(), "", 
		Item::QualityColor(item.GetQuality()), 
		item.GetIcon(), iconFrame, GetQualitySprite(item.GetQuality()), offset, padding + vec2(0, 8), -11, TextAlignment::Center));
*/

	auto player = GetLocalPlayerRecord();

	string iconStr = Modifiers::GetIconString(stat);
	string titleStr;
	
	if (Resources::HasString(".stat.icon." +  iconStr))
		titleStr = Resources::GetString(".stat.icon." +  iconStr) + " ";
	
	auto val = Modifiers::GetValue(player, player.currStats, stat);
	titleStr += Resources::GetString(".stat.name." +  iconStr) + ": ";
	
	switch(Modifiers::GetStatFormatting(stat))
	{
	case Modifiers::StatFormatting::Integer: titleStr += int64(val + 0.001f); break;
	case Modifiers::StatFormatting::Float: titleStr += val; break;
	case Modifiers::StatFormatting::Percentage: titleStr += val * 100.0f + "%"; break;
	}
	
	blocks.insertLast(ScalableBlocks::TextBlock(titleStr, col, vec2(0, 0), offset, padding));
	// Separator
	blocks.insertLast(ScalableBlocks::SeparatorBlock(sepLeft, sepMid, sepRight, padding));

	PlayerStats stats;
	auto@ mods = player.modifiers;
	
	stats.Clear();
	
	
	double value = 0.0f;
	
	int lvl = player.level - 1;
	auto playerClass = player.playerClass;
	if (playerClass !is null)
	{
		stats.Str = playerClass.base_str + lvl * playerClass.level_str;
		stats.Dex = playerClass.base_dex + lvl * playerClass.level_dex;
		stats.Int = playerClass.base_int + lvl * playerClass.level_int;
		stats.Foc = playerClass.base_foc + lvl * playerClass.level_foc;
		stats.Vit = playerClass.base_vit + lvl * playerClass.level_vit;
		
		value = AddBreakdownTooltipStep(blocks, ModifierProvider(Resources::GetString(".menu.player.mods.stats.source.base")), value, Modifiers::GetValue(player, stats, stat), stat);
		
		stats.Str += player.pickedStr;
		stats.Dex += player.pickedDex;
		stats.Int += player.pickedInt;
		stats.Foc += player.pickedFoc;
		stats.Vit += player.pickedVit;
		
		value = AddBreakdownTooltipStep(blocks, ModifierProvider(Resources::GetString(".menu.player.mods.stats.source.picked")), value, Modifiers::GetValue(player, stats, stat), stat);
		
		stats.Str += player.elixirStr;
		stats.Dex += player.elixirDex;
		stats.Int += player.elixirInt;
		stats.Foc += player.elixirFoc;
		stats.Vit += player.elixirVit;
		
		value = AddBreakdownTooltipStep(blocks, ModifierProvider(Resources::GetString(".menu.player.mods.stats.source.elixir")), value, Modifiers::GetValue(player, stats, stat), stat);
		//Resources::GetString(".menu.player.mods.stats.source.elixir.append", {{"max", GetMaximumElixirAmount(player)}}));
		
		stats.Str += player.ngp * Tweak::AttributesPerNGP;
		stats.Dex += player.ngp * Tweak::AttributesPerNGP;
		stats.Int += player.ngp * Tweak::AttributesPerNGP;
		stats.Foc += player.ngp * Tweak::AttributesPerNGP;
		stats.Vit += player.ngp * Tweak::AttributesPerNGP;
		
		value = AddBreakdownTooltipStep(blocks, ModifierProvider(Resources::GetString(".menu.player.mods.stats.source.ngp", {{"num", int(player.ngp)}})), value, Modifiers::GetValue(player, stats, stat), stat);
	}
	else
		stats.Str = stats.Dex = stats.Int = stats.Foc = stats.Vit = 1;

	stats.Str += player.townStr;
	stats.Dex += player.townDex;
	stats.Int += player.townInt;
	stats.Foc += player.townFoc;
	stats.Vit += player.townVit;
	
	value = AddBreakdownTooltipStep(blocks, ModifierProvider(Resources::GetString(".menu.player.mods.stats.source.accomplishments")), value, Modifiers::GetValue(player, stats, stat), stat);
	
	stats.MaxDashes = 1;
	stats.DashRechargeMul = 1.0f;
	
	stats.PotionCharges = 0;
	stats.PotionHeal = Tweak::BasePotionHeal;
	stats.PotionMana = Tweak::BasePotionMana;
	
	stats.LightRadius = 0;

	stats.EvadeChance = stats.ParryChance = 0;
	stats.ParryArc = PI;
	stats.Thorns = 0;
	stats.BloodyBullionStat = 0.0f;

	stats.MoveSpeed = stats.OffHand.AttackSpeed = stats.MainHand.AttackSpeed = stats.CastSpeed = stats.ExperienceMul = stats.TargetedRangeMul = 1.0f;
	stats.PureDamageMul = stats.PhysicalDamageMul = stats.IceDamageMul = stats.LightningDamageMul = stats.PoisonDamageMul = stats.FireDamageMul = 1.0f;
	stats.DamageMul = 1.0f;
	stats.OffHand.CritDamage = stats.MainHand.CritDamage = Tweak::BaseWeaponCritDamage;
	stats.SpellCritDamage = Tweak::BaseSpellCritDamage;
	stats.Health = stats.Mana = 0;
	stats.Armor = stats.ResistanceFire = stats.ResistanceIce = stats.ResistanceLightning = stats.ResistancePoison = 0;
	stats.HealthRegen = stats.ManaRegen = 0;
	stats.HealthGain = stats.ManaGain = 1.0f;
	stats.SummonDamageMul = 1.0f;
	stats.SummonHealthMul = 1.0f;
	
	value = AddBreakdownTooltipStep(blocks, ModifierProvider(Resources::GetString(".menu.player.mods.stats.source.base")), value, Modifiers::GetValue(player, stats, stat), stat);
	
	bool attribsDone = false;
	for (uint i = 0; i < mods.m_statModifiers.length(); i++)
	{
		auto statMod = mods.m_statModifiers[i].m_statMod;
		if (!CheckConditionals(statMod.m_conditionals, player.actor)) 
			continue;
		
		if (!attribsDone && statMod.Ordering >= int(Modifiers::ModifierOrdering::ArmorAdd))
		{
			attribsDone = true;
			mods.CalcAttributes(player, stats, false);
			value = AddBreakdownTooltipStep(blocks, ModifierProvider(Resources::GetString(".menu.player.mods.stats.source.attributes")), value, Modifiers::GetValue(player, stats, stat), stat);
		}
		
		statMod.Modify(player, stats, mods.m_statModifiers[i].m_intensity);
		value = AddBreakdownTooltipStep(blocks, mods.m_statModifiers[i].m_provider, value, Modifiers::GetValue(player, stats, stat), stat);
	}
	
	if (!attribsDone)
	{
		mods.CalcAttributes(player, stats, false);
		value = AddBreakdownTooltipStep(blocks, ModifierProvider(Resources::GetString(".menu.player.mods.stats.source.attributes")), value, Modifiers::GetValue(player, stats, stat), stat);
	}
	
	{
		int armorPenalty = int(g_ngp * float(Tweak::NGPArmorPenalty) + 0.5f);
		int resPenalty = int(g_ngp * float(Tweak::NGPResistancePenalty) + 0.5f);
		
		stats.Armor -= armorPenalty;
		stats.ResistanceFire -= resPenalty;
		stats.ResistanceIce -= resPenalty;
		stats.ResistanceLightning -= resPenalty;
		stats.ResistancePoison -= resPenalty;
		value = AddBreakdownTooltipStep(blocks, ModifierProvider(Resources::GetString(".menu.player.mods.stats.source.ngp", {{"num", int(g_ngp + 0.5f)}})), value, Modifiers::GetValue(player, stats, stat), stat);
	}
	
	{
		int armorPenalty = int(float(player.shadowCurses) * float(Tweak::SCurseArmorPenalty + g_ngp * Tweak::SCurseArmorNGPPenalty) + 0.5f);
		stats.Armor -= armorPenalty;
		stats.ResistanceFire -= armorPenalty;
		stats.ResistanceIce -= armorPenalty;
		stats.ResistanceLightning -= armorPenalty;
		stats.ResistancePoison -= armorPenalty;
		value = AddBreakdownTooltipStep(blocks, ModifierProvider(Resources::GetString(".menu.player.mods.stats.source.shadow_curse", {{"num", int(player.shadowCurses)}})), value, Modifiers::GetValue(player, stats, stat), stat);
	}
	
	
	stats.Health = max(1, int(float(stats.Health) * (1.0f - player.lockedHp) + 0.5f));
	
	value = AddBreakdownTooltipStep(blocks, ModifierProvider(Resources::GetString(".menu.player.mods.stats.source.locked")), value, Modifiers::GetValue(player, stats, stat), stat);
	
	stats.Finalize();
	stats.Cleanup();
	
	if (blocks.length() == 0)
		return null;
	
	blocks[blocks.length() - 1].m_heightAdd = 4;
	
	auto tt = ToolTip(Resources::GetSValue("gui/variable/itemtooltip_common.sval"));
	tt.Initialize(blocks, 160);
	
	return tt;
}

void AppendTagsList(StringBuilder@ desc, uint64 tags)
{
	string skillTags = "";
	for (uint i = 0; i < g_skillTags.m_tags.length(); i++)
	{
		if ((tags & (1 << (i + 1))) == 0)
			continue;
		
		auto str = ".skill.tag." + g_skillTags.m_tags[i];
		if (!Resources::HasString(str))
			continue;
		
		if (!skillTags.isEmpty())
			skillTags += ", ";
		
		skillTags += Resources::GetString(str);
	}
	
	if (!skillTags.isEmpty())
	{
		desc.Append(skillTags);
		desc.Append("\n\n");
	}
}

void AppendSkillDesc(PlayerRecord@ record, StringBuilder@ desc, PlayerSkillDef@ skillDef, int lvlOverride = -1)
{
	StringBuilder paramsStr;
	if (skillDef.m_descParams.length() > 0)
		paramsStr.Append("\n");
	
	dictionary descParams;
	int lvl = record !is null ? record.GetSkillLevel(skillDef) : 0;
	if (lvlOverride >= 0)
		lvl = lvlOverride;
	
	for (uint s = 0; s < skillDef.m_descParams.length(); s++)
	{
		auto@ dp = skillDef.m_descParams[s];
		paramsStr.Append("\n");
		paramsStr.Append(dp.m_levels[0]);
		paramsStr.Append(" ");
		
		int numDPLvls = dp.m_levels.length();
		int cl = min(lvl, numDPLvls -1);
		for (int i = 1; i < numDPLvls; i++)
		{
			if (i != 1)
				paramsStr.Append(Tweak::Book_SkillLevelDelim);
			
			if (i == cl)
				paramsStr.Append(Tweak::Book_SkillLevelCurrColor);
			else
				paramsStr.Append(Tweak::Book_SkillLevelColor);
			
			paramsStr.Append(Resources::GetString(dp.m_levels[i]));
			paramsStr.Append("\\d");
		}
		
		StringBuilder sb;
		sb.Append(Tweak::Book_SkillLevelCurrColor);
		sb.Append(Resources::GetString(dp.m_levels[min(max(1, lvl), numDPLvls -1)]));
		sb.Append("\\d");
		
		descParams.set(dp.m_name, sb.String());
	}
	
	PlayerBase@ player = record !is null ? cast<PlayerBase>(record.actor) : null;
	if (player is null)
	{
		// HWP (core): no player actor yet (the create-character window from the main menu),
		// so fill the %param% tokens of the description from the level 1 values the way the
		// in-game branch below does; vanilla descriptions carry no tokens and are unchanged.
		desc.Append(Resources::GetString(skillDef.m_description, g_bookColors, descParams));
		desc.Append(Resources::GetString(paramsStr.String()));
	}
	else
	{
		player.PrepareSkillFetchData(skillDef.m_idHash);
		
		desc.Append(Resources::GetString(player.m_unit, skillDef.m_description, g_bookColors, descParams));
		desc.Append(Resources::GetString(player.m_unit, paramsStr.String()));
	}
}
