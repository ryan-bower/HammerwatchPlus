// HoH1 classes. Everything about them is data (players/hwp/<class>/,
// tweak/hwp/*_classes.sval); this module self-checks the loaders and answers
// hwp classes.
namespace HWP
{
	namespace Classes
	{
		const array<string> IDS = { "hwp_thief", "hwp_gladiator", "hwp_witch_hunter" };
		const array<string> UNITS = {
			"players/hwp/witchhunter/units/pyre.unit",
			"players/rogue/projectiles/rog_throwing_knife.unit",
			"players/warrior/projectiles/whirling_axe_right.unit",
			"players/ranger/units/wolf.unit",
			"players/priest/units/crusader_pikeman.unit" };
		bool g_checked = false;
		bool g_itemsChecked = false;

		// Parked for later (2026-10-21, the owner): not offered at character creation
		// whatever the switch says. Characters already made with them still play.
		const bool PARKED = true;

		// classes.enabled (the settings page's switch). Off: the classes are left out of
		// character creation (hwplib-classui HWP::HideClass). Characters already made keep
		// loading and playing, and so do the Skill 4-6 keys their specs need.
		bool g_enabled = true;

		void RefreshEnabled()
		{
			g_enabled = HWP::Settings::GetBool("classes.enabled", true);
			bool offered = g_enabled && !PARKED;
			for (uint i = 0; i < IDS.length(); i++)
			{
				if (!offered)
				{
					HWP::HideClass(IDS[i]);
					continue;
				}
				HWP::ShowClass(IDS[i]);
			}
		}

		void OnSettingChanged(const string &in key)
		{
			if (key == "classes.enabled")
				RefreshEnabled();
		}

		int Subclasses(uint parentHash)
		{
			int n = 0;
			for (uint i = 0; i < PlayerClass::Instances.length(); i++)
				if (PlayerClass::Instances[i].parent == parentHash)
					n++;
			return n;
		}

		bool Registered(const string &in id)
		{
			for (uint i = 0; i < PlayerClass::Instances.length(); i++)
				if (PlayerClass::Instances[i].m_id == id)
					return true;
			return false;
		}

		// Classes load at boot, so the constructor checks them once (that is
		// what dev_check sees).
		void SelfCheck()
		{
			if (g_checked)
				return;
			g_checked = true;
			// tools/import_hoh1.py classes writes this string beside the art it cuts
			HWP::HoH1::Report("classes", Resources::HasString(".hwp.classes.hoh1art"), ".hwp.classes.hoh1");
			int found = 0;
			for (uint i = 0; i < IDS.length(); i++)
			{
				if (!Registered(IDS[i]))
				{
					HWP::LogError("classes", "class " + IDS[i] + " not registered (players/hwp/)");
					continue;
				}
				found++;
				int subs = Subclasses(HashString(IDS[i]));
				if (subs != 3)
					HWP::LogError("classes", IDS[i] + " has " + subs + " subclasses, expected 3");
			}
			HWP::CheckUnits("classes", UNITS);
			HWP::Log("classes", "self-check done: " + found + "/" + IDS.length() + " classes");
		}

		// The trident is an item and only resolves at gameplay load; once.
		void CheckTrident()
		{
			if (g_itemsChecked)
				return;
			g_itemsChecked = true;
			HWP::CheckEquipment("classes", { "hwp_trident_01" });
		}

		void CmdClasses(array<string>@ args)
		{
			int found = 0;
			int subs = 0;
			for (uint i = 0; i < IDS.length(); i++)
			{
				if (!Registered(IDS[i]))
					continue;
				found++;
				subs += Subclasses(HashString(IDS[i]));
			}
			auto rec = GetLocalPlayerRecord();
			string cls = (rec is null || rec.playerClass is null) ? "-" : rec.playerClass.m_id;
			HWP::Commands::Reply(Resources::GetString(".hwp.classes.status", { { "found", found }, { "subs", subs }, { "cls", cls } }));
			HWP::Commands::Reply("offered at character creation: " + (PARKED ? "no (parked)" : (g_enabled ? "yes" : "no (classes.enabled off)")));
		}
	}
}

namespace Modules
{
	class HWPClassesModule : Module, HWP::ModuleStart
	{
		HWPClassesModule()
		{
			super("hwp-classes");
			HWP::Commands::Register("classes", " HoH1 classes status", HWP::Commands::Handler(HWP::Classes::CmdClasses));
			HWP::Classes::SelfCheck();
			// parked (HWP::Classes::PARKED) or switched off: not offered at character creation
			HWP::Classes::RefreshEnabled();
			HWP::Commands::OnSettingChanged(HWP::Commands::SettingListener(HWP::Classes::OnSettingChanged));
		}

		void Start(StartMode sMode)
		{
			// the constructor read the settings before the town record was loaded
			HWP::Classes::RefreshEnabled();
			HWP::Classes::CheckTrident();
		}
	}
}
