# SPDX-License-Identifier: GPL-3.0-or-later
"""The stats tier and its gates, on a synthetic `.dat` built with genieutils-py."""

import dataclasses
import zlib

import pytest
from genieutils.datfile import DatFile
from support import dat as sample_dat
from support import game_tree

from patch_scout.capture import gates, stats_tier
from patch_scout.capture.stats_tier import BoundedByteHandler, DatReadError
from patch_scout.snapshot import JsonObject, JsonValue


def files_tier_sections() -> tuple[list[JsonValue], JsonObject, JsonObject]:
    """The files-tier pieces the sanity checks cross-check against."""
    civs: list[JsonValue] = [
        {"internal_name": civ["internal_name"], "index": index}
        for index, civ in enumerate(game_tree.CIVILIZATIONS)
    ]
    trees: JsonObject = {
        "Redlanders": [
            {"node_id": 4, "use_type": "Unit"},
            {"node_id": 87, "use_type": "Building"},
            {"node_id": 199, "use_type": "Tech"},
        ]
    }
    strings: JsonObject = {
        "tables": {"en": {"5004": "Archer", "5087": "Archery Range", "14199": "Fletching"}}
    }
    return civs, trees, strings


def read_sample(**overrides: object) -> stats_tier.StatsResult:
    civs, trees, strings = files_tier_sections()
    dat = sample_dat.sample()
    for name, value in overrides.items():
        setattr(dat, name, value)
    return stats_tier.read(sample_dat.compressed(dat), civs, trees, strings)


def test_a_known_version_is_read_and_flagged_as_verified() -> None:
    result = read_sample()
    assert result.available is True
    assert (result.format_version, result.layout_version) == ("VER 8.9", "VER 8.9")
    assert result.format_verified is True
    assert [attempt.result for attempt in result.attempts] == ["passed"]


def test_every_sanity_check_is_recorded() -> None:
    names = [check.name for check in read_sample().checks]
    assert names == [
        "civ_count",
        "effect_references",
        "tech_tree_references",
        "name_ids_resolve",
        "values_are_plausible",
    ]


def test_units_are_stored_as_a_base_with_per_civ_overrides() -> None:
    stats = read_sample().stats
    assert stats is not None
    units = stats["units"]
    assert isinstance(units, dict)
    archer = units["4"]
    assert isinstance(archer, dict)
    assert archer["base_civs"] == [1, 3]
    assert archer["overrides"] == {"2": {"hit_points": 35}}
    assert archer["absent_civs"] == [0]


def test_a_civ_record_is_rebuilt_from_the_base_and_its_overrides() -> None:
    stats = read_sample().stats
    assert stats is not None
    units = stats["units"]
    assert isinstance(units, dict) and isinstance(units["4"], dict)
    rebuilt = stats_tier.apply_overrides(units["4"], 2)
    assert rebuilt is not None and rebuilt["hit_points"] == 35
    assert stats_tier.apply_overrides(units["4"], 1) == units["4"]["base"]
    assert stats_tier.apply_overrides(units["4"], 0) is None


def test_rebuilding_reaches_a_nested_field() -> None:
    entry: JsonObject = {
        "base": {"type_50": {"max_range": 4.0}},
        "base_civs": [0],
        "overrides": {"1": {"type_50.max_range": 5.0}},
        "absent_civs": [],
    }
    rebuilt = stats_tier.apply_overrides(entry, 1)
    assert rebuilt == {"type_50": {"max_range": 5.0}}
    assert entry["base"] == {"type_50": {"max_range": 4.0}}


def test_rebuilding_an_entry_without_a_base_gives_nothing() -> None:
    assert stats_tier.apply_overrides({"base": None}, 0) is None


def test_techs_and_effects_are_stored_raw() -> None:
    stats = read_sample().stats
    assert stats is not None
    techs, effects = stats["techs"], stats["effects"]
    assert isinstance(techs, dict) and isinstance(effects, dict)
    fletching = techs["199"]
    assert isinstance(fletching, dict)
    assert fletching["name"] == "Fletching"
    costs = fletching["resource_costs"]
    assert isinstance(costs, list)
    assert costs[0] == {"type": 0, "amount": 100, "flag": 1}
    assert effects["1"] == {
        "name": "Fletching",
        "commands": [{"type": 4, "a": -1, "b": 0, "c": 0, "d": 1.0}],
    }


def test_the_civ_records_keep_the_dat_order() -> None:
    stats = read_sample().stats
    assert stats is not None
    civ_dat = stats["civ_dat"]
    assert isinstance(civ_dat, list) and isinstance(civ_dat[1], dict)
    assert civ_dat[1]["name"] == "RedCiv"
    assert civ_dat[1]["tech_tree_effect_id"] == 0


def test_an_unknown_version_is_read_through_layout_substitution() -> None:
    civs, trees, strings = files_tier_sections()
    dat = sample_dat.sample()
    dat.version = "VER 8.9"
    raw = dat.to_bytes()
    faked = b"VER 9.0\x00" + raw[8:]
    result = stats_tier.read(zlib.compress(faked, level=-1, wbits=-15), civs, trees, strings)
    assert result.available is True
    assert result.format_version == "VER 9.0"
    assert result.layout_version == "VER 8.9"
    assert result.format_verified is False
    assert result.attempts[-1].result == "passed"


def test_candidate_layouts_put_the_newest_first_numerically() -> None:
    layouts = stats_tier.candidate_layouts("VER 9.0")
    assert layouts[0] == "VER 8.9"
    assert layouts.index("VER 8.9") < layouts.index("VER 8.8") < layouts.index("VER 8.4")
    assert "VER 7.1" not in layouts


def test_a_known_version_is_the_only_candidate() -> None:
    assert stats_tier.candidate_layouts("VER 8.8") == ["VER 8.8"]


def test_a_layout_name_that_does_not_fit_is_refused() -> None:
    with pytest.raises(DatReadError, match="does not fit"):
        stats_tier.substitute(b"VER 8.9\x00rest", "VER 10.100")


def test_a_file_that_is_not_deflate_gives_no_stats() -> None:
    result = stats_tier.read(b"not compressed at all", [], {}, {})
    assert result.available is False
    assert result.unavailable_reason is not None
    assert "DEFLATE" in result.unavailable_reason


def test_a_truncated_stream_gives_no_stats() -> None:
    civs, trees, strings = files_tier_sections()
    raw = sample_dat.sample().to_bytes()
    truncated = zlib.compress(raw[: len(raw) // 2], level=-1, wbits=-15)
    result = stats_tier.read(truncated, civs, trees, strings)
    assert result.available is False
    assert result.attempts[0].result in ("parse_error", "roundtrip_mismatch")


def test_reading_past_the_end_is_refused_instead_of_reading_zeros() -> None:
    handler = BoundedByteHandler(memoryview(b"1234"))
    with pytest.raises(DatReadError, match="past the end"):
        handler.consume_range(8)


def test_a_failed_sanity_check_gives_no_stats() -> None:
    civs, trees, strings = files_tier_sections()
    trees["Redlanders"] = [{"node_id": 1999, "use_type": "Unit"}]
    result = stats_tier.read(sample_dat.compressed(sample_dat.sample()), civs, trees, strings)
    assert result.available is False
    assert result.attempts[0].result == "sanity_failed"
    assert result.unavailable_reason is not None


def test_the_reason_names_the_layout_when_only_one_was_tried() -> None:
    civs, trees, strings = files_tier_sections()
    trees["Redlanders"] = [{"node_id": 1999, "use_type": "Unit"}]
    result = stats_tier.read(sample_dat.compressed(sample_dat.sample()), civs, trees, strings)
    assert result.unavailable_reason is not None
    assert result.unavailable_reason.startswith("VER 8.9")


def test_a_mismatched_civ_count_fails_the_check() -> None:
    check = gates.sanity_checks(sample_dat.sample(), [{}, {}], {}, {})[0]
    assert (check.name, check.passed) == ("civ_count", False)
    assert "2 in civilizations.json" in check.detail


def test_an_effect_id_that_points_nowhere_fails_the_check() -> None:
    dat = sample_dat.sample()
    dat.civs[1] = dataclasses.replace(dat.civs[1], tech_tree_id=500)
    check = next(
        c for c in gates.sanity_checks(dat, [{}] * 4, {}, {}) if c.name == "effect_references"
    )
    assert check.passed is False
    assert "civ 1" in check.detail


def test_an_implausible_value_fails_the_check() -> None:
    dat = sample_dat.sample()
    slots = list(dat.civs[1].units)
    slots[4] = sample_dat.make_unit(4, "Broken", speed=9999.0)
    dat.civs[1] = dataclasses.replace(dat.civs[1], units=slots)
    civs, trees, strings = files_tier_sections()
    check = next(
        c
        for c in gates.sanity_checks(dat, civs, trees, strings)
        if c.name == "values_are_plausible"
    )
    assert check.passed is False
    assert "speed" in check.detail


def test_a_float_that_is_not_a_number_fails_the_check() -> None:
    dat = sample_dat.sample()
    slots = list(dat.civs[1].units)
    slots[4] = sample_dat.make_unit(4, "Broken", line_of_sight=float("nan"))
    dat.civs[1] = dataclasses.replace(dat.civs[1], units=slots)
    civs, trees, strings = files_tier_sections()
    check = next(
        c
        for c in gates.sanity_checks(dat, civs, trees, strings)
        if c.name == "values_are_plausible"
    )
    assert check.passed is False
    assert "line_of_sight" in check.detail


def test_only_the_records_the_tech_trees_name_are_checked() -> None:
    """Scenario-only objects keep values and name IDs the game never shows (gates.py)."""
    dat = sample_dat.sample()
    slots = list(dat.civs[1].units)
    slots[9] = sample_dat.make_unit(9, "Scenery", speed=9999.0, language_dll_name=424242)
    dat.civs[1] = dataclasses.replace(dat.civs[1], units=slots)
    civs, trees, strings = files_tier_sections()
    checks = {c.name: c for c in gates.sanity_checks(dat, civs, trees, strings)}
    assert checks["values_are_plausible"].passed is True
    assert checks["name_ids_resolve"].passed is True


def test_a_name_id_that_does_not_resolve_fails_the_check() -> None:
    civs, trees, _ = files_tier_sections()
    check = next(
        c
        for c in gates.sanity_checks(
            sample_dat.sample(), civs, trees, {"tables": {"en": {"1": "x"}}}
        )
        if c.name == "name_ids_resolve"
    )
    assert check.passed is False


def test_without_a_string_table_the_name_check_is_skipped() -> None:
    civs, trees, _ = files_tier_sections()
    check = next(
        c
        for c in gates.sanity_checks(sample_dat.sample(), civs, trees, {})
        if c.name == "name_ids_resolve"
    )
    assert check.passed is True
    assert "no string table" in check.detail


def test_the_round_trip_reports_where_a_stream_differs() -> None:
    dat = sample_dat.sample()
    raw = dat.to_bytes()
    passed, detail = gates.round_trip(dat, raw[:-4])
    assert passed is False
    assert "against" in detail


def test_the_round_trip_passes_on_the_stream_it_came_from() -> None:
    dat = sample_dat.sample()
    passed, detail = gates.round_trip(dat, dat.to_bytes())
    assert passed is True
    assert "re-encoded exactly" in detail


def test_first_mismatch_reports_the_shorter_length_when_one_is_a_prefix() -> None:
    assert gates.first_mismatch(b"abcd", b"ab") == 2
    assert gates.first_mismatch(b"abcd", b"abXd") == 2


def test_the_version_string_drops_its_padding() -> None:
    assert stats_tier.format_version(b"VER 8.9\x00rest") == "VER 8.9"


def test_a_parser_that_raises_is_recorded_as_a_parse_error() -> None:
    def boom(_: bytes) -> DatFile:
        raise ValueError("nope")

    result = stats_tier.read(sample_dat.compressed(sample_dat.sample()), [], {}, {}, parser=boom)
    assert result.available is False
    assert result.attempts[0].result == "parse_error"
    assert "nope" in result.attempts[0].detail
