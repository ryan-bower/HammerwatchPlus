// The HoH1 trinkets (tweak/hwp/trinkets_hoh1.sval), their sets (tweak/hwp/trinket_sets_hoh1.sval)
// and the changes to vanilla sets and trinkets (tweak/hwp/trinket_sets_vanilla.sval), from the
// Trinket Map verdicts of 2026-10-26 (mods/trinkets/README.md).
//
// Most of it is plain sval. The script parts:
// - ApplyVanilla (once, at the first level start): a vanilla set gets its new pieces
//   (trinket.m_set, m_totItems) and its bonus tiers replaced from the sval, each tier loaded
//   the way Item::TrinketSet loads them (Modifiers::LoadIModifiers, SyncVerb::TrinketSet with
//   the set's id hash, so trigger effects keep a sync verb). Trader's Coin gets its extra
//   modifier and its new tooltip. Every machine does this for itself.
// - HWPTrinketComboKills (Sphere of Warriors) and HWPTrinketMissingHealthSpeed (Seal of Rage,
//   Seals of Torment): stat modifiers. Player.Update rebuilds stats every frame, so the
//   missing-health one follows health as it changes.
// - HWPTrinketShopContent: the dungeon trinket shop (module.json class_swaps) with
//   Fancy Plume's extra stock and purchase and Trader's Coin's discount.
// - Key Ring is read by the keys mod (HWPGiveKey), by its custom stat name.
// - ApplyArt (with ApplyVanilla): the HoH1 icons. `tools/import_hoh1.py trinkets` cuts them
//   from the player's own HoH1 install into gui/hwp/icons_trinkets_hoh1.png (16x16 cells,
//   ART_COLS a row) and lists the ids in sheet order in the string .hwp.trinkets.hoh1art.
//   Without the import the trinkets keep their placeholder icons from the sval.
namespace HWP
{
	namespace Trinkets
	{
		const string VANILLA = "tweak/hwp/trinket_sets_vanilla.sval";
		const string STAT_SHOP_STOCK = "hwp-shop-stock";       // Fancy Plume: more choices
		const string STAT_SHOP_BUYS = "hwp-shop-buys";         // Fancy Plume attuned: one more purchase
		const string STAT_SHOP_DISCOUNT = "hwp-shop-discount"; // Trader's Coin: % off
		const float MIN_PRICE_MUL = 0.25f;
		const string ART_SHEET = "gui/hwp/icons_trinkets_hoh1.png";
		const string ART_IDS = ".hwp.trinkets.hoh1art";
		const int ART_COLS = 8;
		int g_artIcons = 0;

		bool g_vanillaDone = false;
		string g_vanillaLast;

		// a custom stat's total for a player (Modifiers::CustomStat), 0 when absent
		float StatOf(PlayerRecord@ rec, const string &in id) { return HWP::CustomStat(rec, id); }

		// the dungeon trinket shop's price factor: Trader's Coin's discount, floored
		float ShopPriceMul(PlayerRecord@ rec)
		{
			return max(MIN_PRICE_MUL, 1.0f - StatOf(rec, STAT_SHOP_DISCOUNT) / 100.0f);
		}

		Item::TrinketSet@ FindSet(const string &in id)
		{
			for (uint i = 0; i < Item::TrinketSet::Instances.length(); i++)
			{
				if (Item::TrinketSet::Instances[i].m_id == id)
					return Item::TrinketSet::Instances[i];
			}
			return null;
		}

		string PatchSet(Item::TrinketSet@ set, SValue@ d)
		{
			UnitPtr u;
			int added = 0;
			auto items = GetParamArray(u, d, "add-items", false);
			if (items !is null)
			{
				for (uint i = 0; i < items.length(); i++)
				{
					auto t = Item::Trinket::Get(items[i].GetString());
					if (t is null)
					{
						HWP::Log("trinkets", "set " + set.m_id + ": no trinket " + items[i].GetString());
						continue;
					}
					if (t.m_set is set)
						continue;
					@t.m_set = set;
					set.m_totItems++;
					added++;
				}
			}

			array<Item::TrinketSetBonus@> bonuses;
			for (int n = 1; n <= 16; n++)
			{
				auto bd = GetParamDictionary(u, d, "" + n, false);
				if (bd is null)
					continue;
				Item::TrinketSetBonus bonus;
				bonus.m_num = n;
				bonus.m_desc = Resources::GetString(GetParamString(u, bd, "desc", true, "unknown"));
				bonus.m_modifiers = Modifiers::LoadIModifiers(u, bd, Modifiers::Role::Both, "", Modifiers::SyncVerb::TrinketSet, set.m_idHash);
				bonuses.insertLast(bonus);
			}
			if (bonuses.length() > 0)
				set.m_bonuses = bonuses;
			return set.m_id + " +" + added + " piece(s) (" + set.m_totItems + "), " + set.m_bonuses.length() + " tier(s)";
		}

		string PatchTrinket(Item::Trinket@ t, SValue@ d)
		{
			UnitPtr u;
			auto mods = Modifiers::LoadIModifiers(u, d, Modifiers::Role::Both, "", Modifiers::SyncVerb::Trinket, t.m_idHash, 0x80);
			auto mods2 = Modifiers::LoadIModifiers(u, d, Modifiers::Role::Both, "attune-", Modifiers::SyncVerb::Trinket, t.m_idHash, 0x80);
			for (uint i = 0; i < mods.length(); i++)
				t.m_modifiers.insertLast(mods[i]);
			for (uint i = 0; i < mods2.length(); i++)
				t.m_modifiers2.insertLast(mods2[i]);
			string desc = GetParamString(u, d, "desc", false);
			if (desc != "")
				t.m_desc1 = Resources::GetString(desc);
			string desc2 = GetParamString(u, d, "attune-desc", false);
			if (desc2 != "")
				t.m_desc2 = Resources::GetString(desc2);
			return t.m_id + " +" + mods.length() + "/" + mods2.length() + " modifier(s)";
		}

		// once per game: the vanilla sets and trinkets as tweak/hwp/trinket_sets_vanilla.sval says
		void ApplyVanilla()
		{
			if (g_vanillaDone)
				return;
			g_vanillaDone = true;
			auto root = Resources::GetSValue(VANILLA);
			if (root is null || root.GetType() != SValueType::Dictionary)
			{
				g_vanillaLast = "no " + VANILLA;
				HWP::Log("trinkets", g_vanillaLast);
				return;
			}
			array<string> done;
			auto dict = root.GetDictionary();
			auto keys = dict.getKeys();
			keys.sortAsc();
			for (uint i = 0; i < keys.length(); i++)
			{
				SValue@ d;
				if (!dict.get(keys[i], @d) || d is null)
					continue;
				auto set = FindSet(keys[i]);
				if (set !is null)
				{
					done.insertLast(PatchSet(set, d));
					continue;
				}
				auto t = Item::Trinket::Get(keys[i]);
				if (t !is null)
				{
					done.insertLast(PatchTrinket(t, d));
					continue;
				}
				done.insertLast(keys[i] + ": not a set or trinket");
			}
			g_vanillaLast = join(done, "; ");
			HWP::Log("trinkets", "vanilla changes: " + g_vanillaLast);
			ApplyArt();
			for (uint i = 0; i < g_players.length(); i++)
			{
				if (g_players[i] is null || g_players[i].peer == 255)
					continue;
				g_players[i].RefreshModifiers();
			}
		}

		void ApplyArt()
		{
			HWP::HoH1::Report("trinkets", Resources::HasString(ART_IDS), ".hwp.trinkets.hoh1");
			if (!Resources::HasString(ART_IDS))
			{
				HWP::Log("trinkets", "HoH1 icons not imported (tools/import_hoh1.py trinkets): placeholder icons");
				return;
			}
			auto tex = Resources::GetTexture2D(ART_SHEET);
			if (tex is null)
			{
				HWP::LogError("trinkets", "no " + ART_SHEET + " for " + ART_IDS);
				return;
			}
			auto ids = Resources::GetString(ART_IDS).split(" ");
			for (uint i = 0; i < ids.length(); i++)
			{
				auto t = Item::Trinket::Get(ids[i]);
				if (t is null)
					continue;
				@t.m_icon = ScriptSprite(tex, vec4((i % ART_COLS) * 16, (i / ART_COLS) * 16, 16, 16));
				g_artIcons++;
			}
			HWP::Log("trinkets", "HoH1 icons: " + g_artIcons + " of " + ids.length());
		}

		// hwp trinkets set <id>: a set's pieces and tiers as the game now has them
		void SetCmd(const string &in id)
		{
			ApplyVanilla();
			auto set = FindSet(id);
			if (set is null)
			{
				HWP::Commands::Reply("not a trinket set: " + id);
				return;
			}
			array<string> pieces;
			for (uint i = 0; i < Item::Trinket::Instances.length(); i++)
			{
				if (Item::Trinket::Instances[i].m_set is set)
					pieces.insertLast(Item::Trinket::Instances[i].m_id);
			}
			array<string> tiers;
			for (uint i = 0; i < set.m_bonuses.length(); i++)
				tiers.insertLast(set.m_bonuses[i].m_num + ":" + set.m_bonuses[i].m_modifiers.length() + " " + set.m_bonuses[i].m_desc);
			auto rec = GetLocalPlayerRecord();
			int worn = 0;
			if (rec !is null)
			{
				for (uint i = 0; i < pieces.length(); i++)
				{
					auto t = Item::Trinket::Get(pieces[i]);
					if (t !is null && rec.trinketInventory.HasItem(t))
						worn++;
				}
			}
			HWP::Commands::Reply("set " + set.m_id + " (" + set.m_name + "): " + set.m_totItems + " piece(s) [" + join(pieces, " ")
				+ "]; tiers " + join(tiers, " | ") + "; carried " + worn);
		}

		// hwp trinkets hoh1: how many of the HoH1 trinkets loaded, and the vanilla changes
		void HoH1Cmd()
		{
			ApplyVanilla();
			array<string> ids;
			for (uint i = 0; i < Item::Trinket::Instances.length(); i++)
			{
				auto id = Item::Trinket::Instances[i].m_id;
				if (id.findFirst("hwp_") == 0 && id != HWP::Luck::TRINKET)
					ids.insertLast(id);
			}
			auto rec = GetLocalPlayerRecord();
			HWP::Commands::Reply("hoh1 trinkets: " + ids.length() + " loaded; icons: " + (g_artIcons > 0 ? g_artIcons + " from HoH1" : "placeholders")
				+ "; vanilla: " + g_vanillaLast
				+ (rec is null ? "" : "; shop price x" + ShopPriceMul(rec) + ", stock +" + StatOf(rec, STAT_SHOP_STOCK)
					+ ", buys +" + StatOf(rec, STAT_SHOP_BUYS) + ", key ring " + StatOf(rec, "hwp-key-ring") + "%"));
		}
	}
}

// Sphere of Warriors: Combo starts with fewer kills (never fewer than one, and only once
// something has unlocked Combo, which sets ComboCountMax; Modifiers::Combo runs at StatsAdd)
class HWPTrinketComboKills : Modifiers::StatModifier
{
	int m_num;

	HWPTrinketComboKills(UnitPtr unit, SValue& params)
	{
		super(unit, params);
		Ordering = int(Modifiers::ModifierOrdering::StatsMul);
		m_num = GetParamInt(unit, params, "num", false, 2);
	}

	void Modify(PlayerRecord@ player, PlayerStats@ stats, float intensity) override
	{
		int cur = stats.ComboCountMax;
		if (cur > 0)
			stats.ComboCountMax = max(1, cur - m_num);
	}
}

// Seal of Rage, Seals of Torment: weapon ("attack") and skill ("cast") speed that grow with
// missing health, the full amount at none left
class HWPTrinketMissingHealthSpeed : Modifiers::StatModifier
{
	float m_attack;
	float m_cast;

	HWPTrinketMissingHealthSpeed(UnitPtr unit, SValue& params)
	{
		super(unit, params);
		Ordering = int(Modifiers::ModifierOrdering::StatsAdd);
		m_attack = GetParamFloat(unit, params, "attack", false, 0);
		m_cast = GetParamFloat(unit, params, "cast", false, 0);
	}

	void Modify(PlayerRecord@ player, PlayerStats@ stats, float intensity) override
	{
		float hp = player.hp;
		float missing = clamp(1.0f - hp, 0.0f, 1.0f);
		if (m_attack != 0)
		{
			stats.MainHand.AttackSpeed += m_attack * missing;
			stats.OffHand.AttackSpeed += m_attack * missing;
		}
		if (m_cast != 0)
			stats.CastSpeed += m_cast * missing;
	}

	// the stats screen shows no number that would only hold at the current health
	void ModifyDetail(PlayerRecord@ player, PlayerStatsDetail@ stats, float intensity) override {}
}

// The dungeon trinket shop (actors/npcs/dungeon/npc_trinket_shop.unit, swapped in by
// module.json class_swaps): Fancy Plume's extra choices (and the attuned extra purchase)
// join the vanilla roll the first time the choices are made; Trader's Coin lowers prices.
class HWPTrinketShopContent : TrinketShopShopContent
{
	bool m_hwpExtra = false;

	HWPTrinketShopContent(UnitPtr u, SValue& params)
	{
		super(u, params);
	}

	array<IShopItem@> GetItems() override
	{
		array<IShopItem@> ret;
		if (m_toBuy <= 0)
			return ret;
		TrinketShopShopContent::GetItems(); // rolls the vanilla choices when there are none
		if (!m_hwpExtra && m_trinketChoices.length() > 0)
		{
			m_hwpExtra = true;
			int extra = int(HWP::Trinkets::StatOf(m_player, HWP::Trinkets::STAT_SHOP_STOCK) + 0.5f);
			for (int i = 0; i < extra; i++)
			{
				auto t = Item::GetRandomTrinket(m_player, m_shopLevel > 1 ? Item::Quality::Rare : Item::Quality::Uncommon);
				if (t !is null)
					m_trinketChoices.insertLast(t);
			}
			int buys = int(HWP::Trinkets::StatOf(m_player, HWP::Trinkets::STAT_SHOP_BUYS) + 0.5f);
			m_toBuy += buys;
			if (extra > 0 || buys > 0)
				HWP::Log("trinkets", "trinket shop: +" + extra + " choice(s), +" + buys + " purchase(s)");
		}
		float priceRate = (1.0f + m_shopLevel * 0.2f) * HWP::Trinkets::ShopPriceMul(m_player);
		for (uint i = 0; i < m_trinketChoices.length(); i++)
			ret.insertLast(TrinketShopShopContentItem(this, m_trinketChoices[i], i, priceRate));
		return ret;
	}

	void Save(SValueBuilder& builder) override
	{
		TrinketShopShopContent::Save(builder);
		builder.PushBoolean("hwp-extra", m_hwpExtra);
	}

	void Load(SValue@ sval) override
	{
		TrinketShopShopContent::Load(sval);
		m_hwpExtra = GetParamBool(UnitPtr(), sval, "hwp-extra", false, false);
	}
}
