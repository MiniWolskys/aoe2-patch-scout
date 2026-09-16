# SPDX-License-Identifier: GPL-3.0-or-later
"""The icon pipeline: resolving, decoding, hashing and storing (D-09, P-06)."""

from pathlib import Path

import pytest
from PIL import Image
from support import game_tree

from patch_scout.capture import icons
from patch_scout.capture.inputs import InputReader
from patch_scout.snapshot import JsonObject, JsonValue
from patch_scout.store import DataFolder, IconStore


@pytest.fixture
def pipeline(tmp_path: Path) -> icons.IconPipeline:
    reader = InputReader(game_tree.write(tmp_path / "AoE2DE"))
    folder = DataFolder(tmp_path / "PatchScout")
    folder.create()
    return icons.IconPipeline(reader, IconStore(folder))


def ref(value: object) -> JsonObject:
    assert isinstance(value, dict)
    return value


def test_an_uncompressed_dds_is_decoded_from_its_pixels() -> None:
    data = game_tree.dds_bytes(4, 4, (10, 20, 30, 255))
    image = icons.decode_uncompressed_dds(data)
    assert image is not None
    assert image.size == (4, 4)
    assert image.getpixel((0, 0)) == (10, 20, 30, 255)


def test_a_bgra_dds_is_decoded_in_the_right_channel_order() -> None:
    data = bytearray(game_tree.dds_bytes(1, 1, (1, 2, 3, 255)))
    data[92:108] = (
        (0x00FF0000).to_bytes(4, "little")
        + (0x0000FF00).to_bytes(4, "little")
        + (0x000000FF).to_bytes(4, "little")
        + (0xFF000000).to_bytes(4, "little")
    )
    image = icons.decode_uncompressed_dds(bytes(data))
    assert image is not None
    assert image.getpixel((0, 0)) == (3, 2, 1, 255)


def test_a_png_is_not_taken_for_a_dds() -> None:
    assert icons.decode_uncompressed_dds(game_tree.png_bytes(2, 2, (1, 2, 3, 4))) is None


def test_a_truncated_dds_is_not_decoded_by_the_fast_path() -> None:
    assert icons.decode_uncompressed_dds(game_tree.dds_bytes(4, 4, (1, 2, 3, 4))[:100]) is None


def test_a_dds_with_too_few_pixels_is_not_decoded() -> None:
    data = game_tree.dds_bytes(4, 4, (1, 2, 3, 4))[:132]
    assert icons.decode_uncompressed_dds(data) is None


def test_a_png_is_decoded_through_pillow() -> None:
    image = icons.decode(game_tree.png_bytes(2, 2, (9, 9, 9, 255)))
    assert (image.size, image.mode) == ((2, 2), "RGBA")


def test_a_tech_tree_icon_is_found_by_use_type_and_index(pipeline: icons.IconPipeline) -> None:
    resolved = ref(pipeline.tech_tree_icon("Unit", 17))
    assert resolved["category"] == "units"
    assert resolved["source"] == "widgetui/textures/ingame/units/017_50730.DDS"
    assert isinstance(resolved["hash"], str)
    assert resolved["missing_reason"] is None


def test_each_use_type_picks_its_own_folder(pipeline: icons.IconPipeline) -> None:
    assert ref(pipeline.tech_tree_icon("Tech", 0))["category"] == "tech"
    assert ref(pipeline.tech_tree_icon("Building", 23))["category"] == "buildings"


def test_an_index_with_no_file_is_recorded_as_missing(pipeline: icons.IconPipeline) -> None:
    resolved = ref(pipeline.tech_tree_icon("Unit", 999))
    assert resolved["hash"] is None
    assert resolved["missing_reason"] == "file not found"


def test_a_node_without_a_use_type_is_recorded_as_missing(pipeline: icons.IconPipeline) -> None:
    resolved = ref(pipeline.tech_tree_icon(None, 17))
    assert resolved["missing_reason"] == "no icon folder for this node"


def test_an_emblem_comes_from_its_image_path(pipeline: icons.IconPipeline) -> None:
    resolved = ref(pipeline.wpfg_icon("emblems", "/resources/uniticons/017_50730.png"))
    assert resolved["category"] == "emblems"
    assert isinstance(resolved["hash"], str)


def test_a_civ_without_an_image_path_gets_a_reason(pipeline: icons.IconPipeline) -> None:
    assert ref(pipeline.wpfg_icon("emblems", ""))["missing_reason"] == "no image path"
    assert ref(pipeline.wpfg_icon("emblems", None))["missing_reason"] == "no image path"


def test_an_image_path_that_leads_nowhere_gets_a_reason(pipeline: icons.IconPipeline) -> None:
    resolved = ref(pipeline.wpfg_icon("emblems", "/resources/uniticons/999_none.png"))
    assert resolved["missing_reason"] == "file not found"


def test_the_stat_icons_the_game_has_are_resolved(pipeline: icons.IconPipeline) -> None:
    stat_icons = pipeline.stat_icons()
    assert isinstance(stat_icons["hp"], dict)
    assert stat_icons["hp"]["source"] == "widgetui/textures/ingame/staticons/hp.png"
    assert isinstance(stat_icons["gold"], dict)
    assert stat_icons["gold"]["missing_reason"] == "file not found"


def test_the_same_file_is_decoded_once(pipeline: icons.IconPipeline) -> None:
    first = ref(pipeline.tech_tree_icon("Unit", 17))
    second = ref(pipeline.tech_tree_icon("Unit", 17))
    assert first["hash"] == second["hash"]


def test_an_unreadable_image_is_a_warning_not_a_failure(tmp_path: Path) -> None:
    root = game_tree.write(tmp_path / "AoE2DE")
    (root / "widgetui/textures/ingame/units/017_50730.DDS").write_bytes(b"rubbish")
    folder = DataFolder(tmp_path / "PatchScout")
    folder.create()
    pipeline = icons.IconPipeline(InputReader(root), IconStore(folder))
    resolved = ref(pipeline.tech_tree_icon("Unit", 17))
    assert resolved["missing_reason"] == "not a readable image"
    assert pipeline.warnings == ["icon not decoded: widgetui/textures/ingame/units/017_50730.DDS"]


def test_the_store_ends_up_holding_the_decoded_icon(tmp_path: Path) -> None:
    root = game_tree.write(tmp_path / "AoE2DE")
    folder = DataFolder(tmp_path / "PatchScout")
    folder.create()
    store = IconStore(folder)
    pipeline = icons.IconPipeline(InputReader(root), store)
    resolved = ref(pipeline.tech_tree_icon("Unit", 17))
    digest = resolved["hash"]
    assert isinstance(digest, str)
    assert store.has(digest)
    with Image.open(store.path_for(digest)) as stored:
        assert stored.size == (4, 4)


def test_attaching_fills_in_every_icon_reference(tmp_path: Path) -> None:
    root = game_tree.write(tmp_path / "AoE2DE")
    folder = DataFolder(tmp_path / "PatchScout")
    folder.create()
    pipeline = icons.IconPipeline(InputReader(root), IconStore(folder))
    civs: list[JsonValue] = [
        {
            "emblem_image_path": "/resources/uniticons/017_50730.png",
            "unique_unit_image_paths": ["/x.png"],
        }
    ]
    trees: JsonObject = {"Red": [{"use_type": "Unit", "picture_index": 17}]}
    stat_icons = pipeline.stat_icons()
    attached = icons.attach(pipeline, civs, trees)
    civ = civs[0]
    assert isinstance(civ, dict)
    assert ref(civ["emblem_icon"])["category"] == "emblems"
    unique = civ["unique_unit_icons"]
    assert isinstance(unique, list) and ref(unique[0])["missing_reason"] == "file not found"
    nodes = trees["Red"]
    assert isinstance(nodes, list) and isinstance(nodes[0], dict)
    assert ref(nodes[0]["icon"])["source"] == "widgetui/textures/ingame/units/017_50730.DDS"
    assert attached.keys() == stat_icons.keys()
