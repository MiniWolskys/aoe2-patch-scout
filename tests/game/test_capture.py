# SPDX-License-Identifier: GPL-3.0-or-later
"""Capture a real install. Skipped unless `AOE2DE_PATH` points at one; never runs in CI.

Nothing here writes inside the game folder, and no path is hardcoded (CONTRIBUTING.md).
"""

import os
from pathlib import Path
from typing import Any

import pytest

from patch_scout import locate
from patch_scout.capture import runner, stats_tier
from patch_scout.capture.runner import CaptureRequest
from patch_scout.diff.vocabulary import Vocabulary
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


def test_the_xs_constants_name_the_armour_classes_the_dat_displays(
    captured: tuple[Snapshot, DataFolder],
) -> None:
    """Displayed melee and pierce armour follow classes 4 and 3, as Constants.xs names them."""
    snapshot, _ = captured
    names = Vocabulary(snapshot)
    assert (names.armour_class(3), names.armour_class(4)) == ("Pierce", "Melee")
    assert snapshot.stats is not None
    units = snapshot.stats["units"]
    assert isinstance(units, dict)
    agree = disagree = 0
    for entry in units.values():
        base = entry.get("base") if isinstance(entry, dict) else None
        type_50 = base.get("type_50") if isinstance(base, dict) else None
        creatable = base.get("creatable") if isinstance(base, dict) else None
        if not isinstance(type_50, dict) or not isinstance(creatable, dict):
            continue
        listed = type_50.get("armours")
        armours = {
            item.get("class_"): item.get("amount")
            for item in (listed if isinstance(listed, list) else [])
            if isinstance(item, dict)
        }
        if 3 not in armours or 4 not in armours:
            continue
        shown = (creatable.get("displayed_pierce_armour"), type_50.get("displayed_melee_armour"))
        if shown == (armours[3], armours[4]):
            agree += 1
        else:
            disagree += 1
    assert agree > 1000
    assert disagree <= agree // 100  # 1 of 1,170 on build 101.103.54800.0


def test_every_civ_tech_tree_is_drawn_without_overlaps(
    captured: tuple[Snapshot, DataFolder],
) -> None:
    """The tech tree view (D-39) on real data: every civ, every available node, one cell each."""
    from typing import Any

    from patch_scout.diff import compare
    from patch_scout.tree.build import build

    snapshot, _ = captured
    change_set = compare(snapshot, snapshot)
    for civ, nodes in snapshot.tech_trees.items():
        view: Any = build(snapshot, snapshot, change_set, civ)
        assert view is not None, civ
        drawn = {node["key"]: node for node in view["nodes"]}
        cells = [(node["column"], node["row"]) for node in drawn.values()]
        assert len(cells) == len(set(cells)), civ
        for child, parent in view["links"]:
            assert child in drawn and parent in drawn, civ
        tree: Any = nodes
        available = {
            f"{node['use_type']}:{node['node_id']}"
            for node in tree
            if node.get("node_status") != "NotAvailable"
        }
        assert available <= set(drawn), civ
        assert all(node["mark"] is None for node in drawn.values()), civ


def _sources(view: object) -> list[Any]:
    details: Any = view
    return [source for group in details["groups"] for source in group["sources"]]


def test_a_units_details_never_take_a_tech_command_for_a_unit_bonus(
    captured: tuple[Snapshot, DataFolder],
) -> None:
    """D-49 on real data. Tech 74 (Scale Mail Armor) shares its number with the Militia, and the
    Bulgarians' tech tree effect halves its cost: that is not a Militia bonus (verified on
    101.103.54800.0)."""
    from typing import Any

    from patch_scout.entity.details import build

    snapshot, _ = captured
    militia: Any = build(snapshot, snapshot, "unit", 74, "Bulgarians")
    assert militia is not None and militia["available"]["new"] is True
    rows = [row for source in _sources(militia) for row in source["rows"]]
    assert rows, "the Militia has techs that affect it"
    assert not any(str(row["field"]["key"]).startswith("effect.tech_") for row in rows)
    names = [source["name"]["args"].get("name") for source in _sources(militia)]
    assert "Forging" in names


def test_an_upgrades_details_list_the_bonus_on_its_research(
    captured: tuple[Snapshot, DataFolder],
) -> None:
    """The Bulgarians' free Militia-line upgrades are a bonus on the Man-at-Arms research."""
    from typing import Any

    from patch_scout.entity.details import build

    snapshot, _ = captured
    man_at_arms: Any = build(snapshot, snapshot, "unit", 75, "Bulgarians")
    assert any(section["key"] == "upgrade" for section in man_at_arms["sections"])
    civ_rows = [
        row
        for group in man_at_arms["groups"]
        if group["key"] == "civ"
        for source in group["sources"]
        for row in source["rows"]
    ]
    assert any(row["field"]["key"] == "effect.tech_resource_cost" for row in civ_rows)


def test_every_node_of_a_few_civs_has_details(captured: tuple[Snapshot, DataFolder]) -> None:
    """Every node of a base civ, a civ with a regional building and a Chronicles civ, and every
    node with no civ chosen, builds without error."""
    from patch_scout.entity.details import build

    snapshot, _ = captured
    kinds = {"Unit": "unit", "Building": "building", "Tech": "tech"}
    chronicles = next(
        str(civ["internal_name"])
        for civ in snapshot.civs
        if isinstance(civ, dict) and civ.get("era") == "antiquity"
    )
    for civ in ("Britons", "Bulgarians", chronicles):
        nodes: Any = snapshot.tech_trees[civ]
        for node in nodes:
            kind, node_id = kinds[str(node["use_type"])], node["node_id"]
            assert isinstance(node_id, int)
            for chosen in (civ, None):
                assert build(snapshot, snapshot, kind, node_id, chosen) is not None, (civ, node)
