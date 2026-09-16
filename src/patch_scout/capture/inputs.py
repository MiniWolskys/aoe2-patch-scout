# SPDX-License-Identifier: GPL-3.0-or-later
"""Read files from a game install, fingerprinting every one that is touched (P-05).

Every reader goes through this object, so `sources` in the snapshot always covers exactly the
files the capture read, and the raw backup knows what to copy (P-19). Nothing here writes
anything inside the game folder (D-02).
"""

import hashlib
import json
import logging
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from patch_scout.errors import PatchScoutError
from patch_scout.snapshot import JsonObject, JsonValue

logger = logging.getLogger(__name__)


class MissingInputError(PatchScoutError):
    """A file the capture cannot do without is not in the game folder."""


@dataclass(frozen=True, slots=True)
class Fingerprint:
    """What identifies one input file."""

    sha256: str
    size: int

    def to_json(self) -> JsonObject:
        """The form stored in `sources`."""
        return {"sha256": self.sha256, "size": self.size}


class InputReader:
    """A read-only view of one game folder that remembers what it read."""

    def __init__(self, root: Path) -> None:
        self._root = root
        self._fingerprints: dict[str, Fingerprint] = {}
        self._paths: dict[str, Path] = {}
        # Folder listings are cached: the icon folders hold hundreds of files and are looked up
        # once per tech tree node, which is ten thousand times on a real install. The game
        # folder is read-only for the length of a capture, so the listing cannot go stale.
        self._listings: dict[str, list[str]] = {}

    @property
    def root(self) -> Path:
        """The install root every relative path is resolved against."""
        return self._root

    def path(self, relative: str) -> Path:
        """The absolute path of an input, without reading it."""
        return self._root.joinpath(*PurePosixPath(relative).parts)

    def exists(self, relative: str) -> bool:
        """Whether an input file is there."""
        return self.path(relative).is_file()

    def find(self, folder: str, name: str) -> str | None:
        """Find a file in a folder, ignoring case in both the name and the extension.

        The icon folders mix `.DDS` and `.dds`, so a plain path lookup misses half of them
        (game-files.md §10).
        """
        wanted = name.casefold()
        for entry in self._names(folder):
            if entry.casefold() == wanted:
                return f"{folder}/{entry}"
        return None

    def list_files(self, folder: str) -> list[str]:
        """Every file directly in a folder, as relative paths, sorted."""
        return [f"{folder}/{name}" for name in self._names(folder)]

    def _names(self, folder: str) -> list[str]:
        cached = self._listings.get(folder)
        if cached is None:
            try:
                cached = sorted(
                    entry.name for entry in self.path(folder).iterdir() if entry.is_file()
                )
            except OSError:
                cached = []
            self._listings[folder] = cached
        return cached

    def read_bytes(self, relative: str, *, required: bool = True) -> bytes | None:
        """Read a file and fingerprint it; None when it is absent and not required."""
        path = self.path(relative)
        try:
            data = path.read_bytes()
        except OSError as exc:
            if required:
                raise MissingInputError(f"could not read {relative}: {exc.strerror}") from exc
            logger.info("optional input %s is missing", relative)
            return None
        self._fingerprints[relative] = Fingerprint(
            sha256=hashlib.sha256(data).hexdigest(), size=len(data)
        )
        self._paths[relative] = path
        return data

    def read_text(self, relative: str, *, required: bool = True) -> str | None:
        """Read a UTF-8 text input. Game text and JSON are always UTF-8 (game-files.md §3)."""
        data = self.read_bytes(relative, required=required)
        return None if data is None else data.decode("utf-8")

    def read_json(self, relative: str, *, required: bool = True) -> JsonValue:
        """Read a JSON input; a broken optional file reads as None and is logged."""
        text = self.read_text(relative, required=required)
        if text is None:
            return None
        try:
            parsed: JsonValue = json.loads(text)
        except json.JSONDecodeError as exc:
            if required:
                raise MissingInputError(f"{relative} is not valid JSON: {exc}") from exc
            logger.warning("optional input %s is not valid JSON", relative)
            return None
        return parsed

    def sources(self) -> JsonObject:
        """The `sources` section: every file read, with its hash and size."""
        return {name: self._fingerprints[name].to_json() for name in sorted(self._fingerprints)}

    def fingerprint(self, relative: str) -> Fingerprint | None:
        """What was recorded for one input, or None when it was never read."""
        return self._fingerprints.get(relative)

    def backup_entries(self) -> Iterator[tuple[str, str, Path]]:
        """Each read file as (relative path, hash, absolute path), for the raw backup."""
        for name in sorted(self._paths):
            yield name, self._fingerprints[name].sha256, self._paths[name]
