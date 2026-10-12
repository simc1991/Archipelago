"""Generate many SAI2 fills and report how many fail.

Usage (from the Archipelago root):
    .\\.venv\\Scripts\\python.exe worlds\\sai2\\tools\\fill_stress.py [count] [first_seed] [players]

players = number of SAI2 slots in the multiworld (default 1 = solo).
"""
import contextlib
import io
import logging
import sys
from collections import Counter
from pathlib import Path

ARCHIPELAGO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ARCHIPELAGO_ROOT))

import worlds  # noqa: E402,F401  (must be imported before Fill)
from BaseClasses import CollectionState  # noqa: E402
from Fill import FillError, distribute_items_restrictive  # noqa: E402
from test.general import setup_multiworld  # noqa: E402
from worlds.sai2 import SAI2World  # noqa: E402


def check_seed(seed: int, players: int = 1) -> str | None:
    """Return None when the seed fills and is fully accessible, else a failure reason."""
    with contextlib.redirect_stdout(io.StringIO()):
        try:
            multiworld = setup_multiworld([SAI2World] * players, seed=seed)
            distribute_items_restrictive(multiworld)
        except FillError as error:
            return str(error).splitlines()[0][:70]
    state = CollectionState(multiworld)
    state.sweep_for_advancements()
    if not multiworld.has_beaten_game(state):
        return "game not beatable"
    if any(not location.can_reach(state) for location in multiworld.get_locations()):
        return "unreachable locations"
    return None


def run(count: int, first_seed: int, players: int = 1) -> int:
    logging.disable(logging.WARNING)
    failures: Counter[str] = Counter()
    for seed in range(first_seed, first_seed + count):
        reason = check_seed(seed, players)
        if reason:
            failures[reason] += 1
    failed = sum(failures.values())
    print(f"{count - failed}/{count} seeds OK ({failed} failed)")
    for reason, amount in failures.most_common():
        print(f"  {amount:4d}  {reason}")
    return failed


if __name__ == "__main__":
    total = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    start = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    slots = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    raise SystemExit(1 if run(total, start, slots) else 0)
