// HWP::Bag: bought inventory slots. Each character's equipment bag holds 24
// items (vanilla); every bought slot adds one, up to a full extra row of 8.
// The count lives in the character's HWP save data (bag.extra) and is put
// on the record's EquipmentInventory.m_maxItems after a load and once a
// second (a record built without a load starts at 24 again). Slots are
// sold by the keys module (HWP::BagShop: the exit guard's shop, `hwp bag`);
// without it the bag stays at the size it has.
//
// The character screen (gui/playermenu/character.gui) uses
// <hwp-equipmentinventory>: the vanilla bag widget, but it draws as many
// slots as you can carry (vanilla always draws 24); the screen shows four
// rows, so a full bag fits without scrolling. A click to equip runs the
// HWP::Bag::OnEquip callbacks first.
namespace HWP
{
	namespace Bag
	{
		const string KEY_EXTRA = "bag.extra";
		const int BASE = 24;
		const int MAX_EXTRA = 8;

		int Extra(PlayerRecord@ rec)
		{
			if (rec is null)
				return 0;
			return clamp(HWP::SaveData::Player(rec).GetInt(KEY_EXTRA, 0), 0, MAX_EXTRA);
		}

		int Capacity(PlayerRecord@ rec) { return BASE + Extra(rec); }

		// Called with the bag item a click is about to equip, before the vanilla equip. A
		// module may swap its base item for a twin of another slot (firearms: one pistol
		// that fits either hand). Script globals reset per level: register in a module ctor.
		funcdef void EquipPrepare(PlayerRecord@ rec, Equipment::Equipment@ item);
		array<EquipPrepare@> g_equipPrepare;
		void OnEquip(EquipPrepare@ f) { g_equipPrepare.insertLast(f); }

		void Apply(PlayerRecord@ rec)
		{
			if (rec is null || rec.equipInventory is null)
				return;
			int cap = Capacity(rec);
			if (rec.equipInventory.m_maxItems == cap)
				return;
			rec.equipInventory.m_maxItems = cap;
			rec.equipInventory.m_isDirty = true;
		}
	}
}

class HWPEquipmentInventoryWidget : EquipmentInventoryWidget
{
	int m_check = 0;

	HWPEquipmentInventoryWidget() { super(); }

	// the vanilla bag keeps m_maxItems (set by HWP::Bag::Apply) current
	int SlotCount()
	{
		return max(int(m_owner.equipInventory.m_items.length()), m_owner.equipInventory.m_maxItems);
	}

	// vanilla Refresh with the slot count above, and a height that counts a
	// part-filled last row
	void Refresh() override
	{
		ClearChildren();
		if (m_owner is null)
			return;

		vec2 offset = vec2(0);
		ivec2 navOffset = ivec2(0);
		int count = SlotCount();
		for (int i = 0; i < count; i++)
		{
			auto item = cast<EquipmentItemWidget>(m_itemTemplate.Clone());
			item.SetID("");
			item.m_offset = offset;
			if (uint(i) < m_owner.equipInventory.m_items.length())
				item.Set(m_owner.equipInventory.m_items[i], this);
			item.m_visible = true;
			item.m_navPos += navOffset;
			@item.m_inventory = this;
			AddChild(item);

			navOffset.x += 1;
			offset.x += item.m_width;
			if ((offset.x + item.m_width) > m_width)
			{
				offset.x = 0;
				offset.y += item.m_height;
				navOffset.x = 0;
				navOffset.y += 1;
			}
		}
		m_height = (navOffset.y + (navOffset.x > 0 ? 1 : 0)) * m_itemTemplate.m_height;
		UpdateScroll();
	}

	// the vanilla tab code enables the scrollbar only past 24 items; ours
	// scrolls when the slots outgrow the view
	void UpdateScroll()
	{
		auto sb = cast<ScrollbarWidget>(m_parent);
		if (m_visible && sb !is null && m_owner !is null)
			sb.m_enabled = m_height > sb.m_height;
	}

	// The prepare callbacks (HWP::Bag::OnEquip) run only for an item vanilla may equip, and
	// a base item they swapped goes back if the item stayed in the bag after all (no room
	// to bump a two-handed weapon's pair, Remove failed).
	void OnClick(Equipment::Equipment@ item) override
	{
		auto it = cast<Equipment::Item>(item);
		Equipment::BaseItem@ was = it !is null ? it.baseItem : null;
		if (item !is null && m_owner !is null && m_owner.equipped.MayEquip(item))
		{
			for (uint i = 0; i < HWP::Bag::g_equipPrepare.length(); i++)
				HWP::Bag::g_equipPrepare[i](m_owner, item);
		}
		EquipmentInventoryWidget::OnClick(item);
		if (it !is null && it.baseItem !is was && m_owner !is null && m_owner.equipInventory.m_items.findByRef(item) >= 0)
		{
			@it.baseItem = was;
			m_owner.equipInventory.m_isDirty = true;
		}
	}

	void Update(int dt) override
	{
		// a few times a second is plenty: the size changes only when a slot
		// is bought (and Apply also runs once a second from the module)
		m_check -= dt;
		if (m_visible && m_owner !is null && m_check <= 0)
		{
			m_check = 250;
			HWP::Bag::Apply(m_owner);
			if (m_children.length() != uint(SlotCount()))
				m_owner.equipInventory.m_isDirty = true;
			UpdateScroll();
		}
		EquipmentInventoryWidget::Update(dt);
	}
}

ref@ LoadHWPEquipmentInventoryWidget(WidgetLoadingContext &ctx)
{
	HWPEquipmentInventoryWidget@ w = HWPEquipmentInventoryWidget();
	w.Load(ctx);
	return w;
}

namespace HWPBagSlots
{
	[Hook]
	void LoadWidgetProducers(GUIBuilder@ builder)
	{
		builder.AddWidgetProducer("hwp-equipmentinventory", LoadHWPEquipmentInventoryWidget);
	}

	[Hook]
	void PlayerRecordLoad(PlayerRecord@ record, SValue@ data)
	{
		// should this run before the core hook has read the HWP data, the
		// module's once-a-second Apply catches up
		HWP::Bag::Apply(record);
	}
}

namespace Modules
{
	class HWPBagModule : Module
	{
		int m_timer = 0;

		HWPBagModule()
		{
			super("hwp-bag");
		}

		// HWP::Guard (tools/guard_modules.py): a script error here turns this off, not the game
		HWP::Guard m_guardUpdateFrame;
		void UpdateFrame(int ms, GameInput& gameInput, MenuInput& menuInput, bool paused) override
		{
			if (m_guardUpdateFrame.Skip("hwplib", "HWPBagModule.UpdateFrame"))
				return;
			if (m_guardUpdateFrame.Raw())
			{
				GuardedUpdateFrame(ms, gameInput, menuInput, paused);
				m_guardUpdateFrame.Ok();
				return;
			}
			try { GuardedUpdateFrame(ms, gameInput, menuInput, paused); m_guardUpdateFrame.Ok(); }
			catch { m_guardUpdateFrame.Failed(); }
		}

		void GuardedUpdateFrame(int ms, GameInput& gameInput, MenuInput& menuInput, bool paused)
		{
			m_timer -= ms;
			if (m_timer > 0)
				return;
			m_timer = 1000;
			HWP::Bag::Apply(GetLocalPlayerRecord());
		}
	}
}
