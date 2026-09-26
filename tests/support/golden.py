# SPDX-License-Identifier: GPL-3.0-or-later
"""A pytest plugin for the golden files (CONTRIBUTING.md).

Registered in `pyproject.toml` with `-p support.golden`, rather than a second `conftest.py`:
two conftest modules without packages confuse mypy.
"""

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    """Add `--update-golden`, which rewrites the expected files instead of comparing them."""
    parser.addoption(
        "--update-golden",
        action="store_true",
        default=False,
        help="rewrite the golden files in tests/golden/ from the current output",
    )


@pytest.fixture(scope="session")
def update_golden(request: pytest.FixtureRequest) -> bool:
    """Whether this run should rewrite the golden files."""
    return bool(request.config.getoption("--update-golden"))
