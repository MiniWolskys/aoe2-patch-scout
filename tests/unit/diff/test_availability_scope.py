# SPDX-License-Identifier: GPL-3.0-or-later
"""Who gained a new unit, measured against every civ in the comparison (diff-rules.md).

Civs that list a node as NotAvailable don't have it; counting them read "all 15 civilizations
that have it, except five", for a unit ten civs got (Mounted Crossbowman, 101.103.54800.0).
"""

from support.snapshots import make_snapshot

from patch_scout.diff import compare
from patch_scout.snapshot import JsonValue, Snapshot

UNIT = 2700
GAINING = [f"Civ{index:02d}" for index in range(1, 11)]
WITHOUT = ["Civ11", "Civ12"]
UNLISTED = [f"Civ{index:02d}" for index in range(13, 33)]


def _civ(name: str, index: int) -> JsonValue:
    return {
        "internal_name": name,
        "index": index,
        "name_string_id": None,
        "era": "base",
        "bonus_string_id": None,
        "unique_unit_string_ids": [],
    }


def _build(new: bool) -> Snapshot:
    base: JsonValue = {"use_type": "Unit", "node_id": 4, "node_status": "ResearchedCompleted"}
    trees: dict[str, JsonValue] = {}
    for name in GAINING + WITHOUT + UNLISTED:
        status = "ResearchedCompleted" if name in GAINING else "NotAvailable"
        node: JsonValue = {
            "use_type": "Unit",
            "node_id": UNIT,
            "node_status": status,
            "name_string_id": 1,
        }
        listed = new and name not in UNLISTED
        trees[name] = [base, node] if listed else [base]
    names = GAINING + WITHOUT + UNLISTED
    return make_snapshot(
        civs=[_civ("Gaia", 0)] + [_civ(name, i + 1) for i, name in enumerate(names)],
        tech_trees=trees,
        strings={"tables": {"en": {"1": "Mounted Crossbowman"}}},
    )


def test_a_unit_some_civs_gained_names_them_and_shows_on_their_pages() -> None:
    changes = [
        c for c in compare(_build(False), _build(True)).changes if c.category == "civ_availability"
    ]
    assert {c.kind for c in changes} == {"added"}
    assert {c.scope.kind for c in changes} == {"some"}
    assert {c.scope.civs for c in changes} == {tuple(GAINING)}
    assert sorted(c.civ for c in changes if c.civ) == GAINING


def test_statuses_read_in_words_in_exports() -> None:
    from patch_scout.i18n.catalog import load_catalog
    from patch_scout.report import render_text

    old, new = _build(True), _build(True)
    trees = new.tech_trees
    first = trees["Civ11"]
    assert isinstance(first, list) and isinstance(first[1], dict)
    first[1]["node_status"] = "ResearchRequired"
    text = render_text(compare(old, new), load_catalog("en"))
    assert "Not available → Needs a prerequisite" in text
    assert "NotAvailable" not in text


def test_an_export_names_every_civ_however_many() -> None:
    from patch_scout.i18n.catalog import load_catalog
    from patch_scout.report import render_text

    text = render_text(compare(_build(False), _build(True)), load_catalog("en"))
    assert "(" + ", ".join(GAINING) + ")" in text
    assert "more)" not in text
