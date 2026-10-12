import asyncio
import unittest
from types import SimpleNamespace
from unittest import mock

from NetUtils import ClientStatus

from .. import client as sai2_client
from ..Multiworld import (
    ITEM_NONE,
    MAILBOX_ITEM,
    MAILBOX_MESSAGE,
    MAILBOX_STATE,
    RECEIVED_COUNT,
    received_message,
)
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
ITEM_NAMES = {100: "Aqua Stone", 101: "1000 Coins", 102: "Victory"}


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
        self.item_names = SimpleNamespace(lookup_in_game=lambda item_id: ITEM_NAMES[item_id])
        self.player_names = {1: "Simon", 2: "Link"}

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

    async def fake_write(self, _ctx, writes):
        for address, data, _domain in writes:
            self.wram[address:address + len(data)] = bytes(data)

    def poll(self, times: int = 1) -> None:
        async def run() -> None:
            with mock.patch.object(sai2_client.bizhawk, "read", self.fake_read), \
                    mock.patch.object(sai2_client.bizhawk, "write", self.fake_write):
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


class TestReceiveMailbox(TestGameWatcherGoal):
    def receive(self, item_id: int, player: int = 2) -> None:
        self.ctx.items_received.append(SimpleNamespace(item=item_id, player=player, location=1, flags=0))

    def mailbox(self) -> tuple[int, int]:
        state = int.from_bytes(self.wram[MAILBOX_STATE:MAILBOX_STATE + 2], "little")
        item = int.from_bytes(self.wram[MAILBOX_ITEM:MAILBOX_ITEM + 2], "little")
        return state, item

    def rom_finishes(self) -> None:
        """What the ROM does once the animation is over."""
        count = int.from_bytes(self.wram[RECEIVED_COUNT:RECEIVED_COUNT + 2], "little")
        self.wram[RECEIVED_COUNT:RECEIVED_COUNT + 2] = (count + 1).to_bytes(2, "little")
        self.wram[MAILBOX_STATE:MAILBOX_STATE + 2] = b"\x00\x00"

    def test_queues_item_with_message(self) -> None:
        self.receive(100)
        self.poll()
        self.assertEqual(self.mailbox(), (1, 0x046E))
        message = bytes(self.wram[MAILBOX_MESSAGE:MAILBOX_MESSAGE + 197])
        self.assertEqual(message, received_message("Aqua Stone", "Link"))

    def test_waits_while_rom_busy(self) -> None:
        self.receive(100)
        self.receive(101)
        self.poll(3)
        self.assertEqual(self.mailbox(), (1, 0x046E))
        self.rom_finishes()
        self.poll()
        self.assertEqual(self.mailbox(), (1, 0x0003))

    def test_save_counter_skips_already_received(self) -> None:
        self.receive(100)
        self.receive(101)
        self.wram[RECEIVED_COUNT:RECEIVED_COUNT + 2] = (2).to_bytes(2, "little")
        self.poll()
        self.assertEqual(self.mailbox()[0], 0)

    def test_unsupported_item_is_shown_not_given(self) -> None:
        self.receive(102, player=0)
        self.poll()
        self.assertEqual(self.mailbox(), (1, ITEM_NONE))
        message = bytes(self.wram[MAILBOX_MESSAGE:MAILBOX_MESSAGE + 197])
        self.assertEqual(message, received_message("Victory", "Archipelago"))
