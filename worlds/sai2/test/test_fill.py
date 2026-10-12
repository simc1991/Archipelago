import unittest

from BaseClasses import ItemClassification

from .. import COMMON_REWARDS, VANILLA_LOCKED_ITEMS
from ..Rom import EVENT_LOCATION_ITEMS
from ..tools.fill_stress import check_seed
from . import SAI2TestBase

SOLO_SEEDS = range(1, 101)


class TestFillReliability(unittest.TestCase):
    def test_solo_seeds_always_fill(self) -> None:
        failures = {seed: reason for seed in SOLO_SEEDS if (reason := check_seed(seed))}
        self.assertEqual(failures, {}, f"{len(failures)}/{len(SOLO_SEEDS)} seeds failed")


class TestEventPlacement(SAI2TestBase):
    def test_events_filled_without_common_rewards(self) -> None:
        for name in EVENT_LOCATION_ITEMS:
            item = self.multiworld.get_location(name, self.player).item
            with self.subTest(location=name):
                self.assertIsNotNone(item)
                self.assertNotIn(item.name, COMMON_REWARDS)

    def test_vanilla_locked_items(self) -> None:
        for location_name, item_name in VANILLA_LOCKED_ITEMS.items():
            self.assertEqual(self.multiworld.get_location(location_name, self.player).item.name, item_name)

    def test_only_one_progression_copy_of_repeatable_rewards(self) -> None:
        all_items = self.multiworld.itempool + [
            location.item for location in self.multiworld.get_locations(self.player) if location.item
        ]
        for name in ("Life Bottle", "500 Coins", "1000 Coins"):
            with self.subTest(item=name):
                self.assertEqual(sum(1 for i in all_items if i.name == name and i.advancement), 1)


class TestSelfLockPrevention(SAI2TestBase):
    """A progression item must never be placed behind a check that needs it.

    Regression: a generated seed once put the Sun Stone on 'Sala Isle - Magic FE683',
    which needs Shove -> Sun Stone, making the game unbeatable."""

    def test_sun_stone_cannot_fill_shove_gated_chest(self) -> None:
        from Fill import sweep_from_pool
        state = sweep_from_pool(self.multiworld.state)
        location = self.multiworld.get_location("Sala Isle - Magic FE683", self.player)
        sun_stone = self.multiworld.worlds[self.player].create_item("Sun Stone")
        self.assertFalse(location.can_fill(state, sun_stone, check_access=True))

    def test_aqua_stone_cannot_fill_sala_chest(self) -> None:
        from Fill import sweep_from_pool
        state = sweep_from_pool(self.multiworld.state)
        location = self.multiworld.get_location("Sala Isle - Magic FE69A", self.player)
        aqua_stone = self.multiworld.worlds[self.player].create_item("Aqua Stone")
        self.assertFalse(location.can_fill(state, aqua_stone, check_access=True))

    def test_filler_copies_still_fill_everywhere(self) -> None:
        from Fill import sweep_from_pool
        state = sweep_from_pool(self.multiworld.state)
        location = self.multiworld.get_location("Sala Isle - Magic FE69A", self.player)
        life_bottle = self.multiworld.worlds[self.player].create_item(
            "Life Bottle", ItemClassification.useful)
        self.assertTrue(location.can_fill(state, life_bottle, check_access=True))
