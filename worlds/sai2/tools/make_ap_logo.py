"""Convert data/icon.png into the SNES 4bpp sprite used for the AP item.

Writes worlds/sai2/data/ap_logo.bin (1 KB graphics block) and
ap_logo_palette.bin (16 BGR555 colors).

The held-item sprite sheet is 128x16 px made of eight 16x16 cells. The AP item
uses held pose $11 (the generic vanilla item pose): a 16x16 logo held in
Higgins' hand, drawn from cells 0-3. Cells 4-7 keep a 32x32 version in case a
large pose (e.g. $14, used by vanilla for armors) is ever wanted.

Usage (from the Archipelago root, with the venv that has Pillow):
    .\\.venv\\Scripts\\python.exe worlds\\sai2\\tools\\make_ap_logo.py [preview.png]
"""
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parents[1] / "data"

# Index 0 = transparent, 1 = outline, 2-7 = the six petals.
PALETTE = [
    (0, 0, 0), (40, 24, 48),
    (200, 112, 120), (232, 224, 136), (120, 192, 112),
    (120, 128, 192), (200, 144, 192), (216, 160, 120),
    (248, 248, 248),
] + [(0, 0, 0)] * 7


def nearest(rgb):
    best, dist = 2, 1 << 30
    for i in range(2, 8):
        d = sum((a - b) ** 2 for a, b in zip(rgb, PALETTE[i]))
        if d < dist:
            best, dist = i, d
    return best


def build_pixels(size: int):
    src = Image.open(ROOT / "data" / "icon.png").convert("RGBA")
    inner = size - 2
    small = src.resize((inner, inner), Image.LANCZOS)
    px = [[0] * size for _ in range(size)]
    for y in range(inner):
        for x in range(inner):
            r, g, b, a = small.getpixel((x, y))
            if a > 110 and not (r > 225 and g > 225 and b > 225):
                px[y + 1][x + 1] = nearest((r, g, b))
    out = [row[:] for row in px]
    for y in range(size):
        for x in range(size):
            if px[y][x] == 0 and any(
                0 <= y + dy < size and 0 <= x + dx < size and px[y + dy][x + dx] > 1
                for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1))
            ):
                out[y][x] = 1
    return out


def tile_4bpp(px, tx, ty):
    data = bytearray(32)
    for y in range(8):
        for x in range(8):
            v = px[ty * 8 + y][tx * 8 + x]
            bit = 7 - x
            data[2 * y] |= (v & 1) << bit
            data[2 * y + 1] |= ((v >> 1) & 1) << bit
            data[16 + 2 * y] |= ((v >> 2) & 1) << bit
            data[17 + 2 * y] |= ((v >> 3) & 1) << bit
    return bytes(data)


def put_cell(block: bytearray, cell: int, px, ox: int, oy: int) -> None:
    for ty in range(2):
        for tx in range(2):
            tile = ty * 16 + cell * 2 + tx
            block[tile * 32:tile * 32 + 32] = tile_4bpp(px, ox // 8 + tx, oy // 8 + ty)


def build_block(small, big):
    block = bytearray(0x400)
    for cell in range(4):
        put_cell(block, cell, small, 0, 0)
    for cell, (ox, oy) in zip((4, 5, 6, 7), ((0, 0), (16, 0), (0, 16), (16, 16))):
        put_cell(block, cell, big, ox, oy)
    return bytes(block)


def build_palette():
    out = bytearray()
    for r, g, b in PALETTE:
        out += ((r >> 3) | ((g >> 3) << 5) | ((b >> 3) << 10)).to_bytes(2, "little")
    return bytes(out)


def main():
    small, big = build_pixels(16), build_pixels(32)
    OUT.mkdir(exist_ok=True)
    (OUT / "ap_logo.bin").write_bytes(build_block(small, big))
    (OUT / "ap_logo_palette.bin").write_bytes(build_palette())
    if len(sys.argv) > 1:
        img = Image.new("RGB", (32, 32))
        for y in range(32):
            for x in range(32):
                img.putpixel((x, y), PALETTE[big[y][x]] if big[y][x] else (255, 0, 255))
        img.resize((256, 256), Image.NEAREST).save(sys.argv[1])
    print("wrote", OUT / "ap_logo.bin", OUT / "ap_logo_palette.bin")


if __name__ == "__main__":
    main()
