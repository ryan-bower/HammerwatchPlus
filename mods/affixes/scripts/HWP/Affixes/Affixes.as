// Extra affixes (issue #17): items may roll two prefixes and two suffixes.
//
// An item's modifiers come in tiers, one per quality step (Generator.GenerateItemMods): the
// first from the common pool (stat mods, named as a prefix or a suffix), the second from the
// rare pool (tweak/items/modifiers_equipment_rare.sval, every one a suffix) and the third from
// the epic pool (modifiers_equipment_epic.sval, every one a prefix). So a Rare item has a stat
// mod and one suffix, an Epic one a stat mod, one suffix and one prefix, and never two of a kind.
// Here the rare tier and the epic tier may each roll a second time, affixes.chance (25) percent
// each: a Rare item can get a second suffix, an Epic one a second suffix and a second prefix.
// The extra mod comes from the same pool by the same weights, never a mod the item has already,
// one of the same exclusive group or a second skill. Legendary items keep no modifiers at all
// (Item.Finalize), so they have none.
//
// The generator has no hook: mods/affixes overrides scripts/Items/EquipmentGenerator.as (its
// three added lines are marked HWP) to call RollExtra after a call that rolled a mod, so a drop,
// a chest, a shop's stock, a quest reward and a reroll all get the chance, and an item whose
// mods are all there already (a saved one) is left alone. The extras are ordinary modifiers on
// the item: they are saved with it (Item.Save writes every mod), shown in its tooltip, add to
// its price, and stay when the module is off or gone. The item's name stays vanilla (one prefix,
// one suffix: Item.Finalize).
//
// `hwp affixes` shows the setting and the session's counts; `hwp affixes roll <n> [rare|epic]
// [ilvl]` rolls n items through the generator and counts what they got (nothing is kept);
// `hwp affixes bag` lists the worn and carried items' tiers; `hwp affixes give` (cheats) puts an
// Epic chest piece with both extras in the bag.
namespace HWP
{
	namespace Affixes
	{
		bool g_enabled = true;
		int g_chance = 25;
		bool g_force = false; // `give`: every extra rolls

		// this session, items that rolled a mod with the tiers in play, and the extras they got
		int g_seen = 0;
		int g_suffixes = 0;
		int g_prefixes = 0;

		void RefreshSettings()
		{
			g_enabled = HWP::Settings::GetBool("affixes.enabled", true);
			g_chance = clamp(HWP::Settings::GetInt("affixes.chance", 25), 0, 100);
		}

		void OnSettingChanged(const string &in key)
		{
			if (key.findFirst("affixes.") == 0)
				RefreshSettings();
		}

		int CountTier(Equipment::Item@ item, Item::Quality tier)
		{
			int n = 0;
			for (uint i = 0; i < item.mods.length(); i++)
			{
				if (item.mods[i].quality == tier)
					n++;
			}
			return n;
		}

		bool HasSkillMod(Equipment::Item@ item)
		{
			for (uint i = 0; i < item.mods.length(); i++)
			{
				if (item.mods[i].skill !is null)
					return true;
			}
			return false;
		}

		// one more mod of the tier, from the pool GenerateItemMods draws that tier from (the same
		// item level, tags and exclusive groups), weighted the same way; false when none is left
		bool AddOne(Equipment::Generator@ gen, Equipment::Item@ item, Item::Quality tier, int ilvl, array<uint>@ modTags)
		{
			auto pool = gen.GetAllPossibleItemModifiers(item.baseItem, tier, ilvl, item.mods, modTags);
			bool skill = item.baseItem.skill !is null || HasSkillMod(item);
			float sum = 0.0f;
			for (int i = int(pool.length()) - 1; i >= 0; i--)
			{
				auto m = pool[i].itemMod;
				if (item.mods.findByRef(m) >= 0 || (skill && m.skill !is null))
					pool.removeAt(i);
				else
					sum += pool[i].rarity;
			}
			if (pool.length() == 0 || sum <= 0.0f)
				return false;
			float r = randf() * sum;
			uint idx = pool.length() - 1;
			for (uint i = 0; i < pool.length(); i++)
			{
				r -= pool[i].rarity;
				if (r <= 0)
				{
					idx = i;
					break;
				}
			}
			item.mods.insertLast(pool[idx].itemMod);
			return true;
		}

		// After GenerateItemMods rolled the item's vanilla tiers: the rare tier (index 1, a suffix)
		// and the epic tier (index 2, a prefix) of a Rare or Epic item each get a second mod,
		// affixes.chance percent each. A tier that has two already is left alone.
		void RollExtra(Equipment::Generator@ gen, Equipment::Item@ item, int ilvl, array<uint>@ modTags)
		{
			if (!g_enabled || item is null || item.baseItem is null)
				return;
			if (item.quality != Item::Quality::Rare && item.quality != Item::Quality::Epic)
				return;
			g_seen++;
			int tiers = Equipment::EquipmentModifiersPerQuality(item.quality);
			for (int n = 1; n < tiers; n++)
			{
				auto tier = Item::IndexToQuality(n + 2);
				if (CountTier(item, tier) != 1)
					continue;
				if (!g_force && randi(100) >= g_chance)
					continue;
				if (!AddOne(gen, item, tier, ilvl, modTags))
					continue;
				if (tier == Item::Quality::Rare)
					g_suffixes++;
				else
					g_prefixes++;
			}
		}

		string Describe(Equipment::Item@ item)
		{
			if (item is null || item.baseItem is null)
				return "-";
			return item.baseItem.m_id + " " + Item::QualityToString(item.quality) + " (" + item.GetName() + "): "
				+ item.mods.length() + " mods, suffixes " + CountTier(item, Item::Quality::Rare)
				+ ", prefixes " + CountTier(item, Item::Quality::Epic);
		}

		array<Equipment::Slot> ROLL_SLOTS = {
			Equipment::Slot::Head, Equipment::Slot::Chest, Equipment::Slot::Feet, Equipment::Slot::Hands,
			Equipment::Slot::Back, Equipment::Slot::MainHand, Equipment::Slot::OffHand, Equipment::Slot::TwoHanded };

		// roll <n> [rare|epic] [ilvl]: n items through the generator, every slot in turn, counted
		// and thrown away (ilvl: the character's level)
		void CmdRoll(array<string>@ args)
		{
			int count = args.length() > 1 ? clamp(parseInt(args[1]), 1, 5000) : 200;
			auto quality = (args.length() > 2 && args[2] == "rare") ? Item::Quality::Rare : Item::Quality::Epic;
			auto rec = GetLocalPlayerRecord();
			int ilvl = args.length() > 3 ? clamp(parseInt(args[3]), 1, 100) : (rec is null ? 20 : max(1, rec.level));
			int made = 0, suffix2 = 0, prefix2 = 0, maxMods = 0, dupes = 0, skills = 0, over = 0;
			for (int i = 0; i < count; i++)
			{
				Equipment::Generator gen;
				auto item = gen.GenerateItem(ROLL_SLOTS[i % ROLL_SLOTS.length()], quality, ilvl);
				if (item is null)
					continue;
				made++;
				int s = CountTier(item, Item::Quality::Rare);
				int p = CountTier(item, Item::Quality::Epic);
				if (s == 2)
					suffix2++;
				if (p == 2)
					prefix2++;
				if (s > 2 || p > 2)
					over++;
				maxMods = max(maxMods, int(item.mods.length()));
				int sk = 0;
				for (uint a = 0; a < item.mods.length(); a++)
				{
					if (item.mods[a].skill !is null)
						sk++;
					for (uint b = a + 1; b < item.mods.length(); b++)
					{
						if (item.mods[a] is item.mods[b])
							dupes++;
					}
				}
				if (sk + (item.baseItem.skill !is null ? 1 : 0) > 1)
					skills++;
			}
			string line = "roll: " + made + " " + Item::QualityToString(quality) + " at ilvl " + ilvl + " (chance " + (g_enabled ? g_chance + "%" : "off")
				+ "): second suffix " + suffix2 + ", second prefix " + prefix2 + ", max mods " + maxMods
				+ ", over two " + over + ", duplicates " + dupes + ", two skills " + skills;
			HWP::Log("affixes", line);
			HWP::Commands::Reply(line);
		}

		void CmdBag()
		{
			auto rec = GetLocalPlayerRecord();
			if (rec is null || rec.equipInventory is null || rec.equipped is null)
				return;
			int extras = 0;
			for (uint i = 0; i < rec.equipped.m_items.length(); i++)
			{
				auto it = cast<Equipment::Item>(rec.equipped.m_items[i]);
				if (it is null)
					continue;
				HWP::Log("affixes", "worn " + Describe(it));
				if (CountTier(it, Item::Quality::Rare) > 1 || CountTier(it, Item::Quality::Epic) > 1)
					extras++;
			}
			for (uint i = 0; i < rec.equipInventory.m_items.length(); i++)
			{
				auto it = cast<Equipment::Item>(rec.equipInventory.m_items[i]);
				if (it is null)
					continue;
				HWP::Log("affixes", "bag " + Describe(it));
				if (CountTier(it, Item::Quality::Rare) > 1 || CountTier(it, Item::Quality::Epic) > 1)
					extras++;
			}
			string line = "bag: " + extras + " item(s) with an extra affix";
			HWP::Log("affixes", line);
			HWP::Commands::Reply(line);
		}

		// give: an Epic chest piece at the character's level with both extras, into the bag
		void CmdGive()
		{
			auto rec = GetLocalPlayerRecord();
			if (!HWP::Cheats::On() || rec is null || rec.equipInventory is null)
				return;
			Equipment::Generator gen;
			g_force = true;
			auto item = gen.GenerateItem(Equipment::Slot::Chest, Item::Quality::Epic, max(1, rec.level));
			g_force = false;
			if (item is null)
			{
				HWP::Commands::Reply("affixes: no epic chest piece to give");
				return;
			}
			rec.equipInventory.Add(item);
			string line = "gave " + Describe(item);
			HWP::Log("affixes", line);
			HWP::Commands::Reply(line);
		}

		void CmdAffixes(array<string>@ args)
		{
			if (args.length() > 0 && args[0] == "roll")
			{
				CmdRoll(args);
				return;
			}
			if (args.length() > 0 && args[0] == "bag")
			{
				CmdBag();
				return;
			}
			if (args.length() > 0 && args[0] == "give")
			{
				CmdGive();
				return;
			}
			string line = "extra affixes " + (g_enabled ? "on, " + g_chance + "% per tier" : "off")
				+ "; this session " + g_seen + " rare or epic item(s) rolled, " + g_suffixes + " second suffix(es), "
				+ g_prefixes + " second prefix(es)";
			HWP::Log("affixes", line);
			HWP::Commands::Reply(line);
		}
	}
}

namespace Modules
{
	class HWPAffixesModule : Module, HWP::ModuleStart
	{
		HWPAffixesModule()
		{
			super("hwp-affixes");
			HWP::Commands::OnSettingChanged(HWP::Commands::SettingListener(HWP::Affixes::OnSettingChanged));
			HWP::Commands::Register("affixes", "[roll <n> [rare|epic] [ilvl]|bag|give]  extra affixes: the setting and counts; roll counts n generated items; bag lists your items' tiers; give (cheat) adds an Epic chest piece with both extras", HWP::Commands::Handler(HWP::Affixes::CmdAffixes));
			HWP::Affixes::RefreshSettings();
			HWP::Log("affixes", "self-check done: " + (HWP::Affixes::g_enabled ? "on, " + HWP::Affixes::g_chance + "% per tier" : "off"));
		}

		void Start(StartMode sMode)
		{
			HWP::Settings::Sync("affixes.");
			HWP::Affixes::RefreshSettings();
		}
	}
}
