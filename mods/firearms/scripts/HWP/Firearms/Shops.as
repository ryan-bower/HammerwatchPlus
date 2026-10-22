// Shops. The town's equipment seller and the wagon's "Buy new equipment" (overrides of
// Town/EquipmentSeller.as and ShopContent/EquipmentShopShopContent.as; the added lines are
// marked HWP) roll their stock through Equipment::Generator by slot and the buyer's stats, so a
// Firearms Specialist was offered crossbows and bows and a Ranger could be offered a rifle.
// Here: a Specialist's weapon offers are guns and the stock always holds at least one gun;
// nobody else is offered one (the user, 2026-10-22).
namespace HWP
{
	namespace Firearms
	{
		const uint FIREARM_TAG = HashString("hwp_firearm");

		bool IsFirearmItem(Equipment::Equipment@ e)
		{
			auto it = cast<Equipment::Item>(e);
			return it !is null && it.baseItem !is null && it.baseItem.supportedTags.find(FIREARM_TAG) >= 0;
		}

		bool IsWeaponSlot(Equipment::Slot slot)
		{
			return slot == Equipment::Slot::MainHand || slot == Equipment::Slot::OffHand || slot == Equipment::Slot::TwoHanded;
		}

		// is a shop's roll kept for this buyer? (a null or non-item roll is left to the shop's own checks)
		bool ShopKeeps(PlayerRecord@ rec, Equipment::Equipment@ e)
		{
			auto it = cast<Equipment::Item>(e);
			if (it is null || it.baseItem is null)
				return true;
			bool gun = IsFirearmItem(e);
			if (!IsFirearms(rec))
				return !gun;
			return gun || !IsWeaponSlot(it.baseItem.slot);
		}

		// a Specialist's stock holds a gun: when none was rolled, one for the main hand or both
		// hands at the shop's item level and quality takes the place of the last non-weapon offer
		void ShopNeedsGun(PlayerRecord@ rec, Equipment::Generator@ gen, array<Equipment::Equipment@>@ choices)
		{
			if (rec is null || gen is null || choices is null || choices.length() == 0 || !IsFirearms(rec))
				return;
			for (uint i = 0; i < choices.length(); i++)
			{
				if (IsFirearmItem(choices[i]))
					return;
			}
			array<uint> tags = { FIREARM_TAG };
			Equipment::Slot first = randf() < 0.5f ? Equipment::Slot::MainHand : Equipment::Slot::TwoHanded;
			Equipment::Slot second = first == Equipment::Slot::MainHand ? Equipment::Slot::TwoHanded : Equipment::Slot::MainHand;
			Equipment::Item@ gun = gen.GenerateItem(first, gen.RollQuality(), gen.m_ilvl, tags, null, rec);
			if (gun is null)
				@gun = gen.GenerateItem(second, gen.RollQuality(), gen.m_ilvl, tags, null, rec);
			if (gun is null)
			{
				HWP::Log("firearms", "shop: no gun to stock at ilvl " + gen.m_ilvl);
				return;
			}
			int at = int(choices.length()) - 1;
			for (int i = at; i >= 0; i--)
			{
				auto it = cast<Equipment::Item>(choices[i]);
				if (it is null || it.baseItem is null || !IsWeaponSlot(it.baseItem.slot))
				{
					at = i;
					break;
				}
			}
			@choices[at] = gun;
			HWP::Log("firearms", "shop: stocked " + gun.baseItem.name + " in place of offer " + at);
		}
	}
}
