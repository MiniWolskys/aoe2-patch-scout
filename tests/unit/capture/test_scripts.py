# SPDX-License-Identifier: GPL-3.0-or-later
"""The XS script files: the constants that name the game's IDs, and the scripted effects."""

from pathlib import Path

from support import game_tree

from patch_scout.capture import files_tier, scripts
from patch_scout.capture.inputs import InputReader

CONSTANTS = """\
//======================================================================================
//
// This is the default XS scripting constants file.
//
//======================================================================================

extern const int cBeforeAnyTitle = 7;

//======================================================================================
// Damage Classes
//======================================================================================
extern const int cDamageClassInfantry = 1;
extern const int cDamageClassShockInfantry = 29;

// ======================
// Tech Effect Constants
// ======================

extern const int cHitpoints = 0;
extern const int cCombatAbility = 63;            // Break Off Combat in AGE3
// Reserved Class 66
extern const float cHalf = 0.5;
extern const string cName = "Name";
extern const int cNegative = -1;
const int NotAConstant = 3;
"""


def test_constants_are_grouped_by_section_title_in_file_order() -> None:
    parsed = scripts.parse_constants(CONSTANTS)
    assert list(parsed) == ["", "Damage Classes", "Tech Effect Constants"]
    assert parsed["Damage Classes"] == [
        ["cDamageClassInfantry", 1],
        ["cDamageClassShockInfantry", 29],
    ]


def test_a_comment_that_is_not_between_rules_is_not_a_title() -> None:
    parsed = scripts.parse_constants(CONSTANTS)
    assert "Reserved Class 66" not in parsed
    section = parsed["Tech Effect Constants"]
    assert isinstance(section, list)
    assert ["cCombatAbility", 63] in section


def test_values_keep_their_type_and_non_extern_lines_are_ignored() -> None:
    section = scripts.parse_constants(CONSTANTS)["Tech Effect Constants"]
    assert section == [
        ["cHitpoints", 0],
        ["cCombatAbility", 63],
        ["cHalf", 0.5],
        ["cName", "Name"],
        ["cNegative", -1],
    ]


def test_the_files_tier_reads_both_xs_files(tmp_path: Path) -> None:
    root = game_tree.write(tmp_path / "AoE2DE")
    reader = InputReader(root)
    tier = files_tier.read(reader, {"tables": {"en": {}}})
    constants = tier.scripts["constants"]
    assert isinstance(constants, dict)
    damage = constants["Damage Classes"]
    assert isinstance(damage, list)
    assert ["cDamageClassShockInfantry", 29] in damage
    assert tier.scripts["effects"] == game_tree.EFFECTS_XS
    assert "resources/_common/xs/Constants.xs" in reader.sources()
    assert "resources/_common/xs/Effects.xs" in reader.sources()


def test_missing_xs_files_become_missing_sections(tmp_path: Path) -> None:
    root = game_tree.write(tmp_path / "AoE2DE")
    (root / "resources/_common/xs/Constants.xs").unlink()
    (root / "resources/_common/xs/Effects.xs").unlink()
    tier = files_tier.read(InputReader(root), {"tables": {"en": {}}})
    assert tier.scripts == {}
    assert "scripts.constants" in tier.missing_sections
    assert "scripts.effects" in tier.missing_sections
