from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from NetUtils import ClientStatus
import worlds._bizhawk as bizhawk
from worlds._bizhawk.client import BizHawkClient

from .Multiworld import (
    ITEM_NONE,
    MAILBOX_ITEM,
    MAILBOX_MESSAGE,
    MAILBOX_STATE,
    RECEIVED_COUNT,
    received_message,
)

if TYPE_CHECKING:
    from worlds._bizhawk.context import BizHawkClientContext

logger = logging.getLogger("Client")

AP_TABLE_OFFSET = 0x17B300
AP_TABLE_SIGNATURE = b"SAI2AP03"  # v15 multiworld ROM
AP_TABLE_HEADER_SIZE = 10
AP_TABLE_ENTRY_SIZE = 8
EXPECTED_CHECK_COUNT = 68

# Victory condition, from RetroAchievements #37019 "Save the Girl!":
#   $00D3 == 0x06 at least once        (final boss sequence)
#   Reset if $00D3 == 0x01             (title screen)
#   $00D3 == 0x03 and $0010 == 0xB0    for 50 frames (ending)
# The client polls about every 0.125 s (~7.5 frames), so 7 polls ~ 50 frames.
GAME_MODE_ADDR = 0x00D3
ENDING_ADDR = 0x0010
# Debug/testing hook: writing 1 here (tools/sai2_debug.lua "V" key) forces the
# goal report without corrupting the game. Sits in the event-flag WRAM range.
GOAL_DEBUG_FLAG_ADDR = 0x1E9F
MODE_TITLE = 0x01
MODE_ENDING = 0x03
MODE_FINAL_BOSS = 0x06
ENDING_VALUE = 0xB0
ENDING_POLLS_REQUIRED = 7


class SuperAdventureIslandIIClient(BizHawkClient):
    game = "Super Adventure Island II"
    system = "SNES"
    patch_suffix = None

    def __init__(self) -> None:
        super().__init__()
        self.check_map: dict[int, int] = {}
        self.event_rewards: dict[int, int] = {}
        self.awarded_events: set[int] = set()
        self.reported_checks: set[int] = set()
        self.reset_goal_state()

    @staticmethod
    def mailbox_item_value(item_name: str) -> int:
        """Value the ROM gives: WRAM flag address, common reward 0-5, or ITEM_NONE."""
        from .Items import item_table
        data = item_table.get(item_name)
        if data is None or data.rom_id is None:
            return ITEM_NONE
        return data.rom_id

    def reset_goal_state(self) -> None:
        self.final_boss_seen = False
        self.ending_polls = 0

    def update_goal(self, game_mode: int, ending_value: int) -> bool:
        """Advance the RetroAchievements-style victory state machine. Return True once reached."""
        if game_mode == MODE_TITLE:
            self.reset_goal_state()
            return False
        if game_mode == MODE_FINAL_BOSS:
            self.final_boss_seen = True
        if ending_value == ENDING_VALUE:
            self.ending_polls += 1
        return (
            self.final_boss_seen
            and game_mode == MODE_ENDING
            and self.ending_polls >= ENDING_POLLS_REQUIRED
        )

    async def _read_check_table(self, ctx: "BizHawkClientContext") -> dict[int, int] | None:
        header = (await bizhawk.read(
            ctx.bizhawk_ctx,
            [(AP_TABLE_OFFSET, AP_TABLE_HEADER_SIZE, "ROM")],
        ))[0]

        if header[:8] != AP_TABLE_SIGNATURE:
            return None

        count = int.from_bytes(header[8:10], "little")
        if count != EXPECTED_CHECK_COUNT:
            logger.error(f"[SAI2] Invalid AP check table count: {count}, expected {EXPECTED_CHECK_COUNT}")
            return None

        raw = (await bizhawk.read(
            ctx.bizhawk_ctx,
            [(AP_TABLE_OFFSET + AP_TABLE_HEADER_SIZE, count * AP_TABLE_ENTRY_SIZE, "ROM")],
        ))[0]

        check_map: dict[int, int] = {}
        event_rewards: dict[int, int] = {}
        for index in range(count):
            offset = index * AP_TABLE_ENTRY_SIZE
            memory_id = int.from_bytes(raw[offset:offset + 2], "little")
            location_id = int.from_bytes(raw[offset + 2:offset + 6], "little")

            reward_id = int.from_bytes(raw[offset + 6:offset + 8], "little")
            if reward_id != 0xFFFF:
                event_rewards[memory_id] = reward_id

            if memory_id in check_map:
                logger.error(f"[SAI2] Duplicate check memory in ROM table: 0x{memory_id:04X}")
                return None

            check_map[memory_id] = location_id

        self.event_rewards = event_rewards
        return check_map

    async def validate_rom(self, ctx: "BizHawkClientContext") -> bool:
        try:
            check_map = await self._read_check_table(ctx)
            if check_map is None:
                return False
        except (bizhawk.RequestFailedError, bizhawk.ConnectorError, bizhawk.SyncError):
            return False

        self.check_map = check_map
        self.reported_checks = set()
        self.awarded_events = set()
        self.reset_goal_state()

        ctx.game = self.game

        # Receive remote items + starting inventory, but not local items.
        # Local items are awarded by the SAI2 ROM itself (chests/events).
        ctx.items_handling = 0b101
        ctx.want_slot_data = False
        ctx.watcher_timeout = 0.125

        logger.info(f"[SAI2] ROM recognized. Loaded {len(self.check_map)} seed-specific checks.")
        return True

    async def game_watcher(self, ctx: "BizHawkClientContext") -> None:
        if not self.check_map:
            return

        try:
            # -------------------------------------------------
            # Receive AP items (v15 mailbox).
            # RECEIVED_COUNT lives in the saved WRAM block, so it is the
            # truth for "how many items this save file already got". When
            # the mailbox is idle, queue the next one; the ROM gives it and
            # plays the AP item animation once the player can act.
            # -------------------------------------------------
            state_raw, count_raw = await bizhawk.read(
                ctx.bizhawk_ctx,
                [(MAILBOX_STATE, 2, "WRAM"), (RECEIVED_COUNT, 2, "WRAM")],
            )
            mailbox_state = int.from_bytes(state_raw, "little")
            applied = int.from_bytes(count_raw, "little")

            if mailbox_state == 0 and applied < len(ctx.items_received):
                network_item = ctx.items_received[applied]
                try:
                    item_name = ctx.item_names.lookup_in_game(network_item.item)
                except Exception:
                    item_name = str(network_item.item)
                sender = ctx.player_names.get(network_item.player, "Archipelago")
                value = self.mailbox_item_value(item_name)
                if value == ITEM_NONE:
                    logger.warning(f"[SAI2] RECEIVE UNSUPPORTED: {item_name} (shown, not given)")

                await bizhawk.write(ctx.bizhawk_ctx, [
                    (MAILBOX_ITEM, value.to_bytes(2, "little"), "WRAM"),
                    (MAILBOX_MESSAGE, received_message(item_name, sender), "WRAM"),
                    (MAILBOX_STATE, (1).to_bytes(2, "little"), "WRAM"),
                ])
                logger.info(f"[SAI2] ITEM QUEUED #{applied + 1}: {item_name} from {sender}")

            # -------------------------------------------------
            # Send location checks.
            # -------------------------------------------------
            memory_ids = sorted(self.check_map)

            values = await bizhawk.read(
                ctx.bizhawk_ctx,
                [(memory_id, 1, "WRAM") for memory_id in memory_ids],
            )

            checked_location_ids = {
                self.check_map[memory_id]
                for memory_id, value in zip(memory_ids, values)
                if value and value[0] != 0
            }

            # Event scripts now write only the physical completion flag.
            # Award the local event reward separately; remote events have no reward.
            for memory_id, reward_id in self.event_rewards.items():
                if memory_id in self.awarded_events:
                    continue
                if self.check_map[memory_id] not in checked_location_ids:
                    continue
                if 0x044E <= reward_id <= 0x047F:
                    await bizhawk.write(ctx.bizhawk_ctx, [(reward_id, [1], "WRAM")])
                    logger.info(f"[SAI2] EVENT LOCAL REWARD: 0x{reward_id:04X}")
                else:
                    logger.error(f"[SAI2] Unsupported event local reward 0x{reward_id:04X}")
                self.awarded_events.add(memory_id)

            ctx.locations_checked.update(checked_location_ids)

            # -------------------------------------------------
            # Victory.
            # -------------------------------------------------
            if not ctx.finished_game:
                game_mode, ending_value, goal_debug = await bizhawk.read(
                    ctx.bizhawk_ctx,
                    [
                        (GAME_MODE_ADDR, 1, "WRAM"),
                        (ENDING_ADDR, 1, "WRAM"),
                        (GOAL_DEBUG_FLAG_ADDR, 1, "WRAM"),
                    ],
                )
                if goal_debug[0] == 0x01 or self.update_goal(game_mode[0], ending_value[0]):
                    await ctx.send_msgs([{"cmd": "StatusUpdate", "status": ClientStatus.CLIENT_GOAL}])
                    ctx.finished_game = True
                    logger.info("[SAI2] VICTORY: goal sent to the server.")

            new_checks = checked_location_ids - self.reported_checks
            if not new_checks:
                return

            sent = await ctx.check_locations(new_checks)

            if sent:
                self.reported_checks.update(sent)

                for location_id in sorted(sent):
                    try:
                        location_name = ctx.location_names.lookup_in_game(location_id)
                    except Exception:
                        location_name = str(location_id)

                    logger.info(f"[SAI2] CHECK SENT: {location_name} ({location_id})")

        except (bizhawk.RequestFailedError, bizhawk.ConnectorError, bizhawk.SyncError):
            return
