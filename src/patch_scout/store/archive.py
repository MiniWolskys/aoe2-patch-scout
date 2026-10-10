# SPDX-License-Identifier: GPL-3.0-or-later
"""Version archives: one snapshot with its icons, to share or to start from (P-21).

An archive is a zip file (`.aoe2snap`, snapshot-format.md "Export archive") holding:
- `manifest.json`: format, tool and schema versions, capture ID, icon hashes, baseline flag;
- `snapshot.json.gz`, with the install path removed;
- `library-entry.json`: label, pre-release flag and notes;
- `icons/<hash>.png`, every icon the snapshot references;
- `NOTICE`: the game content is Microsoft's, not covered by the GPL (P-22).

The baseline pack (P-21) is the same archive, marked as a baseline.

Importing trusts nothing: only known names are read, sizes are capped, the snapshot must parse
and migrate, and each icon is decoded and re-encoded before it is stored. An icon already in the
store is never replaced, and nothing is added unless the whole archive is valid.
"""

import gzip
import io
import json
import re
import zipfile
import zlib
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Final, Literal

from PIL import Image, UnidentifiedImageError

from patch_scout.errors import PatchScoutError
from patch_scout.snapshot import JsonObject, JsonValue, Snapshot, SnapshotFormatError
from patch_scout.snapshot.io import dumps, loads
from patch_scout.snapshot.migrations import UnsupportedSchemaError
from patch_scout.snapshot.schema import SCHEMA_VERSION
from patch_scout.store.icons import MAX_SIDE, IconStore
from patch_scout.store.library import Library, LibraryEntry, now_iso
from patch_scout.store.paths import DataFolder
from patch_scout.store.snapshots import SnapshotStore

SUFFIX: Final = ".aoe2snap"
FORMAT: Final = 1
MANIFEST: Final = "manifest.json"
SNAPSHOT: Final = "snapshot.json.gz"
ENTRY: Final = "library-entry.json"
NOTICE_FILE: Final = "NOTICE"
ICONS: Final = "icons/"
# Caps against hostile archives; a real snapshot is about 2.5 MB, 12 MB uncompressed.
MAX_SNAPSHOT_BYTES = 200_000_000
MAX_ICON_BYTES: Final = 1_000_000
MAX_ICONS: Final = 20_000
MAX_SMALL_FILE_BYTES: Final = 1_000_000
_HASH: Final = re.compile(r"^[0-9a-f]{64}$")
# The notice Microsoft's Game Content Usage Rules require, as in the HTML export, and the
# reminder that the game content isn't ours to license (legal.md, P-22).
NOTICE_TEXT: Final = (
    "Age of Empires II \N{COPYRIGHT SIGN} Microsoft Corporation. Patch Scout was created under "
    'Microsoft\'s "Game Content Usage Rules" (https://www.xbox.com/en-US/developers/rules) '
    "using assets from Age of Empires II, and it is not endorsed by or affiliated with "
    "Microsoft.\n\n"
    "The game data and images in this archive are not covered by Patch Scout's licence "
    "(GPL-3.0-or-later).\n"
)

type Reason = Literal[
    "not_an_archive", "too_large", "bad_snapshot", "newer_version", "bad_icon", "missing_file"
]


class ArchiveError(PatchScoutError):
    """An archive that can't be imported; `reason` picks the message the page shows."""

    def __init__(self, reason: Reason, detail: str) -> None:
        super().__init__(f"{reason}: {detail}")
        self.reason: Reason = reason


@dataclass(frozen=True, slots=True)
class ImportResult:
    """What an import did."""

    capture_id: str
    added: bool


# --- export -------------------------------------------------------------------------------------


def export(
    folder: DataFolder,
    capture_id: str,
    path: Path,
    *,
    tool_version: str,
    notice: str,
    baseline: bool = False,
) -> None:
    """Write one stored version, with its icons, as an archive at `path`."""
    snapshot = SnapshotStore(folder).load(capture_id)
    shared = replace(snapshot, meta=dict(snapshot.meta) | {"source_path": None})
    entry = Library(folder).get(capture_id)
    icons = IconStore(folder)
    hashes = sorted(digest for digest in icon_hashes(shared.to_json()) if icons.has(digest))
    manifest: JsonObject = {
        "format": FORMAT,
        "tool_version": tool_version,
        "schema_version": SCHEMA_VERSION,
        "capture_id": capture_id,
        "baseline": baseline,
        "icons": list(hashes),
    }
    library_entry: JsonObject = {
        "label": entry.label if entry else capture_id,
        "prerelease": entry.prerelease if entry else False,
        "notes": entry.notes if entry else "",
    }
    temporary = path.with_name(path.name + ".part")
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as zipped:
            zipped.writestr(MANIFEST, json.dumps(manifest, indent=2, sort_keys=True))
            zipped.writestr(SNAPSHOT, gzip.compress(dumps(shared), mtime=0), zipfile.ZIP_STORED)
            zipped.writestr(ENTRY, json.dumps(library_entry, indent=2, sort_keys=True))
            zipped.writestr(NOTICE_FILE, notice)
            for digest in hashes:
                png = icons.read_png(digest)
                if png is not None:
                    zipped.writestr(f"{ICONS}{digest}.png", png, zipfile.ZIP_STORED)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)  # left only by a failed export


def icon_hashes(value: JsonValue) -> set[str]:
    """Every icon hash a snapshot references: any `{"hash": ..., "category": ...}` object."""
    found: set[str] = set()
    stack: list[JsonValue] = [value]
    while stack:
        item = stack.pop()
        if isinstance(item, dict):
            digest = item.get("hash")
            if "category" in item and isinstance(digest, str) and _HASH.match(digest):
                found.add(digest)
            stack.extend(item.values())
        elif isinstance(item, list):
            stack.extend(item)
    return found


# --- import -------------------------------------------------------------------------------------


def import_(folder: DataFolder, path: Path) -> ImportResult:
    """Add the version an archive holds, unless the library already has it."""
    try:
        zipped = zipfile.ZipFile(path)
    except (zipfile.BadZipFile, OSError, ValueError) as exc:
        raise ArchiveError("not_an_archive", str(exc)) from exc
    try:
        with zipped:
            manifest = _json(zipped, MANIFEST)
            snapshot = read_snapshot(zipped)
            entry = _json(zipped, ENTRY)
            icons = _icons(zipped)
    except (zipfile.BadZipFile, zlib.error, OSError, EOFError, ValueError) as exc:
        # A damaged member (bad CRC, broken deflate stream) shows only when it is read.
        raise ArchiveError("bad_snapshot", f"damaged archive: {exc}") from exc
    store = SnapshotStore(folder)
    library = Library(folder)
    if snapshot.capture_id in store.capture_ids():
        return ImportResult(snapshot.capture_id, added=False)
    icon_store = IconStore(folder)
    for digest, image in icons.items():
        icon_store.put(digest, image)
    store.save(snapshot)
    library.add(
        LibraryEntry(
            capture_id=snapshot.capture_id,
            label=_text(entry.get("label"), snapshot.capture_id),
            prerelease=entry.get("prerelease") is True,
            notes=_text(entry.get("notes"), ""),
            origin="baseline" if manifest.get("baseline") is True else "imported",
            added_at=now_iso(),
        )
    )
    return ImportResult(snapshot.capture_id, added=True)


def read_snapshot(zipped: zipfile.ZipFile) -> Snapshot:
    """The archive's snapshot, decompressed under a size cap, parsed and migrated."""
    compressed = _read(zipped, SNAPSHOT, MAX_SNAPSHOT_BYTES)
    try:
        with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as stream:
            data = stream.read(MAX_SNAPSHOT_BYTES + 1)
    except (OSError, EOFError) as exc:
        raise ArchiveError("bad_snapshot", str(exc)) from exc
    if len(data) > MAX_SNAPSHOT_BYTES:
        raise ArchiveError("too_large", f"{SNAPSHOT} is over {MAX_SNAPSHOT_BYTES} bytes")
    try:
        snapshot = loads(data)
        snapshot.capture_id  # noqa: B018  # a plain name only: it becomes a file name
        return snapshot
    except UnsupportedSchemaError as exc:
        raise ArchiveError("newer_version", str(exc)) from exc
    except (SnapshotFormatError, TypeError, ValueError) as exc:
        raise ArchiveError("bad_snapshot", str(exc)) from exc


def _icons(zipped: zipfile.ZipFile) -> dict[str, Image.Image]:
    """Each `icons/<hash>.png`, decoded and checked; any other name in `icons/` is ignored."""
    names = [
        name
        for name in zipped.namelist()
        if name.startswith(ICONS)
        and name.endswith(".png")
        and _HASH.match(name[len(ICONS) : -len(".png")])
    ]
    if len(names) > MAX_ICONS:
        raise ArchiveError("too_large", f"{len(names)} icons")
    icons: dict[str, Image.Image] = {}
    for name in names:
        data = _read(zipped, name, MAX_ICON_BYTES)
        try:
            with Image.open(io.BytesIO(data)) as image:
                if image.format != "PNG" or max(image.size) > MAX_SIDE:
                    raise ArchiveError("bad_icon", f"{name} is not a PNG icon")
                image.load()
                icons[name[len(ICONS) : -len(".png")]] = image.convert("RGBA")
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
            raise ArchiveError("bad_icon", f"{name}: {exc}") from exc
    return icons


def _json(zipped: zipfile.ZipFile, name: str) -> JsonObject:
    data = _read(zipped, name, MAX_SMALL_FILE_BYTES)
    try:
        parsed = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ArchiveError("bad_snapshot", f"{name}: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ArchiveError("bad_snapshot", f"{name} is not a JSON object")
    return parsed


def _read(zipped: zipfile.ZipFile, name: str, limit: int) -> bytes:
    """One member, refusing it when it is missing or bigger than `limit`."""
    try:
        info = zipped.getinfo(name)
    except KeyError as exc:
        raise ArchiveError("missing_file", f"no {name}") from exc
    if info.file_size > limit:
        raise ArchiveError("too_large", f"{name} is over {limit} bytes")
    with zipped.open(info) as member:
        data = member.read(limit + 1)
    if len(data) > limit:
        raise ArchiveError("too_large", f"{name} is over {limit} bytes")
    return data


def _text(value: JsonValue, default: str) -> str:
    return value if isinstance(value, str) else default
