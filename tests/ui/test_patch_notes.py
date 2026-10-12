# SPDX-License-Identifier: GPL-3.0-or-later
"""The patch notes mode of the comparison (D-51, ui.md "Patch notes")."""

from collections.abc import Callable
from typing import Any

from playwright.sync_api import Page, expect
from support.ui_data import (
    PIXEL,
    calls,
    change_set,
    fixture_data,
    patch_notes,
    startup_data,
    version,
)

type OpenShell = Callable[..., Page]

FRANKS_CREST = {"hash": "crest-franks"}


def _data(**overrides: Any) -> dict[str, Any]:
    """Two versions, a comparison whose Franks have a crest, and the patch notes."""
    versions = [version("new", "PUP build"), version("old", "Live build")]
    base = change_set()
    civs = [
        civ | {"icon": FRANKS_CREST} if civ["internal_name"] == "Franks" else civ
        for civ in base["civs"]
    ]
    data = fixture_data(
        startup=startup_data(versions=versions),
        changeSet=base | {"civs": civs},
        icons={"crest-franks": PIXEL},
    )
    return data | overrides


def _open_notes(open_shell: OpenShell, **overrides: Any) -> Page:
    page = open_shell(data=_data(**overrides))
    page.locator(".version-row").nth(1).click(modifiers=["Control"])
    expect(page.locator("#comparison-view")).to_be_visible()
    page.locator("#comparison-notes").click()
    return page


def test_the_patch_notes_read_like_the_official_ones(open_shell: OpenShell) -> None:
    page = _open_notes(open_shell)

    notes = page.locator("#notes-view")
    expect(notes).to_be_visible()
    expect(page.locator("#comparison-page")).to_be_hidden()
    expect(notes.locator(".notes__title")).to_have_text(
        "Patch notes: Live build → PUP build (pre-release)"
    )
    expect(notes.locator(".notes__section-title")).to_have_text(["General", "Civilizations"])
    franks = notes.locator("#notes-civ-Franks")
    expect(franks.locator(".notes__group-title")).to_have_text("Franks")
    expect(franks.locator("img.notes__crest")).to_have_count(1)
    expect(franks.locator(":scope > .notes__list > li")).to_have_count(2)
    # A NEW item's details are bullets under it.
    expect(franks.locator(".notes__list .notes__list li")).to_have_text(
        ["Cost: 400 food, 250 gold"]
    )
    expect(notes.locator(".notes__closing")).to_have_text("1 more change isn't in these notes.")


def test_the_patch_notes_dont_follow_the_filters(open_shell: OpenShell) -> None:
    notice = change_set()["notices"] + [
        {"kind": "levels_hidden", "message": {"key": "notice.levels_hidden", "args": {"count": 3}}}
    ]
    page = open_shell(data=_data(changeSet=_data()["changeSet"] | {"notices": notice}))
    page.locator(".version-row").nth(1).click(modifiers=["Control"])
    expect(page.locator("#comparison-notice")).to_be_visible()

    page.locator("#comparison-notes").click()

    expect(page.locator("#comparison-filters")).to_be_hidden()
    expect(page.locator("#comparison-notice")).to_be_hidden()
    expect(page.locator("#comparison-notes")).to_have_attribute("aria-pressed", "true")


def test_back_to_changes_shows_the_change_list_again(open_shell: OpenShell) -> None:
    page = _open_notes(open_shell)

    page.locator("#comparison-notes").click()

    expect(page.locator("#notes-view")).to_be_hidden()
    expect(page.locator("#comparison-page")).to_be_visible()
    expect(page.locator("#comparison-filters")).to_be_visible()
    expect(page.locator("#comparison-notes")).to_have_text("Patch notes")


def test_the_patch_notes_are_asked_for_once_per_comparison(open_shell: OpenShell) -> None:
    page = _open_notes(open_shell)
    expect(page.locator(".notes__title")).to_be_visible()

    page.locator("#comparison-notes").click()
    page.locator("#comparison-notes").click()

    expect(page.locator(".notes__title")).to_be_visible()
    assert calls(page, "get_patch_notes") == [["old", "new"]]


def test_choosing_a_civ_brings_its_block_into_view(open_shell: OpenShell) -> None:
    long = patch_notes()
    many = [
        {"text": f"Unit {number} hit points increased.", "children": []} for number in range(80)
    ]
    long["sections"][0]["groups"][0]["items"] = many
    page = _open_notes(open_shell, patchNotes=long)
    franks = page.locator("#notes-civ-Franks")
    expect(franks).not_to_be_in_viewport()

    page.locator(".civ-row", has_text="Franks").click()

    expect(franks).to_be_in_viewport()
    page.locator(".civ-row", has_text="Overall").click()
    expect(page.locator(".notes__title")).to_be_in_viewport()


def test_patch_notes_that_cant_be_written_say_so_and_go_back(open_shell: OpenShell) -> None:
    page = _open_notes(open_shell, patchNotesError="boom")

    expect(page.locator("#toast")).to_contain_text("The patch notes couldn't be written")
    expect(page.locator("#comparison-page")).to_be_visible()
    expect(page.locator("#notes-view")).to_be_hidden()


def test_the_export_in_patch_notes_mode_is_the_patch_notes(open_shell: OpenShell) -> None:
    page = _open_notes(open_shell)
    expect(page.locator(".notes__title")).to_be_visible()

    page.locator("#comparison-export").click()

    expect(page.locator("#export-title")).to_have_text("Export the patch notes")
    expect(page.locator("#export-help")).to_contain_text("Light Markdown")
    expect(page.locator("#export-preview")).to_have_text(patch_notes()["text"])
    expect(page.locator("#export-html")).to_be_hidden()
    expect(page.locator("#export-image")).to_be_hidden()
    # The new version is a pre-release: the embargo reminder shows here too.
    expect(page.locator("#export-embargo")).to_be_visible()
    assert calls(page, "export_text") == []

    page.locator("#export-text").click()

    expect(page.locator("#export-status")).to_contain_text("Saved to C:/tmp/patch-notes.txt")
    assert calls(page, "save_patch_notes") == [["old", "new"]]
    assert calls(page, "save_export") == []


def test_the_export_goes_back_to_the_changes_out_of_patch_notes_mode(
    open_shell: OpenShell,
) -> None:
    page = _open_notes(open_shell)
    expect(page.locator(".notes__title")).to_be_visible()
    page.locator("#comparison-export").click()
    page.locator("#export-close").click()
    page.locator("#comparison-notes").click()

    page.locator("#comparison-export").click()

    expect(page.locator("#export-title")).to_have_text("Export this comparison")
    expect(page.locator("#export-html")).to_be_visible()
    expect(page.locator("#export-image")).to_be_visible()
    expect(page.locator("#export-preview")).to_have_text("Patch Scout - what changed")
