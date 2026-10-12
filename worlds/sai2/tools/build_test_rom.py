from pathlib import Path
import sys

ARCHIPELAGO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ARCHIPELAGO_ROOT))

from worlds.sai2.Rom import (
    load_rom,
    save_rom,
    patch_chest_item,
)


INPUT_ROM = ARCHIPELAGO_ROOT / "Super Adventure Island II (USA).sfc"
OUTPUT_ROM = ARCHIPELAGO_ROOT / "SAI2_AP_TEST.sfc"


def main() -> None:
    print("Loading original ROM...")
    rom = load_rom(INPUT_ROM)

    # ---------------------------------------------------------
    # TEST PATCH
    #
    # Poka Isle - Silver Sword
    # ROM chest address: 0x18E78
    #
    # Replace Silver Sword (0x044E)
    # with Fire Sword (0x044F)
    # ---------------------------------------------------------

    patch_chest_item(
        rom,
        chest_address=0x18E78,
        item_id=0x044F,
    )

    print("Patched:")
    print("  Poka Isle - Silver Sword")
    print("  Silver Sword -> Fire Sword")

    save_rom(rom, OUTPUT_ROM)

    print()
    print("ROM created:")
    print(OUTPUT_ROM)


if __name__ == "__main__":
    main()
    main()