# SPDX-License-Identifier: GPL-3.0-or-later
"""The shared icon store: one downscaled PNG per distinct icon, addressed by hash (P-06).

The hash comes from the decoded full-size RGBA pixels, so it doesn't change when the downscale
pipeline does; `icon_pipeline_version` in the snapshot covers that.
"""

import logging
from io import BytesIO
from pathlib import Path
from typing import Final

from PIL import Image

from patch_scout.store.paths import DataFolder

logger = logging.getLogger(__name__)

# Bump when the stored PNG changes shape; the store then regenerates lazily.
PIPELINE_VERSION: Final = 1
MAX_SIDE: Final = 128


class IconStore:
    """PNG files under `icons/<hash[0:2]>/<hash>.png`."""

    def __init__(self, folder: DataFolder) -> None:
        self._folder = folder

    def path_for(self, digest: str) -> Path:
        """Where an icon with that hash lives, whether or not it exists."""
        return self._folder.icons / digest[:2] / f"{digest}.png"

    def has(self, digest: str) -> bool:
        """Whether the store already holds that icon."""
        return self.path_for(digest).is_file()

    def put(self, digest: str, image: Image.Image) -> Path:
        """Store the downscaled PNG for an icon, unless it's already there."""
        path = self.path_for(digest)
        if path.is_file():
            return path
        path.parent.mkdir(parents=True, exist_ok=True)
        buffer = BytesIO()
        downscale(image).save(buffer, format="PNG", optimize=True)
        temporary = path.with_name(path.name + ".part")
        temporary.write_bytes(buffer.getvalue())
        temporary.replace(path)
        return path

    def read_png(self, digest: str) -> bytes | None:
        """The stored PNG bytes, or None when the store doesn't have that icon."""
        path = self.path_for(digest)
        return path.read_bytes() if path.is_file() else None


def downscale(image: Image.Image) -> Image.Image:
    """Fit an icon inside `MAX_SIDE` without enlarging it, keeping its alpha."""
    rgba = image if image.mode == "RGBA" else image.convert("RGBA")
    longest = max(rgba.width, rgba.height)
    if longest <= MAX_SIDE:
        return rgba
    scale = MAX_SIDE / longest
    size = (max(1, round(rgba.width * scale)), max(1, round(rgba.height * scale)))
    return rgba.resize(size, Image.Resampling.LANCZOS)
