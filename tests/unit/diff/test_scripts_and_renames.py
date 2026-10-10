# SPDX-License-Identifier: GPL-3.0-or-later
"""Renamed units and changed scripted effects: both missed on 101.103.54800.0 (diff-rules.md)."""

from support.snapshots import make_snapshot

from patch_scout.diff import compare
from patch_scout.diff.model import Change
from patch_scout.i18n.catalog import load_catalog
from patch_scout.snapshot import JsonValue, Snapshot

CATALOG = load_catalog("en")
EFFECTS = """\
const int KasbahID = 1;
// 52 - Effect of Kasbah for Berbers
void kasbah() {{ {kasbah} }}
// 56 - Effect of Atheism for Huns
void atheism() {{ {atheism} }}
{extra}"""


def _civ(name: str, index: int) -> JsonValue:
    return {
        "internal_name": name,
        "index": index,
        "name_string_id": None,
        "era": "base",
        "bonus_string_id": None,
        "unique_unit_string_ids": [],
    }


def _build(name: str, effects: str) -> Snapshot:
    node = {"use_type": "Unit", "node_id": 250, "node_status": "ResearchedCompleted"}
    return make_snapshot(
        civs=[_civ("Gaia", 0), _civ("Vikings", 1)],
        tech_trees={"Vikings": [node | {"name_string_id": 5250}]},
        strings={"tables": {"en": {"5250": name}}},
        scripts={"effects": effects},
    )


def _effects(kasbah: str = "a();", atheism: str = "b();", extra: str = "") -> str:
    return EFFECTS.format(kasbah=kasbah, atheism=atheism, extra=extra)


def _line(change: Change) -> tuple[str, str, str | None, str | None]:
    assert change.field is not None
    return (
        change.entity.name,
        CATALOG.message(change.field.key, change.field.args),
        change.old,
        change.new,
    )


def test_a_renamed_unit_is_a_headline_with_old_and_new_names() -> None:
    changes = compare(_build("Longboat", _effects()), _build("Longship", _effects())).changes
    [change] = [c for c in changes if c.kind == "renamed"]
    assert change.category == "civ_availability" and change.level == "headline"
    assert _line(change) == ("Longship", "Name", "Longboat", "Longship")


def test_a_changed_script_names_the_function_that_changed() -> None:
    old = _build("Longboat", _effects())
    new = _build("Longboat", _effects(atheism="c();"))
    [change] = [c for c in compare(old, new).changes if c.category == "other_effects"]
    assert _line(change) == ("Effect of Atheism for Huns", "Script changed", None, None)
    assert change.kind == "modified"


def test_a_new_script_function_is_added() -> None:
    old = _build("Longboat", _effects())
    new = _build(
        "Longboat", _effects(extra="// 57 - Effect of Shield Wall for Saxons\nvoid w() {}\n")
    )
    [change] = [c for c in compare(old, new).changes if c.category == "other_effects"]
    assert (change.kind, change.entity.name) == ("added", "Effect of Shield Wall for Saxons")


def test_unchanged_scripts_report_nothing() -> None:
    changes = compare(_build("Longboat", _effects()), _build("Longboat", _effects())).changes
    assert [c for c in changes if c.category == "other_effects"] == []
