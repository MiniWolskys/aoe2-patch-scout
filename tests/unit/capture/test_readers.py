# SPDX-License-Identifier: GPL-3.0-or-later
"""The files-tier readers, on a synthetic game folder."""

from collections.abc import Sequence
from pathlib import Path

import pytest
from support import game_tree

from patch_scout.capture import files_tier, strings
from patch_scout.capture.inputs import InputReader, MissingInputError
from patch_scout.snapshot import JsonObject, JsonValue


@pytest.fixture
def reader(tmp_path: Path) -> InputReader:
    return InputReader(game_tree.write(tmp_path / "AoE2DE"))


@pytest.fixture
def string_section(reader: InputReader) -> JsonObject:
    section, _ = strings.read(reader)
    return section


def table(section: JsonObject) -> dict[str, str]:
    tables = section["tables"]
    assert isinstance(tables, dict)
    english = tables["en"]
    assert isinstance(english, dict)
    return {key: value for key, value in english.items() if isinstance(value, str)}


def civ_named(civs: Sequence[JsonValue], name: str) -> JsonObject:
    for civ in civs:
        if isinstance(civ, dict) and civ.get("internal_name") == name:
            return civ
    raise AssertionError(f"no civ called {name}")


def test_an_entry_is_read_with_its_trailing_comment_ignored() -> None:
    parsed = strings.parse('26083 "A ranged unit." //trailing comment\n')
    assert parsed.entries == {"26083": "A ranged unit."}


def test_comments_and_blank_lines_are_skipped() -> None:
    assert strings.parse("// note\n\n   \n").entries == {}


def test_a_line_that_is_not_an_entry_is_skipped() -> None:
    assert strings.parse('4 no quotes here\n5 "kept"\n').entries == {"5": "kept"}


def test_non_numeric_keys_are_kept() -> None:
    assert strings.parse('IDS_OPT_ESC_MENU "ESC Menu"\n').entries == {
        "IDS_OPT_ESC_MENU": "ESC Menu"
    }


def test_the_last_duplicate_wins_and_is_reported() -> None:
    parsed = strings.parse('13170 "first"\n13170 "second"\n')
    assert parsed.entries["13170"] == "second"
    assert parsed.duplicates == ["13170"]


def test_escaped_quotes_do_not_end_the_text() -> None:
    assert strings.parse('1 "say \\"hi\\" now" //x\n').entries == {"1": 'say \\"hi\\" now'}


def test_text_keeps_its_tags_and_escapes_raw() -> None:
    parsed = strings.parse('1 "<b>Bold<b>\\nSecond line"\n')
    assert parsed.entries["1"] == "<b>Bold<b>\\nSecond line"


def test_the_three_string_files_are_merged(string_section: JsonObject) -> None:
    entries = table(string_section)
    assert entries["5083"] == "Archer"
    assert entries["407088"] == "Post-Imperial Age"
    assert entries["IDS_TOOL"] == "Tool"


def test_duplicate_keys_are_recorded_for_the_language(string_section: JsonObject) -> None:
    duplicates = string_section["duplicates"]
    assert isinstance(duplicates, dict)
    assert duplicates["en"] == ["13170"]


def test_a_language_that_is_not_installed_is_a_warning(reader: InputReader) -> None:
    _, warnings = strings.read(reader, ("en", "zz"))
    assert any("resources/zz" in warning for warning in warnings)


def test_the_first_language_is_required(tmp_path: Path) -> None:
    root = game_tree.write(tmp_path / "AoE2DE")
    (root / "resources/en/strings/key-value/key-value-strings-utf8.txt").unlink()
    with pytest.raises(MissingInputError):
        strings.read(InputReader(root))


def test_lookup_resolves_only_real_ids() -> None:
    assert strings.lookup({"5": "Archer"}, 5) == "Archer"
    assert strings.lookup({"5": "Archer"}, 6) is None
    assert strings.lookup({"5": "Archer"}, None) is None


def test_civs_keep_file_order_and_get_an_index(
    reader: InputReader, string_section: JsonObject
) -> None:
    civs = files_tier.read_civs(reader, string_section, [])
    assert [civ["internal_name"] for civ in civs if isinstance(civ, dict)] == [
        "Gaia",
        "Redlanders",
        "Bluelanders",
        "Ancients",
    ]
    assert civ_named(civs, "Redlanders")["index"] == 1


def test_the_two_unique_tech_ids_become_one_list(
    reader: InputReader, string_section: JsonObject
) -> None:
    civs = files_tier.read_civs(reader, string_section, [])
    assert civ_named(civs, "Redlanders")["unique_tech_ids"] == [3, 461]


def test_an_unknown_civ_key_is_kept_under_extra(
    reader: InputReader, string_section: JsonObject
) -> None:
    civs = files_tier.read_civs(reader, string_section, [])
    redlanders = civ_named(civs, "Redlanders")
    assert redlanders["extra"] == {"mystery_key": 7}
    assert redlanders["hud_style"] == "CivWest"


def test_the_bonus_text_id_is_derived_and_checked(
    reader: InputReader, string_section: JsonObject
) -> None:
    civs = files_tier.read_civs(reader, string_section, [])
    assert civ_named(civs, "Redlanders")["bonus_string_id"] == 120150
    assert civ_named(civs, "Gaia")["bonus_string_id"] is None


def test_a_bonus_text_that_does_not_name_the_unique_unit_is_dropped(
    reader: InputReader, string_section: JsonObject
) -> None:
    tables = string_section["tables"]
    assert isinstance(tables, dict) and isinstance(tables["en"], dict)
    tables["en"]["120150"] = "Archer civilization with nobody in particular"
    warnings: list[str] = []
    civs = files_tier.read_civs(reader, string_section, warnings)
    assert civ_named(civs, "Redlanders")["bonus_string_id"] is None
    assert any("unique unit" in warning for warning in warnings)


def test_a_bonus_text_that_is_missing_is_dropped(
    reader: InputReader, string_section: JsonObject
) -> None:
    tables = string_section["tables"]
    assert isinstance(tables, dict) and isinstance(tables["en"], dict)
    del tables["en"]["120150"]
    warnings: list[str] = []
    civs = files_tier.read_civs(reader, string_section, warnings)
    assert civ_named(civs, "Redlanders")["bonus_string_id"] is None
    assert any("does not resolve" in warning for warning in warnings)


def test_civilizations_json_is_required(tmp_path: Path) -> None:
    reader = InputReader(tmp_path)
    with pytest.raises(MissingInputError):
        files_tier.read_civs(reader, {}, [])


def test_a_civilizations_file_without_the_list_is_refused(tmp_path: Path) -> None:
    root = game_tree.write(tmp_path / "AoE2DE")
    (root / "resources/_common/dat/civilizations.json").write_text("{}", encoding="utf-8")
    with pytest.raises(MissingInputError, match="civilization_list"):
        files_tier.read_civs(InputReader(root), {}, [])


def test_both_tech_tree_arrays_are_merged_with_their_names(
    reader: InputReader, string_section: JsonObject
) -> None:
    civs = files_tier.read_civs(reader, string_section, [])
    trees = files_tier.read_tech_trees(reader, civs, [])
    nodes = trees["Redlanders"]
    assert isinstance(nodes, list)
    arrays = {node["array"] for node in nodes if isinstance(node, dict)}
    assert arrays == {"civ_techs_units", "civ_techs_buildings"}


def test_gaia_has_no_tech_tree(reader: InputReader, string_section: JsonObject) -> None:
    civs = files_tier.read_civs(reader, string_section, [])
    assert "Gaia" not in files_tier.read_tech_trees(reader, civs, [])


def test_optional_node_keys_read_as_null(reader: InputReader, string_section: JsonObject) -> None:
    civs = files_tier.read_civs(reader, string_section, [])
    trees = files_tier.read_tech_trees(reader, civs, [])
    nodes = trees["Redlanders"]
    assert isinstance(nodes, list)
    building = next(n for n in nodes if isinstance(n, dict) and n["node_id"] == 87)
    assert building["node_type"] is None
    assert building["link_id"] is None


def test_prerequisites_drop_the_none_slots(reader: InputReader, string_section: JsonObject) -> None:
    civs = files_tier.read_civs(reader, string_section, [])
    trees = files_tier.read_tech_trees(reader, civs, [])
    nodes = trees["Redlanders"]
    assert isinstance(nodes, list)
    archer = next(n for n in nodes if isinstance(n, dict) and n["node_id"] == 4)
    assert archer["prerequisites"] == [{"type": "Tech", "id": 101}]


def test_an_unknown_node_key_is_kept_under_extra(
    reader: InputReader, string_section: JsonObject
) -> None:
    civs = files_tier.read_civs(reader, string_section, [])
    trees = files_tier.read_tech_trees(reader, civs, [])
    nodes = trees["Redlanders"]
    assert isinstance(nodes, list)
    fletching = next(n for n in nodes if isinstance(n, dict) and n["node_id"] == 199)
    assert fletching["extra"] == {"Surprise Key": "kept in extra"}


def test_a_missing_tech_tree_file_is_a_warning(tmp_path: Path, string_section: JsonObject) -> None:
    root = game_tree.write(tmp_path / "AoE2DE")
    (root / "resources/_common/dat/CivTechTrees/BLUELANDERS.json").unlink()
    reader = InputReader(root)
    civs = files_tier.read_civs(reader, string_section, [])
    warnings: list[str] = []
    trees = files_tier.read_tech_trees(reader, civs, warnings)
    assert "Bluelanders" not in trees
    assert any("Bluelanders" in warning for warning in warnings)


def test_building_offers_skip_the_placeholder_civs(reader: InputReader) -> None:
    offers = files_tier.read_building_offers(reader, [])
    assert set(offers) == {"Redlanders", "Bluelanders", "Ancients"}


def test_a_building_offer_keeps_its_unknown_keys(reader: InputReader) -> None:
    offers = files_tier.read_building_offers(reader, [])
    redlanders = offers["Redlanders"]
    assert isinstance(redlanders, dict)
    buildings = redlanders["buildings"]
    assert isinstance(buildings, list) and isinstance(buildings[0], dict)
    assert buildings[0]["id"] == 87
    assert buildings[0]["extra"] == {"Mystery Key": 1}


def test_the_helper_files_are_normalized(reader: InputReader) -> None:
    tier = files_tier.read(reader, {"tables": {"en": {}}})
    assert tier.unit_lines and isinstance(tier.unit_lines[0], dict)
    assert tier.unit_lines[0]["line_id"] == -299
    assert tier.linked_techs and isinstance(tier.linked_techs[0], dict)
    assert tier.linked_techs[0]["type"] == "MutuallyExclusive"
    assert tier.linked_units and isinstance(tier.linked_units[0], dict)
    assert tier.linked_units[0]["units"] == [83, 293]
    assert tier.eras and isinstance(tier.eras[0], dict)
    ages = tier.eras[0]["ages"]
    assert isinstance(ages, list) and isinstance(ages[0], dict)
    assert ages[0]["name_id"] == 4201


def test_a_missing_helper_becomes_a_missing_section(tmp_path: Path) -> None:
    root = game_tree.write(tmp_path / "AoE2DE")
    (root / "resources/_common/dat/eras.json").unlink()
    tier = files_tier.read(InputReader(root), {"tables": {"en": {}}})
    assert "eras" in tier.missing_sections


def test_sources_record_every_file_read(reader: InputReader) -> None:
    files_tier.read(reader, {"tables": {"en": {}}})
    sources = reader.sources()
    assert "resources/_common/dat/civilizations.json" in sources
    entry = sources["resources/_common/dat/civilizations.json"]
    assert isinstance(entry, dict)
    assert len(str(entry["sha256"])) == 64
    assert isinstance(entry["size"], int)


def test_a_file_lookup_ignores_case(reader: InputReader) -> None:
    found = reader.find("widgetui/textures/ingame/units", "017_50730.dds")
    assert found == "widgetui/textures/ingame/units/017_50730.DDS"


def test_a_lookup_in_a_folder_that_is_not_there_gives_none(reader: InputReader) -> None:
    assert reader.find("nowhere", "a.dds") is None
    assert reader.list_files("nowhere") == []


def test_a_required_file_that_is_missing_is_refused(tmp_path: Path) -> None:
    with pytest.raises(MissingInputError):
        InputReader(tmp_path).read_bytes("nope.json")


def test_broken_json_is_refused_when_required(tmp_path: Path) -> None:
    (tmp_path / "a.json").write_text("{", encoding="utf-8")
    with pytest.raises(MissingInputError, match="not valid JSON"):
        InputReader(tmp_path).read_json("a.json")


def test_broken_optional_json_reads_as_nothing(tmp_path: Path) -> None:
    (tmp_path / "a.json").write_text("{", encoding="utf-8")
    assert InputReader(tmp_path).read_json("a.json", required=False) is None
