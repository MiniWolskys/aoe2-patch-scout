# SPDX-License-Identifier: GPL-3.0-or-later
"""The comparison itself, on two captures of a synthetic install one build apart."""

from dataclasses import replace
from pathlib import Path

import pytest
from support import pairs
from support.snapshots import make_snapshot

from patch_scout.diff import Options, SideInfo, compare, order
from patch_scout.diff.model import Change, ChangeSet
from patch_scout.snapshot import JsonValue, Snapshot


@pytest.fixture(scope="module")
def change_set(tmp_path_factory: pytest.TempPathFactory) -> ChangeSet:
    pair = pairs.make(tmp_path_factory.mktemp("pair"))
    return compare(pair.old, pair.new)


@pytest.fixture(scope="module")
def pair(tmp_path_factory: pytest.TempPathFactory) -> pairs.Pair:
    return pairs.make(tmp_path_factory.mktemp("pair2"))


def find(change_set: ChangeSet, category: str, name: str, field: str | None = None) -> list[Change]:
    return [
        change
        for change in change_set.changes
        if change.category == category
        and change.entity.name == name
        and (field is None or (change.field is not None and change.field.key == field))
    ]


def test_the_two_sides_carry_what_the_header_shows(change_set: ChangeSet) -> None:
    assert change_set.old.label == "Live build"
    assert change_set.new.label == "PUP build"
    assert change_set.new.prerelease is True
    assert change_set.old.stats_available is True


def test_the_library_label_wins_over_the_one_from_capture(pair: pairs.Pair) -> None:
    result = compare(pair.old, pair.new, new_info=SideInfo(label="Renamed", prerelease=False))
    assert result.new.label == "Renamed"
    assert result.new.prerelease is False


def test_identical_inputs_stop_the_comparison(pair: pairs.Pair) -> None:
    result = compare(pair.old, pair.old)
    assert result.identical is True
    assert result.changes == ()


def test_a_stat_shared_by_every_civ_reads_as_all_civs(change_set: ChangeSet) -> None:
    changes = find(change_set, "unit_stats", "Archery Range", "field.hit_points")
    assert [change.scope.kind for change in changes] == ["all"]
    assert (changes[0].old, changes[0].new) == ("1000", "1100")
    assert changes[0].civ is None


def test_a_stat_that_changed_differently_gives_one_line_per_group(change_set: ChangeSet) -> None:
    changes = find(change_set, "unit_stats", "Archer", "field.hit_points")
    pairs_seen = {(change.old, change.new) for change in changes}
    assert pairs_seen == {("30", "35"), ("35", "45")}


def test_a_civ_specific_change_shows_on_that_civs_page(change_set: ChangeSet) -> None:
    on_bluelanders = [
        change
        for change in change_set.for_civ("Bluelanders")
        if change.category == "unit_stats" and change.entity.name == "Archer"
    ]
    assert [(change.old, change.new) for change in on_bluelanders] == [("35", "45")]


def test_an_all_civs_change_shows_on_the_overall_page(change_set: ChangeSet) -> None:
    overall = [change.entity.name for change in change_set.for_civ(None)]
    assert "Archery Range" in overall


def test_a_node_becoming_available_is_reported(change_set: ChangeSet) -> None:
    changes = find(change_set, "civ_availability", "Archer", "field.node_status")
    assert [(change.old, change.new) for change in changes] == [
        ("NotAvailable", "ResearchedCompleted")
    ]
    assert changes[0].civ == "Bluelanders"


def test_a_tech_cost_change_is_reported(change_set: ChangeSet) -> None:
    changes = find(change_set, "techs", "Fletching", "field.cost")
    assert [(change.old, change.new) for change in changes] == [("100", "120")]


def test_a_changed_bonus_effect_command_shows_its_raw_values(change_set: ChangeSet) -> None:
    changes = find(change_set, "bonuses", "Redlanders", "field.team_bonus_effect")
    assert changes
    assert changes[0].old is not None and changes[0].old.endswith("d=1.20")
    assert changes[0].new is not None and changes[0].new.endswith("d=1.15")
    assert changes[0].detail is not None


def test_a_changed_help_text_is_attached_to_its_node(change_set: ChangeSet) -> None:
    attached = find(change_set, "text", "Archer", "field.help_text")
    assert len(attached) == 1
    assert attached[0].entity.kind == "unit"
    assert attached[0].scope.kind == "all"  # the same text for every civ, so one line
    added = "".join(word.text for word in attached[0].words if word.kind == "added")
    assert added == "foot soldier."


def test_an_icon_redrawn_for_every_civ_reads_as_one_line(change_set: ChangeSet) -> None:
    icons = [change for change in change_set.changes if change.category == "icons"]
    assert {change.scope.kind for change in icons} == {"all"}
    assert {change.entity.name for change in icons} == {"Archer", "Archery Range", "Fletching"}


def test_a_loose_string_lands_in_the_text_category(change_set: ChangeSet) -> None:
    loose = [
        change
        for change in change_set.changes
        if change.category == "text" and change.entity.kind == "string"
    ]
    assert {change.entity.id for change in loose} == {"99001"}
    assert all(change.low_priority for change in loose)


def test_a_string_a_reported_entity_uses_is_not_repeated(change_set: ChangeSet) -> None:
    ids = {
        change.entity.id
        for change in change_set.changes
        if change.category == "text" and change.entity.kind == "string"
    }
    assert "26083" not in ids  # the Archer help text, shown on the Archer node instead


def test_a_redrawn_icon_is_reported_as_low_priority(change_set: ChangeSet) -> None:
    icons = [change for change in change_set.changes if change.category == "icons"]
    assert icons
    assert {change.kind for change in icons} == {"icon_redrawn"}
    assert all(change.low_priority for change in icons)


def test_the_civ_list_counts_the_changes_on_each_page(change_set: ChangeSet) -> None:
    counts = {civ.internal_name: civ.count for civ in change_set.civs}
    assert set(counts) == {"Redlanders", "Bluelanders", "Ancients"}
    assert all(count > 0 for count in counts.values())


def test_the_change_set_is_the_same_every_time(pair: pairs.Pair) -> None:
    first = compare(pair.old, pair.new).to_json()
    second = compare(pair.old, pair.new).to_json()
    assert first == second


def test_unreachable_units_are_left_out_unless_asked_for(pair: pairs.Pair) -> None:
    without = compare(pair.old, pair.new)
    with_them = compare(pair.old, pair.new, options=Options(show_unreachable=True))
    assert len(with_them.changes) >= len(without.changes)


def test_stats_are_not_compared_when_one_side_has_none(pair: pairs.Pair) -> None:
    blind = replace(
        pair.new,
        flags=dict(pair.new.flags) | {"stats_available": False, "stats_unavailable_reason": "test"},
        stats=None,
    )
    result = compare(pair.old, blind)
    assert [notice.kind for notice in result.notices] == ["stats_not_compared"]
    assert not [change for change in result.changes if change.category == "unit_stats"]


def test_a_substituted_layout_raises_a_mild_notice(pair: pairs.Pair) -> None:
    substituted = replace(pair.new, flags=dict(pair.new.flags) | {"format_verified": False})
    kinds = [notice.kind for notice in compare(pair.old, substituted).notices]
    assert kinds == ["layout_substituted"]


def test_a_civ_added_in_the_new_build_is_marked(pair: pairs.Pair) -> None:
    kept = [civ for civ in pair.old.civs if _name(civ) != "Ancients"]
    trimmed = replace(pair.old, civs=kept)
    result = compare(trimmed, pair.new)
    added = [civ for civ in result.civs if civ.added]
    assert [civ.internal_name for civ in added] == ["Ancients"]
    assert any(change.kind == "added" for change in result.for_civ("Ancients"))


def test_a_civ_removed_in_the_new_build_is_reported(pair: pairs.Pair) -> None:
    kept = [civ for civ in pair.new.civs if _name(civ) != "Ancients"]
    trimmed = replace(pair.new, civs=kept)
    result = compare(pair.old, trimmed)
    removed = [
        change
        for change in result.changes
        if change.category == "civilizations" and change.kind == "removed"
    ]
    assert [change.entity.id for change in removed] == ["Ancients"]


def test_an_era_change_is_reported(pair: pairs.Pair) -> None:
    moved = replace(
        pair.new,
        civs=[
            _with_era(civ, "antiquity") if _name(civ) == "Redlanders" else civ
            for civ in pair.new.civs
        ],
    )
    result = compare(pair.old, moved)
    changes = find(result, "civilizations", "Redlanders", "field.era")
    assert [(change.old, change.new) for change in changes] == [("base", "antiquity")]


def test_a_normal_patch_does_not_raise_the_volume_warning(change_set: ChangeSet) -> None:
    assert not [notice for notice in change_set.notices if notice.kind == "unusually_many_changes"]


def test_mass_stat_changes_raise_the_volume_warning(pair: pairs.Pair) -> None:
    huge = compare(pair.old, _change_every_number(pair.new))
    assert any(notice.kind == "unusually_many_changes" for notice in huge.notices)


def test_the_older_build_is_put_first() -> None:
    older = make_snapshot(meta={"capture_id": "a", "captured_at": "t1", "game_build": "1.0.1.0"})
    newer = make_snapshot(meta={"capture_id": "b", "captured_at": "t2", "game_build": "1.0.2.0"})
    assert order(newer, older) == (older, newer)
    assert order(older, newer) == (older, newer)


def test_the_earlier_capture_breaks_a_tie_on_the_build() -> None:
    first = make_snapshot(
        meta={"capture_id": "a", "captured_at": "2026-01-01", "game_build": "1.0"}
    )
    second = make_snapshot(
        meta={"capture_id": "b", "captured_at": "2026-02-01", "game_build": "1.0"}
    )
    assert order(second, first) == (first, second)


def _name(civ: JsonValue) -> JsonValue:
    return civ.get("internal_name") if isinstance(civ, dict) else None


def _with_era(civ: JsonValue, era: str) -> JsonValue:
    return dict(civ) | {"era": era} if isinstance(civ, dict) else civ


def _change_every_number(snapshot: Snapshot) -> Snapshot:
    """A build where every stored number moved, which is what a misread .dat would look like."""
    stats = dict(snapshot.stats or {})
    units = stats.get("units")
    if not isinstance(units, dict):
        return snapshot
    changed: dict[str, JsonValue] = {}
    for key, entry in units.items():
        if not isinstance(entry, dict) or not isinstance(entry.get("base"), dict):
            changed[key] = entry
            continue
        changed[key] = dict(entry) | {"base": _bump(entry["base"]), "overrides": {}}
    return replace(snapshot, stats=stats | {"units": changed})


def _bump(value: JsonValue) -> JsonValue:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value + 7
    if isinstance(value, float):
        return value + 7.0
    if isinstance(value, dict):
        return {key: _bump(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_bump(item) for item in value]
    return value


def test_a_snapshot_pair_with_no_stats_still_compares_the_files_tier(
    tmp_path: Path, pair: pairs.Pair
) -> None:
    stripped = [
        replace(side, flags=dict(side.flags) | {"stats_available": False}, stats=None)
        for side in (pair.old, pair.new)
    ]
    result = compare(stripped[0], stripped[1])
    assert any(change.category == "civ_availability" for change in result.changes)
