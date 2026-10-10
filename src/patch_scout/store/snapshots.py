# SPDX-License-Identifier: GPL-3.0-or-later
"""Snapshot files on disk: write once, then read or delete.

Each snapshot has a small index file next to it (`<id>.index.json`) holding what the version
list and the identical-input check need. A snapshot is ~164 MB in memory, so listing versions
must never load one. The index is derived data: missing or damaged, it is rebuilt from the
snapshot.
"""

import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Final, Self

from patch_scout.errors import PatchScoutError
from patch_scout.snapshot import (
    SUFFIX,
    JsonObject,
    JsonValue,
    Snapshot,
    SnapshotFormatError,
    read,
    write,
)
from patch_scout.snapshot.schema import CAPTURE_ID
from patch_scout.store.paths import DataFolder

logger = logging.getLogger(__name__)

INDEX_SUFFIX: Final = ".index.json"


@dataclass(frozen=True, slots=True)
class SnapshotIndex:
    """What a snapshot says about itself, without the snapshot."""

    capture_id: str
    game_build: str | None
    captured_at: str
    stats_available: bool
    stats_unavailable_reason: str | None
    format_verified: bool | None
    label_at_capture: str | None
    prerelease_at_capture: bool
    sources: JsonObject

    @classmethod
    def of(cls, snapshot: Snapshot) -> Self:
        """The index of a loaded snapshot."""
        reason = snapshot.flags.get("stats_unavailable_reason")
        verified = snapshot.flags.get("format_verified")
        label = snapshot.meta.get("label_at_capture")
        return cls(
            capture_id=snapshot.capture_id,
            game_build=snapshot.game_build,
            captured_at=snapshot.captured_at,
            stats_available=snapshot.stats_available,
            stats_unavailable_reason=reason if isinstance(reason, str) else None,
            format_verified=verified if isinstance(verified, bool) else None,
            label_at_capture=label if isinstance(label, str) else None,
            prerelease_at_capture=snapshot.meta.get("prerelease_at_capture") is True,
            sources=dict(snapshot.sources),
        )

    def to_json(self) -> JsonObject:
        """The form written to the index file."""
        return asdict(self)

    @classmethod
    def from_json(cls, data: JsonValue) -> Self | None:
        """An index read back, or None when it isn't shaped like one."""
        if not isinstance(data, dict):
            return None
        try:
            index = cls(**data)  # type: ignore[arg-type]  # checked just below
        except TypeError:
            return None
        checks = (
            isinstance(index.capture_id, str),
            isinstance(index.game_build, (str, type(None))),
            isinstance(index.captured_at, str),
            isinstance(index.stats_available, bool),
            isinstance(index.stats_unavailable_reason, (str, type(None))),
            isinstance(index.format_verified, (bool, type(None))),
            isinstance(index.label_at_capture, (str, type(None))),
            isinstance(index.prerelease_at_capture, bool),
            isinstance(index.sources, dict),
        )
        return index if all(checks) else None


class SnapshotNotFoundError(PatchScoutError):
    """No snapshot file with that capture ID."""


class SnapshotStore:
    """The snapshot files in one data folder."""

    def __init__(self, folder: DataFolder) -> None:
        self._folder = folder

    def path_for(self, capture_id: str) -> Path:
        """Return the file a capture ID maps to, whether or not it exists."""
        if not CAPTURE_ID.match(capture_id):
            raise SnapshotFormatError(f"not a valid capture ID: {capture_id!r}")
        return self._folder.snapshots / f"{capture_id}{SUFFIX}"

    def save(self, snapshot: Snapshot) -> Path:
        """Write a snapshot and return its path. Snapshots are never overwritten."""
        path = self.path_for(snapshot.capture_id)
        if path.exists():
            raise PatchScoutError(f"snapshot {snapshot.capture_id} already exists")
        write(path, snapshot)
        logger.info("wrote snapshot %s (%d bytes)", snapshot.capture_id, path.stat().st_size)
        self._write_index(SnapshotIndex.of(snapshot))
        return path

    def index(self, capture_id: str) -> SnapshotIndex:
        """A snapshot's index, rebuilt from the snapshot when it is missing or damaged."""
        path = self._index_path(capture_id)
        try:
            index = SnapshotIndex.from_json(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            index = None
        if index is not None and index.capture_id == capture_id:
            return index
        index = SnapshotIndex.of(self.load(capture_id))
        self._write_index(index)
        return index

    def _index_path(self, capture_id: str) -> Path:
        return self.path_for(capture_id).with_name(f"{capture_id}{INDEX_SUFFIX}")

    def _write_index(self, index: SnapshotIndex) -> None:
        """Best effort: an index that can't be written is rebuilt next time."""
        path = self._index_path(index.capture_id)
        temporary = path.with_name(path.name + ".part")
        try:
            temporary.write_text(json.dumps(index.to_json(), sort_keys=True), encoding="utf-8")
            temporary.replace(path)
        except OSError as exc:
            logger.warning("the index of %s couldn't be written: %s", index.capture_id, exc)
        finally:
            temporary.unlink(missing_ok=True)

    def load(self, capture_id: str) -> Snapshot:
        """Read one snapshot."""
        path = self.path_for(capture_id)
        if not path.is_file():
            raise SnapshotNotFoundError(capture_id)
        snapshot = read(path)
        if snapshot.capture_id != capture_id:
            raise SnapshotFormatError(f"{path.name} holds snapshot {snapshot.capture_id}")
        return snapshot

    def capture_ids(self) -> list[str]:
        """Return every capture ID with a snapshot file, sorted."""
        folder = self._folder.snapshots
        if not folder.is_dir():
            return []
        return sorted(path.name.removesuffix(SUFFIX) for path in folder.glob(f"*{SUFFIX}"))

    def delete(self, capture_id: str) -> None:
        """Remove a snapshot file and its index; deleting one that isn't there is not an error."""
        self.path_for(capture_id).unlink(missing_ok=True)
        self._index_path(capture_id).unlink(missing_ok=True)
