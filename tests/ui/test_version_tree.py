# SPDX-License-Identifier: GPL-3.0-or-later
"""A version on its own: its tech tree, and its details behind a gear button (D-52)."""

from collections.abc import Callable
from typing import Any

from playwright.sync_api import Page, expect
from support.ui_data import calls, fixture_data, open_details, startup_data, version

type OpenShell = Callable[..., Page]


def _data(*rows: dict[str, Any], **startup: Any) -> dict[str, Any]:
    return fixture_data(startup=startup_data(versions=list(rows), **startup))


def _two() -> dict[str, Any]:
    return _data(version("new", "PUP build"), version("old", "Live build"))


def test_the_newest_version_opens_alone_in_its_tech_tree(open_shell: OpenShell) -> None:
    page = open_shell(data=_two())

    expect(page.locator("#comparison-view")).to_be_visible()
    expect(page.locator("#tree-view")).to_be_visible()
    expect(page.locator(".tree-node").first).to_be_visible()
    assert calls(page, "compare_versions")[-1][:2] == ["new", "new"]
    assert calls(page, "get_tech_tree")[-1][:3] == ["new", "new", "Franks"]


def test_the_header_names_the_version_alone(open_shell: OpenShell) -> None:
    page = open_shell(data=_two())

    expect(page.locator("#picker-new-name")).to_have_text("PUP build")
    for hidden in (
        "#picker-old",
        "#comparison-swap",
        "#comparison-tree",
        "#comparison-notes",
        "#comparison-filters",
        "#comparison-export",
        ".comparison-header .tag--new",
        ".tree__legend",
    ):
        expect(page.locator(hidden)).to_be_hidden()
    expect(page.locator("#version-compare")).to_be_visible()


def test_the_hint_says_how_to_compare(open_shell: OpenShell) -> None:
    page = open_shell(data=_two())

    expect(page.locator("#version-hint")).to_have_text(
        "Hover another version and click Compare to see what changed."
    )


def test_with_one_version_the_hint_asks_for_a_second(open_shell: OpenShell) -> None:
    page = open_shell(data=_data(version("one", "Live build")))

    expect(page.locator("#version-hint")).to_have_text(
        "Capture or import a second version to see what changed."
    )


def test_the_civ_list_has_every_civ_without_counts(open_shell: OpenShell) -> None:
    page = open_shell(data=_two())

    expect(page.locator(".civ-row")).to_have_count(1)
    expect(page.locator(".civ-row", has_text="Franks")).to_be_visible()
    expect(page.locator(".civ-row .civ-row__count")).to_have_count(0)
    expect(page.locator(".civ-tab .civ-row__count")).to_have_count(0)


def test_the_open_version_is_the_current_row_without_a_side_tag(open_shell: OpenShell) -> None:
    page = open_shell(data=_two())
    row = page.locator(".version-row").first

    expect(row).to_have_attribute("aria-current", "true")
    expect(page.locator(".version-row[data-side]")).to_have_count(0)


def test_clicking_a_version_opens_it_alone(open_shell: OpenShell) -> None:
    page = open_shell(data=_two())

    page.locator(".version-row").nth(1).click()

    assert calls(page, "compare_versions")[-1][:2] == ["old", "old"]
    expect(page.locator("#picker-new-name")).to_have_text("Live build")
    expect(page.locator(".version-row").nth(1)).to_have_attribute("aria-current", "true")


def test_compare_on_another_row_compares_it_with_the_version_alone(open_shell: OpenShell) -> None:
    page = open_shell(data=_two())
    row = page.locator(".version-row").nth(1)

    row.hover()
    row.locator(".version-row__compare").click()

    assert calls(page, "compare_versions")[-1][:2] == ["new", "old"]
    expect(page.locator("#picker-old")).to_be_visible()
    expect(page.locator("#comparison-notes")).to_be_visible()
    expect(page.locator("#version-hint")).to_be_hidden()


def test_compare_with_picks_the_other_version(open_shell: OpenShell) -> None:
    page = open_shell(data=_two())

    page.locator("#version-compare").click()
    page.locator("#pick-list .pick-row", has_text="Live build").click()

    assert calls(page, "compare_versions")[-1][:2] == ["new", "old"]


def test_the_gear_opens_the_version_details(open_shell: OpenShell) -> None:
    page = open_shell(data=_two())
    row = page.locator(".version-row").nth(1)

    row.hover()
    row.locator(".version-row__details").click()

    expect(page.locator("#details-view")).to_be_visible()
    assert calls(page, "get_version")[-1][0] == "old"
    expect(page.locator("#details-back")).to_have_text("← Back to the tech tree")

    page.locator("#details-back").click()

    expect(page.locator("#tree-view")).to_be_visible()


def test_the_gear_has_a_name_and_works_from_the_keyboard(open_shell: OpenShell) -> None:
    page = open_shell(data=_two())
    gear = page.locator(".version-row").first.locator(".version-row__details")

    expect(gear).to_have_attribute("aria-label", "Version details")
    expect(gear).to_have_attribute("title", "Version details")
    # Tab from the row to its Compare button, then to the gear.
    page.locator(".version-row").first.focus()
    page.keyboard.press("Tab")
    page.keyboard.press("Tab")
    expect(gear).to_be_focused()
    page.keyboard.press("Enter")

    expect(page.locator("#details-view")).to_be_visible()
    assert calls(page, "compare_versions")[-1][:2] == ["new", "new"]


def test_a_version_alone_reopens_at_launch(open_shell: OpenShell) -> None:
    page = open_shell(
        data=_data(version("new", "PUP"), version("old", "Live"), last_comparison=["old", "old"])
    )

    assert calls(page, "compare_versions")[0][:2] == ["old", "old"]
    expect(page.locator("#tree-view")).to_be_visible()


def test_clicking_a_tile_opens_its_details_for_the_version(open_shell: OpenShell) -> None:
    page = open_shell(data=_two())

    page.locator(".tree-node").first.click()

    expect(page.locator("#entity-scrim")).to_be_visible()
    assert calls(page, "get_entity_details")[-1][:2] == ["new", "new"]


def test_diagnostics_opens_on_the_version_alone(open_shell: OpenShell) -> None:
    page = open_shell(data=_two())

    page.locator("#diagnostics-button").click()

    assert calls(page, "get_diagnostics")[-1][0] == "new"


def test_a_tree_that_fails_says_so_in_place(open_shell: OpenShell) -> None:
    page = open_shell(data=_two() | {"techTreeError": True})

    expect(page.locator("#tree-view")).to_contain_text("The tech tree couldn't be drawn.")
    expect(page.locator("#comparison-page")).to_be_hidden()


def test_after_a_delete_the_newest_version_left_opens_alone(open_shell: OpenShell) -> None:
    data = _two()
    data["deleteResult"] = {"deleted": True, "versions": []}
    data["startup"]["versions"] = [version("old", "Live build")]
    data["startup"]["last_comparison"] = []
    page = open_shell(data=data)
    open_details(page)

    page.locator("#details-delete").click()
    page.locator("#confirm-yes").click()

    expect(page.locator("#tree-view")).to_be_visible()
    assert calls(page, "compare_versions")[-1][:2] == ["old", "old"]
