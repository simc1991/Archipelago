from BaseClasses import Location, Region

from .Locations import SAI2LocationData, location_table


# Locations assigned to each logical region.
# These names must exactly match the names in Locations.py.
region_locations: dict[str, list[str]] = {
    "Poka": [
        "Poka - Light Stone",
    ],

    "Poka Isle": [
        "Poka Isle - Health 18890",
        "Poka Isle - Dagger",
        "Poka Isle - Health 18D8D",
        "Poka Isle - 500 Coins",
        "Poka Isle - Ice Sword",
        "Poka Isle - 1000 Coins",
        "Poka Isle - Silver Sword",
        "Poka Isle - 2000 Coins",
        "Poka Isle - Fireballs",
        "Poka Isle - Light Spell",
    ],

    "Boa": [
        "Boa - Sun Stone",
    ],

    "Boa Isle": [
        "Boa Isle - Ice Shield",
        "Boa Isle - Magic FC7CE",
        "Boa Isle - Magic FC7E5",
        "Boa Isle - 1000 Coins",
        "Boa Isle - Ice Armor",
        "Boa Isle - 2000 Coins",
        "Boa Isle - Magic FC841",
        "Boa Isle - Sun Spell",
    ],

    "Hiya": [
        "Hiya - Star Stone",
        "Hiya - Shove",
    ],

    "Hiya Isle": [
        "Hiya Isle - Fire Sword",
        "Hiya Isle - Magic FB57E",
        "Hiya Isle - Health FB59A",
        "Hiya Isle - Fire Shield",
        "Hiya Isle - Health FB5D2",
        "Hiya Isle - Health FB5EE",
        "Hiya Isle - Fire Armor",
        "Hiya Isle - 1000 Coins",
        "Hiya Isle - Health FB642",
        "Hiya Isle - Star Spell",
    ],

    "Puka": [
        "Puka - Aqua Stone",
        "Puka - Down Jab",
    ],

    "Puka Isle": [
        "Puka Isle - 500 Coins",
        "Puka Isle - Magic FD5B2",
        "Puka Isle - 1000 Coins FD5C9",
        "Puka Isle - Magic FD5E0",
        "Puka Isle - Magic FD5F7",
        "Puka Isle - Health FD60E",
        "Puka Isle - 1000 Coins FD625",
        "Puka Isle - Magic FD63C",
        "Puka Isle - Aqua Armor",
        "Puka Isle - Thunder Sword",
        "Puka Isle - Aqua Spell",
    ],

    "Puka Drained": [],

    "Sala": [
        "Sala - Moon Stone",
        "Sala - Up Jab",
    ],

    "Sala Isle": [
        "Sala - Elven Flute",
        "Sala Isle - Health FE610",
        "Sala Isle - 2000 Coins",
        "Sala Isle - Magic FE63E",
        "Sala Isle - Crystal Sword",
        "Sala Isle - Aqua Shield",
        "Sala Isle - Magic FE683",
        "Sala Isle - Magic FE69A",
        "Sala Isle - Axe",
        "Sala Isle - Moon Spell",
    ],

    "Star Zone": [
        "Overworld - Sun Ring",
        "Overworld - Magic Wand",
    ],

    "Overworld": [
        "Overworld - Ice Bell",
        "Overworld - Shovel",
    ],

    "Fuwa Isle": [
        "Fuwa - Sky Bell",
        "Fuwa Isle - Health FEF90",
        "Fuwa Isle - 5000 Coins",
        "Fuwa Isle - Magic FEFBE",
        "Fuwa Isle - Magic FEFD5",
        "Fuwa Isle - Power Sword",
    ],

    "Final Boss": [],
}


def create_regions(world) -> None:
    """
    Create the logical regions used by Super Adventure Island II.

    Access rules between these regions will be added separately in Rules.py.
    """

    multiworld = world.multiworld
    player = world.player

    # Starting region
    menu = Region("Menu", player, multiworld)
    multiworld.regions.append(menu)

    # Game regions
    for region_name, location_names in region_locations.items():
        region = Region(region_name, player, multiworld)

        for location_name in location_names:
            data: SAI2LocationData = location_table[location_name]

            location = Location(
                player,
                location_name,
                data.code,
                region,
            )

            region.locations.append(location)

        multiworld.regions.append(region)