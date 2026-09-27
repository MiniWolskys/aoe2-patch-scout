# SPDX-License-Identifier: GPL-3.0-or-later
"""The plain-text and HTML exports, including the golden files (CONTRIBUTING.md).

Update the golden files deliberately with `uv run pytest --update-golden`, and read the diff.
"""

import base64
import io
import json
from dataclasses import replace
from pathlib import Path

import pytest
from PIL import Image
from support import pairs

from patch_scout.diff import compare
from patch_scout.diff.entries import group
from patch_scout.diff.model import Change, ChangeSet, Entity, Message, Scope, Side
from patch_scout.i18n.catalog import Catalog, load_catalog
from patch_scout.report import Filters, render_html, render_text
from patch_scout.report.html import ICON_PIXELS, MICROSOFT_NOTICE, shrink_icon
from patch_scout.report.text import scope_text
from patch_scout.store import IconStore

GOLDEN = Path(__file__).resolve().parents[2] / "golden"
# The two fields that differ between runs (snapshot-format.md); pinned so the golden files can be
# compared at all.
FIXED_TIME = "2026-09-16T00:00:00Z"


@pytest.fixture(scope="module")
def prepared(tmp_path_factory: pytest.TempPathFactory) -> tuple[ChangeSet, IconStore]:
    pair = pairs.make(tmp_path_factory.mktemp("report"))
    change_set = compare(pair.old, pair.new)
    pinned = replace(
        change_set,
        old=_at(change_set.old),
        new=_at(change_set.new),
    )
    return pinned, IconStore(pair.folder)


@pytest.fixture(scope="module")
def catalog() -> Catalog:
    return load_catalog("en")


def _at(side: Side) -> Side:
    return replace(side, captured_at=FIXED_TIME)


def check_golden(name: str, produced: str, update: bool) -> None:
    """Compare against the stored expectation, or rewrite it when asked."""
    path = GOLDEN / name
    if update or not path.is_file():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(produced, encoding="utf-8")
        if not update:
            pytest.fail(f"golden file {name} was missing; it has been written, re-run the tests")
        return
    assert produced == path.read_text(encoding="utf-8")


def test_the_plain_text_export_matches_its_golden_file(
    prepared: tuple[ChangeSet, IconStore], catalog: Catalog, update_golden: bool
) -> None:
    change_set, _ = prepared
    check_golden("comparison.txt", render_text(change_set, catalog), update_golden)


def test_the_full_plain_text_export_matches_its_golden_file(
    prepared: tuple[ChangeSet, IconStore], catalog: Catalog, update_golden: bool
) -> None:
    change_set, _ = prepared
    produced = render_text(change_set, catalog, Filters(low_priority=True))
    check_golden("comparison-all.txt", produced, update_golden)


def test_the_change_set_json_matches_its_golden_file(
    prepared: tuple[ChangeSet, IconStore], update_golden: bool
) -> None:
    change_set, _ = prepared
    produced = json.dumps(change_set.to_json(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    check_golden("comparison.json", produced, update_golden)


def test_the_header_names_both_versions(
    prepared: tuple[ChangeSet, IconStore], catalog: Catalog
) -> None:
    text = render_text(prepared[0], catalog)
    assert "Old: Live build" in text
    assert "New: PUP build" in text
    assert "pre-release" in text


def test_low_priority_categories_are_left_out_by_default(
    prepared: tuple[ChangeSet, IconStore], catalog: Catalog
) -> None:
    default = render_text(prepared[0], catalog)
    full = render_text(prepared[0], catalog, Filters(low_priority=True))
    assert "Icons" not in default
    assert "Icons" in full


def test_a_civ_filter_keeps_that_civ_and_the_overall_page(
    prepared: tuple[ChangeSet, IconStore], catalog: Catalog
) -> None:
    text = render_text(prepared[0], catalog, Filters(civs=("Bluelanders",)))
    assert "BLUELANDERS" in text
    assert "REDLANDERS" not in text
    assert "OVERALL" in text


def test_an_identical_comparison_says_so(
    prepared: tuple[ChangeSet, IconStore], catalog: Catalog
) -> None:
    change_set = replace(prepared[0], identical=True, changes=())
    assert "identical game files" in render_text(change_set, catalog)


def test_the_html_export_is_one_self_contained_file(
    prepared: tuple[ChangeSet, IconStore], catalog: Catalog
) -> None:
    change_set, store = prepared
    document = render_html(change_set, catalog, icons=store.read_png, tool_version="0.1.0")
    assert document.startswith("<!doctype html>")
    assert "<style>" in document
    assert 'src="http' not in document
    assert "data:image/png;base64," in document


def test_the_html_export_embeds_each_icon_once(
    prepared: tuple[ChangeSet, IconStore], catalog: Catalog
) -> None:
    """Regression: every row embedded its icon again, 739 MB on the first real patch."""
    change_set, store = prepared
    document = render_html(
        change_set, catalog, icons=store.read_png, filters=Filters(low_priority=True)
    )
    used = {
        change.entity.icon["hash"]
        for change in change_set.changes
        if change.entity.icon and change.entity.icon.get("hash")
    }
    assert len(used) < sum(1 for change in change_set.changes if change.entity.icon)
    assert document.count("data:image/png;base64,") == len(used)


def test_the_html_export_shrinks_icons_to_the_size_they_are_shown_at(
    prepared: tuple[ChangeSet, IconStore], catalog: Catalog
) -> None:
    change_set, store = prepared
    document = render_html(change_set, catalog, icons=store.read_png)
    encoded = document.split("data:image/png;base64,", 1)[1].split(")", 1)[0]
    with Image.open(io.BytesIO(base64.b64decode(encoded))) as image:
        assert max(image.size) <= ICON_PIXELS


def test_a_full_size_game_icon_is_shrunk_before_it_is_embedded() -> None:
    big = io.BytesIO()
    Image.new("RGBA", (256, 256), (200, 30, 30, 255)).save(big, format="PNG")
    with Image.open(io.BytesIO(shrink_icon(big.getvalue()))) as image:
        assert image.size == (ICON_PIXELS, ICON_PIXELS)


def test_the_html_export_carries_the_microsoft_notice(
    prepared: tuple[ChangeSet, IconStore], catalog: Catalog
) -> None:
    document = render_html(prepared[0], catalog)
    assert MICROSOFT_NOTICE in document


def test_the_html_export_marks_old_and_new(
    prepared: tuple[ChangeSet, IconStore], catalog: Catalog
) -> None:
    document = render_html(prepared[0], catalog)
    assert 'class="old"' in document
    assert 'class="new"' in document


def test_the_html_export_shows_a_word_diff_with_del_and_ins(
    prepared: tuple[ChangeSet, IconStore], catalog: Catalog
) -> None:
    document = render_html(prepared[0], catalog, filters=Filters(low_priority=True))
    assert "<del>" in document and "<ins>" in document


def test_the_html_export_escapes_game_text(
    prepared: tuple[ChangeSet, IconStore], catalog: Catalog
) -> None:
    change_set, _ = prepared
    nasty = replace(change_set, old=replace(change_set.old, label="<script>x</script>"))
    document = render_html(nasty, catalog)
    assert "<script>x</script>" not in document
    assert "&lt;script&gt;" in document


def test_an_entity_only_some_civs_have_says_how_many_have_it(catalog: Catalog) -> None:
    assert scope_text(Scope("having", count=12), catalog) == ("(all 12 civilizations that have it)")
    assert scope_text(Scope("having_except", ("Goths",), count=12), catalog) == (
        "(all 12 civilizations that have it, except Goths)"
    )


def _entry_set(*changes: Change) -> ChangeSet:
    side = Side("a", "A", "1.0", FIXED_TIME, prerelease=False, stats_available=True)
    return ChangeSet(old=side, new=side, changes=changes, entries=group(changes))


def test_a_unit_with_several_changed_fields_reads_as_one_item(catalog: Catalog) -> None:
    knight = Entity("unit", "38", "Knight")
    text = render_text(
        _entry_set(
            Change(
                "unit_stats",
                "modified",
                knight,
                Scope("all"),
                Message("field.hit_points"),
                old="100",
                new="110",
            ),
            Change(
                "unit_stats",
                "modified",
                knight,
                Scope("all"),
                Message("field.speed"),
                old="1.35",
                new="1.4",
            ),
        ),
        catalog,
    )
    assert "    • Knight · (all civilizations)\n" in text
    assert "        - Hit points · 100 → 110\n" in text
    assert "        - Movement speed · 1.35 → 1.4\n" in text


def test_a_new_unit_lists_its_main_stats_and_says_what_it_leaves_out(catalog: Catalog) -> None:
    jarl = Entity("unit", "2716", "Jarl")
    everywhere = Scope("all")
    fields = [("field.hit_points", "65"), ("field.garrison_capacity", "0")]
    text = render_text(
        _entry_set(
            *[
                Change("unit_stats", "modified", jarl, everywhere, Message(key), old="", new=value)
                for key, value in fields
            ]
        ),
        catalog,
    )
    assert "• Added: Jarl · (all civilizations)" in text
    assert "- Hit points · 65\n" in text
    assert "1 more values not shown" in text
