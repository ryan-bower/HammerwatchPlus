// The key pickups' effect: vanilla GiveKey, but in a run the key goes to the
// party pool (HWP::Keys::GiveFoundKey; a client's add goes to the host), in town through
// HWP::Keys::AddKeys (vanilla PlayerRecord.AddKeys corrupts it, KeysModule.as).
// A run key also rolls the Key Ring trinket (mods/trinkets, the custom stat hwp-key-ring, a
// percent chance): one more key of a random tier, bronze 60%, silver 30%, gold 10%.
class HWPGiveKey : GiveKey
{
	HWPGiveKey(UnitPtr unit, SValue& params)
	{
		super(unit, params);
	}

	void Apply(PlayerRecord@ player) override
	{
		int amount = m_amount;
		int tier = HWP::Keys::TierIndex(m_key);
		if (tier == 0)
		{
			HWP::Keys::AddKeys(player, m_key, amount);
			return;
		}
		HWP::Keys::GiveFoundKey(player, tier, amount);
		Stats::Add(HashString("key-found-" + m_key), amount, player);
		LootLog::PresentPickup(player, Resources::GetString(".item.key." + m_key), amount);
		KeyRing(player);
		HWP::Keys::RefreshHUD();
	}

	void KeyRing(PlayerRecord@ player)
	{
		float chance = HWP::CustomStat(player, "hwp-key-ring");
		if (chance <= 0 || randf() * 100.0f >= chance)
			return;
		float roll = randf();
		int tier = roll < 0.6f ? 1 : (roll < 0.9f ? 2 : 3);
		string key = HWP::Keys::TIERS[tier - 1];
		HWP::Keys::GiveFoundKey(player, tier, 1);
		Stats::Add(HashString("key-found-" + key), 1, player);
		LootLog::PresentPickup(player, Resources::GetString(".item.key." + key), 1);
		HWP::Log("keys", "key ring: an extra " + key + " key");
	}
}
