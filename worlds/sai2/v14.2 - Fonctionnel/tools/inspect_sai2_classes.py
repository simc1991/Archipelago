 from pathlib import Path
import ast


ROOT = Path(__file__).resolve().parent
TARGET_CLASSES = {
    "EventChestObject",
    "EventMemoryObject",
    "BossMemoryObject",
    "MemoryMixin",
}


def find_python_files():
    for path in ROOT.rglob("*.py"):
        # Ignore common huge/unrelated directories.
        parts = {p.lower() for p in path.parts}

        if any(
            ignored in parts
            for ignored in {
                ".git",
                ".venv",
                "venv",
                "__pycache__",
                "build",
                "dist",
            }
        ):
            continue

        yield path


def main():
    found = 0

    for path in find_python_files():

        try:
            source = path.read_text(
                encoding="utf-8",
                errors="replace",
            )

            tree = ast.parse(
                source,
                filename=str(path),
            )

        except Exception:
            continue

        lines = source.splitlines()

        for node in tree.body:

            if not isinstance(node, ast.ClassDef):
                continue

            if node.name not in TARGET_CLASSES:
                continue

            found += 1

            print("=" * 70)
            print(f"CLASS: {node.name}")
            print(f"FILE : {path.relative_to(ROOT)}")
            print(
                f"LINES: {node.lineno}-{node.end_lineno}"
            )
            print("-" * 70)

            start = max(0, node.lineno - 1)
            end = min(
                len(lines),
                node.end_lineno or node.lineno,
            )

            # Print ONLY the class itself.
            for line_number in range(start, end):

                print(
                    f"{line_number + 1:5}: "
                    f"{lines[line_number]}"
                )

            print()

    print("=" * 70)
    print(f"Classes found: {found}")


if __name__ == "__main__":
    main()