# SPDX-License-Identifier: GPL-3.0-or-later
"""Raw backups of the input files, stored once per distinct content (P-19).

The backup is a safety net against extractor bugs: with the exact inputs kept, a fixed reader
can re-capture an old build. Backups are never exported (D-12).
"""

import json
import logging
from pathlib import Path

from patch_scout.store.paths import DataFolder

logger = logging.getLogger(__name__)


class BackupStore:
    """Content-addressed copies of input files, plus one manifest per capture."""

    def __init__(self, folder: DataFolder) -> None:
        self._folder = folder

    @property
    def objects(self) -> Path:
        """The folder holding the stored file contents."""
        return self._folder.backups / "objects"

    def object_path(self, digest: str) -> Path:
        """Where a file with that hash is stored, whether or not it exists."""
        return self.objects / digest[:2] / digest

    def store(self, digest: str, source: Path) -> bool:
        """Copy a file in unless its content is already stored; True if it was copied."""
        path = self.object_path(digest)
        if path.is_file():
            return False
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(path.name + ".part")
        temporary.write_bytes(source.read_bytes())
        temporary.replace(path)
        return True

    def write_manifest(self, capture_id: str, files: dict[str, str]) -> Path:
        """Record which object hash each input path of a capture maps to."""
        path = self._folder.backups / f"{capture_id}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"files": files}, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        return path

    def purge(self) -> int:
        """Delete every stored object and manifest; returns how many files were removed."""
        folder = self._folder.backups
        if not folder.is_dir():
            return 0
        removed = 0
        for path in sorted(folder.rglob("*"), reverse=True):
            if path.is_file():
                path.unlink()
                removed += 1
            elif path.is_dir():
                path.rmdir()
        return removed
