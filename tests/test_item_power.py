import pytest

from tools.devarena.item_power import crit_factor, effective_health, item_share, power_ratio


def test_power_is_relative_to_existing_power():
    assert power_ratio(0, 40) == pytest.approx(1.2)
    assert power_ratio(200, 40) == pytest.approx(1.1)


def test_crit_chances_use_complement_product():
    # INT 100 gives 15% crit. Another 10% source produces 23.5%, not 25%.
    damage = 0.8 * 0.7 + 0.2 * 1.7
    assert crit_factor(100, 0.1, spell=True) == pytest.approx(1 + 0.235 * (0.5 + damage))


def test_no_crit_attribute():
    assert crit_factor(0) == 1
    assert crit_factor(0, 0.1, 0.2) == pytest.approx(1.07)


@pytest.mark.parametrize("armor, expected", [(0, 100), (200, 200), (-100, 100 / 1.5)])
def test_armor_effective_health(armor, expected):
    assert effective_health(100, armor) == pytest.approx(expected)


def test_removal_attribution_is_not_percent_increase():
    assert item_share(2) == 0.5
    assert item_share(1.5) == pytest.approx(1 / 3)
