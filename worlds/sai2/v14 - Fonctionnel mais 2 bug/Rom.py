import hashlib
from pathlib import Path


EXPECTED_ROM_SIZE = 0x180000

EXPECTED_SHA1 = (
    "06776efd3cc3997513f90fbe2507939a1c61bb87"
)


def get_sha1(data: bytes) -> str:
    """
    Return the SHA-1 hash of the supplied ROM data.
    """
    return hashlib.sha1(data).hexdigest()


def validate_rom(data: bytes) -> None:
    """
    Validate that the ROM is the supported unheadered
    Super Adventure Island II (USA) ROM.
    """
    if len(data) != EXPECTED_ROM_SIZE:
        raise ValueError(
            f"Invalid SAI2 ROM size: {len(data)} bytes. "
            f"Expected {EXPECTED_ROM_SIZE} bytes."
        )

    sha1 = get_sha1(data)

    if sha1 != EXPECTED_SHA1:
        raise ValueError(
            "Unsupported Super Adventure Island II ROM.\n"
            f"SHA-1: {sha1}\n"
            f"Expected: {EXPECTED_SHA1}"
        )


def load_rom(path: str | Path) -> bytearray:
    """
    Load and validate the original SAI2 ROM.

    A bytearray is returned so that future Archipelago
    patches can modify the ROM data in memory.
    """
    path = Path(path)

    data = bytearray(path.read_bytes())

    validate_rom(data)

    return data


def save_rom(data: bytes | bytearray, path: str | Path) -> None:
    """
    Write patched ROM data to disk.
    """
    Path(path).write_bytes(data)    
    
def write_u16_le(data: bytearray, address: int, value: int) -> None:
    """
    Write an unsigned 16-bit value in little-endian format.
    """
    if not 0 <= value <= 0xFFFF:
        raise ValueError(
            f"Value {value:#06x} does not fit in 16 bits."
        )

    data[address] = value & 0xFF
    data[address + 1] = (value >> 8) & 0xFF


def patch_chest_item(
    data: bytearray,
    chest_address: int,
    item_id: int,
) -> None:
    """
    Replace the item contained in a standard SAI2 chest.

    The chest pointers used by sai2_rando point to the start
    of the chest structure. The 16-bit item ID is stored
    three bytes after that address.
    """
    item_address = chest_address + 3
    write_u16_le(data, item_address, item_id)


def read_u16_le(data: bytes | bytearray, address: int) -> int:
    return data[address] | (data[address + 1] << 8)


def read_chest_data(
    data: bytes | bytearray,
    chest_address: int,
) -> tuple[int, int, int]:
    """
    Read a standard SAI2 chest structure.

    Structure:
        +0/+1 : memory ID
        +2    : marker / unknown byte
        +3/+4 : item ID
    """
    memory_id = read_u16_le(data, chest_address)
    marker = data[chest_address + 2]
    item_id = read_u16_le(data, chest_address + 3)

    return memory_id, marker, item_id
    
def build_standard_chest_checks(
    data: bytes | bytearray,
    locations: dict,
) -> dict[str, int]:
    """
    Build a mapping of Archipelago location names to their
    SAI2 WRAM chest completion IDs.

    Only standard chests (marker $7B) are included.
    """
    checks: dict[str, int] = {}

    for name, location in locations.items():
        address = location.rom_address

        if address is None:
            continue

        memory_id, marker, _item_id = read_chest_data(
            data,
            address,
        )

        if marker != 0x7B:
            continue

        checks[name] = memory_id

    return checks

def build_unused_memory_pool(
    data: bytes | bytearray,
    chest_addresses: list[int],
) -> list[int]:
    """
    Reproduce ChestObject.unused_memory from sai2_rando.

    Vanilla standard chests whose memory ID differs from their
    item ID provide reusable memory IDs for common rewards:

        0x0000 = Health
        0x0001 = Magic
        0x0002 = 500 Coins
        0x0003 = 1000 Coins
        0x0004 = 2000 Coins
        0x0005 = 5000 Coins

    Memory IDs >= 0x051F are excluded.
    0x0470 is explicitly reserved by the original randomizer.
    """

    unused_memory: set[int] = set()

    for chest_address in chest_addresses:
        memory_id, marker, item_id = read_chest_data(
            data,
            chest_address,
        )

        # Ignore anything that is not a standard chest.
        if marker != 0x7B:
            continue

        if memory_id >= 0x051F:
            continue

        if memory_id != item_id:
            unused_memory.add(memory_id)

    # Explicit behavior from sai2_rando.
    unused_memory.discard(0x0470)

    return sorted(unused_memory)


STAR_SPELL_DUPLICATE_CHECK = 0x19B58


def patch_standard_location(
    data: bytearray,
    chest_address: int,
    item_id: int,
    unused_memory: list[int],
) -> int:
    """
    Patch a standard SAI2 chest using the same memory behavior
    as ChestObject.cleanup() in sai2_rando.

    Standard chest structure:
        +0/+1 : memory ID
        +2    : marker ($7B)
        +3/+4 : item ID

    Common rewards ($0000-$0005) require an unused memory ID.

    Normal inventory items ($044E-$0474) use the randomized
    item ID itself as their memory ID.

    The vanilla Star Spell chest requires an additional
    duplicate-check pointer to be synchronized.
    """

    old_memory_id, marker, old_item_id = read_chest_data(
        data,
        chest_address,
    )

    if marker != 0x7B:
        raise ValueError(
            f"Location at ROM 0x{chest_address:05X} "
            f"is not a standard chest "
            f"(marker=0x{marker:02X})."
        )

    # ---------------------------------------------------------
    # Health / Magic / Coins
    # ---------------------------------------------------------

    if item_id <= 0x0005:
        if not unused_memory:
            raise ValueError(
                f"No unused chest memory available for "
                f"common item 0x{item_id:04X} "
                f"at ROM 0x{chest_address:05X}."
            )

        new_memory_id = unused_memory.pop()

    # ---------------------------------------------------------
    # Normal inventory item
    # ---------------------------------------------------------

    elif 0x044E <= item_id <= 0x0474:
        new_memory_id = item_id

    else:
        raise ValueError(
            f"Unsupported standard chest item "
            f"0x{item_id:04X} "
            f"at ROM 0x{chest_address:05X}."
        )

    # ---------------------------------------------------------
    # Patch chest memory + item
    # ---------------------------------------------------------

    write_u16_le(
        data,
        chest_address,
        new_memory_id,
    )

    write_u16_le(
        data,
        chest_address + 3,
        item_id,
    )

    # ---------------------------------------------------------
    # Special vanilla Star Spell duplicate check
    #
    # sai2_rando:
    #
    # if self.old_data['item'] == 0x471:
    #     assert self.old_data['memory'] == 0x51f
    #     ...
    #     write_multi(f, self.memory, length=2)
    # ---------------------------------------------------------

    if old_item_id == 0x0471:
        if old_memory_id != 0x051F:
            raise ValueError(
                "Vanilla Star Spell chest has unexpected "
                f"memory ID 0x{old_memory_id:04X}; "
                "expected 0x051F."
            )

        old_duplicate_memory = read_u16_le(
            data,
            STAR_SPELL_DUPLICATE_CHECK,
        )

        if old_duplicate_memory != 0x051F:
            raise ValueError(
                "Star Spell duplicate check contains "
                f"0x{old_duplicate_memory:04X}; "
                "expected 0x051F."
            )

        if new_memory_id == 0x051F:
            raise ValueError(
                "Star Spell randomized memory cannot remain "
                "0x051F."
            )

        write_u16_le(
            data,
            STAR_SPELL_DUPLICATE_CHECK,
            new_memory_id,
        )

        print(
            f"[SAI2] STAR SPELL DUPLICATE CHECK: "
            f"0x051F -> 0x{new_memory_id:04X}"
        )

    return new_memory_id
# -------------------------------------------------------------
# Event locations
# -------------------------------------------------------------

# Event locations use the item ID directly at the ROM address:
#
#   +0/+1 : item ID (little endian)
#
# Unlike standard chests, they do not use the $7B chest
# structure.
#
# expected_item_id is used as a safety check against patching
# the wrong ROM structure.


def patch_event_location(
    data: bytearray,
    address: int,
    item_id: int,
    expected_item_id: int,
) -> None:
    old_item_id = read_u16_le(
        data,
        address,
    )

    if old_item_id != expected_item_id:
        raise ValueError(
            f"Unexpected event item at ROM 0x{address:05X}: "
            f"expected 0x{expected_item_id:04X}, "
            f"found 0x{old_item_id:04X}"
        )

    write_u16_le(
        data,
        address,
        item_id,
    )
    
def apply_common_reward_table_patch(data: bytearray) -> None:
    """Apply only sai2_rando's reward-dispatch table at ROM $050306."""
    table_patch = bytes([
        0x90, 0x28,
        0x8F, 0x2C,
        0x8F, 0x2C,
        0x8F, 0x2C,
        0x90, 0x28,
        0x52, 0x2C,
        0x5E, 0x2C,
        0x58, 0x2C,
        0x5D, 0x2C,
        0x62, 0x2C,
        0x90, 0x28,
    ])
    data[0x050306:0x050306 + len(table_patch)] = table_patch


def apply_chest_engine_patch(data: bytearray) -> None:
    """
    Apply the chest engine patch required for randomized
    rewards in standard SAI2 chests.
    """

    # ---------------------------------------------------------
    # Chest handling table at ROM $050306
    # ---------------------------------------------------------
    table_patch = bytes([
        0x90, 0x28,
        0x8F, 0x2C,
        0x8F, 0x2C,
        0x8F, 0x2C,
        0x90, 0x28,
        0x52, 0x2C,
        0x5E, 0x2C,
        0x58, 0x2C,
        0x5D, 0x2C,
        0x62, 0x2C,
        0x90, 0x28,
    ])

    data[
        0x050306:
        0x050306 + len(table_patch)
    ] = table_patch

    # ---------------------------------------------------------
    # Hook at ROM $005DEA
    #
    # JSL $D7B200
    # ---------------------------------------------------------
    data[0x005DEA:0x005DEE] = bytes([
        0x22,
        0x00,
        0xB2,
        0xD7,
    ])

    # ---------------------------------------------------------
    # New routine at ROM $17B200
    # ---------------------------------------------------------
    routine_patch = bytes([
        # $17B200
        0xAD, 0x54, 0x22,       # LDA $2254

        # $17B203
        0xC9, 0x03, 0x00,       # CMP #$0003

        # $17B206
        0xD0, 0x15,             # BNE exit ($17B21D)

        # $17B208
        0xA2, 0x06, 0x00,       # LDX #$0006

        # $17B20B
        0xE2, 0x30,             # SEP #$30

        # loop: $17B20D
        0xCA,                   # DEX

        # $17B20E
        0xE0, 0x07,             # CPX #$07

        # $17B210
        0xB0, 0x0B,             # BCS exit ($17B21D)

        # $17B212
        0xBD, 0x35, 0x04,       # LDA $0435,X

        # $17B215
        0xC9, 0x09,             # CMP #$09

        # $17B217
        0xF0, 0xF4,             # BEQ loop ($17B20D)

        # $17B219
        0x1A,                   # INC A

        # $17B21A
        0x9D, 0x35, 0x04,       # STA $0435,X

        # exit: $17B21D
        0xC2, 0x30,             # REP #$30

        # $17B21F
        0xAD, 0x54, 0x22,       # LDA $2254

        # $17B222
        0x0A,                   # ASL A

        # $17B223
        0x6B,                   # RTL
    ])

    data[
        0x17B200:
        0x17B200 + len(routine_patch)
    ] = routine_patch
    
# Event location:
#     location name -> vanilla item ID
#
# The ROM address itself already comes from Locations.py.

EVENT_LOCATION_ITEMS = {
    "Poka - Light Stone": 0x046B,
    "Hiya - Star Stone": 0x046D,
    "Sala - Elven Flute": 0x0469,
    "Fuwa - Sky Bell": 0x046A,
    "Puka - Aqua Stone": 0x046E,
    "Puka Isle - Moon Stone": 0x046F,
    "Boa - Sun Stone": 0x046C,
    "Puka - Power Fan": 0x0468,

    "Overworld - Sun Ring": 0x0467,
    "Overworld - Ice Bell": 0x0466,
    "Overworld - Magic Wand": 0x0464,
    "Overworld - Shovel": 0x0459,

    "Boa Isle - Sun Spell": 0x0472,
    "Sala Isle - Moon Spell": 0x0474,
}    
EVENT_MESSAGE_ADDRESSES = {
    "Overworld - Shovel": 0x39DB1,
    "Overworld - Magic Wand": 0x394CF,
    "Overworld - Ice Bell": 0x39340,
    "Overworld - Sun Ring": 0x39171,
    "Puka - Power Fan": 0x1A9D1,
    "Sala - Elven Flute": 0x14151,
    "Fuwa - Sky Bell": 0x14C54,
    "Poka - Light Stone": 0x102FD,
    "Boa - Sun Stone": 0x1A959,
    "Hiya - Star Stone": 0x116E4,
    "Puka - Aqua Stone": 0x16D68,
    "Puka Isle - Moon Stone": 0x17A89,
    "Boa Isle - Sun Spell": 0xFC88C,
    "Sala Isle - Moon Spell": 0xFE6FC,
}
EVENT_MEMORY_ADDRESSES = {
    "Overworld - Shovel": 0x39D83,
    "Overworld - Magic Wand": 0x394A1,
    "Overworld - Ice Bell": 0x39312,
    "Overworld - Sun Ring": 0x39142,
    "Puka - Power Fan": 0x2FA1D,
    "Sala - Elven Flute": 0x140CB,
    "Fuwa - Sky Bell": 0x14BC2,
    "Poka - Light Stone": 0x1025E,
    "Boa - Sun Stone": 0x2F942,
    "Hiya - Star Stone": 0x11651,
    "Puka - Aqua Stone": 0x16CD2,
    "Puka Isle - Moon Stone": 0x179F6,
    "Boa Isle - Sun Spell": 0xFC85D,
    "Sala Isle - Moon Spell": 0xFE6CD,
}
BOSS_MEMORY_ADDRESSES = {
    "Sala - Elven Flute": 0x3CB8A,
    "Fuwa - Sky Bell": 0x2EDD2,
    "Poka - Light Stone": 0x18C5A,
    "Hiya - Star Stone": 0x19B04,
    "Puka - Aqua Stone": 0x1A7D0,
    "Puka Isle - Moon Stone": 0x3B364,
}

def patch_event_message(
    data: bytearray,
    location_name: str,
    item_id: int,
) -> None:
    """
    Synchronize an event location's pickup message with its
    randomized reward.

    SAI2 event message codes use:
        message_code = item_id - 0x044A
    """

    address = EVENT_MESSAGE_ADDRESSES.get(
        location_name
    )

    if address is None:
        return

    message_code = item_id - 0x044A

    # The vanilla EventMessage table only supports codes
    # from $03 through $2A.
    if not 0x03 <= message_code <= 0x2A:
        print(
            f"[SAI2] MESSAGE UNSUPPORTED: "
            f"{location_name} -> "
            f"item 0x{item_id:04X}"
        )
        return

    data[address] = message_code
    
def patch_event_memory(
    data: bytearray,
    location_name: str,
    item_id: int,
    unused_memory: list[int],
) -> int:
    """Synchronize EventMemory/BossMemory with the randomized reward.

    Normal inventory rewards use their item ID as the completion memory.
    Common rewards ($0000-$0005) use one of ChestObject.unused_memory,
    matching sai2_rando's EventChest cleanup behavior.
    """
    if item_id <= 0x0005:
        if not unused_memory:
            raise ValueError(
                f"No unused memory ID available for event {location_name}."
            )
        memory_id = unused_memory.pop()
    else:
        memory_id = item_id

    event_address = EVENT_MEMORY_ADDRESSES.get(location_name)
    if event_address is not None:
        write_u16_le(data, event_address, memory_id)

    boss_address = BOSS_MEMORY_ADDRESSES.get(location_name)
    if boss_address is not None:
        write_u16_le(data, boss_address, memory_id)

    return memory_id


# -------------------------------------------------------------
# Technique rooms (Down Jab / Up Jab / Shove)
# -------------------------------------------------------------

TECHNIQUE_ITEM_IDS = {
    "Shove": 0x047D,
    "Up Jab": 0x047E,
    "Down Jab": 0x047F,
}

TECHNIQUE_MAP_CODES = {
    0x047D: 5,  # Shove
    0x047E: 4,  # Up Jab
    0x047F: 3,  # Down Jab
}

TECHNIQUE_ENTRANCE_ADDRESSES = {
    "Puka - Down Jab": 0x2B9EF,
    "Sala - Up Jab": 0x2BA05,
    "Hiya - Shove": 0x2BA1B,
}

TECHNIQUE_EXIT_ADDRESSES = {
    "Puka - Down Jab": 0x39585,
    "Sala - Up Jab": 0x3983F,
    "Hiya - Shove": 0x39A86,
}

TECHNIQUE_VANILLA_MAP_CODES = {
    "Puka - Down Jab": 3,
    "Sala - Up Jab": 4,
    "Hiya - Shove": 5,
}

BONUS_ITEM_ADDRESS = 0x2CF18
BONUS_ITEM_VALUE_ADDRESS = 0x2CF16

def patch_technique_locations(data: bytearray, placements: dict[str, int]) -> None:
    """Patch the three SAI2 technique rooms like sai2_rando.

    placements maps each technique location name to the technique ROM ID
    (Shove=$047D, Up Jab=$047E, Down Jab=$047F).
    """
    expected_locations = set(TECHNIQUE_ENTRANCE_ADDRESSES)
    if set(placements) != expected_locations:
        raise ValueError("Technique placements must contain exactly the three technique locations.")

    if set(placements.values()) != set(TECHNIQUE_MAP_CODES):
        raise ValueError("Technique locations must contain exactly Shove, Up Jab and Down Jab.")

    # Preserve the vanilla exit structures before changing anything.
    vanilla_exits = {
        name: bytes(data[address:address + 12])
        for name, address in TECHNIQUE_EXIT_ADDRESSES.items()
    }

    # Validate the fixed marker bytes in each exit structure.
    for name, raw in vanilla_exits.items():
        if len(raw) != 12 or (raw[0], raw[3], raw[6], raw[9]) != (0x59, 0x5A, 0x7A, 0x7B):
            raise ValueError(f"Unexpected technique exit structure for {name}.")

    # Map vanilla map code -> vanilla location/exit.
    vanilla_location_for_code = {
        code: name for name, code in TECHNIQUE_VANILLA_MAP_CODES.items()
    }

    # TechEntranceObject.cleanup(): write the randomized map code.
    for location_name, item_id in placements.items():
        entrance = TECHNIQUE_ENTRANCE_ADDRESSES[location_name]
        map_code = TECHNIQUE_MAP_CODES[item_id]
        write_u16_le(data, entrance, map_code)

    # TechExitObject.cleanup(): each exit follows the entrance that now owns
    # its original map code. Copy the complete 12-byte coordinate structure.
    for old_exit_location, old_code in TECHNIQUE_VANILLA_MAP_CODES.items():
        new_entrance_location = next(
            name for name, item_id in placements.items()
            if TECHNIQUE_MAP_CODES[item_id] == old_code
        )
        destination_exit = TECHNIQUE_EXIT_ADDRESSES[old_exit_location]
        source_exit = vanilla_exits[new_entrance_location]
        data[destination_exit:destination_exit + 12] = source_exit

    # Same initialization used by sai2_rando: FIST ($047C), value 1.
    write_u16_le(data, BONUS_ITEM_ADDRESS, 0x047C)
    data[BONUS_ITEM_VALUE_ADDRESS] = 0x01



# Experimental event-specific completion flags; validate WRAM region in BizHawk.
EVENT_CHECK_FLAGS = {name: 0x1E80 + i for i, name in enumerate(EVENT_LOCATION_ITEMS)}

def patch_event_check_flag(data: bytearray, name: str) -> int:
    """Redirect script reward write and event/boss guards to a location-only flag."""
    flag = EVENT_CHECK_FLAGS[name]
    reward_address = EVENT_ITEM_POINTERS[name]
    for address in (reward_address, EVENT_MEMORY_ADDRESSES[name], BOSS_MEMORY_ADDRESSES.get(name)):
        if address is None:
            continue
        old = read_u16_le(data, address)
        # Event pointers must still refer to a WRAM item/flag address.
        if not (0x044E <= old <= 0x047F):
            raise ValueError(f"Unexpected event pointer {name} at 0x{address:X}: 0x{old:04X}")
        write_u16_le(data, address, flag)
    return flag

EVENT_ITEM_POINTERS = {
    "Overworld - Shovel": 0x39DB9, "Overworld - Magic Wand": 0x394D7,
    "Overworld - Ice Bell": 0x39348, "Overworld - Sun Ring": 0x39179,
    "Puka - Power Fan": 0x1A9D9, "Sala - Elven Flute": 0x14159,
    "Fuwa - Sky Bell": 0x14C5C, "Poka - Light Stone": 0x10305,
    "Boa - Sun Stone": 0x1A961, "Hiya - Star Stone": 0x116EC,
    "Puka - Aqua Stone": 0x16D70, "Puka Isle - Moon Stone": 0x17A91,
    "Boa Isle - Sun Spell": 0xFC894, "Sala Isle - Moon Spell": 0xFE704,
}

# Experimental physical-only completion flag for the Poka Light Spell chest.
# WRAM persistence across save/load must be verified in BizHawk.
LIGHT_SPELL_CHEST_CHECK_FLAG = 0x1E90
