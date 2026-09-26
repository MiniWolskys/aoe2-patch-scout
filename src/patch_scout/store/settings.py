# SPDX-License-Identifier: GPL-3.0-or-later
"""User settings: where data lives, which folders were used before, whether backups run (P-10)."""

import json
import logging
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Final

from patch_scout.snapshot import JsonObject, JsonValue
from patch_scout.store.paths import DataFolder

logger = logging.getLogger(__name__)

SETTINGS_VERSION: Final = 1
MAX_RECENT_FOLDERS: Final = 8


@dataclass(frozen=True, slots=True)
class Settings:
    """Everything the Settings screen can change."""

    raw_backups: bool = True
    language: str = "en"
    recent_game_folders: tuple[str, ...] = ()
    data_folder: str | None = None
    last_comparison: tuple[str, str] | None = None

    def to_json(self) -> JsonObject:
        """The form written to `settings.json`."""
        return {
            "version": SETTINGS_VERSION,
            "raw_backups": self.raw_backups,
            "language": self.language,
            "recent_game_folders": list(self.recent_game_folders),
            "data_folder": self.data_folder,
            "last_comparison": list(self.last_comparison) if self.last_comparison else None,
        }


@dataclass(slots=True)
class SettingsStore:
    """Reads and writes `settings.json`; a missing or broken file falls back to the defaults."""

    folder: DataFolder
    _cached: Settings | None = field(default=None, init=False, repr=False)

    def load(self) -> Settings:
        """The current settings."""
        if self._cached is not None:
            return self._cached
        path = self.folder.settings_file
        settings = Settings()
        if path.is_file():
            try:
                settings = _read(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError):
                logger.exception("settings.json could not be read; using the defaults")
        self._cached = settings
        return settings

    def save(self, settings: Settings) -> Settings:
        """Write the settings and keep them for this session."""
        self.folder.root.mkdir(parents=True, exist_ok=True)
        self.folder.settings_file.write_text(
            json.dumps(settings.to_json(), indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        self._cached = settings
        return settings

    def remember_game_folder(self, path: Path) -> Settings:
        """Put a folder at the front of the recently used list."""
        current = self.load()
        text = str(path)
        recent = (text, *(item for item in current.recent_game_folders if item != text))
        return self.save(replace(current, recent_game_folders=recent[:MAX_RECENT_FOLDERS]))

    def remember_comparison(self, old_id: str, new_id: str) -> Settings:
        """Remember which comparison was open, so the app reopens it (ui.md)."""
        return self.save(replace(self.load(), last_comparison=(old_id, new_id)))


def _read(data: JsonValue) -> Settings:
    if not isinstance(data, dict):
        return Settings()
    comparison = data.get("last_comparison")
    pair: tuple[str, str] | None = None
    if isinstance(comparison, list) and len(comparison) == 2:
        old, new = comparison
        if isinstance(old, str) and isinstance(new, str):
            pair = (old, new)
    folders = data.get("recent_game_folders")
    data_folder = data.get("data_folder")
    language = data.get("language")
    return Settings(
        raw_backups=data.get("raw_backups") is not False,
        language=language if isinstance(language, str) else "en",
        recent_game_folders=tuple(
            item for item in (folders if isinstance(folders, list) else []) if isinstance(item, str)
        ),
        data_folder=data_folder if isinstance(data_folder, str) else None,
        last_comparison=pair,
    )
