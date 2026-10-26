// NG+ scaling for flat trinket bonuses (the Trinket Map verdicts of 2026-10-26: "in NG+
// become +X per NGL"). A trinket's flat numbers (health, armor, power, regen, thorns, proc
// damage) grow by a fixed amount per NG+ level of the run (g_ngp). An attuned trinket
// grows twice as fast when attuning doubles its flat number, and at the same rate when
// attuning changes something else (a shorter cooldown, a higher chance).
//
// Item::Trinket keeps its modifiers in public arrays (m_modifiers, m_modifiers2 for the
// attuned copy, Items/Trinkets.as) built once from its sval dict. When the NG+ level
// changes, every trinket in SPEC gets new arrays loaded from a copy of that dict with the
// numbers patched (Patched), the same way the game loads them, so the trigger effects keep
// their sync verb and index. Its tooltip strings get the new numbers too. NG+ 0 puts the
// original arrays back. Every machine does this for itself from the same g_ngp.
//
// Proc damage that lives in a projectile or unit file (Cauldron, Searing Torch, Magic
// Missile, ...) cannot be patched in the trinket's dict: its effects list gets an
// intensity-mul entry first instead (EffectListMod, Behaviors/Effects/IEffect.as), and the
// projectile, the spawned unit or the applied buff carries that intensity into its Damage
// effects. The multiplier is (dmg + amount * ng) / dmg, dmg being the tooltip's number.
namespace HWP
{
	namespace Trinkets
	{
		// "<trinket> <op> <path> <amount> [<base>]"
		//   add     the number at path grows by amount per NG+ level
		//   set4    from NG+ 4 on, the number at path is amount
		//   mul     the effects array at path is scaled: intensity (base + amount * ng) / base
		//   buff    the Modifiers::Buff dict at path applies its buff at that intensity
		//   int     a new integer key at path: base + amount * ng (when the dict lacks it)
		//   desc    the %param% of the tooltip: path is desc:<param> or attune-desc:<param>
		//   dset4   from NG+ 4 on, the tooltip's %param% is amount
		const array<string> SPEC = {
			"amulet_health add modifier.health 5", "amulet_health add attune-modifier.health 10",
			"amulet_health desc desc:num 5", "amulet_health desc attune-desc:num 10",
			"amulet_mana add modifier.mana 5", "amulet_mana add attune-modifier.mana 10",
			"amulet_mana desc desc:num 5", "amulet_mana desc attune-desc:num 10",
			"amulet_vigor_greater add modifier.health 10", "amulet_vigor_greater add modifier.mana 10",
			"amulet_vigor_greater add attune-modifier.health 20", "amulet_vigor_greater add attune-modifier.mana 20",
			"amulet_vigor_greater desc desc:num 10", "amulet_vigor_greater desc attune-desc:num 20",
			"apothecarys_antidote add modifier.poison 5", "apothecarys_antidote desc desc:num 5",
			"apothecarys_flask set4 modifier.charges 2", "apothecarys_flask set4 attune-modifier.charges 4",
			"apothecarys_flask dset4 desc:num 2", "apothecarys_flask dset4 attune-desc:num 4",
			// the speed buff (buffs_items.sval apothecarys_tincture, 5000 ms): ApplyBuff's duration
			"apothecarys_tincture int modifier.effects.1.duration 1000 5000", "apothecarys_tincture desc desc:num 1",
			"arctic_step buff modifiers.1 10 30", "arctic_step desc desc:dmg 10",
			"book_attacks add modifier.attack-power 5", "book_attacks add attune-modifier.attack-power 10",
			"book_attacks desc desc:num 5", "book_attacks desc attune-desc:num 10",
			"book_spells add modifier.spell-power 5", "book_spells add attune-modifier.spell-power 10",
			"book_spells desc desc:num 5", "book_spells desc attune-desc:num 10",
			"caltrops mul modifiers.1.effects 5 25", "caltrops desc desc:dmg 5",
			"cauldron mul modifiers.0.effects 10 30", "cauldron desc desc:dmg 10",
			"chain_undershirt add modifier.armor 10", "chain_undershirt add attune-modifier.armor 20",
			"chain_undershirt desc desc:num 10", "chain_undershirt desc attune-desc:num 20",
			"chaos_orb add modifiers.0.effects.0.poison 10", "chaos_orb add modifiers.1.effects.0.fire 10",
			"chaos_orb add modifiers.2.effects.0.ice 10", "chaos_orb add modifiers.3.effects.0.lightning 10",
			"chaos_orb desc desc:dmg 10",
			// the tooltip's mana per second is two 500 ms ticks of mana
			"chicken_feet add modifiers.0.effects.0.effects.1.mana 0.25", "chicken_feet desc desc:num 0.5",
			"closed_circuit add modifiers.0.lightning 2", "closed_circuit add attune-modifiers.0.lightning 4",
			"closed_circuit mul modifiers.2.effects 10 50", "closed_circuit mul attune-modifiers.1.effects 10 50",
			"closed_circuit desc desc:add 2", "closed_circuit desc attune-desc:add 4",
			"closed_circuit desc desc:dmg 10", "closed_circuit desc attune-desc:dmg 10",
			"codex_power add modifier.attack-power 10", "codex_power add modifier.spell-power 10",
			"codex_power add attune-modifier.attack-power 20", "codex_power add attune-modifier.spell-power 20",
			"codex_power desc desc:num 10", "codex_power desc attune-desc:num 20",
			"coiled_serpent add modifiers.0.poison 2", "coiled_serpent add attune-modifiers.0.poison 4",
			"coiled_serpent mul modifiers.1.effects 5 30", "coiled_serpent mul attune-modifiers.1.effects 5 30",
			"coiled_serpent desc desc:add 2", "coiled_serpent desc attune-desc:add 4",
			"coiled_serpent desc desc:dmg 5", "coiled_serpent desc attune-desc:dmg 5",
			"decaying_hand add modifier.mul 1", "decaying_hand desc desc:num 1",
			"dragon_heart add modifiers.0.health 20", "dragon_heart add modifiers.1.health-regen 5",
			"dragon_heart desc desc:num 20", "dragon_heart desc desc:regen 5",
			"dragon_scale_blue add modifier.armor 10", "dragon_scale_blue add modifier.ice 10", "dragon_scale_blue desc desc:num 10",
			"dragon_scale_red add modifier.armor 10", "dragon_scale_red add modifier.fire 10", "dragon_scale_red desc desc:num 10",
			"ectoplasm add modifiers.0.ice 2", "ectoplasm add attune-modifiers.0.ice 4",
			"ectoplasm mul modifiers.2.effects 5 10", "ectoplasm mul attune-modifiers.2.effects 5 10",
			"ectoplasm desc desc:add 2", "ectoplasm desc attune-desc:add 4",
			"ectoplasm desc desc:dmg 5", "ectoplasm desc attune-desc:dmg 5",
			"fiddle add modifier.effects.1.effects.1.physical 10", "fiddle desc desc:dmg 10",
			"fire_salts add modifiers.0.fire 2", "fire_salts add attune-modifiers.0.fire 4",
			"fire_salts mul modifiers.1.effects 10 30", "fire_salts mul attune-modifiers.1.effects 10 30",
			"fire_salts desc desc:add 2", "fire_salts desc attune-desc:add 4",
			"fire_salts desc desc:dmg 10", "fire_salts desc attune-desc:dmg 10",
			"gambeson add modifier.armor 5", "gambeson add attune-modifier.armor 10",
			"gambeson desc desc:num 5", "gambeson desc attune-desc:num 10",
			"gemstone_fire add modifiers.0.fire 5", "gemstone_fire add attune-modifiers.0.fire 10",
			"gemstone_fire desc desc:res 5", "gemstone_fire desc attune-desc:res 10",
			"gemstone_ice add modifiers.0.ice 5", "gemstone_ice add attune-modifiers.0.ice 10",
			"gemstone_ice desc desc:res 5", "gemstone_ice desc attune-desc:res 10",
			"gemstone_lightning add modifiers.0.lightning 5", "gemstone_lightning add attune-modifiers.0.lightning 10",
			"gemstone_lightning desc desc:res 5", "gemstone_lightning desc attune-desc:res 10",
			"gemstone_poison add modifiers.0.poison 5", "gemstone_poison add attune-modifiers.0.poison 10",
			"gemstone_poison desc desc:res 5", "gemstone_poison desc attune-desc:res 10",
			"life_stone add modifier.effect.heal 2", "life_stone add attune-modifier.effect.heal 4",
			"life_stone desc desc:num 2", "life_stone desc attune-desc:num 4",
			"maggot_gland mul modifiers.0.effects 10 40", "maggot_gland mul attune-modifiers.0.effects 10 40",
			"maggot_gland desc desc:dmg 10", "maggot_gland desc attune-desc:dmg 10",
			"mana_stone add modifier.effect.mana 3", "mana_stone add attune-modifier.effect.mana 6",
			"mana_stone desc desc:num 3", "mana_stone desc attune-desc:num 6",
			"markhams_amulet add modifiers.0.mul 1", "markhams_amulet add modifiers.1.mul 1", "markhams_amulet desc desc:num 1",
			"markhams_mace add modifiers.0.mul 1", "markhams_mace desc desc:num 1",
			"markhams_purse add modifiers.0.gold-mul 0.01", "markhams_purse desc desc:num 1",
			"markhams_stone add modifiers.0.wood-mul 0.01", "markhams_stone add modifiers.0.stone-mul 0.01",
			"markhams_stone add modifiers.0.iron-mul 0.01", "markhams_stone desc desc:num 1",
			"markhams_wand add modifiers.0.mul 1", "markhams_wand desc desc:num 1",
			"moonstone_pendant add modifier.any 10", "moonstone_pendant desc desc:blck 10",
			"orb_of_restoration add modifiers.1.mana-regen 1", "orb_of_restoration desc desc:rgn 1",
			"pickled_eye add modifier.mul 1", "pickled_eye desc desc:num 1",
			"razor_amulet add modifiers.0.attack-power 5", "razor_amulet add modifiers.1.thorns 5",
			"razor_amulet add attune-modifiers.0.attack-power 10", "razor_amulet add attune-modifiers.1.thorns 10",
			"razor_amulet desc desc:num 5", "razor_amulet desc attune-desc:num 10",
			"ring_health add modifier.health-regen 0.25", "ring_health add attune-modifier.health-regen 0.5",
			"ring_health desc desc:num 0.25", "ring_health desc attune-desc:num 0.5",
			"ring_mana add modifier.mana-regen 0.25", "ring_mana add attune-modifier.mana-regen 0.5",
			"ring_mana desc desc:num 0.25", "ring_mana desc attune-desc:num 0.5",
			"ring_rejuvenation add modifier.health-regen 0.2", "ring_rejuvenation add modifier.mana-regen 0.2",
			"ring_rejuvenation add attune-modifier.health-regen 0.4", "ring_rejuvenation add attune-modifier.mana-regen 0.4",
			"ring_rejuvenation desc desc:num 0.2", "ring_rejuvenation desc attune-desc:num 0.4",
			"ring_rejuvenation_greater add modifier.health-regen 0.5", "ring_rejuvenation_greater add modifier.mana-regen 0.5",
			"ring_rejuvenation_greater add attune-modifier.health-regen 1", "ring_rejuvenation_greater add attune-modifier.mana-regen 1",
			"ring_rejuvenation_greater desc desc:num 0.5", "ring_rejuvenation_greater desc attune-desc:num 1",
			"ring_resistances add modifier.fire 5", "ring_resistances add modifier.ice 5",
			"ring_resistances add modifier.lightning 5", "ring_resistances add modifier.poison 5",
			"ring_resistances add attune-modifier.fire 10", "ring_resistances add attune-modifier.ice 10",
			"ring_resistances add attune-modifier.lightning 10", "ring_resistances add attune-modifier.poison 10",
			"ring_resistances desc desc:num 5", "ring_resistances desc attune-desc:num 10",
			"ring_resistances_greater add modifier.fire 5", "ring_resistances_greater add modifier.ice 5",
			"ring_resistances_greater add modifier.lightning 5", "ring_resistances_greater add modifier.poison 5",
			"ring_resistances_greater add attune-modifier.fire 10", "ring_resistances_greater add attune-modifier.ice 10",
			"ring_resistances_greater add attune-modifier.lightning 10", "ring_resistances_greater add attune-modifier.poison 10",
			"ring_resistances_greater desc desc:num 5", "ring_resistances_greater desc attune-desc:num 10",
			"rosethorn_wand add modifiers.0.spell-power 5", "rosethorn_wand add modifiers.1.thorns 5",
			"rosethorn_wand add attune-modifiers.0.spell-power 10", "rosethorn_wand add attune-modifiers.1.thorns 10",
			"rosethorn_wand desc desc:num 5", "rosethorn_wand desc attune-desc:num 10",
			"scroll_earth mul modifiers.0.effects 10 50", "scroll_earth desc desc:dmg 10",
			"scroll_hellfire mul modifiers.1.effects 20 100", "scroll_hellfire desc desc:dmg 20",
			"scroll_magic_missile mul modifiers.0.effects 10 40", "scroll_magic_missile mul attune-modifiers.0.effects 10 40",
			"scroll_magic_missile desc desc:dmg 10", "scroll_magic_missile desc attune-desc:dmg 10",
			"scroll_meteor mul modifiers.1.effects 20 100", "scroll_meteor desc desc:dmg 20",
			"searing_torch mul modifiers.0.effects 10 50", "searing_torch mul attune-modifiers.0.effects 10 50",
			"searing_torch desc desc:dmg 10", "searing_torch desc attune-desc:dmg 10",
			"spiked_collar add modifiers.0.thorns 10", "spiked_collar add attune-modifiers.0.thorns 20",
			"spiked_collar desc desc:num 10", "spiked_collar desc attune-desc:num 20",
			"spiked_pauldrons add modifiers.0.armor 5", "spiked_pauldrons add modifiers.1.thorns 5",
			"spiked_pauldrons add attune-modifiers.0.armor 10", "spiked_pauldrons add attune-modifiers.1.thorns 10",
			"spiked_pauldrons desc desc:armr 5", "spiked_pauldrons desc desc:num 5",
			"spiked_pauldrons desc attune-desc:armr 10", "spiked_pauldrons desc attune-desc:num 10",
			"thunderbird_feather mul modifiers.1.effects 20 100", "thunderbird_feather desc desc:dmg 20",
			// HoH1 trinkets (HoH1.as)
			"hwp_judgement add modifiers.0.physical 1", "hwp_judgement add attune-modifiers.0.physical 2",
			"hwp_judgement desc desc:add 1", "hwp_judgement desc attune-desc:add 2",
			"hwp_talisman_of_conflagration add modifier.effects.0.effects.0.fire 10",
			"hwp_talisman_of_conflagration add attune-modifier.effects.0.effects.0.fire 10",
			"hwp_talisman_of_conflagration desc desc:dmg 10", "hwp_talisman_of_conflagration desc attune-desc:dmg 10"
		};

		// the trinket files Item::Trinket::LoadMultiple reads these from
		const array<string> FILES = { "tweak/trinkets/common.sval", "tweak/trinkets/uncommon.sval",
			"tweak/trinkets/rare.sval", "tweak/trinkets/epic.sval", "tweak/trinkets/cursed.sval",
			"tweak/hwp/trinkets_hoh1.sval" };

		class Patch
		{
			string op;
			string path;
			float amount;
			float base;
		}

		// one scaled trinket: its patches, its dict and what the game loaded (NG+ 0)
		class Scaled
		{
			string id;
			array<Patch@> patches;
			SValue@ dict;
			Item::Trinket@ trinket;
			array<Modifiers::IModifier@> mods;
			array<Modifiers::IModifier@> mods2;
			string desc1;
			string desc2;
		}

		array<Scaled@> g_scaled;
		int g_applied = 0;     // the NG+ level the trinkets are scaled for
		bool g_ready = false;
		string g_last;         // what the last Apply changed, for 'hwp trinkets'

		bool g_enabled = true;

		void RefreshSettings()
		{
			g_enabled = HWP::Settings::GetBool("trinkets.ngp_scaling", true);
		}

		int NG()
		{
			return g_enabled ? max(0, int(g_ngp + 0.5f)) : 0;
		}

		Scaled@ Find(const string &in id)
		{
			for (uint i = 0; i < g_scaled.length(); i++)
			{
				if (g_scaled[i].id == id)
					return g_scaled[i];
			}
			return null;
		}

		SValue@ FindDict(const string &in id)
		{
			for (uint f = 0; f < FILES.length(); f++)
			{
				auto root = Resources::GetSValue(FILES[f]);
				if (root is null || root.GetType() != SValueType::Array)
					continue;
				auto arr = root.GetArray();
				for (uint i = 0; i < arr.length(); i++)
				{
					if (HWP::SV::Str(arr[i], "id") == id)
						return arr[i];
				}
			}
			return null;
		}

		// the spec, the source dicts and the trinkets, once
		void Init()
		{
			if (g_ready)
				return;
			g_ready = true;
			for (uint i = 0; i < SPEC.length(); i++)
			{
				auto w = SPEC[i].split(" ");
				if (w.length() < 4)
				{
					HWP::LogError("trinkets", "bad spec line: " + SPEC[i]);
					continue;
				}
				auto s = Find(w[0]);
				if (s is null)
				{
					@s = Scaled();
					s.id = w[0];
					g_scaled.insertLast(s);
				}
				Patch p;
				p.op = w[1];
				p.path = w[2];
				p.amount = parseFloat(w[3]);
				p.base = w.length() > 4 ? parseFloat(w[4]) : 0.0f;
				s.patches.insertLast(p);
			}
			for (uint i = 0; i < g_scaled.length(); i++)
			{
				auto s = g_scaled[i];
				@s.dict = FindDict(s.id);
				@s.trinket = Item::Trinket::Get(s.id);
				if (s.dict is null || s.trinket is null)
				{
					HWP::LogError("trinkets", "no trinket " + s.id + (s.dict is null ? " in the trinket files" : " loaded"));
					continue;
				}
				s.mods = s.trinket.m_modifiers;
				s.mods2 = s.trinket.m_modifiers2;
				s.desc1 = s.trinket.m_desc1;
				s.desc2 = s.trinket.m_desc2;
			}
		}

		// ---- the patched copy

		string Num(float f)
		{
			if (abs(f - float(int(f))) < 0.001f)
				return "" + int(f);
			string ret = formatFloat(f, "", 0, 2);
			while (ret.substr(ret.length() - 1) == "0")
				ret = ret.substr(0, ret.length() - 1);
			return ret;
		}

		bool IsNum(SValue@ v)
		{
			return v !is null && (v.GetType() == SValueType::Integer || v.GetType() == SValueType::Float);
		}

		float NumOf(SValue@ v)
		{
			return v.GetType() == SValueType::Integer ? float(v.GetInteger()) : v.GetFloat();
		}

		void PushNum(SValueBuilder& b, const string &in name, bool named, float f, bool wasInt)
		{
			bool asInt = wasInt && abs(f - float(int(f))) < 0.001f;
			if (named)
			{
				if (asInt) b.PushInteger(name, int(f)); else b.PushFloat(name, f);
			}
			else
			{
				if (asInt) b.PushInteger(int(f)); else b.PushFloat(f);
			}
		}

		float Mul(Patch@ p, int ng)
		{
			return p.base > 0.0f ? (p.base + p.amount * float(ng)) / p.base : 1.0f;
		}

		// "<key>?a=1&b=2": each param named in the patches grows (desc) or is set (dset4)
		string PatchDesc(const string &in s, const string &in which, array<Patch@>@ patches, int ng)
		{
			int q = s.findFirst("?");
			if (q < 0)
				return s;
			auto parts = s.substr(q + 1).split("&");
			for (uint i = 0; i < parts.length(); i++)
			{
				int eq = parts[i].findFirst("=");
				if (eq < 0)
					continue;
				string key = parts[i].substr(0, eq);
				string val = parts[i].substr(eq + 1);
				string pct = val.findFirst("%") >= 0 ? "%" : "";
				for (uint j = 0; j < patches.length(); j++)
				{
					auto p = patches[j];
					if (p.path != which + ":" + key)
						continue;
					float f = parseFloat(val);
					if (p.op == "desc")
						f += p.amount * float(ng);
					else if (p.op == "dset4" && ng >= 4)
						f = p.amount;
					else
						continue;
					parts[i] = key + "=" + Num(f) + pct;
				}
			}
			string ret = s.substr(0, q + 1);
			for (uint i = 0; i < parts.length(); i++)
				ret += (i > 0 ? "&" : "") + parts[i];
			return ret;
		}

		void Copy(SValueBuilder& b, const string &in name, bool named, SValue@ v, const string &in path, Scaled@ s, int ng)
		{
			auto t = v.GetType();
			if (t == SValueType::Array)
			{
				if (named) b.PushArray(name); else b.PushArray();
				for (uint j = 0; j < s.patches.length(); j++)
				{
					auto p = s.patches[j];
					if (p.op == "mul" && p.path == path)
					{
						// an effect-list modifier entry: what follows hits at this intensity
						float m = Mul(p, ng);
						b.PushDictionary();
						b.PushVector2("intensity-mul", vec2(m, m));
						b.PopDictionary();
					}
				}
				auto arr = v.GetArray();
				for (uint i = 0; i < arr.length(); i++)
					Copy(b, "", false, arr[i], path + "." + i, s, ng);
				b.PopArray();
				return;
			}
			if (t == SValueType::Dictionary)
			{
				Patch@ buff = null;
				for (uint j = 0; j < s.patches.length(); j++)
				{
					if (s.patches[j].op == "buff" && s.patches[j].path == path)
						@buff = s.patches[j];
				}
				if (named) b.PushDictionary(name); else b.PushDictionary();
				auto keys = v.GetDictionaryKeys();
				for (uint i = 0; i < keys.length(); i++)
				{
					string sub = path.isEmpty() ? keys[i] : path + "." + keys[i];
					if (buff !is null && keys[i] == "class")
					{
						b.PushString("class", "HWPTrinketNGBuff");
						continue;
					}
					Copy(b, keys[i], true, v.GetDictionaryEntry(keys[i]), sub, s, ng);
				}
				if (buff !is null)
					b.PushFloat("intensity", Mul(buff, ng));
				for (uint j = 0; j < s.patches.length(); j++)
				{
					auto p = s.patches[j];
					if (p.op != "int")
						continue;
					int dot = p.path.findLast(".");
					string key = p.path.substr(dot + 1);
					if (p.path.substr(0, dot) == path && keys.find(key) < 0)
						b.PushInteger(key, int(p.base + p.amount * float(ng)));
				}
				b.PopDictionary();
				return;
			}
			if (t == SValueType::String && (path == "desc" || path == "attune-desc"))
			{
				b.PushString(name, PatchDesc(v.GetString(), path, s.patches, ng));
				return;
			}
			if (IsNum(v))
			{
				float f = NumOf(v);
				bool hit = false;
				for (uint j = 0; j < s.patches.length(); j++)
				{
					auto p = s.patches[j];
					if (p.path != path)
						continue;
					if (p.op == "add")
						f += p.amount * float(ng);
					else if (p.op == "set4" && ng >= 4)
						f = p.amount;
					else
						continue;
					hit = true;
				}
				if (hit)
				{
					PushNum(b, name, named, f, v.GetType() == SValueType::Integer);
					return;
				}
			}
			if (named) b.PushSimple(name, v.Copy()); else b.PushSimple(v.Copy());
		}

		SValue@ Patched(Scaled@ s, int ng)
		{
			SValueBuilder b;
			Copy(b, "", false, s.dict, "", s, ng);
			return b.Build();
		}

		// ---- applying

		void Restore(Scaled@ s)
		{
			s.trinket.m_modifiers = s.mods;
			s.trinket.m_modifiers2 = s.mods2;
			s.trinket.m_desc1 = s.desc1;
			s.trinket.m_desc2 = s.desc2;
		}

		void Scale(Scaled@ s, int ng)
		{
			auto dict = Patched(s, ng);
			UnitPtr u;
			auto t = s.trinket;
			t.m_modifiers = Modifiers::LoadIModifiers(u, dict, Modifiers::Role::Both, "", Modifiers::SyncVerb::Trinket, t.m_idHash);
			t.m_modifiers2 = Modifiers::LoadIModifiers(u, dict, Modifiers::Role::Both, "attune-", Modifiers::SyncVerb::Trinket, t.m_idHash);
			t.m_desc1 = Resources::GetString(GetParamString(u, dict, "desc", false));
			t.m_desc2 = Resources::GetString(GetParamString(u, dict, "attune-desc", false));
		}

		// every scaled trinket to NG+ ng; the players' modifier lists rebuilt
		void Apply(int ng)
		{
			Init();
			int n = 0;
			for (uint i = 0; i < g_scaled.length(); i++)
			{
				auto s = g_scaled[i];
				if (s.dict is null || s.trinket is null)
					continue;
				if (ng <= 0)
					Restore(s);
				else
					Scale(s, ng);
				n++;
			}
			g_applied = ng;
			for (uint i = 0; i < g_players.length(); i++)
			{
				if (g_players[i] is null || g_players[i].peer == 255)
					continue;
				g_players[i].RefreshModifiers();
				g_players[i].RefreshStats();
			}
			auto amulet = Find("amulet_health");
			g_last = "NG+ " + ng + ": " + n + " trinket(s) " + (ng <= 0 ? "as the game made them" : "scaled")
				+ (amulet is null || amulet.trinket is null ? "" : " (Amulet of Health: " + amulet.trinket.m_desc1 + ")");
			HWP::Log("trinkets", g_last);
		}

		void Update()
		{
			int ng = NG();
			if (ng != g_applied)
				Apply(ng);
		}

		// hwp trinkets [show <id> | ng <n>]
		void Cmd(array<string>@ args)
		{
			if (args.length() >= 2 && args[0] == "set")
			{
				SetCmd(args[1]);
				return;
			}
			if (args.length() >= 1 && args[0] == "hoh1")
			{
				HoH1Cmd();
				return;
			}
			if (args.length() >= 2 && args[0] == "show")
			{
				Init();
				auto s = Find(args[1]);
				if (s is null || s.trinket is null)
				{
					HWP::Commands::Reply("not a scaled trinket: " + args[1]);
					return;
				}
				auto rec = GetLocalPlayerRecord();
				HWP::Commands::Reply(s.id + " at NG+ " + g_applied + ": " + s.trinket.m_desc1 + " | attuned: " + s.trinket.m_desc2
					+ " | " + s.trinket.m_modifiers.length() + "+" + s.trinket.m_modifiers2.length() + " modifier(s)"
					+ (rec is null ? "" : " | max health " + rec.MaxHealth() + ", max mana " + rec.MaxMana()
						+ (rec.trinketInventory.HasItem(s.trinket) ? ", carried" : "") + (s.trinket.IsAttuned(rec) ? ", attuned" : "")));
				return;
			}
			if (args.length() >= 2 && args[0] == "ng")
			{
				if (!HWP::Cheats::On())
					return;
				g_ngp = float(max(0, parseInt(args[1])));
				Update();
				HWP::Commands::Reply(g_last);
				return;
			}
			Init();
			int found = 0;
			for (uint i = 0; i < g_scaled.length(); i++)
			{
				if (g_scaled[i].dict !is null && g_scaled[i].trinket !is null)
					found++;
			}
			HWP::Commands::Reply("trinket NG+ scaling (" + (g_enabled ? "on" : "off") + "): " + found + "/" + g_scaled.length()
				+ " trinket(s) found, scaled for NG+ " + g_applied + (g_last.isEmpty() ? "" : "; last: " + g_last));
		}
	}
}

// Modifiers::Buff that applies its buff at an intensity (Arctic Step's frosted ground):
// the buff's move effects spawn their units at it (ActorBuff.as)
class HWPTrinketNGBuff : Modifiers::Buff
{
	float m_intensity = 1.0f;

	HWPTrinketNGBuff() {}
	HWPTrinketNGBuff(UnitPtr unit, SValue& params)
	{
		super(unit, params);
		m_intensity = GetParamFloat(unit, params, "intensity", false, 1.0f);
	}

	Modifiers::Modifier@ Instance() override
	{
		auto ret = HWPTrinketNGBuff();
		ret = this;
		ret.m_cloned++;
		return ret;
	}

	void Update(PlayerBase@ player, int dt, float intensity) override
	{
		if (player.IsHusk())
			return;
		m_timer -= dt;
		if (m_timer <= 0)
		{
			m_timer += m_freq;
			player.ApplyBuff(ActorBuff(player, m_buff, m_intensity, false));
		}
	}
}

namespace Modules
{
	class HWPTrinketsModule : Module, HWP::ModuleStart
	{
		HWPTrinketsModule()
		{
			super("hwp-trinkets");
			HWP::Commands::Register("trinkets", " NG+ scaling of flat trinket bonuses; 'show <id>' a trinket's tooltip; 'set <id>' a set's pieces and tiers; 'hoh1' the HoH1 trinkets and vanilla changes; cheats: 'ng <n>' sets the NG+ level",
				HWP::Commands::Handler(HWP::Trinkets::Cmd));
		}

		void Start(StartMode sMode)
		{
			HWP::Trinkets::RefreshSettings();
			HWP::Trinkets::ApplyVanilla();
			HWP::Trinkets::Update();
		}

		void UpdateFrame(int ms, GameInput& gameInput, MenuInput& menuInput, bool paused) override
		{
			// the mission loadout's NG+ picker changes g_ngp in town
			HWP::Trinkets::Update();
		}
	}
}
