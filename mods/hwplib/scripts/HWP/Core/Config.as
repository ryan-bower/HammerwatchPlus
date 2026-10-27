// HWP::Config - what the HammerwatchPlus tab lists: every package, its modules,
// their on/off switch and settings. Read from tweak/hwp/config.sval, which
// tools/make_config.py writes from the modules' module.json "config" blocks
// (docs/modules.md, Settings); every package ships the same hwplib, so every
// package carries the whole list and a module shows only when it is loaded:
// its generated lang file (hwp_<id>_cfg.lang) holds ".hwp.cfg.<id>".
//
// The values themselves are plain HWP::Settings. A host-scope key is made
// host-synced here (Settings::Sync), so modules don't have to; a local-scope key
// under a prefix a module syncs is kept per player (Settings::LocalOnly).
// Changing a value calls HWP::Commands::NotifySettingChanged, as `hwp set` does.
namespace HWP
{
	namespace Config
	{
		const string FILE = "tweak/hwp/config.sval";
		const float EPS = 0.0001f;

		class Setting
		{
			string mod;
			string key;          // "" for an option
			string option;       // an HWP::Options::Option id, or ""
			string type;         // bool, int, float
			bool host;
			bool level;
			bool defBool;
			float def;
			array<float> values; // the choices, or none for a range
			int labels;          // values have names (.hwp.cfg.s.<key>.v<i>)
			float min;
			float max;
			float step;
			string suffix;

			bool IsOption() { return !option.isEmpty(); }

			HWP::Options::Option@ Opt() { return HWP::Options::Get(option); }

			string Title()
			{
				if (IsOption())
				{
					auto o = Opt();
					return o is null ? option : o.Title();
				}
				return Resources::GetString(".hwp.cfg.s." + key);
			}

			string About()
			{
				string id = IsOption() ? ".hwp.cfg.o." + option + ".about" : ".hwp.cfg.s." + key + ".about";
				return Resources::HasString(id) ? Resources::GetString(id) : "";
			}

			// a client sees the host's value and cannot change it
			bool Locked() { return !IsOption() && host && !Network::IsServer(); }

			bool Available() { return !IsOption() || Opt() !is null; }

			float Number()
			{
				if (type == "int")
					return float(HWP::Settings::GetInt(key, int(def)));
				return HWP::Settings::GetFloat(key, def);
			}

			string Value()
			{
				if (IsOption())
				{
					auto o = Opt();
					return o is null ? "" : o.Value();
				}
				if (type == "bool")
					return OnOff(HWP::Settings::GetBool(key, defBool));
				float v = Number();
				if (labels > 0)
				{
					for (uint i = 0; i < values.length() && int(i) < labels; i++)
					{
						if (abs(values[i] - v) < EPS)
							return Resources::GetString(".hwp.cfg.s." + key + ".v" + i);
					}
				}
				return Num(v) + suffix;
			}

			// the button: the next choice (wraps)
			void Next()
			{
				if (IsOption())
				{
					auto o = Opt();
					if (o !is null)
						o.Next();
					return;
				}
				if (Locked() || !HWP::Settings::CanSave())
					return;
				if (type == "bool")
				{
					HWP::Settings::SetBool(key, !HWP::Settings::GetBool(key, defBool));
					HWP::Commands::NotifySettingChanged(key);
					return;
				}
				float v = Number();
				float next = v;
				if (values.length() > 0)
				{
					next = values[0];
					for (uint i = 0; i < values.length(); i++)
					{
						if (values[i] > v + EPS)
						{
							next = values[i];
							break;
						}
					}
				}
				else
				{
					next = v + step;
					if (next > max + EPS || next < min - EPS)
						next = min;
				}
				if (type == "int")
					HWP::Settings::SetInt(key, int(round(next)));
				else
					HWP::Settings::SetFloat(key, next);
				HWP::Commands::NotifySettingChanged(key);
			}
		}

		class Mod
		{
			string id;
			string package;
			string toggle;       // "" when it cannot be turned off
			bool host;
			bool level;
			array<Setting@> settings;

			string Title() { return Resources::GetString(".hwp.cfg." + id); }
			string About() { return Resources::GetString(".hwp.cfg." + id + ".about"); }
			string AlwaysOn()
			{
				string s = ".hwp.cfg." + id + ".always_on";
				return Resources::HasString(s) ? Resources::GetString(s) : "";
			}
			bool CanToggle() { return !toggle.isEmpty(); }
			bool On() { return toggle.isEmpty() || HWP::Settings::GetBool(toggle, true); }
			bool Locked() { return host && !Network::IsServer(); }

			void Toggle()
			{
				if (toggle.isEmpty() || Locked() || !HWP::Settings::CanSave())
					return;
				HWP::Settings::SetBool(toggle, !On());
				HWP::Commands::NotifySettingChanged(toggle);
			}
		}

		class Package
		{
			string id;
			array<Mod@> mods;     // the loaded ones

			string Title() { return Resources::GetString(".hwp.cfg.pkg." + id); }
		}

		array<Package@> g_packages;
		array<Setting@> g_top;
		dictionary g_mods;       // id -> Mod@ (loaded modules)
		bool g_loaded = false;

		string OnOff(bool on) { return Resources::GetString(on ? ".hwp.cfg.on" : ".hwp.cfg.off"); }

		string Num(float v)
		{
			if (abs(v - round(v)) < EPS)
				return "" + int(round(v));
			string s = formatFloat(v, "", 0, 2);
			while (s.length() > 0 && s.substr(s.length() - 1) == "0")
				s = s.substr(0, s.length() - 1);
			return s;
		}

		bool Present(const string &in mod) { return Resources::HasString(".hwp.cfg." + mod); }

		Mod@ GetMod(const string &in id)
		{
			Mod@ m;
			if (g_mods.get(id, @m))
				return m;
			return null;
		}

		Package@ GetPackage(const string &in id)
		{
			for (uint i = 0; i < g_packages.length(); i++)
			{
				if (g_packages[i].id == id)
					return g_packages[i];
			}
			return null;
		}

		// a module's on/off switch: true when it has none or the config is not loaded
		bool Enabled(const string &in mod)
		{
			auto m = GetMod(mod);
			return m is null || m.On();
		}

		// an array field, or null
		array<SValue@>@ Arr(SValue@ d, const string &in key)
		{
			auto v = HWP::SV::Field(d, key);
			if (v is null || v.GetType() != SValueType::Array)
				return null;
			return v.GetArray();
		}

		Setting@ ReadSetting(SValue@ d, Mod@ mod)
		{
			Setting@ s = Setting();
			s.mod = mod.id;
			s.option = HWP::SV::Str(d, "option");
			s.key = HWP::SV::Str(d, "key");
			s.type = HWP::SV::Str(d, "type");
			s.host = HWP::SV::Bool(d, "host", mod.host);
			s.level = HWP::SV::Bool(d, "level", mod.level);
			s.defBool = HWP::SV::Bool(d, "default", false);
			s.def = HWP::SV::Float(d, "default", 0);
			s.labels = HWP::SV::Int(d, "labels", 0);
			s.min = HWP::SV::Float(d, "min", 0);
			s.max = HWP::SV::Float(d, "max", 0);
			s.step = HWP::SV::Float(d, "step", 1);
			s.suffix = HWP::SV::Str(d, "suffix");
			auto arr = Arr(d, "values");
			for (uint i = 0; arr !is null && i < arr.length(); i++)
			{
				if (arr[i] is null)
					continue;
				if (arr[i].GetType() == SValueType::Integer)
					s.values.insertLast(float(arr[i].GetInteger()));
				else if (arr[i].GetType() == SValueType::Float)
					s.values.insertLast(arr[i].GetFloat());
			}
			return s;
		}

		void Load()
		{
			g_packages.removeRange(0, g_packages.length());
			g_top.removeRange(0, g_top.length());
			g_mods.deleteAll();
			SValue@ root = Resources::GetSValue(FILE);
			if (root is null)
			{
				HWP::Log("config", FILE + " is missing: the Plus tab lists only the options");
				return;
			}
			auto parr = Arr(root, "packages");
			for (uint p = 0; parr !is null && p < parr.length(); p++)
			{
				Package@ pkg = Package();
				pkg.id = HWP::SV::Str(parr[p], "id");
				auto marr = Arr(parr[p], "mods");
				for (uint m = 0; marr !is null && m < marr.length(); m++)
				{
					string id = HWP::SV::Str(marr[m], "id");
					if (id.isEmpty() || !Present(id) || g_mods.exists(id))
						continue; // not loaded, or listed by an earlier package
					Mod@ mod = Mod();
					mod.id = id;
					mod.package = pkg.id;
					mod.toggle = HWP::SV::Str(marr[m], "toggle");
					mod.host = HWP::SV::Bool(marr[m], "host", true);
					mod.level = HWP::SV::Bool(marr[m], "level", false);
					auto sarr = Arr(marr[m], "settings");
					for (uint i = 0; sarr !is null && i < sarr.length(); i++)
						mod.settings.insertLast(ReadSetting(sarr[i], mod));
					pkg.mods.insertLast(mod);
					g_mods.set(id, @mod);
				}
				if (pkg.mods.length() > 0)
					g_packages.insertLast(pkg);
			}
			// the top section: "option:<id>" or a setting key, of a loaded module
			auto tarr = Arr(root, "top");
			for (uint t = 0; tarr !is null && t < tarr.length(); t++)
			{
				if (tarr[t] is null || tarr[t].GetType() != SValueType::String)
					continue;
				string want = tarr[t].GetString();
				bool opt = want.findFirst("option:") == 0;
				auto s = opt ? Find("", want.substr(7)) : Find(want, "");
				if (s !is null)
					g_top.insertLast(s);
			}
		}

		Setting@ Find(const string &in key, const string &in option)
		{
			for (uint p = 0; p < g_packages.length(); p++)
				for (uint m = 0; m < g_packages[p].mods.length(); m++)
				{
					auto mod = g_packages[p].mods[m];
					for (uint i = 0; i < mod.settings.length(); i++)
					{
						auto s = mod.settings[i];
						if ((!key.isEmpty() && s.key == key) || (!option.isEmpty() && s.option == option))
							return s;
					}
				}
			return null;
		}

		// host-scope keys follow the host (the toggle with its module's scope)
		void RegisterSync()
		{
			for (uint p = 0; p < g_packages.length(); p++)
				for (uint m = 0; m < g_packages[p].mods.length(); m++)
				{
					auto mod = g_packages[p].mods[m];
					if (!mod.toggle.isEmpty())
						SyncKey(mod.toggle, mod.host);
					for (uint i = 0; i < mod.settings.length(); i++)
					{
						if (!mod.settings[i].IsOption())
							SyncKey(mod.settings[i].key, mod.settings[i].host);
					}
				}
		}

		void SyncKey(const string &in key, bool host)
		{
			if (host)
				HWP::Settings::Sync(key);
			else if (HWP::Settings::IsSynced(key))
				HWP::Settings::LocalOnly(key);
		}

		// core module ctor (every level: script globals reset)
		void Init()
		{
			Load();
			RegisterSync();
			g_loaded = true;
			int n = 0;
			for (uint p = 0; p < g_packages.length(); p++)
				n += g_packages[p].mods.length();
			HWP::Log("config", g_packages.length() + " package(s), " + n + " module(s) loaded");
		}
	}
}
