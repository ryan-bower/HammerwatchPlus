// Free skills after a respec (issue #78): a respec at the Skill Trainer unlearns the skills a
// class starts with (their "starting-level": the vanilla first skill and passive, the HWP
// classes' and specializations' starting skills, the Firearms ranks), and the trainer sells
// those levels back for 0 skill points.
//
// Vanilla's "respec-skills yes" (ShopContent/WindowSkillTrainer.as) clears pickedSkills, and
// PlayerRecord.GetSkillLevel is the pick + m_startingLevel, so a starting skill stays learned
// and the player can't drop it to spend the points elsewhere. The class swap (module.json)
// points the trainer unit at HWPSkillTrainerContent, whose window runs the vanilla respec and
// then saves each starting skill's pick as -m_startingLevel: level 0, not learned. The points
// spent (GetSkillPointsSpentOnSkills) only count levels from m_startingLevel up, so a negative
// pick counts 0 and buying it back (pick -1 -> 0) costs nothing: Buy does that level up itself
// (SkillUp would check m_levelSkillCost[0] against the free points) and the trainer shows 0 on
// it. The save keeps the negative pick; PlayerRecord.Load clamps it to 0, so the
// PlayerRecordLoad hook puts it back. With the mod removed the skill is learned again, as
// vanilla has it. The respec now also tells the other players (PlayerResetPickedSkills and
// one PlayerSyncSkillLevel per skill); vanilla's never did.
//
// `hwp freeskills` lists the starting skills (saved pick / level) and the skill points.
namespace HWP
{
	namespace FreeSkills
	{
		bool g_enabled = true;

		void RefreshSettings()
		{
			g_enabled = HWP::Settings::GetBool("freeskills.enabled", true);
		}

		void OnSettingChanged(const string &in key)
		{
			if (key.findFirst("freeskills.") == 0)
				RefreshSettings();
		}

		// a skill the class starts with: the trainer lists it (not the dash) and it has levels free
		bool Starting(PlayerSkillDef@ def)
		{
			return def !is null && def.m_type != PlayerSkillType::Dash && def.m_startingLevel > 0;
		}

		int Pick(PlayerRecord@ rec, const string &in id)
		{
			int lvl = 0;
			if (!rec.pickedSkills.get(id, lvl))
				lvl = 0;
			return lvl;
		}

		// the levels of this skill still free to learn (a negative pick), else 0
		int FreeLeft(PlayerRecord@ rec, PlayerSkillDef@ def)
		{
			if (!Starting(def))
				return 0;
			return max(0, -Pick(rec, def.m_id));
		}

		void Changed(PlayerRecord@ rec)
		{
			rec.SyncStatPoints();
			rec.SyncTownStatPoints();
			if (rec.actor !is null)
				cast<PlayerBase>(rec.actor).LoadSkills();
			rec.RefreshModifiers();
		}

		// after the vanilla respec: each starting skill to level 0 (pick -m_startingLevel)
		void Unlearn(PlayerRecord@ rec)
		{
			(Network::Message("PlayerResetPickedSkills")).SendToAll();
			string ids;
			int n = 0;
			auto@ defs = rec.playerClass.m_skillDefs;
			for (uint i = 0; i < defs.length(); i++)
			{
				if (!Starting(defs[i]))
					continue;
				int pick = -defs[i].m_startingLevel;
				rec.pickedSkills.set(defs[i].m_id, pick);
				(Network::Message("PlayerSyncSkillLevel") << defs[i].m_idHash << pick << false).SendToAll();
				ids += (n++ == 0 ? "" : ", ") + defs[i].m_id + " (" + pick + ")";
			}
			Changed(rec);
			HWP::Log("freeskills", "respec: " + n + " starting skill(s) unlearned: " + ids + "; "
				+ rec.GetFreeSkillPoints() + " point(s) free");
		}

		// a level of a starting skill bought back: free, the pick one up
		bool BuyFree(PlayerRecord@ rec, const string &in id)
		{
			auto def = rec.playerClass.GetSkillDef(HashString(id));
			if (FreeLeft(rec, def) <= 0)
				return false;
			int pick = Pick(rec, id) + 1;
			rec.pickedSkills.set(id, pick);
			(Network::Message("PlayerSyncSkillLevel") << def.m_idHash << pick << false).SendToAll();
			Changed(rec);
			HWP::Log("freeskills", "learned " + id + " level " + rec.GetSkillLevel(def) + " for free, "
				+ rec.GetFreeSkillPoints() + " point(s) free");
			return true;
		}

		// the trainer draws each level's cost from m_levelSkillCost (PickSkillWidget.GetSkillCost):
		// the free levels read 0 while it draws, then the costs go back
		array<PlayerSkillDef@> g_zeroDefs;
		array<int> g_zeroAt;
		array<int> g_zeroWas;

		void ZeroFreeCosts(PlayerRecord@ rec)
		{
			auto@ defs = rec.playerClass.m_skillDefs;
			for (uint i = 0; i < defs.length(); i++)
			{
				int left = FreeLeft(rec, defs[i]);
				int lvl = rec.GetSkillLevel(defs[i]);
				for (int j = lvl; j < lvl + left && j < int(defs[i].m_levelSkillCost.length()); j++)
				{
					g_zeroDefs.insertLast(defs[i]);
					g_zeroAt.insertLast(j);
					g_zeroWas.insertLast(defs[i].m_levelSkillCost[j]);
					defs[i].m_levelSkillCost[j] = 0;
				}
			}
		}

		void RestoreCosts()
		{
			for (uint i = 0; i < g_zeroDefs.length(); i++)
				g_zeroDefs[i].m_levelSkillCost[g_zeroAt[i]] = g_zeroWas[i];
			g_zeroDefs.removeRange(0, g_zeroDefs.length());
			g_zeroAt.removeRange(0, g_zeroAt.length());
			g_zeroWas.removeRange(0, g_zeroWas.length());
		}

		string Status(PlayerRecord@ rec)
		{
			string line = "free skills " + (g_enabled ? "on" : "off") + ";";
			auto@ defs = rec.playerClass.m_skillDefs;
			int n = 0;
			for (uint i = 0; i < defs.length(); i++)
			{
				if (!Starting(defs[i]))
					continue;
				line += (n++ == 0 ? " " : ", ") + defs[i].m_id + " " + Pick(rec, defs[i].m_id) + "/" + rec.GetSkillLevel(defs[i]);
			}
			return line + "; " + rec.GetFreeSkillPoints() + " point(s) free, " + rec.GetSkillPointsSpentOnSkills() + " spent";
		}

		void CmdFreeSkills(array<string>@ args)
		{
			auto rec = GetLocalPlayerRecord();
			string line = "free skills: no player";
			if (rec !is null && rec.playerClass !is null)
				line = Status(rec);
			HWP::Log("freeskills", line);
			HWP::Commands::Reply(line);
		}
	}
}

namespace HWPFreeSkills
{
	// PlayerRecord.Load clamps a saved pick to 0..levels: put the negative ones back
	[Hook]
	void PlayerRecordLoad(PlayerRecord@ record, SValue@ data)
	{
		if (record is null || record.playerClass is null || data is null)
			return;
		auto picked = data.GetDictionaryEntry("picked-skills");
		if (picked is null)
			return;
		auto keys = picked.GetDictionary().getKeys();
		for (uint i = 0; i < keys.length(); i++)
		{
			int lvl = HWP::SV::Int(picked, keys[i], 0);
			auto def = record.playerClass.GetSkillDef(HashString(keys[i]));
			if (lvl < 0 && HWP::FreeSkills::Starting(def) && def.m_startingLevel + lvl >= 0)
				record.pickedSkills.set(keys[i], lvl);
		}
	}
}

class HWPSkillTrainerContent : SkillTrainerContent
{
	HWPSkillTrainerContent(UnitPtr u, SValue& params)
	{
		super(u, params);
	}

	AWindowObject@ MakeShopWindow(GUIBuilder@ guiBuilder) override
	{
		@m_window = HWPSkillTrainerWindow(guiBuilder, this);
		return m_window;
	}

	bool Buy(const string &in func, uint hash, IShopItem@ item) override
	{
		auto it = cast<SkillTrainerContentItem>(item);
		if (func == "buy" && it !is null && HWP::FreeSkills::BuyFree(m_player, it.m_item.m_id))
			return true;
		return SkillTrainerContent::Buy(func, hash, item);
	}

	// a free level: cost 0, buyable with no points left
	array<IShopItem@> GetItems() override
	{
		auto items = SkillTrainerContent::GetItems();
		for (uint i = 0; i < items.length(); i++)
		{
			auto it = cast<SkillTrainerContentItem>(items[i]);
			if (it is null || it.m_owned)
				continue;
			auto def = m_player.playerClass.GetSkillDef(HashString(it.m_item.m_id));
			if (HWP::FreeSkills::FreeLeft(m_player, def) <= 0 || it.m_lvl != m_player.GetSkillLevel(def))
				continue;
			it.m_skillCost = 0;
			it.m_buyable = true;
			HWP::Log("freeskills", "trainer: " + it.m_item.m_id + " level " + (it.m_lvl + 1) + " free");
		}
		return items;
	}
}

class HWPSkillTrainerWindow : WindowSkillTrainer
{
	HWPSkillTrainerWindow(GUIBuilder@ b, AShopContent@ content)
	{
		super(b, content);
	}

	PlayerRecord@ Player()
	{
		if (m_shopContent is null)
			return null;
		return m_shopContent.m_player;
	}

	void Draw(SpriteBatch& sb, int idt) override
	{
		auto rec = Player();
		if (rec !is null)
			HWP::FreeSkills::ZeroFreeCosts(rec);
		WindowSkillTrainer::Draw(sb, idt);
		HWP::FreeSkills::RestoreCosts();
	}

	void OnFunc(Widget@ sender, const string &in name) override
	{
		auto rec = Player();
		WindowSkillTrainer::OnFunc(sender, name);
		// the vanilla respec ran when it cleared the picks (it does nothing it can't afford)
		if (name == "respec-skills yes" && rec !is null && HWP::FreeSkills::g_enabled && rec.pickedSkills.isEmpty())
		{
			HWP::FreeSkills::Unlearn(rec);
			Refresh();
		}
	}
}

namespace Modules
{
	class HWPFreeSkillsModule : Module, HWP::ModuleStart
	{
		HWPFreeSkillsModule()
		{
			super("hwp-freeskills");
			HWP::Commands::OnSettingChanged(HWP::Commands::SettingListener(HWP::FreeSkills::OnSettingChanged));
			HWP::Commands::Register("freeskills", " free skills after a respec: the class's starting skills (saved pick/level) and the skill points", HWP::Commands::Handler(HWP::FreeSkills::CmdFreeSkills));
			HWP::FreeSkills::RefreshSettings();
			HWP::Log("freeskills", "self-check done: " + (HWP::FreeSkills::g_enabled ? "on" : "off"));
		}

		void Start(StartMode sMode)
		{
			HWP::FreeSkills::RefreshSettings();
		}
	}
}
