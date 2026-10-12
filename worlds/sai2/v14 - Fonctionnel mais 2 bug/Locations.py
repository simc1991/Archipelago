from dataclasses import dataclass


@dataclass(frozen=True)
class SAI2LocationData:
    code: int
    rom_address: int | None = None


BASE_LOCATION_ID = 0x53414A00


location_table: dict[str, SAI2LocationData] = {
    # Poka Isle
    "Poka Isle - Health 18890": SAI2LocationData(BASE_LOCATION_ID + 0, 0x18890),
    "Poka Isle - Dagger": SAI2LocationData(BASE_LOCATION_ID + 1, 0x18B47),
    "Poka Isle - Health 18D8D": SAI2LocationData(BASE_LOCATION_ID + 2, 0x18D8D),
    "Poka Isle - 500 Coins": SAI2LocationData(BASE_LOCATION_ID + 3, 0x18DD0),
    "Poka Isle - Ice Sword": SAI2LocationData(BASE_LOCATION_ID + 4, 0x18E22),
    "Poka Isle - 1000 Coins": SAI2LocationData(BASE_LOCATION_ID + 5, 0x18E3E),
    "Poka Isle - Silver Sword": SAI2LocationData(BASE_LOCATION_ID + 6, 0x18E78),
    "Poka Isle - 2000 Coins": SAI2LocationData(BASE_LOCATION_ID + 7, 0x1907E),
    "Poka Isle - Fireballs": SAI2LocationData(BASE_LOCATION_ID + 8, 0x1909A),
    "Poka Isle - Light Spell": SAI2LocationData(BASE_LOCATION_ID + 9, 0x1911A),

    # Boss / Event Rewards
    "Poka - Light Stone": SAI2LocationData(BASE_LOCATION_ID + 20, 0x10305),
    "Boa - Sun Stone": SAI2LocationData(BASE_LOCATION_ID + 21, 0x1A961),
    "Hiya - Star Stone": SAI2LocationData(BASE_LOCATION_ID + 22, 0x116EC),
    "Puka - Aqua Stone": SAI2LocationData(BASE_LOCATION_ID + 23, 0x16D70),
    "Puka - Power Fan": SAI2LocationData(BASE_LOCATION_ID + 67,0x1A9D9),
    "Puka Isle - Moon Stone": SAI2LocationData(BASE_LOCATION_ID + 24, 0x17A91),
    "Sala - Elven Flute": SAI2LocationData(BASE_LOCATION_ID + 25, 0x14159),
    "Fuwa - Sky Bell": SAI2LocationData(BASE_LOCATION_ID + 26, 0x14C5C),

    # Overworld / Event Items
    "Overworld - Sun Ring": SAI2LocationData(BASE_LOCATION_ID + 30, 0x39179),
    "Overworld - Ice Bell": SAI2LocationData(BASE_LOCATION_ID + 31, 0x39348),
    "Overworld - Magic Wand": SAI2LocationData(BASE_LOCATION_ID + 32, 0x394D7),
    "Overworld - Shovel": SAI2LocationData(BASE_LOCATION_ID + 33, 0x39DB9),

    # Techniques
    "Puka - Down Jab": SAI2LocationData(BASE_LOCATION_ID + 40, 0x2B9EF),
    "Sala - Up Jab": SAI2LocationData(BASE_LOCATION_ID + 41, 0x2BA05),
    "Hiya - Shove": SAI2LocationData(BASE_LOCATION_ID + 42, 0x2BA1B),

    # Hiya Isle
    "Hiya Isle - Fire Sword": SAI2LocationData(BASE_LOCATION_ID + 50, 0xFB562),
    "Hiya Isle - Magic FB57E": SAI2LocationData(BASE_LOCATION_ID + 51, 0xFB57E),
    "Hiya Isle - Health FB59A": SAI2LocationData(BASE_LOCATION_ID + 52, 0xFB59A),
    "Hiya Isle - Fire Shield": SAI2LocationData(BASE_LOCATION_ID + 53, 0xFB5B6),
    "Hiya Isle - Health FB5D2": SAI2LocationData(BASE_LOCATION_ID + 54, 0xFB5D2),
    "Hiya Isle - Health FB5EE": SAI2LocationData(BASE_LOCATION_ID + 55, 0xFB5EE),
    "Hiya Isle - Fire Armor": SAI2LocationData(BASE_LOCATION_ID + 56, 0xFB60A),
    "Hiya Isle - 1000 Coins": SAI2LocationData(BASE_LOCATION_ID + 57, 0xFB626),
    "Hiya Isle - Health FB642": SAI2LocationData(BASE_LOCATION_ID + 58, 0xFB642),
    "Hiya Isle - Star Spell": SAI2LocationData(BASE_LOCATION_ID + 59, 0xFB659),

    # Boa Isle
    "Boa Isle - Ice Shield": SAI2LocationData(BASE_LOCATION_ID + 70, 0xFC7B7),
    "Boa Isle - Magic FC7CE": SAI2LocationData(BASE_LOCATION_ID + 71, 0xFC7CE),
    "Boa Isle - Magic FC7E5": SAI2LocationData(BASE_LOCATION_ID + 72, 0xFC7E5),
    "Boa Isle - 1000 Coins": SAI2LocationData(BASE_LOCATION_ID + 73, 0xFC7FC),
    "Boa Isle - Ice Armor": SAI2LocationData(BASE_LOCATION_ID + 74, 0xFC813),
    "Boa Isle - 2000 Coins": SAI2LocationData(BASE_LOCATION_ID + 75, 0xFC82A),
    "Boa Isle - Magic FC841": SAI2LocationData(BASE_LOCATION_ID + 76, 0xFC841),
    "Boa Isle - Sun Spell": SAI2LocationData(BASE_LOCATION_ID + 77, 0xFC894),

    # Puka Isle
    "Puka Isle - 500 Coins": SAI2LocationData(BASE_LOCATION_ID + 90, 0xFD59B),
    "Puka Isle - Magic FD5B2": SAI2LocationData(BASE_LOCATION_ID + 91, 0xFD5B2),
    "Puka Isle - 1000 Coins FD5C9": SAI2LocationData(BASE_LOCATION_ID + 92, 0xFD5C9),
    "Puka Isle - Magic FD5E0": SAI2LocationData(BASE_LOCATION_ID + 93, 0xFD5E0),
    "Puka Isle - Magic FD5F7": SAI2LocationData(BASE_LOCATION_ID + 94, 0xFD5F7),
    "Puka Isle - Health FD60E": SAI2LocationData(BASE_LOCATION_ID + 95, 0xFD60E),
    "Puka Isle - 1000 Coins FD625": SAI2LocationData(BASE_LOCATION_ID + 96, 0xFD625),
    "Puka Isle - Magic FD63C": SAI2LocationData(BASE_LOCATION_ID + 97, 0xFD63C),
    "Puka Isle - Aqua Armor": SAI2LocationData(BASE_LOCATION_ID + 98, 0xFD653),
    "Puka Isle - Thunder Sword": SAI2LocationData(BASE_LOCATION_ID + 99, 0xFD66A),
    "Puka Isle - Aqua Spell": SAI2LocationData(BASE_LOCATION_ID + 100, 0xFD681),

    # Sala Isle
    "Sala Isle - Health FE610": SAI2LocationData(BASE_LOCATION_ID + 110, 0xFE610),
    "Sala Isle - 2000 Coins": SAI2LocationData(BASE_LOCATION_ID + 111, 0xFE627),
    "Sala Isle - Magic FE63E": SAI2LocationData(BASE_LOCATION_ID + 112, 0xFE63E),
    "Sala Isle - Crystal Sword": SAI2LocationData(BASE_LOCATION_ID + 113, 0xFE655),
    "Sala Isle - Aqua Shield": SAI2LocationData(BASE_LOCATION_ID + 114, 0xFE66C),
    "Sala Isle - Magic FE683": SAI2LocationData(BASE_LOCATION_ID + 115, 0xFE683),
    "Sala Isle - Magic FE69A": SAI2LocationData(BASE_LOCATION_ID + 116, 0xFE69A),
    "Sala Isle - Axe": SAI2LocationData(BASE_LOCATION_ID + 117, 0xFE6B1),
    "Sala Isle - Moon Spell": SAI2LocationData(BASE_LOCATION_ID + 118, 0xFE704),

    # Fuwa Isle
    "Fuwa Isle - Health FEF90": SAI2LocationData(BASE_LOCATION_ID + 130, 0xFEF90),
    "Fuwa Isle - 5000 Coins": SAI2LocationData(BASE_LOCATION_ID + 131, 0xFEFA7),
    "Fuwa Isle - Magic FEFBE": SAI2LocationData(BASE_LOCATION_ID + 132, 0xFEFBE),
    "Fuwa Isle - Magic FEFD5": SAI2LocationData(BASE_LOCATION_ID + 133, 0xFEFD5),
    "Fuwa Isle - Power Sword": SAI2LocationData(BASE_LOCATION_ID + 134, 0xFEFEC),
}


location_name_to_id = {
    name: data.code
    for name, data in location_table.items()
}