// Native sphere acquisition/window observation. Query never changes picks,
// eligibility, RNG, skill levels or the sphere. "pick" invokes the same actual
// open window callback as a native click, after validating current eligibility.
// Rendered title/description/layout proof still requires actual screenshots.
namespace GameLab
{
	const uint QA_SPHERE_ELIGIBLE_CAP = 128;

	GiveSkillSphereMenu@ QASphereMenu()
	{
		auto gm = cast<BaseGameMode>(g_gameMode);
		if (gm is null || gm.m_windowManager is null)
			return null;
		return cast<GiveSkillSphereMenu>(gm.m_windowManager.GetCurrentWindow());
	}

	string QASphereOffer(PlayerRecord@ rec, PlayerSkillDef@ def, Widget@ widget,
		array<PlayerSkillDef@>@ eligible)
	{
		Json row;
		row.Bool("present", def !is null);
		if (def is null)
			return row.Close();
		int level = rec.GetSkillLevel(def);
		int index = min(level, int(def.m_levelQualities.length()) - 1);
		row.Str("id", def.m_id).Int("level", level).Int("next_level", level + 1)
			.Str("parent", def.m_parentSkill is null ? "" : def.m_parentSkill.m_id)
			.Bool("eligible", eligible.findByRef(def) >= 0)
			.Str("name_key", def.m_name).Str("description_key", def.m_description)
			.Str("localized_name", Resources::GetString(def.m_name))
			.Int("quality", index < 0 ? -1 : int(def.m_levelQualities[index]))
			.Bool("icon", def.m_icon !is null)
			.Bool("widget_present", widget !is null)
			.Bool("widget_visible", widget !is null && widget.m_visible);
		if (widget !is null)
		{
			auto title = cast<TextWidget>(widget.GetWidgetById("name"));
			auto description = cast<TextWidget>(widget.GetWidgetById("desc"));
			row.Bool("name_widget", title !is null).Bool("description_widget", description !is null);
			// Same actual TextWidget.m_str read as existing Probe.WidgetNodes.
			if (title !is null)
				row.Str("rendered_name", title.m_str).Int("name_w", title.m_width).Int("name_h", title.m_height);
			if (description !is null)
				row.Str("rendered_description", description.m_str).Int("desc_w", description.m_width).Int("desc_h", description.m_height);
		}
		return row.Close();
	}

	void VerbQASphere(const string &in id, array<string>@ args)
	{
		auto rec = GetLocalPlayerRecord();
		if (rec is null || rec.playerClass is null)
		{
			Fail(id, "no local native player class");
			return;
		}
		auto eligible = GetAllSkillSpheres(rec); // Native req/blocker/parent/max rules.
		auto menu = QASphereMenu();
		if (args.length() > 0)
		{
			if (args.length() != 2 || args[0] != "pick")
			{
				Fail(id, "usage: sphereui [pick <1..3>]");
				return;
			}
			int index = int(parseInt(args[1]));
			if (menu is null || menu.m_skillSphereItem is null || menu.m_skillSphereItem.m_used
				|| index < 1 || index > 3)
			{
				Fail(id, "requires an unused actual open sphere and one of its three choices");
				return;
			}
			PlayerSkillDef@ selected = index == 1 ? menu.m_skill1 : index == 2 ? menu.m_skill2 : menu.m_skill3;
			if (selected is null || eligible.findByRef(selected) < 0)
			{
				Fail(id, "actual offered choice is not currently native eligible");
				return;
			}
			auto sphere = menu.m_skillSphereItem;
			int before = rec.GetSkillLevel(selected);
			// GiveSkillSphereMenu.OnFunc calls PickedSkill before SkillTempUp and
			// closes the real window; never call either operation independently.
			menu.OnFunc(menu.m_widget.GetWidgetById("perk" + index), "pick " + index);
			Emit(Reply(id, true).Str("selected", selected.m_id).Int("choice", index)
				.Int("level0", before).Int("level", rec.GetSkillLevel(selected))
				.Bool("consumed", sphere.m_used).Bool("window_closed", QASphereMenu() is null));
			return;
		}
		array<string> possible;
		for (uint i = 0; i < eligible.length() && i < QA_SPHERE_ELIGIBLE_CAP; i++)
			possible.insertLast(eligible[i].m_id);
		auto reply = Reply(id, true).Bool("open", menu !is null).Str("class", rec.playerClass.m_id)
			.Int("possible_count", eligible.length()).Int("possible_truncated", eligible.length() > QA_SPHERE_ELIGIBLE_CAP ? eligible.length() - QA_SPHERE_ELIGIBLE_CAP : 0)
			.Raw("possible", StrArray(possible));
		if (menu !is null)
		{
			array<string> offers;
			offers.insertLast(QASphereOffer(rec, menu.m_skill1, menu.m_widget.GetWidgetById("perk1"), eligible));
			offers.insertLast(QASphereOffer(rec, menu.m_skill2, menu.m_widget.GetWidgetById("perk2"), eligible));
			offers.insertLast(QASphereOffer(rec, menu.m_skill3, menu.m_widget.GetWidgetById("perk3"), eligible));
			if (menu.m_skillSphereItem !is null)
				reply.Int("sphere_unit_id", menu.m_skillSphereItem.GetUseUnit().GetId())
					.Str("sphere_unit", menu.m_skillSphereItem.GetUseUnit().GetDebugName());
			reply.Raw("offers", RawArray(offers)).Bool("sphere_present", menu.m_skillSphereItem !is null)
				.Bool("sphere_used", menu.m_skillSphereItem !is null && menu.m_skillSphereItem.m_used);
		}
		Json qualities;
		qualities.Int("common", int(Item::Quality::Common)).Int("uncommon", int(Item::Quality::Uncommon))
			.Int("rare", int(Item::Quality::Rare)).Int("epic", int(Item::Quality::Epic));
		reply.Raw("quality_values", qualities.Close());
		Emit(reply);
	}

	void Register_qa_spheres()
	{
		RegisterVerb("sphereui", "[pick <1..3>]", Verb(VerbQASphere));
	}
}
