from BaseClasses import Item, ItemClassification, Location, Region
from worlds.AutoWorld import World, WebWorld


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

    item_name_to_id = {}
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
        return SAI2Item(
            name,
            ItemClassification.filler,
            self.item_name_to_id[name],
            self.player,
        )