# SPDX-License-Identifier: GPL-3.0-or-later
"""Read the game's JSON files into snapshot sections (game-files.md sections 5 to 8).

Field names are ours and frozen once in the schema, so each reader maps the game's key names
explicitly. Keys we don't know about are kept verbatim under `extra`, so new game data shows up
as a change instead of disappearing.
"""

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Final

from patch_scout.capture.inputs import InputReader, MissingInputError
from patch_scout.capture.strings import lookup
from patch_scout.snapshot import JsonObject, JsonValue

logger = logging.getLogger(__name__)

DAT_FOLDER: Final = "resources/_common/dat"
CIVILIZATIONS: Final = f"{DAT_FOLDER}/civilizations.json"
TECH_TREES: Final = f"{DAT_FOLDER}/CivTechTrees"
BUILDING_OFFERS: Final = f"{DAT_FOLDER}/futuravailableunits.json"
PAPHOS_OFFERS: Final = f"{DAT_FOLDER}/paphosfutureavailableunits.json"

# Placeholder civ keys in the building-offer files (game-files.md §7).
SKIPPED_OFFER_KEYS: Final = frozenset({"FullTechCiv", "Paphos6", "Paphos7", "Paphos8", "Paphos9"})
# Civ bonus text ID = 120150 + index - 1, re-verified on every capture (game-files.md §6).
BONUS_STRING_BASE: Final = 120150

CIV_KEYS: Final = {
    "internal_name": "internal_name",
    "tech_tree_name": "tech_tree_name",
    "data_name": "data_name",
    "hud_style": "hud_style",
    "era": "era",
    "name_string_id": "name_string_id",
    "computer_name_string_table_offset": "computer_name_string_table_offset",
    "unique_unit_id": "unique_unit_id",
    "elite_unique_unit_id": "elite_unique_unit_id",
    "unique_unit_line": "unique_unit_line",
    "unique_unit_upgrade_id": "unique_unit_upgrade_id",
    "unique_unit_string_ids": "unique_unit_string_ids",
    "tech_tree_image_path": "tech_tree_image_path",
    "emblem_image_path": "emblem_image_path",
    "unique_unit_image_paths": "unique_unit_image_paths",
}
NODE_KEYS: Final = {
    "Name": "name",
    "Use Type": "use_type",
    "Node Status": "node_status",
    "Node Type": "node_type",
    "Name String ID": "name_string_id",
    "Help String ID": "help_string_id",
    "Age ID": "age_id",
    "Building ID": "building_id",
    "Node ID": "node_id",
    "Picture Index": "picture_index",
    "Link ID": "link_id",
    "Link Node Type": "link_node_type",
    "Draw Node Type": "draw_node_type",
    "Trigger Tech ID": "trigger_tech_id",
    "Building upgraded from ID": "building_upgraded_from_id",
    "Building in new column": "building_in_new_column",
}
# Optional node keys are stored as null when the game file leaves them out (game-files.md §5).
OPTIONAL_NODE_KEYS: Final = (
    "node_type",
    "link_node_type",
    "draw_node_type",
    "link_id",
    "trigger_tech_id",
    "building_upgraded_from_id",
    "building_in_new_column",
)
OFFER_KEYS: Final = {
    "ID": "id",
    "Name": "name",
    "RequiredAge": "required_age",
    "PrereqTech": "prereq_tech",
    "RequiredTechID": "required_tech_id",
    "RequiredUnitID": "required_unit_id",
    "PrereqIconSet": "prereq_icon_set",
    "PrereqIconIndex": "prereq_icon_index",
    "PrereqStyle": "prereq_style",
    "PrereqStringID": "prereq_string_id",
    "Techs": "techs",
    "Units": "units",
}
UNIT_LINE_KEYS: Final = {
    "Name": "name",
    "Identifier": "identifier",
    "Building": "building",
    "LineID": "line_id",
    "IDChain": "id_chain",
}
LINKED_TECH_KEYS: Final = {
    "NameId": "name_id",
    "Comment": "comment",
    "Type": "type",
    "Techs": "techs",
    "StartingTech": "starting_tech",
    "Instant": "instant",
    "Local": "local",
}
LINKED_UNIT_KEYS: Final = {"Name": "name", "Units": "units"}
ERA_KEYS: Final = {"Name": "name", "Ages": "ages"}
AGE_KEYS: Final = {
    "NameId": "name_id",
    "TechTreeIconMaterialName": "tech_tree_icon_material_name",
    "ShieldMaterialName": "shield_material_name",
    "PrerequisiteStringId": "prerequisite_string_id",
}


@dataclass(slots=True)
class FilesTier:
    """Everything the files tier produces, plus what could not be read."""

    civs: list[JsonValue] = field(default_factory=list)
    tech_trees: JsonObject = field(default_factory=dict)
    building_offers: JsonObject = field(default_factory=dict)
    unit_lines: list[JsonValue] = field(default_factory=list)
    linked_techs: list[JsonValue] = field(default_factory=list)
    linked_units: list[JsonValue] = field(default_factory=list)
    eras: list[JsonValue] = field(default_factory=list)
    missing_sections: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def normalize(record: Mapping[str, JsonValue], keys: Mapping[str, str]) -> JsonObject:
    """Map the game's key names to ours, keeping anything unknown under `extra`."""
    result: JsonObject = {}
    extra: JsonObject = {}
    for name, value in record.items():
        target = keys.get(name)
        if target is None:
            extra[name] = value
        else:
            result[target] = value
    result["extra"] = extra
    return result


def read(reader: InputReader, strings: JsonObject) -> FilesTier:
    """Read every files-tier section. Only `civilizations.json` is required."""
    tier = FilesTier()
    tier.civs = read_civs(reader, strings, tier.warnings)
    tier.tech_trees = read_tech_trees(reader, tier.civs, tier.warnings)
    tier.building_offers = read_building_offers(reader, tier.warnings)
    _optional(tier, "unit_lines", read_unit_lines(reader))
    _optional(tier, "linked_techs", read_linked_techs(reader))
    _optional(tier, "linked_units", read_linked_units(reader))
    _optional(tier, "eras", read_eras(reader))
    return tier


def read_civs(reader: InputReader, strings: JsonObject, warnings: list[str]) -> list[JsonValue]:
    """Read `civilizations.json`, in file order, with the civ bonus text ID derived and checked."""
    data = reader.read_json(CIVILIZATIONS)
    entries = data.get("civilization_list") if isinstance(data, dict) else None
    if not isinstance(entries, list):
        raise MissingInputError("civilizations.json has no civilization_list")
    table = _table(strings)
    civs: list[JsonValue] = []
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            continue
        civ = normalize(entry, CIV_KEYS)
        extra = civ["extra"]
        assert isinstance(extra, dict)  # normalize always sets it
        civ["index"] = index
        civ["unique_tech_ids"] = [
            value
            for key in ("unique_tech_id_1", "unique_tech_id_2")
            if isinstance(value := extra.pop(key, None), int)
        ]
        civ["bonus_string_id"] = _bonus_string_id(civ, index, table, warnings)
        civs.append(civ)
    return civs


def read_tech_trees(
    reader: InputReader, civs: Sequence[JsonValue], warnings: list[str]
) -> JsonObject:
    """Read one `CivTechTrees\\<CIV>.json` per civ, merging both arrays and keeping their names."""
    trees: JsonObject = {}
    for civ in civs:
        if not isinstance(civ, dict):
            continue
        internal_name = civ.get("internal_name")
        tech_tree_name = civ.get("tech_tree_name")
        if not isinstance(internal_name, str) or not isinstance(tech_tree_name, str):
            continue
        if not tech_tree_name:  # Gaia has no tech tree file
            continue
        relative = f"{TECH_TREES}/{tech_tree_name}.json"
        data = reader.read_json(relative, required=False)
        if not isinstance(data, dict):
            warnings.append(f"no tech tree for {internal_name} ({relative})")
            continue
        nodes: list[JsonValue] = []
        for array in ("civ_techs_units", "civ_techs_buildings"):
            raw = data.get(array)
            if not isinstance(raw, list):
                warnings.append(f"{relative}: {array} is missing")
                continue
            for entry in raw:
                if isinstance(entry, dict):
                    nodes.append(_node(entry, array))
        trees[internal_name] = nodes
    return trees


def read_building_offers(reader: InputReader, warnings: list[str]) -> JsonObject:
    """Read what each building offers each civ, from the base and Chronicles files (§7)."""
    offers: JsonObject = {}
    for relative in (BUILDING_OFFERS, PAPHOS_OFFERS):
        data = reader.read_json(relative, required=False)
        if not isinstance(data, dict):
            warnings.append(f"building offers not read: {relative}")
            continue
        for civ_name, value in data.items():
            if civ_name in SKIPPED_OFFER_KEYS or not isinstance(value, dict):
                continue
            buildings = value.get("Buildings")
            offers[civ_name] = {
                "buildings": [
                    normalize(entry, OFFER_KEYS)
                    for entry in (buildings if isinstance(buildings, list) else [])
                    if isinstance(entry, dict)
                ]
            }
    return offers


def read_unit_lines(reader: InputReader) -> list[JsonValue] | None:
    """Read `unitlines.json`."""
    return _list_section(reader, f"{DAT_FOLDER}/unitlines.json", "UnitLines", UNIT_LINE_KEYS)


def read_linked_techs(reader: InputReader) -> list[JsonValue] | None:
    """Read `linkedTechs.json`."""
    return _list_section(reader, f"{DAT_FOLDER}/linkedTechs.json", "LinkedTechs", LINKED_TECH_KEYS)


def read_linked_units(reader: InputReader) -> list[JsonValue] | None:
    """Read `linkedUnits.json`."""
    return _list_section(reader, f"{DAT_FOLDER}/linkedUnits.json", "Data", LINKED_UNIT_KEYS)


def read_eras(reader: InputReader) -> list[JsonValue] | None:
    """Read `eras.json`, a bare array of eras each holding five age entries (§8)."""
    data = reader.read_json(f"{DAT_FOLDER}/eras.json", required=False)
    if not isinstance(data, list):
        return None
    eras: list[JsonValue] = []
    for entry in data:
        if not isinstance(entry, dict):
            continue
        era = normalize(entry, ERA_KEYS)
        ages = era.get("ages")
        era["ages"] = [
            normalize(age, AGE_KEYS)
            for age in (ages if isinstance(ages, list) else [])
            if isinstance(age, dict)
        ]
        eras.append(era)
    return eras


def _list_section(
    reader: InputReader, relative: str, array: str, keys: Mapping[str, str]
) -> list[JsonValue] | None:
    data = reader.read_json(relative, required=False)
    entries = data.get(array) if isinstance(data, dict) else None
    if not isinstance(entries, list):
        return None
    return [normalize(entry, keys) for entry in entries if isinstance(entry, dict)]


def _optional(tier: FilesTier, name: str, value: list[JsonValue] | None) -> None:
    if value is None:
        tier.missing_sections.append(name)
        tier.warnings.append(f"section not read: {name}")
        return
    setattr(tier, name, value)


def _node(entry: Mapping[str, JsonValue], array: str) -> JsonObject:
    node = normalize(entry, NODE_KEYS)
    node["array"] = array
    for key in OPTIONAL_NODE_KEYS:
        node.setdefault(key, None)
    extra = node["extra"]
    assert isinstance(extra, dict)  # normalize always sets it
    node["prerequisites"] = _prerequisites(
        extra.pop("Prerequisite IDs", None), extra.pop("Prerequisite Types", None)
    )
    return node


def _prerequisites(ids: JsonValue, types: JsonValue) -> list[JsonValue]:
    """Pair the two fixed-length arrays and drop the `None` slots (game-files.md §5)."""
    if not isinstance(ids, list) or not isinstance(types, list):
        return []
    return [
        {"type": kind, "id": identifier}
        for identifier, kind in zip(ids, types, strict=False)
        if kind != "None"
    ]


def _bonus_string_id(
    civ: JsonObject, index: int, table: JsonObject, warnings: list[str]
) -> int | None:
    """Derive the civ bonus text ID and check it names the civ's unique unit (§6).

    A mismatch means a civ was added or moved, so the ID is dropped rather than guessed.
    """
    if index == 0:  # Gaia has no bonus text
        return None
    string_id = BONUS_STRING_BASE + index - 1
    text = lookup(table, string_id)
    name = civ.get("internal_name")
    if text is None:
        warnings.append(f"civ bonus text {string_id} for {name} does not resolve")
        return None
    unit_name = _unique_unit_name(civ, table)
    if unit_name and unit_name not in text:
        warnings.append(
            f"civ bonus text {string_id} for {name} does not name its unique unit; dropped"
        )
        return None
    return string_id


def _unique_unit_name(civ: JsonObject, table: JsonObject) -> str | None:
    ids = civ.get("unique_unit_string_ids")
    if not isinstance(ids, list) or not ids:
        return None
    first = ids[0]
    if not isinstance(first, dict):
        return None
    name_id = first.get("name")
    return lookup(table, name_id) if isinstance(name_id, int) else None


def _table(strings: JsonObject) -> JsonObject:
    tables = strings.get("tables")
    if not isinstance(tables, dict):
        return {}
    english = tables.get("en")
    return english if isinstance(english, dict) else {}
