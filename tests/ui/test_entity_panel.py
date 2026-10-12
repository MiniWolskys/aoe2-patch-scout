# SPDX-License-Identifier: GPL-3.0-or-later
"""The details panel of a unit, building or tech (D-49, ui.md "Details panel")."""

from collections.abc import Callable
from typing import Any

from playwright.sync_api import Page, expect
from support.ui_data import (
    calls,
    detail_row,
    entity_details,
    fixture_data,
    show_changes,
    startup_data,
    tech_tree,
    version,
)

type OpenShell = Callable[..., Page]

ARCHER = ".tree-node:has(.tree-node__name:text-is('Archer'))"


def _compared(open_shell: OpenShell, **overrides: Any) -> Page:
    rows = [version("new", "PUP build"), version("old", "Live build")]
    data = fixture_data(startup=startup_data(versions=rows), techTree=tech_tree()) | overrides
    page = open_shell(data=data)
    page.locator(".version-row").nth(1).click(modifiers=["Control"])
    show_changes(page)
    expect(page.locator("#comparison-view")).to_be_visible()
    return page


def _open_tree(page: Page) -> None:
    page.locator(".civ-row", has_text="Franks").click()
    page.locator("#comparison-tree").click()
    expect(page.locator(".tree-node").first).to_be_visible()


def _open_archer(page: Page) -> None:
    _open_tree(page)
    page.locator(ARCHER).click()


def test_clicking_a_tree_tile_opens_its_details_for_the_trees_civ(open_shell: OpenShell) -> None:
    page = _compared(open_shell)

    _open_archer(page)

    drawer = page.locator("#entity-scrim")
    expect(drawer).to_be_visible()
    assert calls(page, "get_entity_details")[-1] == ["old", "new", "unit", 4, "Franks"]
    expect(page.locator("#entity-title")).to_have_text("Militia 4 Franks")
    expect(drawer).to_contain_text("Unit · Dark Age")
    expect(drawer).to_contain_text("All-purpose Infantry.")
    expect(page.locator("#entity-civ")).to_have_value("Franks")
    # The hover panel gives way to the drawer.
    expect(page.locator("#tree-panel")).to_be_hidden()


def test_values_read_like_the_comparison(open_shell: OpenShell) -> None:
    page = _compared(open_shell)
    _open_archer(page)

    stats = page.locator(".drawer__rows").first
    expect(stats.locator(".value-old")).to_have_text(["40"])
    expect(stats.locator(".value-new")).to_have_text(["45"])
    expect(stats).to_contain_text("Line of sight")
    added = page.locator(".drawer__row.is-added .change-row__field")
    expect(added).to_have_text("Militia: Hitpoints")
    expect(page.locator(".drawer__row.is-added .value-new")).to_have_text("+5")
    expect(page.locator(".drawer__row.is-removed del")).to_have_text("+1")
    expect(page.locator(".drawer__source-name")).to_have_text(["Civ bonus: Tough", "Forging"])
    expect(page.locator(".drawer__requires")).to_have_text(["Requires Feudal Age"])
    expect(page.locator(".drawer__note")).to_contain_text("aren't applied")


def test_escape_closes_the_drawer_and_gives_focus_back_to_the_tile(open_shell: OpenShell) -> None:
    page = _compared(open_shell)
    _open_archer(page)
    expect(page.locator("#entity-scrim")).to_be_visible()

    page.keyboard.press("Escape")

    expect(page.locator("#entity-scrim")).to_be_hidden()
    expect(page.locator(ARCHER)).to_be_focused()


def test_the_close_button_and_a_click_beside_the_drawer_close_it(open_shell: OpenShell) -> None:
    page = _compared(open_shell)
    _open_archer(page)
    page.locator("#entity-close").click()
    expect(page.locator("#entity-scrim")).to_be_hidden()

    page.locator(ARCHER).click()
    expect(page.locator("#entity-scrim")).to_be_visible()
    page.mouse.click(20, 400)  # on the dimmed page, left of the drawer

    expect(page.locator("#entity-scrim")).to_be_hidden()


def test_a_change_rows_icon_opens_its_details_and_overall_has_no_civ(open_shell: OpenShell) -> None:
    page = _compared(open_shell)

    button = page.locator(".change-row__open")
    expect(button).to_have_count(1)  # the Knight; Overall's text change is hidden
    expect(button).to_have_attribute("aria-label", "Details of Knight")
    button.click()

    assert calls(page, "get_entity_details")[-1] == ["old", "new", "unit", 38, None]
    expect(page.locator("#entity-civ")).to_have_value("")


def test_from_a_civ_page_the_details_are_for_that_civ(open_shell: OpenShell) -> None:
    page = _compared(open_shell)
    page.locator(".civ-row", has_text="Franks").click()

    page.locator(".change-row__open").first.click()

    assert calls(page, "get_entity_details")[-1] == ["old", "new", "unit", 4, "Franks"]


def test_only_units_buildings_and_techs_open_details(open_shell: OpenShell) -> None:
    page = _compared(open_shell)
    page.locator("#comparison-filters").click()
    page.locator("#filter-low").check()

    # The help text change is about a string: its row has no button.
    text_row = page.locator(".change-row", has_text="26083")
    expect(text_row).to_be_visible()
    expect(text_row.locator(".change-row__open")).to_have_count(0)


def test_choosing_another_civ_in_the_drawer_reads_the_details_again(open_shell: OpenShell) -> None:
    page = _compared(open_shell)
    _open_archer(page)
    expect(page.locator("#entity-title")).to_have_text("Militia 4 Franks")

    page.locator("#entity-civ").select_option("")

    expect(page.locator("#entity-title")).to_have_text("Militia 4 -")
    assert calls(page, "get_entity_details")[-1] == ["old", "new", "unit", 4, None]
    # The page keeps its own civ.
    expect(page.locator(".civ-row[aria-current='true']")).to_contain_text("Franks")


def test_a_slow_earlier_answer_does_not_replace_a_newer_one(open_shell: OpenShell) -> None:
    page = _compared(open_shell, entityDelays=[600, 0])
    _open_archer(page)

    page.locator("#entity-civ").select_option("")

    expect(page.locator("#entity-title")).to_have_text("Militia 4 -")
    page.wait_for_timeout(900)
    expect(page.locator("#entity-title")).to_have_text("Militia 4 -")


def test_a_failed_read_says_so_and_closes(open_shell: OpenShell) -> None:
    page = _compared(open_shell, entityError="boom")

    _open_archer(page)

    expect(page.locator("#toast")).to_have_text("The details couldn't be read.")
    expect(page.locator("#entity-scrim")).to_be_hidden()


def test_an_entity_gone_from_both_versions_says_so(open_shell: OpenShell) -> None:
    page = _compared(open_shell, entity=None)

    _open_archer(page)

    expect(page.locator("#toast")).to_have_text("Neither version has this anymore.")
    expect(page.locator("#entity-scrim")).to_be_hidden()


def test_tags_and_notices_say_what_is_missing(open_shell: OpenShell) -> None:
    details = entity_details(
        presence="new",
        available={"old": None, "new": False},
        stats_missing={"old": True, "new": False},
        groups=[],
        scripts=["Effect of Kasbah for Berbers"],
    )
    page = _compared(open_shell, entity=details)

    _open_archer(page)

    drawer = page.locator("#entity-scrim")
    expect(drawer.locator(".tag")).to_have_text(
        ["Not available to Franks", "Only in the newer version"]
    )
    expect(drawer).to_contain_text("The older version's game data couldn't be read")
    expect(drawer).to_contain_text("No civilization bonus or technology affects it.")
    expect(drawer).to_contain_text("Effect of Kasbah for Berbers")


def test_a_tech_shows_its_own_sections(open_shell: OpenShell) -> None:
    details = entity_details(
        kind="tech",
        sections=[
            {
                "key": "effects",
                "title": {"key": "entity.section.effects", "args": {}},
                "rows": [detail_row("field.effect_command", "type 4 a=1", "type 4 a=2", "changed")],
            }
        ],
    )
    page = _compared(open_shell, entity=details)
    _open_tree(page)

    page.locator(".tree-node:has(.tree-node__name:text-is('Thumb Ring'))").click()

    assert calls(page, "get_entity_details")[-1][2:4] == ["tech", 437]
    expect(page.locator(".drawer__section").first).to_have_text("Effects")
    expect(page.locator("#entity-scrim")).to_contain_text("Effect command")


def test_the_civ_picker_lists_the_comparisons_civs(open_shell: OpenShell) -> None:
    page = _compared(open_shell)

    _open_archer(page)

    # Chronicles civs included, after "No civilization".
    expect(page.locator("#entity-civ option")).to_have_text(
        ["No civilization", "Franks", "Spartans"]
    )


def test_a_change_in_availability_is_said_in_the_comparisons_colours(
    open_shell: OpenShell,
) -> None:
    lost = entity_details(available={"old": True, "new": False})
    page = _compared(open_shell, entity=lost)
    _open_archer(page)
    expect(page.locator("#entity-scrim .tag--old")).to_have_text("No longer available to Franks")

    gained = entity_details(available={"old": False, "new": True})
    page = _compared(open_shell, entity=gained)
    _open_archer(page)
    expect(page.locator("#entity-scrim .tag--new")).to_have_text("Newly available to Franks")


def test_closing_before_the_answer_comes_shows_nothing_later(open_shell: OpenShell) -> None:
    page = _compared(open_shell, entity=None, entityDelays=[600])
    _open_archer(page)

    page.keyboard.press("Escape")
    page.wait_for_timeout(900)

    expect(page.locator("#entity-scrim")).to_be_hidden()
    expect(page.locator("#toast")).to_be_hidden()
