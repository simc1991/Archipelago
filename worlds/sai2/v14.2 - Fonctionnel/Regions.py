from BaseClasses import Entrance, Location, Region

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
        "Puka - Aqua Stone",
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
        "Puka - Down Jab",
        "Puka - Power Fan",
    ],

    "Puka Isle": [
        "Puka Isle - Moon Stone",
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

    "Final Boss": [
    "Defeat Final Boss",
],
}


def connect_regions(world) -> None:
    """
    Create the logical connections between SAI2 regions.

    Access rules will be assigned separately in Rules.py.
    """

    multiworld = world.multiworld
    player = world.player

    def connect(
        source_name: str,
        target_name: str,
        connection_name: str,
    ) -> None:
        source = multiworld.get_region(source_name, player)
        target = multiworld.get_region(target_name, player)

        entrance = Entrance(
            player,
            connection_name,
            source,
        )

        source.exits.append(entrance)
        entrance.connect(target)

    # Game start
    connect("Menu", "Poka", "Start Game")

    # Poka
    connect("Poka", "Poka Isle", "Enter Poka Isle")
    connect("Poka", "Boa", "Poka to Boa")
    connect("Poka", "Overworld", "Access Overworld")

    # Boa
    connect("Boa", "Boa Isle", "Enter Boa Isle")
    connect("Boa", "Hiya", "Boa to Hiya")
    
    # Boa warps
    connect("Boa Isle", "Hiya", "Boa Isle Warp to Hiya")
    connect("Boa Isle", "Poka", "Boa Isle Warp to Poka")

    # Hiya
    connect("Hiya", "Hiya Isle", "Enter Hiya Isle")
    connect("Hiya", "Star Zone", "Hiya to Star Zone")

    # Star Zone
    connect("Star Zone", "Hiya", "Star Zone to Hiya")
    connect("Star Zone", "Puka", "Star Zone to Puka")
    connect("Star Zone", "Sala", "Star Zone to Sala")

    # Puka
    connect("Puka", "Puka Isle", "Enter Puka Isle")
    connect("Puka Isle", "Puka Drained", "Drain Puka")
    connect("Puka", "Sala", "Puka to Sala")
    connect("Puka", "Star Zone", "Puka to Star Zone")

    # Sala
    connect("Sala", "Sala Isle", "Enter Sala Isle")
    connect("Sala", "Puka", "Sala to Puka")
    connect("Sala", "Star Zone", "Sala to Star Zone")
    connect("Sala", "Fuwa Isle", "Sala to Fuwa Isle")

    # Sala warps
    connect("Sala Isle", "Hiya", "Sala Isle Warp to Hiya")
    connect("Sala Isle", "Puka", "Sala Isle Warp to Puka")

    # Alternate routes to Hiya Isle
    connect("Boa Isle", "Hiya Isle", "Boa Warp to Hiya Isle")
    connect("Sala Isle", "Hiya Isle", "Sala Warp to Hiya Isle")

    # Alternate route to Puka Isle
    connect("Sala Isle", "Puka Isle", "Sala Warp to Puka Isle")

    # Fuwa warps
    connect("Fuwa Isle", "Poka", "Fuwa Warp to Poka")
    connect("Fuwa Isle", "Puka", "Fuwa Warp to Puka")

    # Aqua Gate route:
    # Allows the player to reach Puka directly from the Overworld.
    # The access requirement (Aqua Stone) is defined in Rules.py.
    connect(
        "Overworld",
        "Puka",
        "Aqua Gate to Puka",
    )

    # Sun Gate return route:
    # Allows the player to return from Hiya to Boa.
    # The access requirement (Sun Stone) is defined in Rules.py.
    connect(
        "Hiya",
        "Boa",
        "Hiya to Boa",
    )

    # End game
    connect("Fuwa Isle", "Final Boss", "Enter Final Boss")


def create_regions(world) -> None:
    """
    Create all logical regions and locations for
    Super Adventure Island II.
    """

    multiworld = world.multiworld
    player = world.player

    # Starting region
    menu = Region(
        "Menu",
        player,
        multiworld,
    )

    multiworld.regions.append(menu)

    # Game regions
    for region_name, location_names in region_locations.items():
        region = Region(
            region_name,
            player,
            multiworld,
        )

        for location_name in location_names:
            if location_name == "Defeat Final Boss":
                # Event location - no network address
                location = Location(
                    player,
                    location_name,
                    None,
                    region,
                )
            else:
                data: SAI2LocationData = location_table[location_name]

                location = Location(
                    player,
                    location_name,
                    data.code,
                    region,
                )

            # Add every location exactly once
            region.locations.append(location)

        # Add every region exactly once
        multiworld.regions.append(region)

    # Connect regions only after all regions exist
    connect_regions(world)