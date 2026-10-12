import os
import tempfile
import unittest
from pathlib import Path

from Fill import distribute_items_restrictive

from . import SAI2TestBase
from ..Items import item_table
from ..Locations import location_table
from ..Rom import EVENT_LOCATION_ITEMS, read_chest_data

BASE_ROM_NAME = "Super Adventure Island II (USA).sfc"
BASE_ROM = Path(__file__).resolve().parents[3] / BASE_ROM_NAME

# "FOUND! 1000 COINS" message tilemap for item $0003 (vanilla bytes).
COIN_MESSAGE_OFFSET = 0x050306
VANILLA_1000_COINS_TEXT = bytes.fromhex("A12C A02C A02C A02C 9028 522C 5E2C 582C 5D2C 622C 9028")


@unittest.skipUnless(BASE_ROM.exists(), f"{BASE_ROM_NAME} not found in the Archipelago root")
class TestGeneratedRom(SAI2TestBase):
    def generate_rom(self) -> tuple[bytes, bytearray]:
        distribute_items_restrictive(self.multiworld)
        vanilla = BASE_ROM.read_bytes()
        previous_cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as work:
            (Path(work) / BASE_ROM_NAME).write_bytes(vanilla)
            os.chdir(work)
            try:
                self.world.generate_output(work)
                patched = next((Path(work) / "output").glob("*_SAI2.sfc")).read_bytes()
            finally:
                os.chdir(previous_cwd)
        return vanilla, bytearray(patched)

    def test_1000_coins_message_is_vanilla(self) -> None:
        vanilla, patched = self.generate_rom()
        end = COIN_MESSAGE_OFFSET + len(VANILLA_1000_COINS_TEXT)
        self.assertEqual(vanilla[COIN_MESSAGE_OFFSET:end], VANILLA_1000_COINS_TEXT)
        self.assertEqual(patched[COIN_MESSAGE_OFFSET:end], VANILLA_1000_COINS_TEXT)
        # sai2_rando "??? coins" hook must not be installed.
        self.assertEqual(patched[0x005DEA:0x005DEE], vanilla[0x005DEA:0x005DEE])

    def test_local_chest_items_match_ap_placement(self) -> None:
        _vanilla, patched = self.generate_rom()
        for name, data in location_table.items():
            if name in EVENT_LOCATION_ITEMS or data.rom_address is None:
                continue
            item = self.multiworld.get_location(name, self.player).item
            _memory, marker, rom_item = read_chest_data(patched, data.rom_address)
            if marker != 0x7B or item.player != self.player:
                continue
            with self.subTest(location=name):
                self.assertEqual(rom_item, item_table[item.name].rom_id)
