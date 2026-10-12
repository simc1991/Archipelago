import asyncio
import unittest
from types import SimpleNamespace
from unittest import mock

from NetUtils import ClientStatus

from .. import client as sai2_client
from ..client import (
    ENDING_ADDR,
    ENDING_POLLS_REQUIRED,
    ENDING_VALUE,
    GAME_MODE_ADDR,
    GOAL_DEBUG_FLAG_ADDR,
    MODE_ENDING,
    MODE_FINAL_BOSS,
    MODE_TITLE,
    SuperAdventureIslandIIClient,
)

CHEST_MEMORY = 0x0490
CHEST_LOCATION = 0x53414A06


class TestGoalStateMachine(unittest.TestCase):
    def setUp(self) -> None:
        self.client = SuperAdventureIslandIIClient()

    def run_frames(self, mode: int, value: int, polls: int) -> bool:
        return any([self.client.update_goal(mode, value) for _ in range(polls)])

    def test_full_ending_triggers_goal(self) -> None:
        self.assertFalse(self.run_frames(MODE_FINAL_BOSS, 0x00, 3))
        self.assertTrue(self.run_frames(MODE_ENDING, ENDING_VALUE, ENDING_POLLS_REQUIRED))

    def test_ending_without_final_boss_does_not_trigger(self) -> None:
        self.assertFalse(self.run_frames(MODE_ENDING, ENDING_VALUE, 50))

    def test_too_short_ending_does_not_trigger(self) -> None:
        self.run_frames(MODE_FINAL_BOSS, 0x00, 1)
        self.assertFalse(self.run_frames(MODE_ENDING, ENDING_VALUE, ENDING_POLLS_REQUIRED - 1))

    def test_title_screen_resets(self) -> None:
        self.run_frames(MODE_FINAL_BOSS, 0x00, 1)
        self.run_frames(MODE_ENDING, ENDING_VALUE, ENDING_POLLS_REQUIRED - 1)
        self.run_frames(MODE_TITLE, 0x00, 1)
        self.assertFalse(self.run_frames(MODE_ENDING, ENDING_VALUE, ENDING_POLLS_REQUIRED - 1))


class FakeContext:
    def __init__(self) -> None:
        self.bizhawk_ctx = object()
        self.items_received = []
        self.locations_checked = set()
        self.finished_game = False
        self.sent_messages = []
        self.location_names = SimpleNamespace(lookup_in_game=lambda location_id: str(location_id))

    async def send_msgs(self, messages) -> None:
        self.sent_messages.extend(messages)

    async def check_locations(self, locations):
        return set(locations)


class TestGameWatcherGoal(unittest.TestCase):
    def setUp(self) -> None:
        self.client = SuperAdventureIslandIIClient()
        self.client.check_map = {CHEST_MEMORY: CHEST_LOCATION}
        self.ctx = FakeContext()
        self.wram = bytearray(0x2000)

    async def fake_read(self, _ctx, requests):
        return [bytes(self.wram[address:address + size]) for address, size, _domain in requests]

    def poll(self, times: int = 1) -> None:
        async def run() -> None:
            with mock.patch.object(sai2_client.bizhawk, "read", self.fake_read):
                for _ in range(times):
                    await self.client.game_watcher(self.ctx)
        asyncio.run(run())

    def goal_messages(self) -> list:
        return [m for m in self.ctx.sent_messages if m.get("status") == ClientStatus.CLIENT_GOAL]

    def test_goal_sent_once_after_ending(self) -> None:
        self.wram[GAME_MODE_ADDR] = MODE_FINAL_BOSS
        self.poll(5)
        self.assertEqual(self.goal_messages(), [])

        self.wram[GAME_MODE_ADDR] = MODE_ENDING
        self.wram[ENDING_ADDR] = ENDING_VALUE
        self.poll(ENDING_POLLS_REQUIRED + 5)

        self.assertTrue(self.ctx.finished_game)
        self.assertEqual(len(self.goal_messages()), 1)

    def test_debug_flag_reports_goal(self) -> None:
        self.wram[GOAL_DEBUG_FLAG_ADDR] = 1
        self.poll(2)
        self.assertTrue(self.ctx.finished_game)
        self.assertEqual(len(self.goal_messages()), 1)

    def test_goal_is_independent_of_new_checks(self) -> None:
        self.wram[CHEST_MEMORY] = 1
        self.poll(1)
        self.assertIn(CHEST_LOCATION, self.ctx.locations_checked)
        self.wram[GAME_MODE_ADDR] = MODE_FINAL_BOSS
        self.poll(1)
        self.wram[GAME_MODE_ADDR] = MODE_ENDING
        self.wram[ENDING_ADDR] = ENDING_VALUE
        self.poll(ENDING_POLLS_REQUIRED)
        self.assertTrue(self.ctx.finished_game)
