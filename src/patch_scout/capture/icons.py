# SPDX-License-Identifier: GPL-3.0-or-later
"""Resolve, decode and store the icons a snapshot refers to (D-09, game-files.md §10).

Icons never fail a capture: anything that cannot be read is recorded with `hash: null` and a
reason. Hashes come from the decoded full-size RGBA pixels, because the game's uncompressed DDS
files use two different channel orders and raw bytes would not compare (P-06).
"""

import hashlib
import logging
import struct
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from io import BytesIO
from typing import Final

from PIL import Image, UnidentifiedImageError

from patch_scout.capture.inputs import InputReader
from patch_scout.snapshot import JsonObject, JsonValue
from patch_scout.store import IconStore

logger = logging.getLogger(__name__)

TECH_TREE_FOLDERS: Final = {
    "Unit": "units",
    "Tech": "tech",
    "Building": "buildings",
}
INGAME: Final = "widgetui/textures/ingame"
STAT_ICON_FOLDER: Final = f"{INGAME}/staticons"
# Image paths in civilizations.json start at "/resources/…" under this folder (verified).
WPFG_ROOT: Final = "resources/_common/wpfg"

# Our stat keys mapped to the game's file names (game-files.md §10). Line of sight and train time
# have no game icon, so the interface falls back to text labels for them.
STAT_ICON_FILES: Final = {
    "hp": "hp.png",
    "melee_attack": "damage.png",
    "pierce_attack": "pierceAttack.png",
    "melee_armor": "armor.png",
    "pierce_armor": "range-armor.png",
    "range": "range.png",
    "movement_speed": "movementSpeed.png",
    "reload_time": "reloadTime.png",
    "food": "food.png",
    "wood": "wood.png",
    "gold": "gold.png",
    "stone": "stone.png",
    "garrison": "garrison.png",
    "convert": "convert.png",
    "work_rate": "workrate.png",
    "blast_radius": "blastRadius.png",
    "hp_regen": "hpRegen.png",
    "hp_loss": "hpLoss.png",
    "transport": "transport.png",
}

_DDS_MAGIC: Final = b"DDS "
_DDS_HEADER_SIZE: Final = 124
_DDS_PIXELS_AT: Final = 4 + _DDS_HEADER_SIZE
_DDPF_FOURCC: Final = 0x4
# Channel orders seen in the game's uncompressed files, as (red, green, blue, alpha) masks.
_RAW_MODES: Final = {
    (0x000000FF, 0x0000FF00, 0x00FF0000, 0xFF000000): "RGBA",
    (0x00FF0000, 0x0000FF00, 0x000000FF, 0xFF000000): "BGRA",
}


@dataclass(frozen=True, slots=True)
class IconRef:
    """What a snapshot stores about one icon."""

    category: str
    picture_index: int | None
    source: str | None
    hash: str | None
    width: int | None
    height: int | None
    missing_reason: str | None

    def to_json(self) -> JsonObject:
        """The form stored in the snapshot."""
        return {
            "category": self.category,
            "picture_index": self.picture_index,
            "source": self.source,
            "hash": self.hash,
            "width": self.width,
            "height": self.height,
            "missing_reason": self.missing_reason,
        }


class IconPipeline:
    """Decodes each distinct icon once and keeps the store filled."""

    def __init__(self, reader: InputReader, store: IconStore) -> None:
        self._reader = reader
        self._store = store
        self._cache: dict[str, IconRef] = {}
        self.warnings: list[str] = []

    def resolve(
        self, category: str, relative: str | None, picture_index: int | None = None
    ) -> JsonObject:
        """Decode and store one icon, returning its reference. Failures are recorded, not raised."""
        if relative is None:
            return self._missing(category, picture_index, "file not found")
        cached = self._cache.get(relative)
        if cached is not None:
            return IconRef(
                category=category,
                picture_index=picture_index,
                source=cached.source,
                hash=cached.hash,
                width=cached.width,
                height=cached.height,
                missing_reason=cached.missing_reason,
            ).to_json()
        ref = self._decode(category, relative, picture_index)
        self._cache[relative] = ref
        return ref.to_json()

    def tech_tree_icon(self, use_type: str | None, picture_index: int | None) -> JsonObject:
        """Find a tech tree icon: `Use Type` picks the folder, `Picture Index` the file (§10)."""
        folder = TECH_TREE_FOLDERS.get(use_type or "")
        if folder is None or picture_index is None:
            return self._missing(folder or "units", picture_index, "no icon folder for this node")
        return self.resolve(
            folder, self._find_indexed(f"{INGAME}/{folder}", picture_index), picture_index
        )

    def wpfg_icon(self, category: str, image_path: JsonValue) -> JsonObject:
        """Find an emblem or unique unit icon from a `civilizations.json` image path."""
        if not isinstance(image_path, str) or not image_path:
            return self._missing(category, None, "no image path")
        relative = f"{WPFG_ROOT}/{image_path.lstrip('/')}"
        if not self._reader.exists(relative):
            folder, _, name = relative.rpartition("/")
            relative = self._reader.find(folder, name) or relative
        return self.resolve(category, relative if self._reader.exists(relative) else None)

    def stat_icons(self) -> JsonObject:
        """The game's stat icons, keyed by our own stat keys (D-09)."""
        icons: JsonObject = {}
        for key, name in STAT_ICON_FILES.items():
            icons[key] = self.resolve("stat_icons", self._reader.find(STAT_ICON_FOLDER, name))
        return icons

    def _find_indexed(self, folder: str, picture_index: int) -> str | None:
        prefix = f"{picture_index:03d}_"
        for relative in self._reader.list_files(folder):
            if relative.rpartition("/")[2].startswith(prefix):
                return relative
        return None

    def _decode(self, category: str, relative: str, picture_index: int | None) -> IconRef:
        data = self._reader.read_bytes(relative, required=False)
        if data is None:
            return IconRef(category, picture_index, relative, None, None, None, "file not readable")
        try:
            image = decode(data)
        except (OSError, ValueError, UnidentifiedImageError) as exc:
            logger.warning("could not decode %s: %s", relative, exc)
            self.warnings.append(f"icon not decoded: {relative}")
            return IconRef(
                category, picture_index, relative, None, None, None, "not a readable image"
            )
        digest = hashlib.sha256(image.tobytes()).hexdigest()
        self._store.put(digest, image)
        return IconRef(category, picture_index, relative, digest, image.width, image.height, None)

    def _missing(self, category: str, picture_index: int | None, reason: str) -> JsonObject:
        return IconRef(category, picture_index, None, None, None, None, reason).to_json()


def decode(data: bytes) -> Image.Image:
    """Decode an icon to full-size RGBA, using the fast path for uncompressed DDS files."""
    raw = decode_uncompressed_dds(data)
    if raw is not None:
        return raw
    with Image.open(BytesIO(data)) as opened:
        return opened.convert("RGBA")


def decode_uncompressed_dds(data: bytes) -> Image.Image | None:
    """Read a 32-bit uncompressed DDS straight from its pixels; None for any other file.

    Pillow decodes these too, but takes about 110 ms each (game-files.md §10); reading the
    buffer with the header's channel order takes well under a millisecond.
    """
    if len(data) < _DDS_PIXELS_AT or data[:4] != _DDS_MAGIC:
        return None
    header_size, _flags, height, width = struct.unpack_from("<IIII", data, 4)
    if header_size != _DDS_HEADER_SIZE:
        return None
    pf_flags, _four_cc, bit_count = struct.unpack_from("<I4sI", data, 80)
    masks = struct.unpack_from("<IIII", data, 92)
    if pf_flags & _DDPF_FOURCC or bit_count != 32:
        return None
    raw_mode = _RAW_MODES.get(masks)
    if raw_mode is None:
        return None
    needed = width * height * 4
    pixels = data[_DDS_PIXELS_AT : _DDS_PIXELS_AT + needed]
    if len(pixels) < needed:
        return None
    return Image.frombuffer("RGBA", (width, height), pixels, "raw", raw_mode, 0, 1)


def attach(
    pipeline: IconPipeline,
    civs: Sequence[JsonValue],
    tech_trees: Mapping[str, JsonValue],
) -> JsonObject:
    """Fill in every icon reference in the civ records and tech trees, and the stat icons."""
    for civ in civs:
        if not isinstance(civ, dict):
            continue
        civ["emblem_icon"] = pipeline.wpfg_icon("emblems", civ.get("emblem_image_path"))
        paths = civ.get("unique_unit_image_paths")
        civ["unique_unit_icons"] = [
            pipeline.wpfg_icon("unique_units", path)
            for path in (paths if isinstance(paths, list) else [])
        ]
    for nodes in tech_trees.values():
        for node in nodes if isinstance(nodes, list) else []:
            if not isinstance(node, dict):
                continue
            use_type = node.get("use_type")
            index = node.get("picture_index")
            node["icon"] = pipeline.tech_tree_icon(
                use_type if isinstance(use_type, str) else None,
                index if isinstance(index, int) else None,
            )
    return pipeline.stat_icons()
