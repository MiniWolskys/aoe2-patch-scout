# SPDX-License-Identifier: GPL-3.0-or-later
"""The app's log: a file in the data folder, and recent problems for Diagnostics."""

import logging
import threading
from collections.abc import Iterator
from pathlib import Path

import pytest

from patch_scout.gui import logs


@pytest.fixture
def root_logger() -> Iterator[logging.Logger]:
    """The root logger, with its handlers, level and thread hook put back after the test."""
    root = logging.getLogger()
    handlers, level, hook = list(root.handlers), root.level, threading.excepthook
    yield root
    threading.excepthook = hook
    for handler in root.handlers:
        if handler not in handlers:
            handler.close()
    root.handlers[:] = handlers
    root.setLevel(level)


def test_the_log_goes_to_a_file_in_the_data_folder(
    tmp_path: Path, root_logger: logging.Logger
) -> None:
    setup = logs.setup(tmp_path / "PatchScout", debug=False)
    logging.getLogger("patch_scout.test").info("hello from the test")
    for handler in root_logger.handlers:
        handler.flush()
    assert setup.path == tmp_path / "PatchScout" / "logs" / "patch-scout.log"
    assert "hello from the test" in setup.path.read_text(encoding="utf-8")


def test_recent_problems_keep_warnings_and_errors_only(
    tmp_path: Path, root_logger: logging.Logger
) -> None:
    setup = logs.setup(tmp_path / "PatchScout", debug=False)
    log = logging.getLogger("patch_scout.test")
    log.info("routine")
    log.warning("odd")
    log.error("broken")
    lines = setup.recent.lines()
    assert len(lines) == 2
    assert "WARNING" in lines[0] and "odd" in lines[0]
    assert "ERROR" in lines[1] and "broken" in lines[1]


def test_recent_problems_keep_only_the_last_ones() -> None:
    recent = logs.RecentProblems(capacity=3)
    log = logging.getLogger("patch_scout.recent")
    log.addHandler(recent)
    try:
        for number in range(5):
            log.error("problem %d", number)
    finally:
        log.removeHandler(recent)
    assert [line.rsplit(" ", 1)[1] for line in recent.lines()] == ["2", "3", "4"]


def test_a_data_folder_that_cant_be_written_still_logs(
    tmp_path: Path, root_logger: logging.Logger
) -> None:
    blocked = tmp_path / "PatchScout"
    blocked.write_text("a file where the folder should be", encoding="utf-8")
    setup = logs.setup(blocked, debug=False)
    assert setup.path is None
    logging.getLogger("patch_scout.test").error("still recorded")
    assert any("still recorded" in line for line in setup.recent.lines())


def test_an_exception_that_ends_a_thread_is_logged(
    tmp_path: Path, root_logger: logging.Logger
) -> None:
    setup = logs.setup(tmp_path / "PatchScout", debug=False)

    def fail() -> None:
        raise RuntimeError("boom in a worker")

    worker = threading.Thread(target=fail, name="worker")
    worker.start()
    worker.join()
    assert any("uncaught exception in worker" in line for line in setup.recent.lines())
