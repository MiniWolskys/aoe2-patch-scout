# SPDX-License-Identifier: GPL-3.0-or-later
"""The plain-text and HTML exports, including the golden files (CONTRIBUTING.md).

Update the golden files deliberately with `uv run pytest --update-golden`, and read the diff.
"""

import json
from dataclasses import replace
from pathlib import Path

import pytest
from support import pairs

from patch_scout.diff import compare
from patch_scout.diff.model import ChangeSet, Side
from patch_scout.i18n.catalog import Catalog, load_catalog
from patch_scout.report import Filters, render_html, render_text
from patch_scout.report.html import MICROSOFT_NOTICE
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
