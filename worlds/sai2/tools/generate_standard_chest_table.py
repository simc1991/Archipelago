from pathlib import Path
import sys

ARCHIPELAGO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ARCHIPELAGO_ROOT))

from worlds.sai2.Locations import location_table
from worlds.sai2.Rom import load_rom, read_chest_data


ROM_PATH = ARCHIPELAGO_ROOT / "Super Adventure Island II (USA).sfc"


def main() -> None:
    rom = load_rom(ROM_PATH)

    standard_chests = []

    for name, location in location_table.items():
        address = location.rom_address

        if address is None:
            continue

        memory_id, marker, item_id = read_chest_data(
            rom,
            address,
        )

        # Standard chest structures use marker $7B.
        if marker != 0x7B:
            continue

        standard_chests.append(
            (name, address, memory_id, item_id)
        )

    print("STANDARD_CHEST_CHECKS = {")

    for name, address, memory_id, item_id in standard_chests:
        print(
            f'    "{name}": '
            f'(0x{address:05X}, 0x{memory_id:04X}),'
            f"  # vanilla item 0x{item_id:04X}"
        )

    print("}")
    print()
    print(f"Standard chests: {len(standard_chests)}")


if __name__ == "__main__":
    main()