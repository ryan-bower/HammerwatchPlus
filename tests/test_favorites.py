"""Source/package contracts for #61. Engine behavior is checked by fix-favorites, not pytest."""
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

import pytest

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "mods/hwplib"


def source(path):
    return (ROOT / path).read_text(encoding="utf-8")


def test_favorites_is_in_qol_and_all_mod_smoke():
    packages = json.loads(source("packages.json"))["packages"]
    assert [p["id"] for p in packages if "favorites" in p["mods"]] == ["qol"]
    assert "favorites" in json.loads(source("gamelab/scenarios/mod-all.json"))["mods"]
    module = json.loads(source("mods/favorites/module.json"))
    assert module["requires"] == ["hwplib"]
    assert module["config"]["scope"] == "local"
    assert module["config"]["toggle"] == "favorites.enabled"


def test_buyer_rechecks_protection_and_ownership_before_payment():
    buyer = source("mods/hwplib/scripts/Town/EquipmentBuyer.as")
    buy = buyer.split("bool Buy(", 1)[1].split("array<IShopItem@> GetItems", 1)[0]
    assert buy.index("Favorites::Protected(eqItem)") < buy.index("equipInventory.Remove(eqItem)") < buy.index("cost.Spend(m_player)")
    assert "if (!m_player.equipInventory.Remove(eqItem))" in buy
    rows, available = buyer.split("array<IShopItem@> GetItems", 1)[1].split("bool IsAvailable", 1)
    assert rows.index("Favorites::Protected(item)") < rows.index("ret.insertLast(")
    assert "!HWP::Favorites::Protected(m_item)" in available
    assert "findByRef(m_item) >= 0" in available


def test_state_lives_on_the_owned_item_not_a_hash_or_global_reference_list():
    item = source("mods/hwplib/scripts/Items/Item.as")
    favorites = source("mods/hwplib/scripts/HWP/Core/Favorites.as")
    assert "bool m_hwpFavorite = false;" in item
    assert "return item !is null && item.m_hwpFavorite;" in favorites
    assert "item.m_hwpFavorite = favorite;" in favorites
    assert "array<Equipment::Equipment@> g_" not in favorites


def test_all_favorite_empty_state_explains_protection_and_how_to_sell():
    buyer = source("mods/hwplib/scripts/Town/EquipmentBuyer.as")
    empty = buyer.split("string GetEmptyShopText() override", 1)[1].split("bool Buy(", 1)[0]
    assert "HWP::Favorites::Enabled() && m_player !is null" in empty
    assert "if (item is null)" in empty
    assert 'bool hasFavorites = false;' in empty
    assert 'if (!HWP::Favorites::Protected(item))\n\t\t\t\t\treturn ".npc.shop.equip.sell.empty";' in empty
    assert 'if (hasFavorites)\n\t\t\t\treturn ".hwp.favorites.empty";' in empty
    assert empty.rstrip().endswith('return ".npc.shop.equip.sell.empty";\n\t}')
    lang = ET.fromstring(source("mods/favorites/res/language/english/hwp_favorites.lang"))
    texts = {node.attrib["name"]: node.text for node in lang}
    assert texts["hwp.favorites.empty"] == (
        "All your bag equipment is favorited and protected from selling. "
        "Unfavorite an item in your inventory to sell it."
    )


@pytest.mark.parametrize("event,call", [
    ("PlayerRecordSave", "SavePlayer(record, bag)"),
    ("PlayerRecordLoad", "LoadPlayer(record, bag)"),
    ("TownRecordSave", "SaveTown(town, bag)"),
    ("TownRecordLoad", "LoadTown(town, bag)"),
])
def test_sidecar_is_updated_inside_the_save_data_owner(event, call):
    data = source("mods/hwplib/scripts/HWP/Core/SaveData.as")
    hook = data.split(f"void {event}(", 1)[1].split("\n\t}", 1)[0]
    assert f"HWP::Favorites::{call}" in hook
    if "Save" in event:
        assert hook.index(call) < hook.index("bag.Save(builder)")
    else:
        assert hook.index("bag.Load(data)") < hook.index(call)


def test_restoration_checks_slot_type_bounds_and_item_snapshot():
    favorites = source("mods/hwplib/scripts/HWP/Core/Favorites.as")
    load = favorites.split("void LoadItems(", 1)[1].split("void SavePlayer", 1)[0]
    for guard in ("saved.GetType() != SValueType::Array", "entry.length() != 2",
                  "entry[0].GetType() != SValueType::Integer", "index < 0",
                  "index >= int(items.length())", "items[index] is null", "Same(entry[1], current)"):
        assert guard in load
    assert load.index("Same(entry[1], current)") < load.index("Set(items[index], true)")
    assert "current.Delete();" in load


def test_unique_definitions_are_copied_at_lookup_and_bag_admission():
    item = source("mods/hwplib/scripts/Items/Item.as")
    unique = source("mods/hwplib/scripts/Items/UniqueEquipment.as")
    inventory = source("mods/hwplib/scripts/GUI/Widgets/EquipmentInventoryWidget.as")
    assert len(re.findall(r"@ret = Equipment::UniqueEquipment::Get\(idh\);\s*if \(ret !is null\)\s*return ret.Copy\(\);", item)) == 2
    copy = unique.split("Item::Item@ Copy()", 1)[1].split("void Save(", 1)[0]
    assert "auto item = UniqueEquipment();" in copy and "item = this;" in copy
    assert "Item::Get(" not in copy
    add = inventory.split("void Add(", 1)[1].split("bool Remove(", 1)[0]
    assert "unique is Equipment::UniqueEquipment::Get(unique.m_idHash)" in add
    assert "unique.Copy()" in add


def test_item_serialization_stays_vanilla():
    for name in ("Item.as", "UniqueEquipment.as"):
        current = (LIB / "scripts/Items" / name).read_text(encoding="utf-8")
        original = (LIB / "scripts/Items" / (name + ".orig")).read_text(encoding="utf-8")
        # Complete SaveItem/Save bodies are unchanged; favorites are in record sidecars.
        start = "void SaveItem(" if name == "Item.as" else "void Save("
        assert current.split(start, 1)[1].split("\n\t\t}", 1)[0] == original.split(start, 1)[1].split("\n\t\t}", 1)[0]


def test_weapon_swap_persists_and_restores_favorite_metadata():
    swap = source("mods/weaponswap/scripts/HWP/WeaponSwap/WeaponSwapModule.as")
    assert 'Bag().SetBool(key + ".favorite", HWP::Favorites::Has(item));' in swap
    for hand in ("Main", "Off"):
        line = f'HWP::Favorites::Set(alt{hand}, Bag().GetBool(KEY_{hand.upper()} + ".favorite", false));'
        assert swap.count(line) == 2  # swapping into hand and returning to the bag


def test_action_uses_existing_hint_key_and_settings_paths():
    action = source("mods/favorites/scripts/HWP/Favorites/FavoritesModule.as")
    assert 'super("favorites.key", 9)' in action
    assert 'string Id() override { return "favorite"; }' in action
    assert "ItemActions::Register(action)" in action
    assert 'Options::Register("favoritekey"' in action
    assert 'Settings::GetBool("favorites.enabled", true)' in action
    assert "Commands::OnSettingChanged" in action
    lang = ET.fromstring(source("mods/favorites/res/language/english/hwp_favorites.lang"))
    texts = {node.attrib["name"]: node.text for node in lang}
    assert texts["hwp.favorites.add"] == "Favorite"
    assert texts["hwp.favorites.remove"] == "Unfavorite"


def test_new_overrides_have_pristine_upstream_copies():
    overrides = json.loads((LIB / "module.json").read_text())["overrides"]
    for path in ("scripts/Town/EquipmentBuyer.as", "scripts/Items/Item.as",
                 "scripts/Items/UniqueEquipment.as", "scripts/GUI/Widgets/EquipmentInventoryWidget.as"):
        assert path in overrides
        original = LIB / (path + ".orig")
        assert original.is_file()
        sdk = ROOT / "gamecode/sdk/hoh2" / path
        if sdk.is_file():
            assert original.read_bytes() == sdk.read_bytes()


def test_controlled_engine_scenario_is_explicit_and_not_shipped():
    scenario = json.loads(source("gamelab/scenarios/fix-favorites.json"))
    assert "gamelab-it-favorites" in scenario["mods"]
    assert scenario["steps"][0]["expect"] == "finished 19 checks, 0 failed"
    module = json.loads(source("mods/gamelab-it-favorites/module.json"))
    assert module["gamelab"] is True


def test_pr_screenshot_scenario_uses_the_inventory_hint_before_capture():
    scenario = json.loads(source("gamelab/scenarios/look-favorites.json"))
    assert set(scenario["mods"]) == {"favorites", "gamelab-hands"}
    steps = scenario["steps"]
    click = next(i for i, step in enumerate(steps) if step.get("verb") == "navbar")
    capture = next(i for i, step in enumerate(steps) if step["do"] == "shot")
    assert steps[click]["args"] == ["click", "4"]
    assert steps[click]["expect"] == {"handler": True}
    assert click < capture
    assert any(step["do"] == "log_has" and "favorited " in step["pattern"] for step in steps[click:capture])
