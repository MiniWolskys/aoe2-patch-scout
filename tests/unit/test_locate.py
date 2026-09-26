# SPDX-License-Identifier: GPL-3.0-or-later
"""Detection proposes folders, validation confirms them, and nothing is ever assumed (D-19)."""

from pathlib import Path

import pytest
from support import game_tree

from patch_scout import vdf
from patch_scout.locate import (
    Candidate,
    InvalidInstallError,
    detect,
    fixed_file_info_version,
    game_build,
    looks_like_install,
    steam_candidates,
    store_candidates,
    suggest_root,
    validate,
)


@pytest.fixture
def install(tmp_path: Path) -> Path:
    return game_tree.write(tmp_path / "AoE2DE")


def steam_library(root: Path, install_dir: str = "AoE2DE", extra: str = "") -> Path:
    """Write a Steam library with an app manifest for 813780, and return the Steam root."""
    steamapps = root / "steamapps"
    steamapps.mkdir(parents=True, exist_ok=True)
    (steamapps / "libraryfolders.vdf").write_text(
        '"libraryfolders"\n{\n\t"0"\n\t{\n\t\t"path"\t\t"'
        + str(root).replace("\\", "\\\\")
        + '"\n\t}\n}\n',
        encoding="utf-8",
    )
    (steamapps / "appmanifest_813780.acf").write_text(
        '"AppState"\n{\n'
        '\t"appid"\t\t"813780"\n'
        f'\t"installdir"\t\t"{install_dir}"\n'
        '\t"buildid"\t\t"24094652"\n'
        '\t"UserConfig"\n\t{\n\t\t"language"\t\t"english"\n' + extra + "\t}\n}\n",
        encoding="utf-8",
    )
    return root


def test_a_real_looking_folder_is_recognised(install: Path) -> None:
    assert looks_like_install(install) is True


def test_an_empty_folder_is_not_an_install(tmp_path: Path) -> None:
    assert looks_like_install(tmp_path) is False


def test_validate_returns_the_root_it_was_given(install: Path) -> None:
    assert validate(install) == install


def test_validate_walks_up_from_a_sub_folder(install: Path) -> None:
    assert validate(install / "resources" / "_common" / "dat") == install


def test_validate_looks_one_level_down(install: Path) -> None:
    assert validate(install.parent) == install


def test_validate_explains_what_is_missing(tmp_path: Path) -> None:
    with pytest.raises(InvalidInstallError, match=r"empires2_x2_p1\.dat"):
        validate(tmp_path)


def test_validate_refuses_something_that_is_not_a_folder(tmp_path: Path) -> None:
    file = tmp_path / "a.txt"
    file.write_text("x", encoding="utf-8")
    with pytest.raises(InvalidInstallError, match="not a folder"):
        validate(file)


def test_suggest_root_gives_up_quietly(tmp_path: Path) -> None:
    assert suggest_root(tmp_path / "nowhere") is None


def test_steam_detection_reads_the_library_and_the_manifest(tmp_path: Path) -> None:
    root = steam_library(tmp_path / "Steam")
    game_tree.write(root / "steamapps" / "common" / "AoE2DE")
    found = steam_candidates(lambda hive, key, name: str(root) if name == "SteamPath" else None)
    assert [candidate.steam_build_id for candidate in found] == ["24094652"]
    assert found[0].game_language == "english"
    assert found[0].steam_branch is None
    assert found[0].prerelease_hint is False


def test_a_beta_branch_becomes_a_prerelease_hint(tmp_path: Path) -> None:
    root = steam_library(tmp_path / "Steam", extra='\t\t"betakey"\t\t"pup"\n')
    game_tree.write(root / "steamapps" / "common" / "AoE2DE")
    found = steam_candidates(lambda hive, key, name: str(root) if name == "SteamPath" else None)
    assert (found[0].steam_branch, found[0].prerelease_hint) == ("pup", True)


def test_without_steam_in_the_registry_nothing_is_proposed() -> None:
    assert steam_candidates(lambda hive, key, name: None) == []


def test_the_uninstall_entry_is_the_steam_fallback(tmp_path: Path) -> None:
    install = game_tree.write(tmp_path / "AoE2DE")

    def read(hive: str, key: str, name: str) -> str | None:
        return str(install) if name == "InstallLocation" else None

    assert [candidate.path for candidate in steam_candidates(read)] == [install]


def test_detection_keeps_only_folders_that_are_installs(tmp_path: Path) -> None:
    install = game_tree.write(tmp_path / "AoE2DE")
    found = detect(read_value=lambda *args: None, recent=[install, tmp_path / "gone"])
    assert [candidate.path for candidate in found] == [install]


def test_detection_proposes_each_folder_once(tmp_path: Path) -> None:
    install = game_tree.write(tmp_path / "AoE2DE")
    found = detect(read_value=lambda *args: None, recent=[install, install])
    assert len(found) == 1


def test_a_gaming_root_library_is_proposed(tmp_path: Path) -> None:
    drive = tmp_path / "X"
    library = drive / "XboxGames"
    game_tree.write(library / "Age of Empires II" / "Content")
    (drive).mkdir(parents=True, exist_ok=True)
    (drive / ".GamingRoot").write_bytes(
        b"RGBX" + b"\x01\x00\x00\x00" + "XboxGames\x00".encode("utf-16-le")
    )
    found = store_candidates([drive])
    assert [candidate.source for candidate in found] == ["microsoft_store"]


def test_a_drive_without_a_gaming_root_proposes_nothing(tmp_path: Path) -> None:
    assert store_candidates([tmp_path]) == []


def test_a_truncated_gaming_root_proposes_nothing(tmp_path: Path) -> None:
    (tmp_path / ".GamingRoot").write_bytes(b"RGB")
    assert store_candidates([tmp_path]) == []


def test_the_build_is_unknown_when_the_exe_is_missing(install: Path) -> None:
    assert game_build(install) is None


def test_a_version_resource_becomes_a_four_part_build() -> None:
    block = b"\xbd\x04\xef\xfe" + b"\x00\x00\x04\x00"
    block += (101 << 16 | 103).to_bytes(4, "little") + (48987 << 16).to_bytes(4, "little")
    assert fixed_file_info_version(block) == "101.103.48987.0"


def test_a_block_that_is_not_a_version_resource_is_refused() -> None:
    assert fixed_file_info_version(b"\x00" * 16) is None
    assert fixed_file_info_version(b"\x00" * 4) is None


def test_the_vdf_reader_keeps_nested_blocks_and_skips_comments() -> None:
    parsed = vdf.parse('// note\n"root"\n{\n\t"a"\t"1"\n\t"sub" { "b" "2" }\n}\n')
    assert vdf.string(vdf.block(parsed, "root"), "a") == "1"
    assert vdf.string(vdf.block(parsed, "root", "SUB"), "b") == "2"


def test_the_vdf_reader_returns_nothing_for_a_missing_path() -> None:
    assert vdf.block({}, "nope") == {}
    assert vdf.string({"a": {}}, "a") is None


def test_the_vdf_reader_survives_unbalanced_braces() -> None:
    assert vdf.parse('"a" "1" } } "b" "2"') == {"a": "1", "b": "2"}


def test_a_candidate_knows_where_it_came_from(tmp_path: Path) -> None:
    assert Candidate(path=tmp_path, source="recent").prerelease_hint is False
