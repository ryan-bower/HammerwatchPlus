// HWP::HoH1 - the features that use the player's own Heroes of Hammerwatch 1 content.
// HoH1 assets are never shipped: tools/import_hoh1.py cuts them from the player's own HoH1
// install and `build.py --with-local` packs them (README, Installing). Without them each
// feature keeps a stand-in (HoH2 themes, placeholder icons), so no package needs HoH1 to run.
// The player is told once which features are on stand-ins:
//
//   HWP::HoH1::Report("pets", imported > 0, ".hwp.pets.hoh1");   // when the mod knows
//
// The key names what the player gets without HoH1. The core module calls Tell on the
// town's TELL_TICK-th gameplay tick, after every mod's self-check: one chat line per save
// for each set of features on stand-ins (the setting hoh1.told). hwp hoh1 lists them all.
// Script globals reset with every level, so the mods report again on each one.
namespace HWP
{
	namespace HoH1
	{
		const int TELL_TICK = 60;

		class Feature
		{
			string mod;
			bool present;
			string key;
		}

		array<Feature@> g_features;

		void Report(const string &in mod, bool present, const string &in key)
		{
			for (uint i = 0; i < g_features.length(); i++)
			{
				if (g_features[i].mod == mod)
				{
					g_features[i].present = present;
					g_features[i].key = key;
					return;
				}
			}
			Feature@ f = Feature();
			f.mod = mod;
			f.present = present;
			f.key = key;
			g_features.insertLast(f);
		}

		// the mods on stand-ins, sorted: what hoh1.told remembers
		array<string>@ Missing()
		{
			array<string> ids;
			for (uint i = 0; i < g_features.length(); i++)
			{
				if (g_features[i].present)
					continue;
				uint at = 0;
				while (at < ids.length() && ids[at] < g_features[i].mod)
					at++;
				ids.insertAt(at, g_features[i].mod);
			}
			return ids;
		}

		string Phrase(const string &in mod)
		{
			for (uint i = 0; i < g_features.length(); i++)
				if (g_features[i].mod == mod)
					return Resources::GetString(g_features[i].key);
			return mod;
		}

		void Tell()
		{
			auto ids = Missing();
			auto told = join(ids, ",");
			if (ids.length() == 0 || HWP::Settings::GetString("hoh1.told", "") == told)
				return;
			HWP::Settings::SetString("hoh1.told", told);
			array<string> phrases;
			for (uint i = 0; i < ids.length(); i++)
				phrases.insertLast(Phrase(ids[i]));
			HWP::Log("hoh1", "on stand-ins: " + told);
			HWP::Commands::Reply(Resources::GetString(".hwp.hoh1.missing", { { "list", join(phrases, "; ") } }));
		}

		void CmdHoH1(array<string>@ args)
		{
			if (g_features.length() == 0)
			{
				HWP::Commands::Reply(Resources::GetString(".hwp.hoh1.none"));
				return;
			}
			for (uint i = 0; i < g_features.length(); i++)
			{
				auto f = g_features[i];
				HWP::Commands::Reply(f.mod + ": " + (f.present ? Resources::GetString(".hwp.hoh1.present")
					: Resources::GetString(f.key)));
			}
		}

		void Init()
		{
			HWP::Commands::Register("hoh1", " the features that use Heroes of Hammerwatch 1 content, and whether it is installed",
				HWP::Commands::Handler(CmdHoH1));
		}
	}
}
