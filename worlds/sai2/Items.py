from dataclasses import dataclass

from BaseClasses import ItemClassification


@dataclass(frozen=True)
class SAI2ItemData:
    code: int
    classification: ItemClassification
    rom_id: int | None = None


# Archipelago IDs.
# Keep these separate from the game's internal ROM item IDs.
BASE_ID = 0x53414900


item_table: dict[str, SAI2ItemData] = {
    # Resources
    "Life Bottle": SAI2ItemData(
        BASE_ID + 0,
        ItemClassification.progression,
        0x0000,
    ),
    "Magic": SAI2ItemData(
        BASE_ID + 1,
        ItemClassification.filler,
        0x0001,
    ),
    "500 Coins": SAI2ItemData(
        BASE_ID + 2,
        ItemClassification.progression,
        0x0002,
    ),
    "1000 Coins": SAI2ItemData(
        BASE_ID + 3,
        ItemClassification.progression,
        0x0003,
    ),
    "2000 Coins": SAI2ItemData(
        BASE_ID + 4,
        ItemClassification.useful,
        0x0004,
    ),
    "5000 Coins": SAI2ItemData(
        BASE_ID + 5,
        ItemClassification.useful,
        0x0005,
    ),

    # Weapons
    "Silver Sword": SAI2ItemData(
        BASE_ID + 10,
        ItemClassification.progression,
        0x044E,
    ),
    "Fire Sword": SAI2ItemData(
        BASE_ID + 11,
        ItemClassification.progression,
        0x044F,
    ),
    "Ice Sword": SAI2ItemData(
        BASE_ID + 12,
        ItemClassification.progression,
        0x0450,
    ),
    "Thunder Sword": SAI2ItemData(
        BASE_ID + 13,
        ItemClassification.progression,
        0x0451,
    ),
    "Crystal Sword": SAI2ItemData(
        BASE_ID + 14,
        ItemClassification.progression,
        0x0452,
    ),
    "Power Sword": SAI2ItemData(
        BASE_ID + 15,
        ItemClassification.progression,
        0x0453,
    ),
    "Dagger": SAI2ItemData(
        BASE_ID + 16,
        ItemClassification.progression,
        0x0455,
    ),
    "Fireballs": SAI2ItemData(
        BASE_ID + 17,
        ItemClassification.progression,
        0x0456,
    ),
    "Axe": SAI2ItemData(
        BASE_ID + 18,
        ItemClassification.progression,
        0x0458,
    ),

    # Tools / Key Items
    "Shovel": SAI2ItemData(
        BASE_ID + 20,
        ItemClassification.progression,
        0x0459,
    ),
    "Magic Wand": SAI2ItemData(
        BASE_ID + 21,
        ItemClassification.progression,
        0x0464,
    ),
    "Ice Bell": SAI2ItemData(
        BASE_ID + 22,
        ItemClassification.progression,
        0x0466,
    ),
    "Sun Ring": SAI2ItemData(
        BASE_ID + 23,
        ItemClassification.progression,
        0x0467,
    ),
    "Power Fan": SAI2ItemData(
        BASE_ID + 24,
        ItemClassification.progression,
        0x0468,
    ),
    "Elven Flute": SAI2ItemData(
        BASE_ID + 25,
        ItemClassification.progression,
        0x0469,
    ),
    "Sky Bell": SAI2ItemData(
        BASE_ID + 26,
        ItemClassification.progression,
        0x046A,
    ),

    # Stones
    "Light Stone": SAI2ItemData(
        BASE_ID + 30,
        ItemClassification.progression,
        0x046B,
    ),
    "Sun Stone": SAI2ItemData(
        BASE_ID + 31,
        ItemClassification.progression,
        0x046C,
    ),
    "Star Stone": SAI2ItemData(
        BASE_ID + 32,
        ItemClassification.progression,
        0x046D,
    ),
    "Aqua Stone": SAI2ItemData(
        BASE_ID + 33,
        ItemClassification.progression,
        0x046E,
    ),
    "Moon Stone": SAI2ItemData(
        BASE_ID + 34,
        ItemClassification.progression,
        0x046F,
    ),

    # Spells
    "Light Spell": SAI2ItemData(
        BASE_ID + 40,
        ItemClassification.progression,
        0x0470,
    ),
    "Star Spell": SAI2ItemData(
        BASE_ID + 41,
        ItemClassification.progression,
        0x0471,
    ),
    "Sun Spell": SAI2ItemData(
        BASE_ID + 42,
        ItemClassification.progression,
        0x0472,
    ),
    "Aqua Spell": SAI2ItemData(
        BASE_ID + 43,
        ItemClassification.progression,
        0x0473,
    ),
    "Moon Spell": SAI2ItemData(
        BASE_ID + 44,
        ItemClassification.progression,
        0x0474,
    ),

    # Techniques
    "Shove": SAI2ItemData(
        BASE_ID + 50,
        ItemClassification.progression,
        0x047D,
    ),
    "Up Jab": SAI2ItemData(
        BASE_ID + 51,
        ItemClassification.progression,
        0x047E,
    ),
    "Down Jab": SAI2ItemData(
        BASE_ID + 52,
        ItemClassification.progression,
        0x047F,
    ),

    # Armor
    "Fire Armor": SAI2ItemData(
        BASE_ID + 60,
        ItemClassification.progression,
        0x045B,
    ),
    "Ice Armor": SAI2ItemData(
        BASE_ID + 61,
        ItemClassification.progression,
        0x045C,
    ),
    "Aqua Armor": SAI2ItemData(
        BASE_ID + 62,
        ItemClassification.progression,
        0x045D,
    ),

    # Shields
    "Fire Shield": SAI2ItemData(
        BASE_ID + 70,
        ItemClassification.useful,
        0x0460,
    ),
    "Ice Shield": SAI2ItemData(
        BASE_ID + 71,
        ItemClassification.useful,
        0x0461,
    ),
    "Aqua Shield": SAI2ItemData(
        BASE_ID + 72,
        ItemClassification.useful,
        0x0462,
    ),
}


item_name_to_id = {
    name: data.code
    for name, data in item_table.items()
}