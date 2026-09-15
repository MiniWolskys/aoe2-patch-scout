# SPDX-License-Identifier: GPL-3.0-or-later
import pytest

from check_forbidden_files import forbidden_reason, main


@pytest.mark.parametrize(
    "path",
    [
        "resources/_common/dat/empires2_x2_p1.dat",
        "notes/BlkEdge.Dat",
        "tests/fixtures/tree/resources/_common/dat/empires2_x2_p1.dat",
    ],
)
def test_dat_files_are_refused_everywhere(path: str) -> None:
    assert forbidden_reason(path) is not None


@pytest.mark.parametrize(
    "path",
    [
        ".private/README.md",
        "CLAUDE.local.md",
        "docs/CLAUDE.local.md",
        "tests/fixtures/.private/a.md",
    ],
)
def test_private_notes_are_refused_everywhere(path: str) -> None:
    assert forbidden_reason(path) is not None


@pytest.mark.parametrize(
    "path",
    [
        "civilizations.json",
        "data/CivTechTrees/FRANKS.json",
        "data/FuturAvailableUnits.json",
        "icons/sword.DDS",
        "key-value-strings-utf8.txt",
        "franks-utf8.txt",
        "captures/live.snapshot.json.gz",
        "live.aoe2snap",
        "copy/resources/_common/readme.md",
    ],
)
def test_game_files_are_refused_outside_test_fixtures(path: str) -> None:
    assert forbidden_reason(path) is not None


@pytest.mark.parametrize(
    "path",
    [
        "tests/fixtures/tree/resources/_common/dat/civilizations.json",
        "tests/fixtures/tree/resources/_common/dat/CivTechTrees/FRANKS.json",
        "tests/fixtures/icons/placeholder.dds",
        "tests/fixtures/tree/resources/en/strings/key-value/key-value-strings-utf8.txt",
        "tests/fixtures/game-derived/live.snapshot.json.gz",
    ],
)
def test_synthetic_game_files_are_allowed_in_test_fixtures(path: str) -> None:
    assert forbidden_reason(path) is None


@pytest.mark.parametrize(
    "path",
    [
        "pyproject.toml",
        "biome.json",
        "src/patch_scout/i18n/en.json",
        "src/patch_scout/gui/web/assets/badge.png",
        "docs/reference/game-files.md",
    ],
)
def test_project_files_are_allowed(path: str) -> None:
    assert forbidden_reason(path) is None


def test_windows_path_separators_are_understood() -> None:
    assert forbidden_reason(".private\\README.md") is not None


def test_main_succeeds_when_no_file_is_refused() -> None:
    assert main(["pyproject.toml", "src/patch_scout/errors.py"]) == 0


def test_main_fails_when_a_file_is_refused() -> None:
    assert main(["pyproject.toml", "CLAUDE.local.md"]) == 1


def test_main_names_only_the_refused_files(capsys: pytest.CaptureFixture[str]) -> None:
    main(["pyproject.toml", "CLAUDE.local.md", "civilizations.json"])

    errors = capsys.readouterr().err
    assert ("CLAUDE.local.md" in errors, "civilizations.json" in errors) == (True, True)
    assert "pyproject.toml" not in errors
