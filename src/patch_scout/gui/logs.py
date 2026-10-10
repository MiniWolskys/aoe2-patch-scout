# SPDX-License-Identifier: GPL-3.0-or-later
"""Where the app's log goes: a file in the data folder, and recent problems for Diagnostics.

The packaged app has no console, so without a file a user's errors would be lost. The file
rotates, so it never grows past a few MB. Warnings and errors are also kept in memory, so
Diagnostics can show them and "Copy diagnostics" can include them in a bug report.
"""

import logging
from collections import deque
from dataclasses import dataclass
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Final

LOG_FILE: Final = Path("logs") / "patch-scout.log"
MAX_BYTES: Final = 1_000_000
BACKUPS: Final = 3
_FORMAT: Final = "%(asctime)s %(levelname)s %(name)s: %(message)s"


class RecentProblems(logging.Handler):
    """Keeps the last few warnings and errors, formatted, for Diagnostics."""

    def __init__(self, capacity: int = 50) -> None:
        super().__init__(level=logging.WARNING)
        self._lines: deque[str] = deque(maxlen=capacity)
        self.setFormatter(logging.Formatter(_FORMAT, datefmt="%H:%M:%S"))

    def emit(self, record: logging.LogRecord) -> None:
        """Remember one record."""
        try:
            self._lines.append(self.format(record))
        except Exception:  # a logging handler must never raise
            self.handleError(record)

    def lines(self) -> list[str]:
        """The remembered problems, oldest first."""
        return list(self._lines)


@dataclass(frozen=True, slots=True)
class Logging:
    """What `setup` installed."""

    path: Path
    recent: RecentProblems


def setup(data_folder: Path, *, debug: bool) -> Logging:
    """Log to stderr, to a rotating file in the data folder, and to recent problems."""
    path = data_folder / LOG_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    root.setLevel(logging.DEBUG if debug else logging.INFO)
    formatter = logging.Formatter(_FORMAT)
    stream = logging.StreamHandler()
    stream.setFormatter(formatter)
    file = RotatingFileHandler(path, maxBytes=MAX_BYTES, backupCount=BACKUPS, encoding="utf-8")
    file.setFormatter(formatter)
    recent = RecentProblems()
    for handler in (stream, file, recent):
        root.addHandler(handler)
    return Logging(path=path, recent=recent)
