from __future__ import annotations

import ast
import sys
from dataclasses import dataclass
from pathlib import Path


# ============================================================
# Paths
# ============================================================

SCRIPT_DIR = Path(__file__).resolve().parent
SAI2_DIR = SCRIPT_DIR.parent
ARCHIPELAGO_DIR = SAI2_DIR.parent.parent

DEFAULT_ROM = ARCHIPELAGO_DIR / "Super Adventure Island II (USA).sfc"
LOCATIONS_FILE = SAI2_DIR / "Locations.py"


# ============================================================
# Constants
# ============================================================

EXPECTED_ROM_SIZE = 0x180000

VALID_LOW_ITEMS = range(0x0000, 0x0006)
VALID_MAIN_ITEMS = range(0x044E, 0x0480)

# We observed standard chest memory IDs through $053F.
VALID_MEMORY_MIN = 0x044E
VALID_MEMORY_MAX = 0x053F


# Event locations already identified from sai2_rando's
# event_chest_pointers.txt.
EVENT_LOCATION_NAMES = {
    "Puka - Power Fan",
    "Poka - Light Stone",
    "Hiya - Star Stone",
    "Sala - Elven Flute",
    "Fuwa - Sky Bell",
    "Puka - Aqua Stone",
    "Puka Isle - Moon Stone",
    "Boa - Sun Stone",
    "Overworld - Sun Ring",
    "Overworld - Ice Bell",
    "Overworld - Magic Wand",
    "Overworld - Shovel",
    "Boa Isle - Sun Spell",
    "Sala Isle - Moon Spell",
}


TECH_LOCATION_NAMES = {
    "Puka - Down Jab",
    "Sala - Up Jab",
    "Hiya - Shove",
}


# ============================================================
# Data classes
# ============================================================

@dataclass
class LocationInfo:
    name: str
    rom_address: int


@dataclass
class LocationAnalysis:
    name: str
    rom_address: int
    raw: bytes

    classification: str
    confidence: str

    memory_id: int | None = None
    item_id: int | None = None
    marker: int | None = None
    tech_index: int | None = None

    reason: str = ""


# ============================================================
# Helpers
# ============================================================

def read_u16_le(data: bytes, offset: int) -> int:
    return data[offset] | (data[offset + 1] << 8)


def format_bytes(data: bytes) -> str:
    return " ".join(f"{b:02X}" for b in data)


def valid_item_id(value: int) -> bool:
    return (
        value in VALID_LOW_ITEMS
        or value in VALID_MAIN_ITEMS
    )


def valid_memory_id(value: int) -> bool:
    return VALID_MEMORY_MIN <= value <= VALID_MEMORY_MAX


# ============================================================
# Parse Locations.py
# ============================================================

def extract_locations(path: Path) -> list[LocationInfo]:

    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    locations: list[LocationInfo] = []

    for node in ast.walk(tree):

        if not isinstance(node, ast.Dict):
            continue

        for key, value in zip(node.keys, node.values):

            if not (
                isinstance(key, ast.Constant)
                and isinstance(key.value, str)
            ):
                continue

            if not isinstance(value, ast.Call):
                continue

            func = value.func

            if isinstance(func, ast.Name):
                func_name = func.id

            elif isinstance(func, ast.Attribute):
                func_name = func.attr

            else:
                continue

            if func_name != "SAI2LocationData":
                continue

            name = key.value
            rom_address = None

            # Keyword form.
            for keyword in value.keywords:

                if keyword.arg != "rom_address":
                    continue

                try:
                    parsed = ast.literal_eval(keyword.value)
                except Exception:
                    parsed = None

                if isinstance(parsed, int):
                    rom_address = parsed

            # Positional fallback.
            if rom_address is None and len(value.args) >= 2:

                try:
                    parsed = ast.literal_eval(value.args[1])
                except Exception:
                    parsed = None

                if isinstance(parsed, int):
                    rom_address = parsed

            if rom_address is not None:

                locations.append(
                    LocationInfo(
                        name=name,
                        rom_address=rom_address,
                    )
                )

    unique = {
        (location.name, location.rom_address): location
        for location in locations
    }

    return sorted(
        unique.values(),
        key=lambda location: location.rom_address,
    )


# ============================================================
# Standard chest
# ============================================================

def analyze_standard_chest(
    rom: bytes,
    location: LocationInfo,
) -> LocationAnalysis | None:

    address = location.rom_address

    memory_id = read_u16_le(rom, address)
    marker = rom[address + 2]
    item_id = read_u16_le(rom, address + 3)

    if (
        marker == 0x7B
        and valid_memory_id(memory_id)
        and valid_item_id(item_id)
    ):

        return LocationAnalysis(
            name=location.name,
            rom_address=address,
            raw=rom[address:address + 8],
            classification="STANDARD_CHEST",
            confidence="HIGH",
            memory_id=memory_id,
            item_id=item_id,
            marker=marker,
            reason=(
                "Standard chest structure: "
                "memory + $7B + item."
            ),
        )

    return None


# ============================================================
# Event chest
# ============================================================

def analyze_event_chest(
    rom: bytes,
    location: LocationInfo,
) -> LocationAnalysis | None:

    if location.name not in EVENT_LOCATION_NAMES:
        return None

    address = location.rom_address

    item_id = read_u16_le(rom, address)
    marker = rom[address + 2]

    if (
        item_id in VALID_MAIN_ITEMS
        and marker == 0x7E
    ):

        return LocationAnalysis(
            name=location.name,
            rom_address=address,
            raw=rom[address:address + 8],
            classification="EVENT_CHEST",
            confidence="HIGH",
            item_id=item_id,
            marker=marker,
            reason=(
                "Known EventChestObject location with "
                "item ID followed by $7E."
            ),
        )

    return LocationAnalysis(
        name=location.name,
        rom_address=address,
        raw=rom[address:address + 8],
        classification="EVENT_CHEST",
        confidence="LOW",
        item_id=item_id,
        marker=marker,
        reason=(
            "Known event location, but ROM signature "
            "did not match the expected $7E structure."
        ),
    )


# ============================================================
# Technique
# ============================================================

def analyze_technique(
    rom: bytes,
    location: LocationInfo,
) -> LocationAnalysis | None:

    if location.name not in TECH_LOCATION_NAMES:
        return None

    address = location.rom_address
    raw = rom[address:address + 8]

    # Observed:
    #
    # Down Jab:
    # 03 00 01 00 12 01 7E 1C
    #
    # Up Jab:
    # 04 00 01 00 12 01 7E 1C
    #
    # Shove:
    # 05 00 01 00 12 01 7E 1C

    tech_index = read_u16_le(rom, address)

    signature_ok = (
        len(raw) >= 8
        and raw[2:] == bytes(
            [0x01, 0x00, 0x12, 0x01, 0x7E, 0x1C]
        )
    )

    return LocationAnalysis(
        name=location.name,
        rom_address=address,
        raw=raw,
        classification="TECHNIQUE",
        confidence="HIGH" if signature_ok else "LOW",
        tech_index=tech_index,
        reason=(
            "Known technique acquisition structure."
            if signature_ok
            else
            "Known technique location but unexpected ROM signature."
        ),
    )


# ============================================================
# Generic analysis
# ============================================================

def analyze_location(
    rom: bytes,
    location: LocationInfo,
) -> LocationAnalysis:

    address = location.rom_address

    if address < 0 or address + 8 > len(rom):

        return LocationAnalysis(
            name=location.name,
            rom_address=address,
            raw=b"",
            classification="OUT_OF_RANGE",
            confidence="NONE",
            reason="ROM address is outside ROM.",
        )

    # Known special structures first.

    result = analyze_event_chest(
        rom,
        location,
    )

    if result is not None:
        return result

    result = analyze_technique(
        rom,
        location,
    )

    if result is not None:
        return result

    # Then standard chest.

    result = analyze_standard_chest(
        rom,
        location,
    )

    if result is not None:
        return result

    return LocationAnalysis(
        name=location.name,
        rom_address=address,
        raw=rom[address:address + 8],
        classification="UNKNOWN",
        confidence="NONE",
        reason="Unknown ROM structure.",
    )


# ============================================================
# Individual report
# ============================================================

def print_result(result: LocationAnalysis) -> None:

    print("=" * 78)
    print(result.name)

    print(
        f"ROM address : ${result.rom_address:05X}"
    )

    if result.raw:

        print(
            f"Raw bytes   : {format_bytes(result.raw)}"
        )

    print(
        f"Type        : {result.classification}"
    )

    print(
        f"Confidence  : {result.confidence}"
    )

    if result.marker is not None:

        print(
            f"Marker      : ${result.marker:02X}"
        )

    if result.memory_id is not None:

        print(
            f"Memory ID   : ${result.memory_id:04X}"
        )

    if result.item_id is not None:

        print(
            f"Item ID     : ${result.item_id:04X}"
        )

    if result.tech_index is not None:

        print(
            f"Tech index  : ${result.tech_index:04X}"
        )

    if result.classification == "STANDARD_CHEST":

        print(
            f"WRAM check  : ${result.memory_id:04X}"
        )

    else:

        print(
            "WRAM check  : UNKNOWN"
        )

    print(
        f"Reason      : {result.reason}"
    )


# ============================================================
# Generate Python tables
# ============================================================

def print_generated_tables(
    results: list[LocationAnalysis],
) -> None:

    standard = [
        r for r in results
        if r.classification == "STANDARD_CHEST"
    ]

    events = [
        r for r in results
        if r.classification == "EVENT_CHEST"
    ]

    techniques = [
        r for r in results
        if r.classification == "TECHNIQUE"
    ]

    print()
    print("=" * 78)
    print("GENERATED PYTHON TABLES")
    print("=" * 78)

    print()
    print("STANDARD_CHEST_MEMORY = {")

    for result in standard:

        print(
            f'    "{result.name}": '
            f'0x{result.memory_id:04X},'
        )

    print("}")

    print()
    print("EVENT_LOCATION_ITEMS = {")

    for result in events:

        print(
            f'    "{result.name}": '
            f'0x{result.item_id:04X},'
        )

    print("}")

    print()
    print("TECH_LOCATION_INDEX = {")

    for result in techniques:

        print(
            f'    "{result.name}": '
            f'0x{result.tech_index:04X},'
        )

    print("}")


# ============================================================
# Summary
# ============================================================

def print_summary(
    results: list[LocationAnalysis],
) -> None:

    counts: dict[str, int] = {}

    for result in results:

        counts[result.classification] = (
            counts.get(result.classification, 0) + 1
        )

    print()
    print("=" * 78)
    print("SUMMARY")
    print("=" * 78)

    print(
        f"Locations analyzed : {len(results)}"
    )

    for classification in sorted(counts):

        print(
            f"{classification:20s}: "
            f"{counts[classification]}"
        )

    recognized = sum(
        1
        for result in results
        if result.classification
        in {
            "STANDARD_CHEST",
            "EVENT_CHEST",
            "TECHNIQUE",
        }
    )

    high_confidence = sum(
        1
        for result in results
        if result.confidence == "HIGH"
    )

    print()
    print(
        f"Recognized locations : "
        f"{recognized}/{len(results)}"
    )

    print(
        f"High confidence       : "
        f"{high_confidence}/{len(results)}"
    )

    unknown = [
        result
        for result in results
        if result.classification == "UNKNOWN"
    ]

    print()

    if unknown:

        print("UNKNOWN LOCATIONS")
        print("-" * 78)

        for result in unknown:

            print(
                f"${result.rom_address:05X} "
                f"{result.name}"
            )

    else:

        print("No unknown ROM location structures.")


# ============================================================
# Main
# ============================================================

def main() -> int:

    rom_path = DEFAULT_ROM

    if len(sys.argv) >= 2:
        rom_path = Path(sys.argv[1])

    print("Super Adventure Island II")
    print("Archipelago ROM Location Analyzer v2")
    print()

    print(f"ROM       : {rom_path}")
    print(f"Locations : {LOCATIONS_FILE}")
    print()

    if not rom_path.exists():

        print("ERROR: ROM not found.")
        return 1

    if not LOCATIONS_FILE.exists():

        print("ERROR: Locations.py not found.")
        return 1

    rom = rom_path.read_bytes()

    print(
        f"ROM size  : {len(rom)} bytes "
        f"(${len(rom):X})"
    )

    if len(rom) != EXPECTED_ROM_SIZE:

        print(
            "WARNING: Unexpected ROM size."
        )

    locations = extract_locations(
        LOCATIONS_FILE
    )

    print(
        f"Locations with ROM addresses: "
        f"{len(locations)}"
    )

    print()

    results = []

    for location in locations:

        result = analyze_location(
            rom,
            location,
        )

        results.append(result)

        print_result(result)

    print_summary(results)

    print_generated_tables(results)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())