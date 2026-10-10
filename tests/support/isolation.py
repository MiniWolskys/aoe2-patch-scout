# SPDX-License-Identifier: GPL-3.0-or-later
"""A pytest plugin that keeps every test away from the real data folder and logging setup.

`DataFolder.default()` follows `%LOCALAPPDATA%`, and `app.main` sets up logging there; without
this, a test of the app would write into the developer's own Patch Scout folder.
"""

import logging
from collections.abc import Iterator
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _isolated_data_folder(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "LocalAppData"))
    root = logging.getLogger()
    handlers, level = list(root.handlers), root.level
    yield
    for handler in root.handlers:
        if handler not in handlers:
            handler.close()
    root.handlers[:] = handlers
    root.setLevel(level)
