from pathlib import Path

from BaseClasses import Item, Location, ItemClassification, CollectionState
from Fill import FillError, fill_restrictive, sweep_from_pool
from worlds.AutoWorld import World, WebWorld

from .Items import (
    SAI2ItemData,
    item_name_to_id,
    item_table,
    item_pool,
)

from .Locations import location_name_to_id, location_table
from .Regions import create_regions
from .Rules import set_rules, set_self_lock_rules
from . import client  # register SAI2 BizHawk handler

from .Rom import (
    load_rom,
    save_rom,
    patch_standard_location,
    patch_event_location,
    patch_event_message,
    patch_event_memory,
    read_chest_data,
    build_unused_memory_pool,
    EVENT_LOCATION_ITEMS,
    EVENT_MESSAGE_ADDRESSES,
    EVENT_MEMORY_ADDRESSES,
    BOSS_MEMORY_ADDRESSES,
    patch_event_check_flag,
    EVENT_CHECK_FLAGS,
    LIGHT_SPELL_CHEST_CHECK_FLAG,
)


VANILLA_TECHNIQUES = {
    "Puka - Down Jab": "Down Jab",
    "Sala - Up Jab": "Up Jab",
    "Hiya - Shove": "Shove",
}

# With an empty inventory, the Silver Sword chest is the only reachable
# location, and only the Silver Sword opens anything further. It is therefore
# locked at its vanilla chest instead of being forced there by the fill.
VANILLA_LOCKED_ITEMS = {
    "Poka Isle - Silver Sword": "Silver Sword",
}

# Rewards that SAI2 event scripts cannot award.
COMMON_REWARDS = {
    "Life Bottle",
    "Magic",
    "500 Coins",
    "1000 Coins",
    "2000 Coins",
    "5000 Coins",
}

EVENT_FILL_ATTEMPTS = 50

# Logic only ever checks for one copy of these. Extra copies are demoted
# so the fill has far fewer progression items to place.
EXTRA_COPY_CLASSIFICATION = {
    "Life Bottle": ItemClassification.useful,
    "500 Coins": ItemClassification.filler,
    "1000 Coins": ItemClassification.filler,
}


class SAI2Item(Item):
    game = "Super Adventure Island II"


class SAI2Location(Location):
    game = "Super Adventure Island II"


class SAI2WebWorld(WebWorld):
    game = "Super Adventure Island II"


class SAI2World(World):
    """
    Super Adventure Island II Archipelago World.
    """

    game = "Super Adventure Island II"
    web = SAI2WebWorld()

    item_name_to_id = item_name_to_id
    location_name_to_id = location_name_to_id

    # ---------------------------------------------------------
    # Regions
    # ---------------------------------------------------------

    def create_regions(self) -> None:
        create_regions(self)

    # ---------------------------------------------------------
    # Items
    # ---------------------------------------------------------

    def create_item(self, name: str, classification: ItemClassification | None = None) -> SAI2Item:
        data: SAI2ItemData = item_table[name]

        return SAI2Item(
            name,
            data.classification if classification is None else classification,
            data.code,
            self.player,
        )

    def create_items(self) -> None:
        locked_items = set(VANILLA_TECHNIQUES.values()) | set(VANILLA_LOCKED_ITEMS.values())

        items = []
        for item_name in item_pool:
            if item_name in locked_items:
                continue
            already_created = any(item.name == item_name for item in items)
            items.append(self.create_item(
                item_name,
                EXTRA_COPY_CLASSIFICATION.get(item_name) if already_created else None,
            ))

        self.multiworld.itempool += items

        print(
            f"[SAI2] Randomized item pool: {len(items)} items "
            f"({len(locked_items)} locked vanilla)"
        )

    # ---------------------------------------------------------
    # Rules
    # ---------------------------------------------------------

    def set_rules(self) -> None:
        set_rules(self)

        # Native SAI2 event rewards cannot correctly award common rewards
        # (Life Bottle, Magic, Coins). Keep those rewards in standard chests
        # during Archipelago fill so AP placement and ROM placement stay identical.
        for location_name in EVENT_LOCATION_ITEMS:
            location = self.multiworld.get_location(location_name, self.player)
            old_rule = location.item_rule

            location.item_rule = (
                lambda item, old_rule=old_rule:
                    old_rule(item)
                    and not (
                        item.player == self.player
                        and item.name in COMMON_REWARDS
                    )
            )

    def pre_fill(self) -> None:
        # Event locations have a stricter item rule than standard chests, so
        # fill them first with this world's non-common items. Without this,
        # only common rewards could be left for the last event slots.
        # A random subset is used (one item per slot) so the other key items
        # stay in the logical state; failed attempts are undone and retried.
        multiworld = self.multiworld
        event_locations = [
            location for name in EVENT_LOCATION_ITEMS
            if (location := multiworld.get_location(name, self.player)).item is None
        ]
        candidates = [
            item for item in multiworld.itempool
            if item.player == self.player and item.name not in COMMON_REWARDS
        ]

        for _attempt in range(EVENT_FILL_ATTEMPTS):
            chosen = self.random.sample(candidates, len(event_locations))
            self._remove_from_pool(chosen)

            locations = event_locations.copy()
            self.random.shuffle(locations)
            unplaced = chosen.copy()
            state = sweep_from_pool(multiworld.state, multiworld.itempool)
            fill_restrictive(
                multiworld, state, locations, unplaced,
                single_player_placement=True, allow_partial=True, allow_excluded=True,
                name="SAI2 Event Locations",
            )
            multiworld.itempool += unplaced
            if not locations and self._progression_can_complete():
                for location in event_locations:
                    location.locked = True
                return

            placed = [item for item in chosen if item.location is not None]
            self._clear_locations(event_locations)
            multiworld.itempool += placed

        raise FillError(
            f"SAI2: could not fill the event locations after {EVENT_FILL_ATTEMPTS} attempts.",
            multiworld=multiworld,
        )

    def _remove_from_pool(self, items) -> None:
        # Items compare equal by name, so remove by identity (e.g. Life Bottle copies).
        removed = {id(item) for item in items}
        self.multiworld.itempool[:] = [item for item in self.multiworld.itempool if id(item) not in removed]

    @staticmethod
    def _clear_locations(locations) -> None:
        for location in locations:
            if location.item is not None:
                location.item.location = None
                location.item = None

    def _progression_can_complete(self) -> bool:
        """Trial-fill this world's remaining progression into its own empty
        locations, proving the current event placement is not a dead end.

        Solo game: a successful trial is kept (every item is local anyway),
        because AP's main fill can still randomly use up the few early-game
        chests. Multiworld: the trial is undone and AP's main fill is used."""
        multiworld = self.multiworld
        progression = [
            item for item in multiworld.itempool
            if item.player == self.player and item.advancement
        ]
        progression_ids = {id(item) for item in progression}
        locations = multiworld.get_unfilled_locations(self.player)
        self.random.shuffle(locations)
        others = [item for item in multiworld.itempool if id(item) not in progression_ids]
        state = sweep_from_pool(multiworld.state, others)
        trial_locations = locations.copy()
        unplaced = progression.copy()
        fill_restrictive(
            multiworld, state, trial_locations, unplaced,
            single_player_placement=True, allow_partial=True, allow_excluded=True,
            name="SAI2 Progression Trial",
        )
        if not unplaced:
            # Reverse fill can put an item behind a check that needs it:
            # its exploration state owns every unplaced item. Prove the
            # placement with a forward sweep from the empty inventory.
            forward = CollectionState(multiworld)
            forward.sweep_for_advancements()
            unplaced = progression if not (
                multiworld.has_beaten_game(forward)
                and all(location.can_reach(forward) for location in locations)
            ) else unplaced
        if not unplaced and multiworld.players == 1:
            self._remove_from_pool(progression)
            return True
        self._clear_locations(locations)
        return not unplaced


    # ---------------------------------------------------------
    # Victory
    # ---------------------------------------------------------

    def generate_basic(self) -> None:
        # Keep the three techniques at their vanilla locations.
        # They are deliberately excluded from the randomized item pool.
        for location_name, item_name in VANILLA_TECHNIQUES.items():
            technique_location = self.multiworld.get_location(
                location_name,
                self.player,
            )

            technique_location.place_locked_item(
                self.create_item(item_name)
            )

            print(
                f"[SAI2] VANILLA TECHNIQUE: "
                f"{location_name} -> {item_name}"
            )

        for location_name, item_name in VANILLA_LOCKED_ITEMS.items():
            self.multiworld.get_location(location_name, self.player).place_locked_item(
                self.create_item(item_name)
            )

        victory_location = self.multiworld.get_location(
            "Defeat Final Boss",
            self.player,
        )

        victory_location.place_locked_item(
            SAI2Item(
                "Victory",
                ItemClassification.progression,
                None,
                self.player,
            )
        )

        self.multiworld.completion_condition[self.player] = (
            lambda state: state.has(
                "Victory",
                self.player,
            )
        )

        # Locked items are placed above; only now can the self-lock
        # computation see them (Shove behind Sun Stone etc.).
        set_self_lock_rules(self.multiworld, self.player)

    # ---------------------------------------------------------
    # ROM generation
    # ---------------------------------------------------------

    def generate_output(self, output_directory: str) -> None:
        """
        Create a patched SAI2 ROM using the item placements
        generated by Archipelago.

        Currently supported:
            - 51 standard chests
            - 14 event locations
            - 3 vanilla technique locations (left unchanged)

        Not yet supported:
            - Remote multiworld items
        """

        input_rom = Path(
            "Super Adventure Island II (USA).sfc"
        )

        if not input_rom.exists():
            raise FileNotFoundError(
                "Super Adventure Island II base ROM not found:\n"
                f"{input_rom.resolve()}"
            )

        rom = load_rom(input_rom)

        # v14.1: sai2_rando's chest_patch.txt ("??? coins" feature) is NOT
        # applied. It rewrites the 1000 Coins message to "??? COINS" and adds a
        # random digit bonus. Vanilla already awards item $0003 correctly.

        # ---------------------------------------------------------
        # Build vanilla unused-memory pool BEFORE modifying any
        # standard chest.
        # ---------------------------------------------------------

        standard_chest_addresses = []
        for location_name, location_data in location_table.items():
            rom_address = location_data.rom_address

            if rom_address is None:
                continue

            # Event locations are not standard $7B chests.
            if location_name in EVENT_LOCATION_ITEMS:
                continue

            try:
                _memory_id, marker, _item_id = read_chest_data(
                    rom,
                    rom_address,
                )
            except IndexError:
                continue

            if marker == 0x7B:
                standard_chest_addresses.append(
                    rom_address
                )

        unused_memory = build_unused_memory_pool(
            rom,
            standard_chest_addresses,
        )

        print(
            f"[SAI2] Unused chest memory IDs: "
            f"{len(unused_memory)}"
        )

        print(
            "[SAI2] Memory pool: "
            + ", ".join(
                f"0x{x:04X}"
                for x in unused_memory
            )
        )

        patched_standard = 0
        patched_event = 0
        standard_check_map: dict[int, str] = {}
        event_check_map: dict[int, str] = {}
        technique_check_map: dict[int, str] = {}
        event_reward_map: dict[str, int | None] = {}

        def add_check(check_map, memory_id, location_name, category):
            if memory_id in check_map:
                print(
                    f"[SAI2] DIAGNOSTIC COLLISION {category}: "
                    f"0x{memory_id:04X} = "
                    f"{check_map[memory_id]} | {location_name}"
                )
            check_map[memory_id] = location_name
        skipped_nonstandard = 0
        skipped_remote = 0
        skipped_unsupported = 0

        print()
        print("=" * 60)
        print("[SAI2] Building patched ROM")
        print(f"[SAI2] Seed: {self.multiworld.seed_name}")
        print("=" * 60)

        # -----------------------------------------------------
        # Process every SAI2 location
        # -----------------------------------------------------

        for location_name, location_data in location_table.items():
            rom_address = location_data.rom_address

            if rom_address is None:
                continue

            ap_location = self.multiworld.get_location(
                location_name,
                self.player,
            )

            item = ap_location.item

            if item is None:
                print(
                    f"[SAI2] NO ITEM: "
                    f"{location_name}"
                )
                continue

            # -------------------------------------------------
            # Remote Archipelago item
            # -------------------------------------------------

            if item.player != self.player:
                print(
                    f"[SAI2] REMOTE: "
                    f"{location_name} -> {item.name}"
                )

                skipped_remote += 1

                # TEST BUILD: do not alter the reward or memory behavior of
                # remote locations. Register the vanilla completion memory only.
                if location_name in VANILLA_TECHNIQUES:
                    technique_memory_id = item_table[
                        VANILLA_TECHNIQUES[location_name]
                    ].rom_id
                    add_check(technique_check_map, technique_memory_id, location_name, "TECHNIQUE")
                    continue

                if location_name in EVENT_LOCATION_ITEMS:
                    event_memory_id = patch_event_check_flag(rom, location_name)
                    event_reward_map[location_name] = None
                    add_check(event_check_map, event_memory_id, location_name, "EVENT")
                    continue

                old_memory_id, marker, _old_item_id = read_chest_data(
                    rom,
                    rom_address,
                )

                if marker == 0x7B:
                    if location_name == "Poka Isle - Light Spell":
                        rom[rom_address:rom_address + 2] = LIGHT_SPELL_CHEST_CHECK_FLAG.to_bytes(2, "little")
                        old_memory_id = LIGHT_SPELL_CHEST_CHECK_FLAG
                    add_check(standard_check_map, old_memory_id, location_name, "CHEST")
                    continue

                raise ValueError(
                    f"Unable to identify remote location memory: "
                    f"{location_name} at ROM 0x{rom_address:06X}"
                )

            item_data = item_table.get(item.name)

            if item_data is None:
                print(
                    f"[SAI2] UNKNOWN ITEM: "
                    f"{location_name} -> {item.name}"
                )

                skipped_unsupported += 1
                continue

            if item_data.rom_id is None:
                print(
                    f"[SAI2] NO ROM ID: "
                    f"{location_name} -> {item.name}"
                )

                skipped_unsupported += 1
                continue

            # -------------------------------------------------
            # Vanilla technique location
            # -------------------------------------------------

            if location_name in VANILLA_TECHNIQUES:
                expected_item = VANILLA_TECHNIQUES[location_name]

                if item.name != expected_item:
                    raise ValueError(
                        f"{location_name} must contain {expected_item}, "
                        f"found {item.name}."
                    )

                technique_memory_id = item_data.rom_id
                add_check(technique_check_map, technique_memory_id, location_name, "TECHNIQUE")

                print(
                    f"[SAI2] VANILLA TECHNIQUE UNCHANGED: "
                    f"{location_name} -> {item.name} "
                    f"(memory 0x{technique_memory_id:04X})"
                )
                continue

            # -------------------------------------------------
            # Event location
            # -------------------------------------------------

            if location_name in EVENT_LOCATION_ITEMS:
                expected_item_id = EVENT_LOCATION_ITEMS[
                    location_name
                ]

                patch_event_location(
                    rom,
                    rom_address,
                    item_data.rom_id,
                    expected_item_id,
                )

                patch_event_memory(
                    rom,
                    location_name,
                    item_data.rom_id,
                    unused_memory,
                )

                event_memory_id = patch_event_check_flag(rom, location_name)
                event_reward_map[location_name] = item_data.rom_id
                add_check(event_check_map, event_memory_id, location_name, "EVENT")

                if item_data.rom_id <= 0x0005:
                    # Original sai2_rando uses generic EventChest message $03
                    # for common rewards.
                    message_address = EVENT_MESSAGE_ADDRESSES.get(location_name)
                    if message_address is not None:
                        rom[message_address] = 0x03
                    print(
                        f"[SAI2] EVENT COMMON: {location_name} -> {item.name} "
                        f"(memory 0x{event_memory_id:04X}, message 0x03)"
                    )
                else:
                    patch_event_message(
                        rom,
                        location_name,
                        item_data.rom_id,
                    )

                print(
                    f"[SAI2] EVENT PATCH: "
                    f"{location_name} -> {item.name} "
                    f"(ROM item 0x{item_data.rom_id:04X})"
                )

                patched_event += 1
                continue

            # -------------------------------------------------
            # Standard chest
            # -------------------------------------------------

            try:
                location_memory_id, marker, _old_item_id = read_chest_data(
                    rom,
                    rom_address,
                )

                new_memory_id = patch_standard_location(
                    rom,
                    rom_address,
                    item_data.rom_id,
                    unused_memory,
                )

                # AP MULTIWORLD TEST:
                # reward stays randomized, but completion memory stays
                # tied to the physical chest/location.
                rom[rom_address:rom_address + 2] = (
                    location_memory_id.to_bytes(2, "little")
                )
                new_memory_id = (
                    LIGHT_SPELL_CHEST_CHECK_FLAG
                    if location_name == "Poka Isle - Light Spell"
                    else location_memory_id
                )
                rom[rom_address:rom_address + 2] = new_memory_id.to_bytes(2, "little")

                add_check(standard_check_map, new_memory_id, location_name, "CHEST")

            except ValueError:
                # At this point, the remaining non-standard
                # locations should be the three techniques:
                #
                #   Hiya - Shove
                #   Sala - Up Jab
                #   Puka - Down Jab

                skipped_nonstandard += 1

                print(
                    f"[SAI2] NON-STANDARD: "
                    f"{location_name} -> {item.name}"
                )

                continue

            print(
                f"[SAI2] CHEST PATCH: "
                f"{location_name} -> {item.name} "
                f"(ROM item 0x{item_data.rom_id:04X}, "
                f"memory 0x{new_memory_id:04X})"
            )

            patched_standard += 1

        # -----------------------------------------------------
        # Write patched ROM
        # -----------------------------------------------------

        total_patched = (
            patched_standard
            + patched_event
        )

        # -----------------------------------------------------
        # Save ROM in Archipelago's normal output folder
        # -----------------------------------------------------

        output_folder = Path.cwd() / "output"
        output_folder.mkdir(
            parents=True,
            exist_ok=True,
        )

        output_path = output_folder / (
            f"AP_{self.multiworld.seed_name}_"
            f"P{self.player}_SAI2.sfc"
        )

        # -----------------------------------------------------
        # Embed seed-specific Archipelago check table in ROM.
        #
        # Format at ROM offset 0x17B300:
        #   8 bytes  signature b"SAI2AP01"
        #   2 bytes  entry count (little-endian)
        #   repeated:
        #       2 bytes WRAM memory/check id
        #       4 bytes Archipelago location id
        #       2 bytes local event reward ID, 0xFFFF otherwise
        # -----------------------------------------------------

        AP_TABLE_OFFSET = 0x17B300
        AP_TABLE_SIGNATURE = b"SAI2AP02"

        all_check_map: dict[int, str] = {}

        duplicate_checks = []

        for source_map in (
            standard_check_map,
            event_check_map,
            technique_check_map,
        ):
            for memory_id, location_name in source_map.items():
                if memory_id in all_check_map:
                    duplicate_checks.append(
                        (
                            memory_id,
                            all_check_map[memory_id],
                            location_name,
                        )
                    )
                    print(
                        f"[SAI2] DIAGNOSTIC COLLISION: "
                        f"0x{memory_id:04X} = "
                        f"{all_check_map[memory_id]} | {location_name}"
                    )
                    continue

                all_check_map[memory_id] = location_name

        if len(all_check_map) != 68:
            mapped_locations = set(all_check_map.values())

            expected_locations = set()
            for location_name, location_data in location_table.items():
                if location_data.rom_address is not None:
                    expected_locations.add(location_name)

            missing_locations = sorted(
                expected_locations - mapped_locations
            )

            print(
                f"[SAI2] DIAGNOSTIC COUNTS: "
                f"CHEST={len(standard_check_map)} "
                f"EVENT={len(event_check_map)} "
                f"TECHNIQUE={len(technique_check_map)} "
                f"UNIQUE={len(all_check_map)}"
            )

            for location_name in missing_locations:
                print(
                    f"[SAI2] DIAGNOSTIC MISSING: "
                    f"{location_name}"
                )

            raise ValueError(
                f"Expected 68 SAI2 checks, got {len(all_check_map)}"
            )

        ap_table = bytearray(AP_TABLE_SIGNATURE)
        ap_table += len(all_check_map).to_bytes(2, "little")

        for memory_id, location_name in sorted(all_check_map.items()):
            location_id = location_name_to_id[location_name]
            ap_table += memory_id.to_bytes(2, "little")
            ap_table += location_id.to_bytes(4, "little")
            reward_id = event_reward_map.get(location_name)
            ap_table += (0xFFFF if reward_id is None else reward_id).to_bytes(2, "little")

        table_end = AP_TABLE_OFFSET + len(ap_table)
        if table_end > len(rom):
            raise ValueError(
                f"SAI2 ROM is too small for AP table: "
                f"need 0x{table_end:X}, ROM is 0x{len(rom):X}"
            )

        rom[AP_TABLE_OFFSET:table_end] = ap_table

        print(
            f"[SAI2] Embedded AP check table: "
            f"{len(all_check_map)} locations at ROM 0x{AP_TABLE_OFFSET:06X}"
        )

        save_rom(
            rom,
            output_path,
        )
        # -----------------------------------------------------
        # Generate BizHawk check detector for this seed
        # -----------------------------------------------------

        lua_path = output_folder / (
            f"AP_{self.multiworld.seed_name}_"
            f"P{self.player}_SAI2_CheckDetector.lua"
        )

        lua_checks = []

        for memory_id, location_name in sorted(standard_check_map.items()):
            safe_name = location_name.replace("\\", "\\\\").replace('"', '\\"')
            lua_checks.append(
                f'    [0x{memory_id:04X}] = {{ name = "{safe_name}", kind = "CHEST" }},'
            )

        for memory_id, location_name in sorted(event_check_map.items()):
            safe_name = location_name.replace("\\", "\\\\").replace('"', '\\"')
            lua_checks.append(
                f'    [0x{memory_id:04X}] = {{ name = "{safe_name}", kind = "EVENT" }},'
            )

        for memory_id, location_name in sorted(technique_check_map.items()):
            safe_name = location_name.replace("\\", "\\\\").replace('"', '\\"')
            lua_checks.append(
                f'    [0x{memory_id:04X}] = {{ name = "{safe_name}", kind = "TECHNIQUE" }},'
            )

        lua_script = """-- Auto-generated SAI2 Archipelago Check Detector
-- Seed: {seed}
-- READ ONLY - does not modify game memory.

local DOMAIN = "WRAM"

local checks = {{
{checks}
}}

local previous = {{}}

console.clear()
console.log("==============================================")
console.log(" SAI2 Archipelago - Check Detector")
console.log(" Seed: {seed}")
console.log(" Standard chests: {chest_count}")
console.log(" Event locations: {event_count}")
console.log(" Technique locations: {technique_count}")
console.log(" Total locations: {total_count}")
console.log("==============================================")

for memory_id, check in pairs(checks) do
    previous[memory_id] = memory.read_u8(memory_id, DOMAIN)
end

while true do
    for memory_id, check in pairs(checks) do
        local value = memory.read_u8(memory_id, DOMAIN)
        local old = previous[memory_id]

        if old == 0 and value ~= 0 then
            console.log(
                string.format(
                    "[SAI2] %s CHECK: %s (0x%04X)",
                    check.kind,
                    check.name,
                    memory_id
                )
            )
        end

        previous[memory_id] = value
    end

    emu.frameadvance()
end
""".format(
            seed=self.multiworld.seed_name,
            chest_count=len(standard_check_map),
            event_count=len(event_check_map),
            technique_count=len(technique_check_map),
            total_count=(
                len(standard_check_map)
                + len(event_check_map)
                + len(technique_check_map)
            ),
            checks="\n".join(lua_checks),
        )

        lua_path.write_text(
            lua_script,
            encoding="utf-8",
        )

        print(
            f"[SAI2] BizHawk check detector : "
            f"{lua_path}"
        )

        # -----------------------------------------------------
        # Summary
        # -----------------------------------------------------

        print()
        print("=" * 60)
        print("[SAI2] ROM generation complete")
        print(
            f"[SAI2] Standard chests patched : "
            f"{patched_standard}"
        )
        print(
            f"[SAI2] Event locations patched : "
            f"{patched_event}"
        )
        print(
            f"[SAI2] Total locations patched : "
            f"{total_patched}"
        )
        print(
            f"[SAI2] Non-standard skipped    : "
            f"{skipped_nonstandard}"
        )
        print(
            f"[SAI2] Remote items skipped    : "
            f"{skipped_remote}"
        )
        print(
            f"[SAI2] Unsupported skipped     : "
            f"{skipped_unsupported}"
        )
        print(
            f"[SAI2] Output                  : "
            f"{output_path}"
        )
        print("=" * 60)