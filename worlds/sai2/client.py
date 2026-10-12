from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from NetUtils import ClientStatus
import worlds._bizhawk as bizhawk
from worlds._bizhawk.client import BizHawkClient
from worlds.AutoSNIClient import SNES_READ_CHUNK_SIZE, SNIClient

from .Multiworld import (
    ITEM_NONE,
    MAILBOX_ITEM,
    MAILBOX_MESSAGE,
    MAILBOX_STATE,
    RECEIVED_COUNT,
    received_message,
)

if TYPE_CHECKING:
    from SNIClient import SNIContext
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

# SNI/FXPak address space (worlds.smw conventions): WRAM $7E:xxxx -> $F5xxxx,
# ROM is read by plain file offset.
SNI_WRAM_START = 0xF50000


class SAI2ClientLogic:
    """Transport-agnostic SAI2 client logic.

    The ROM does all the real work (mailbox item display, check flags,
    event completion). The client only reads/writes WRAM and the embedded
    AP table, so the BizHawk connector and SNI versions below share
    everything except the memory access primitives.
    """

    # -- transport interface -------------------------------------------

    async def read_rom(self, ctx, offset: int, size: int) -> bytes | None:
        raise NotImplementedError

    async def read_wram(self, ctx, offset: int, size: int) -> bytes | None:
        raise NotImplementedError

    async def write_wram(self, ctx, writes: list[tuple[int, bytes]]) -> bool:
        raise NotImplementedError

    async def read_wram_multi(self, ctx, reads: list[tuple[int, int]]) -> list[bytes] | None:
        raise NotImplementedError

    async def read_check_flags(self, ctx, memory_ids: list[int]) -> list[int] | None:
        """Return the byte at each WRAM address in memory_ids (same order)."""
        raise NotImplementedError

    # -- shared state ----------------------------------------------------

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

    def reset_connection_state(self) -> None:
        """Called when a (new) ROM is accepted."""
        self.reported_checks = set()
        self.awarded_events = set()
        self.reset_goal_state()

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

    # -- shared protocol -------------------------------------------------

    async def _read_check_table(self, ctx) -> dict[int, int] | None:
        header = await self.read_rom(ctx, AP_TABLE_OFFSET, AP_TABLE_HEADER_SIZE)
        if header is None or header[:8] != AP_TABLE_SIGNATURE:
            return None

        count = int.from_bytes(header[8:10], "little")
        if count != EXPECTED_CHECK_COUNT:
            logger.error(f"[SAI2] Invalid AP check table count: {count}, expected {EXPECTED_CHECK_COUNT}")
            return None

        raw = await self.read_rom(ctx, AP_TABLE_OFFSET + AP_TABLE_HEADER_SIZE, count * AP_TABLE_ENTRY_SIZE)
        if raw is None:
            return None

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
        # Seed-unique identity, used as the SNI auth token (ctx.rom).
        self.table_identity = header + raw
        return check_map

    async def _watcher_body(self, ctx) -> None:
        if not self.check_map:
            return

        # -------------------------------------------------
        # Receive AP items (v15 mailbox).
        # RECEIVED_COUNT lives in the saved WRAM block, so it is the
        # truth for "how many items this save file already got". When
        # the mailbox is idle, queue the next one; the ROM gives it and
        # plays the AP item animation once the player can act.
        # -------------------------------------------------
        reads = await self.read_wram_multi(
            ctx, [(MAILBOX_STATE, 2), (RECEIVED_COUNT, 2)]
        )
        if reads is None:
            return
        mailbox_state = int.from_bytes(reads[0], "little")
        applied = int.from_bytes(reads[1], "little")

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

            if not await self.write_wram(ctx, [
                (MAILBOX_ITEM, value.to_bytes(2, "little")),
                (MAILBOX_MESSAGE, received_message(item_name, sender)),
                (MAILBOX_STATE, (1).to_bytes(2, "little")),
            ]):
                return
            logger.info(f"[SAI2] ITEM QUEUED #{applied + 1}: {item_name} from {sender}")

        # -------------------------------------------------
        # Send location checks.
        # -------------------------------------------------
        memory_ids = sorted(self.check_map)
        values = await self.read_check_flags(ctx, memory_ids)
        if values is None:
            return

        checked_location_ids = {
            self.check_map[memory_id]
            for memory_id, value in zip(memory_ids, values)
            if value != 0
        }

        # Event scripts now write only the physical completion flag.
        # Award the local event reward separately; remote events have no reward.
        for memory_id, reward_id in self.event_rewards.items():
            if memory_id in self.awarded_events:
                continue
            if self.check_map[memory_id] not in checked_location_ids:
                continue
            if 0x044E <= reward_id <= 0x047F:
                if not await self.write_wram(ctx, [(reward_id, b"\x01")]):
                    return
                logger.info(f"[SAI2] EVENT LOCAL REWARD: 0x{reward_id:04X}")
            else:
                logger.error(f"[SAI2] Unsupported event local reward 0x{reward_id:04X}")
            self.awarded_events.add(memory_id)

        ctx.locations_checked.update(checked_location_ids)

        # -------------------------------------------------
        # Victory.
        # -------------------------------------------------
        if not ctx.finished_game:
            goal_reads = await self.read_wram_multi(
                ctx,
                [(GAME_MODE_ADDR, 1), (ENDING_ADDR, 1), (GOAL_DEBUG_FLAG_ADDR, 1)],
            )
            if goal_reads is None:
                return
            if goal_reads[2][0] == 0x01 or self.update_goal(goal_reads[0][0], goal_reads[1][0]):
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


class SuperAdventureIslandIIClient(SAI2ClientLogic, BizHawkClient):
    """BizHawk transport (connector_bizhawk_generic.lua)."""

    game = "Super Adventure Island II"
    system = "SNES"
    patch_suffix = None

    async def read_rom(self, ctx: "BizHawkClientContext", offset: int, size: int) -> bytes | None:
        try:
            return (await bizhawk.read(ctx.bizhawk_ctx, [(offset, size, "ROM")]))[0]
        except (bizhawk.RequestFailedError, bizhawk.ConnectorError, bizhawk.SyncError):
            return None

    async def read_wram(self, ctx: "BizHawkClientContext", offset: int, size: int) -> bytes | None:
        try:
            return (await bizhawk.read(ctx.bizhawk_ctx, [(offset, size, "WRAM")]))[0]
        except (bizhawk.RequestFailedError, bizhawk.ConnectorError, bizhawk.SyncError):
            return None

    async def write_wram(self, ctx: "BizHawkClientContext", writes: list[tuple[int, bytes]]) -> bool:
        try:
            await bizhawk.write(ctx.bizhawk_ctx, [(a, d, "WRAM") for a, d in writes])
            return True
        except (bizhawk.RequestFailedError, bizhawk.ConnectorError, bizhawk.SyncError):
            return False

    async def read_wram_multi(
        self, ctx: "BizHawkClientContext", reads: list[tuple[int, int]]
    ) -> list[bytes] | None:
        try:
            return await bizhawk.read(ctx.bizhawk_ctx, [(a, s, "WRAM") for a, s in reads])
        except (bizhawk.RequestFailedError, bizhawk.ConnectorError, bizhawk.SyncError):
            return None

    async def read_check_flags(
        self, ctx: "BizHawkClientContext", memory_ids: list[int]
    ) -> list[int] | None:
        try:
            values = await bizhawk.read(
                ctx.bizhawk_ctx, [(memory_id, 1, "WRAM") for memory_id in memory_ids]
            )
            return [value[0] for value in values]
        except (bizhawk.RequestFailedError, bizhawk.ConnectorError, bizhawk.SyncError):
            return None

    async def validate_rom(self, ctx: "BizHawkClientContext") -> bool:
        check_map = await self._read_check_table(ctx)
        if check_map is None:
            return False

        self.check_map = check_map
        self.reset_connection_state()

        ctx.game = self.game

        # Receive remote items + starting inventory, but not local items.
        # Local items are awarded by the SAI2 ROM itself (chests/events).
        ctx.items_handling = 0b101
        ctx.want_slot_data = False
        ctx.watcher_timeout = 0.125

        logger.info(f"[SAI2] ROM recognized. Loaded {len(self.check_map)} seed-specific checks.")
        return True

    async def game_watcher(self, ctx: "BizHawkClientContext") -> None:
        await self._watcher_body(ctx)


class SuperAdventureIslandIISNIClient(SAI2ClientLogic, SNIClient):
    """SNI transport: snes9x-nwa, RetroArch, BizHawk via SNI's Connector.lua,
    or real hardware (FXPakPro/SD2SNES). Same protocol as the BizHawk client.
    """

    game = "Super Adventure Island II"

    async def read_rom(self, ctx: "SNIContext", offset: int, size: int) -> bytes | None:
        from SNIClient import snes_read
        return await snes_read(ctx, offset, size)

    async def read_wram(self, ctx: "SNIContext", offset: int, size: int) -> bytes | None:
        from SNIClient import snes_read
        return await snes_read(ctx, SNI_WRAM_START + offset, size)

    async def write_wram(self, ctx: "SNIContext", writes: list[tuple[int, bytes]]) -> bool:
        from SNIClient import snes_write
        return await snes_write(ctx, [(SNI_WRAM_START + a, d) for a, d in writes])

    async def read_wram_multi(
        self, ctx: "SNIContext", reads: list[tuple[int, int]]
    ) -> list[bytes] | None:
        from SNIClient import snes_read
        out: list[bytes] = []
        for offset, size in reads:
            data = await snes_read(ctx, SNI_WRAM_START + offset, size)
            if data is None:
                return None
            out.append(data)
        return out

    async def read_check_flags(
        self, ctx: "SNIContext", memory_ids: list[int]
    ) -> list[int] | None:
        from SNIClient import snes_read
        # One span read chunked at SNES_READ_CHUNK_SIZE beats 68 roundtrips.
        lo, hi = min(memory_ids), max(memory_ids) + 1
        buf = bytearray()
        pos = lo
        while pos < hi:
            chunk = min(SNES_READ_CHUNK_SIZE, hi - pos)
            data = await snes_read(ctx, SNI_WRAM_START + pos, chunk)
            if data is None:
                return None
            buf += data
            pos += chunk
        return [buf[memory_id - lo] for memory_id in memory_ids]

    async def validate_rom(self, ctx: "SNIContext") -> bool:
        # Runs every watcher tick on SNI: keep it cheap and idempotent.
        check_map = await self._read_check_table(ctx)
        if check_map is None:
            return False

        # ctx.rom is the per-seed identity (auth token); the embedded check
        # table is unique per generated ROM.
        if self.check_map != check_map:
            self.check_map = check_map
            self.reset_connection_state()
            logger.info(f"[SAI2] ROM recognized. Loaded {len(self.check_map)} seed-specific checks.")

        ctx.rom = self.table_identity
        ctx.game = self.game
        ctx.items_handling = 0b101
        ctx.want_slot_data = False
        return True

    async def game_watcher(self, ctx: "SNIContext") -> None:
        await self._watcher_body(ctx)
