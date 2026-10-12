import contextlib
import io
import os
import tempfile
import unittest
from pathlib import Path

from Fill import distribute_items_restrictive
from test.general import setup_multiworld

from .. import SAI2World
from ..Locations import location_table
from ..Multiworld import (
    DISPLAY_SENT_BASE,
    GFX_ENTRY_OFFSET,
    MESSAGE_SIZE,
    SENT_MESSAGES_OFFSET,
    SINK_BASE,
    SENT_TABLE_OFFSET,
    apply_multiworld_patch,
    encode_message,
    message_row,
    received_message,
    sent_message,
)
from ..Rom import EVENT_LOCATION_ITEMS, EVENT_MESSAGE_ADDRESSES, read_chest_data
from .test_rom import BASE_ROM, BASE_ROM_NAME


class TestMessages(unittest.TestCase):
    def test_message_layout(self) -> None:
        message = received_message("Hookshot", "Simon")
        self.assertEqual(len(message), MESSAGE_SIZE)
        self.assertEqual(message[:5], bytes([0x20, 0x00, 0x03, 0x00, 0x00]))

    def test_rows_are_centered_and_uppercase(self) -> None:
        row = message_row("ab")
        self.assertEqual(len(row), 64)
        self.assertEqual(row[30:34], bytes([0x50, 0x2C, 0x51, 0x2C]))  # "AB" at columns 15-16

    def test_long_and_unknown_text(self) -> None:
        row = message_row("x" * 50 + "é")
        self.assertEqual(len(row), 64)
        self.assertEqual(message_row("é~"), message_row(""))

    def test_sent_and_received_wording(self) -> None:
        self.assertEqual(sent_message("Bow", "Link"), encode_message("YOU SENT", "Bow", "TO Link"))
        self.assertEqual(received_message("Bow", "Link"), encode_message("YOU'VE OBTAINED", "Bow", "FROM Link"))


@unittest.skipUnless(BASE_ROM.exists(), f"{BASE_ROM_NAME} not found in the Archipelago root")
class TestMultiworldRom(unittest.TestCase):
    def test_patch_installs_on_vanilla(self) -> None:
        rom = bytearray(BASE_ROM.read_bytes())
        apply_multiworld_patch(rom)
        self.assertNotEqual(rom[GFX_ENTRY_OFFSET:GFX_ENTRY_OFFSET + 8], b"\xFF" * 8)
        with self.assertRaises(ValueError):
            apply_multiworld_patch(rom)  # hook sites are no longer vanilla

    def test_remote_locations_show_sent_messages(self) -> None:
        with contextlib.redirect_stdout(io.StringIO()):
            multiworld = setup_multiworld([SAI2World, SAI2World], seed=7)
            distribute_items_restrictive(multiworld)
            vanilla = BASE_ROM.read_bytes()
            previous = os.getcwd()
            with tempfile.TemporaryDirectory() as work:
                (Path(work) / BASE_ROM_NAME).write_bytes(vanilla)
                os.chdir(work)
                try:
                    multiworld.worlds[1].generate_output(work)
                    rom = next((Path(work) / "output").glob("*_P1_SAI2.sfc")).read_bytes()
                finally:
                    os.chdir(previous)

        remote = 0
        for name, data in location_table.items():
            item = multiworld.get_location(name, 1).item
            if data.rom_address is None or item.player == 1:
                continue
            remote += 1
            if name in EVENT_LOCATION_ITEMS:
                k = rom[EVENT_MESSAGE_ADDRESSES[name]] - DISPLAY_SENT_BASE
            else:
                _memory, marker, rom_item = read_chest_data(rom, data.rom_address)
                self.assertEqual(marker, 0x7B)
                k = rom_item - SINK_BASE
            with self.subTest(location=name):
                self.assertGreaterEqual(k, 0)
                pointer = int.from_bytes(rom[SENT_TABLE_OFFSET + 2 * k:SENT_TABLE_OFFSET + 2 * k + 2], "little")
                offset = 0x170000 + pointer
                self.assertGreaterEqual(offset, SENT_MESSAGES_OFFSET)
                expected = sent_message(item.name, multiworld.get_player_name(item.player))
                self.assertEqual(rom[offset:offset + MESSAGE_SIZE], expected)
        self.assertGreater(remote, 0, "seed should place some items in the other world")
