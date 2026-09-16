# SPDX-License-Identifier: GPL-3.0-or-later
r"""Where Patch Scout keeps its own data (P-10).

Default: `%LOCALAPPDATA%\PatchScout\`. The folder can be moved in Settings, and tests pass an
explicit root, so nothing here reads a hardcoded absolute path.
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Final

APP_FOLDER_NAME: Final = "PatchScout"


def default_root() -> Path:
    """Return the default data folder, following `%LOCALAPPDATA%` when Windows sets it."""
    local = os.environ.get("LOCALAPPDATA")
    if local:
        return Path(local) / APP_FOLDER_NAME
    return Path.home() / ".local" / "share" / APP_FOLDER_NAME


@dataclass(frozen=True, slots=True)
class DataFolder:
    """The local data folder and everything inside it."""

    root: Path

    @classmethod
    def default(cls) -> "DataFolder":
        """The data folder the app uses unless Settings points somewhere else."""
        return cls(default_root())

    @property
    def snapshots(self) -> Path:
        """Immutable snapshot files, one per capture."""
        return self.root / "snapshots"

    @property
    def icons(self) -> Path:
        """The shared, content-addressed icon store."""
        return self.root / "icons"

    @property
    def backups(self) -> Path:
        """Raw input backups and their manifests (P-19)."""
        return self.root / "backups"

    @property
    def library_file(self) -> Path:
        """The editable metadata index (P-18)."""
        return self.root / "library.json"

    @property
    def settings_file(self) -> Path:
        """User settings: data folder, recent game folders, backups on or off."""
        return self.root / "settings.json"

    def create(self) -> None:
        """Create the folders the app writes to."""
        for folder in (self.root, self.snapshots, self.icons, self.backups):
            folder.mkdir(parents=True, exist_ok=True)
