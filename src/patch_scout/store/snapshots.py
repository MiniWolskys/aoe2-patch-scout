# SPDX-License-Identifier: GPL-3.0-or-later
"""Snapshot files on disk: write once, then read or delete."""

import logging
from pathlib import Path

from patch_scout.errors import PatchScoutError
from patch_scout.snapshot import SUFFIX, Snapshot, read, write
from patch_scout.store.paths import DataFolder

logger = logging.getLogger(__name__)


class SnapshotNotFoundError(PatchScoutError):
    """No snapshot file with that capture ID."""


class SnapshotStore:
    """The snapshot files in one data folder."""

    def __init__(self, folder: DataFolder) -> None:
        self._folder = folder

    def path_for(self, capture_id: str) -> Path:
        """Return the file a capture ID maps to, whether or not it exists."""
        return self._folder.snapshots / f"{capture_id}{SUFFIX}"

    def save(self, snapshot: Snapshot) -> Path:
        """Write a snapshot and return its path. Snapshots are never overwritten."""
        path = self.path_for(snapshot.capture_id)
        if path.exists():
            raise PatchScoutError(f"snapshot {snapshot.capture_id} already exists")
        write(path, snapshot)
        logger.info("wrote snapshot %s (%d bytes)", snapshot.capture_id, path.stat().st_size)
        return path

    def load(self, capture_id: str) -> Snapshot:
        """Read one snapshot."""
        path = self.path_for(capture_id)
        if not path.is_file():
            raise SnapshotNotFoundError(capture_id)
        return read(path)

    def capture_ids(self) -> list[str]:
        """Return every capture ID with a snapshot file, sorted."""
        folder = self._folder.snapshots
        if not folder.is_dir():
            return []
        return sorted(path.name.removesuffix(SUFFIX) for path in folder.glob(f"*{SUFFIX}"))

    def delete(self, capture_id: str) -> None:
        """Remove a snapshot file; deleting one that isn't there is not an error."""
        self.path_for(capture_id).unlink(missing_ok=True)
