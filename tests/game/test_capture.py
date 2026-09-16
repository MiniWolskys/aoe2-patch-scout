# SPDX-License-Identifier: GPL-3.0-or-later
"""Capture a real install. Skipped unless `AOE2DE_PATH` points at one; never runs in CI.

Nothing here writes inside the game folder, and no path is hardcoded (CONTRIBUTING.md).
"""

import os
from pathlib import Path

import pytest

from patch_scout import locate
from patch_scout.capture import runner, stats_tier
from patch_scout.capture.runner import CaptureRequest
from patch_scout.snapshot import Snapshot, dumps
from patch_scout.store import DataFolder

pytestmark = pytest.mark.game


@pytest.fixture(scope="session")
def install() -> Path:
    path = os.environ.get("AOE2DE_PATH")
    if not path:
        pytest.skip("set AOE2DE_PATH to a game folder to run the game tests")
    return locate.validate(Path(path))


@pytest.fixture(scope="session")
def captured(
    install: Path, tmp_path_factory: pytest.TempPathFactory
) -> tuple[Snapshot, DataFolder]:
    folder = DataFolder(tmp_path_factory.mktemp("PatchScout"))
    result = runner.run(
        CaptureRequest(game_folder=install, label="game test", raw_backups=False), folder
    )
    assert result.snapshot is not None
    return result.snapshot, folder


def test_the_install_is_recognised(install: Path) -> None:
    assert locate.looks_like_install(install)


def test_the_game_build_reads_from_the_executable(install: Path) -> None:
    build = locate.game_build(install)
    assert build is not None
    assert build.count(".") == 3


def test_the_files_tier_reads_every_civ(captured: tuple[Snapshot, DataFolder]) -> None:
    snapshot, _ = captured
    assert len(snapshot.civs) >= 40
    first = snapshot.civs[0]
    assert isinstance(first, dict) and first["internal_name"] == "Gaia"


def test_every_civ_with_a_tech_tree_file_has_nodes(captured: tuple[Snapshot, DataFolder]) -> None:
    snapshot, _ = captured
    assert len(snapshot.tech_trees) == len(snapshot.civs) - 1  # Gaia has no tech tree
    assert all(nodes for nodes in snapshot.tech_trees.values())


def test_the_civ_bonus_text_ids_all_check_out(captured: tuple[Snapshot, DataFolder]) -> None:
    snapshot, _ = captured
    missing = [
        civ["internal_name"]
        for civ in snapshot.civs
        if isinstance(civ, dict) and civ["index"] != 0 and civ["bonus_string_id"] is None
    ]
    assert missing == []


def test_the_string_table_resolves_the_tech_tree_labels(
    captured: tuple[Snapshot, DataFolder],
) -> None:
    snapshot, _ = captured
    tables = snapshot.strings["tables"]
    assert isinstance(tables, dict)
    english = tables["en"]
    assert isinstance(english, dict)
    unresolved = 0
    checked = 0
    for nodes in snapshot.tech_trees.values():
        for node in nodes if isinstance(nodes, list) else []:
            if not isinstance(node, dict):
                continue
            checked += 1
            if str(node["name_string_id"]) not in english:
                unresolved += 1
    assert checked > 1000
    assert unresolved == 0


def test_the_help_string_ids_resolve_with_the_offset(captured: tuple[Snapshot, DataFolder]) -> None:
    snapshot, _ = captured
    tables = snapshot.strings["tables"]
    assert isinstance(tables, dict)
    english = tables["en"]
    assert isinstance(english, dict)
    unresolved = [
        node["help_string_id"]
        for nodes in snapshot.tech_trees.values()
        for node in (nodes if isinstance(nodes, list) else [])
        if isinstance(node, dict)
        and isinstance(node["help_string_id"], int)
        and str(node["help_string_id"] - 79000) not in english
    ]
    assert unresolved == []


def test_every_tech_tree_icon_resolves(captured: tuple[Snapshot, DataFolder]) -> None:
    snapshot, _ = captured
    missing = [
        node["icon"]
        for nodes in snapshot.tech_trees.values()
        for node in (nodes if isinstance(nodes, list) else [])
        if isinstance(node, dict)
        and isinstance(node["icon"], dict)
        and node["icon"]["hash"] is None
    ]
    assert missing == []


def test_the_stats_tier_passes_every_gate(captured: tuple[Snapshot, DataFolder]) -> None:
    snapshot, _ = captured
    assert snapshot.flags["stats_unavailable_reason"] is None
    assert snapshot.stats_available is True
    assert snapshot.flags["format_verified"] is True
    checks = snapshot.flags["sanity_checks"]
    assert isinstance(checks, list)
    assert all(isinstance(check, dict) and check["passed"] for check in checks)


def test_the_dat_civ_order_matches_civilizations_json(
    captured: tuple[Snapshot, DataFolder],
) -> None:
    snapshot, _ = captured
    assert snapshot.stats is not None
    civ_dat = snapshot.stats["civ_dat"]
    assert isinstance(civ_dat, list)
    assert len(civ_dat) == len(snapshot.civs)


def test_a_known_unit_value_matches_the_game(captured: tuple[Snapshot, DataFolder]) -> None:
    """Knight (38) has 100 hit points in every civ (game-files.md §4, checked in-game)."""
    snapshot, _ = captured
    assert snapshot.stats is not None
    units = snapshot.stats["units"]
    assert isinstance(units, dict)
    knight = units["38"]
    assert isinstance(knight, dict)
    for index in range(len(snapshot.civs)):
        record = stats_tier.apply_overrides(knight, index)
        if record is not None:
            assert record["hit_points"] == 100


def test_a_known_tech_cost_matches_the_game(captured: tuple[Snapshot, DataFolder]) -> None:
    """Fletching (199) costs 100 food and 50 gold (game-files.md §4, checked in-game)."""
    snapshot, _ = captured
    assert snapshot.stats is not None
    techs = snapshot.stats["techs"]
    assert isinstance(techs, dict)
    fletching = techs["199"]
    assert isinstance(fletching, dict)
    costs = fletching["resource_costs"]
    assert isinstance(costs, list)
    paid = {c["type"]: c["amount"] for c in costs if isinstance(c, dict) and c["flag"]}
    assert paid == {0: 100, 3: 50}


def test_a_snapshot_of_a_real_install_stays_a_sensible_size(
    captured: tuple[Snapshot, DataFolder],
) -> None:
    snapshot, _ = captured
    megabytes = len(dumps(snapshot)) / 1_000_000
    assert megabytes < 60  # uncompressed; the gzipped file is far smaller (P-03)
