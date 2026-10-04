from BaseClasses import Item, Location, Region
from worlds.AutoWorld import World, WebWorld

from .Items import SAI2ItemData, item_name_to_id, item_table


class SAI2WebWorld(WebWorld):
    theme = "grass"


class SAI2Item(Item):
    game = "Super Adventure Island II"


class SAI2Location(Location):
    game = "Super Adventure Island II"


class SAI2World(World):
    """
    Archipelago integration for Super Adventure Island II (SNES).
    """

    game = "Super Adventure Island II"

    web = SAI2WebWorld()

    item_name_to_id = item_name_to_id
    location_name_to_id = {}

    def create_regions(self) -> None:
        menu = Region("Menu", self.player, self.multiworld)
        self.multiworld.regions.append(menu)

    def create_items(self) -> None:
        pass

    def set_rules(self) -> None:
        pass

    def generate_basic(self) -> None:
        pass

    def create_item(self, name: str) -> SAI2Item:
        data: SAI2ItemData = item_table[name]

        return SAI2Item(
            name,
            data.classification,
            data.code,
            self.player,
        )