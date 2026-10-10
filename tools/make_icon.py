# SPDX-License-Identifier: GPL-3.0-or-later
"""Draw the app icon, `packaging/patch-scout.ico`: our own artwork, no game content (P-22).

A gold magnifying glass on the app's dark background, with an old (red) and a new (green) bar in
the lens: comparing two builds. Run it again after changing the design:
    uv run python tools/make_icon.py
"""

from pathlib import Path

from PIL import Image, ImageDraw

BACKGROUND = (21, 18, 15, 255)  # theme bg-app
GOLD = (201, 164, 92, 255)  # theme accent
OLD = (227, 91, 80, 255)  # theme --old, #e35b50
NEW = (146, 220, 170, 255)  # theme --new, #92dcaa
SIZE = 256
SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
OUTPUT = Path(__file__).resolve().parent.parent / "packaging" / "patch-scout.ico"


def draw() -> Image.Image:
    """The icon at 256 px; the .ico keeps smaller sizes too."""
    image = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    pen = ImageDraw.Draw(image)
    pen.rounded_rectangle((8, 8, 248, 248), radius=48, fill=BACKGROUND)
    # The handle first, so the lens ring covers its end.
    pen.line((168, 168, 222, 222), fill=GOLD, width=30)
    pen.ellipse((40, 40, 184, 184), outline=GOLD, width=18)
    pen.rounded_rectangle((76, 82, 148, 102), radius=8, fill=OLD)
    pen.rounded_rectangle((76, 122, 148, 142), radius=8, fill=NEW)
    return image


if __name__ == "__main__":
    draw().save(OUTPUT, format="ICO", sizes=SIZES)
