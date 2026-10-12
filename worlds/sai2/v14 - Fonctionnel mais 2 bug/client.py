from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import worlds._bizhawk as bizhawk
from worlds._bizhawk.client import BizHawkClient

if TYPE_CHECKING:
    from worlds._bizhawk.context import BizHawkClientContext

logger = logging.getLogger("Client")

AP_TABLE_OFFSET = 0x17B300
AP_TABLE_SIGNATURE = b"SAI2AP02"
AP_TABLE_HEADER_SIZE = 10
AP_TABLE_ENTRY_SIZE = 8
EXPECTED_CHECK_COUNT = 68


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
        self.received_index = 0

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
        self.received_index = 0

        ctx.game = self.game

        # Receive remote items + starting inventory, but not local items.
        # Local items are still awarded directly by the current SAI2 ROM.
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
            # Receive AP items.
            # Test milestone: inventory/key-item flags only.
            # Common rewards are detected but not injected yet.
            # -------------------------------------------------
            while self.received_index < len(ctx.items_received):
                network_item = ctx.items_received[self.received_index]
                ap_item_id = network_item.item

                try:
                    item_name = ctx.item_names.lookup_in_game(ap_item_id)
                except Exception:
                    item_name = str(ap_item_id)

                from .Items import item_table
                item_data = item_table.get(item_name)

                if item_data is None or item_data.rom_id is None:
                    logger.warning(f"[SAI2] RECEIVE UNSUPPORTED: {item_name} (AP item {ap_item_id})")
                    self.received_index += 1
                    continue

                rom_id = item_data.rom_id

                # SAI2 persistent inventory/key-item/technique flags.
                if 0x044E <= rom_id <= 0x047F:
                    current = (await bizhawk.read(
                        ctx.bizhawk_ctx,
                        [(rom_id, 1, "WRAM")],
                    ))[0][0]

                    if current == 0:
                        await bizhawk.write(
                            ctx.bizhawk_ctx,
                            [(rom_id, [1], "WRAM")],
                        )

                    logger.info(f"[SAI2] ITEM RECEIVED: {item_name} (WRAM 0x{rom_id:04X})")
                    self.received_index += 1
                    continue

                if 0x0000 <= rom_id <= 0x0005:
                    logger.info(f"[SAI2] COMMON REWARD PENDING: {item_name}")
                    self.received_index += 1
                    continue

                logger.warning(f"[SAI2] RECEIVE UNKNOWN ROM ID: {item_name} -> 0x{rom_id:04X}")
                self.received_index += 1

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
