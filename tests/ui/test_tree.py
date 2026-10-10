# SPDX-License-Identifier: GPL-3.0-or-later
"""The tech tree view: opening it, the shared civ, marks, fit (D-39, ui.md "Tech tree")."""

from collections.abc import Callable
from typing import Any

from playwright.sync_api import Page, expect
from support.ui_data import calls, fixture_data, startup_data, tech_tree, version

type OpenShell = Callable[..., Page]


def _compared(open_shell: OpenShell, **overrides: Any) -> Page:
    """The app with a comparison open, its tech tree answering with the sample tree."""
    rows = [version("new", "PUP build"), version("old", "Live build")]
    data = fixture_data(startup=startup_data(versions=rows), techTree=tech_tree()) | overrides
    page = open_shell(data=data)
    page.locator(".version-row").nth(1).click(modifiers=["Control"])
    expect(page.locator("#comparison-view")).to_be_visible()
    return page


def _civ(page: Page, name: str) -> None:
    page.locator(".civ-row", has_text=name).click()


def test_the_tree_button_shows_the_civ_tree_and_back_returns(open_shell: OpenShell) -> None:
    page = _compared(open_shell)
    _civ(page, "Franks")

    page.locator("#comparison-tree").click()

    expect(page.locator("#tree-view")).to_be_visible()
    expect(page.locator("#comparison-page")).to_be_hidden()
    expect(page.locator(".tree-node")).to_have_count(6)
    assert calls(page, "get_tech_tree")[-1][:3] == ["old", "new", "Franks"]

    page.locator("#comparison-tree").click()

    expect(page.locator("#comparison-page")).to_be_visible()
    expect(page.locator("#tree-view")).to_be_hidden()
    expect(page.locator("#comparison-title")).to_have_text("Franks")


def test_the_tree_from_overall_shows_the_last_civ_selected(open_shell: OpenShell) -> None:
    page = _compared(open_shell)
    _civ(page, "Franks")
    _civ(page, "Overall")

    page.locator("#comparison-tree").click()

    assert calls(page, "get_tech_tree")[-1][2] == "Franks"
    page.locator("#comparison-tree").click()
    expect(page.locator("#comparison-title")).to_have_text("Overall")


def test_the_tree_from_overall_with_no_civ_yet_shows_the_first_civ(open_shell: OpenShell) -> None:
    page = _compared(open_shell)

    page.locator("#comparison-tree").click()

    assert calls(page, "get_tech_tree")[-1][2] == "Franks"


def test_a_civ_chosen_on_the_tree_is_the_one_shown_after_going_back(open_shell: OpenShell) -> None:
    page = _compared(open_shell)
    page.locator("#comparison-tree").click()

    page.locator(".civ-tab", has_text="Chronicles").click()

    assert calls(page, "get_tech_tree")[-1][2] == "Spartans"
    page.locator("#comparison-tree").click()
    expect(page.locator("#comparison-title")).to_have_text("Spartans")


def test_marks_and_unavailable_nodes_are_drawn(open_shell: OpenShell) -> None:
    page = _compared(open_shell)
    page.locator("#comparison-tree").click()

    expect(page.locator(".tree-node.mark-changed")).to_have_text("Archer")
    expect(page.locator(".tree-node.mark-gained")).to_have_text("Crossbowman")
    expect(page.locator(".tree-node.mark-lost")).to_have_text("Thumb Ring")
    expect(page.locator(".tree-node.is-unavailable")).to_have_text("Militia")
    expect(page.locator(".tree__lines path")).to_have_count(1)


def test_tiles_do_not_overlap(open_shell: OpenShell) -> None:
    page = _compared(open_shell)
    page.locator("#comparison-tree").click()
    expect(page.locator(".tree-node")).to_have_count(6)

    boxes = [node.bounding_box() for node in page.locator(".tree-node").all()]
    assert all(box is not None for box in boxes)
    for index, first in enumerate(boxes):
        for second in boxes[index + 1 :]:
            assert first is not None and second is not None
            apart = (
                first["x"] + first["width"] <= second["x"]
                or second["x"] + second["width"] <= first["x"]
                or first["y"] + first["height"] <= second["y"]
                or second["y"] + second["height"] <= first["y"]
            )
            assert apart


def test_fit_scales_a_wide_tree_down_to_the_width(open_shell: OpenShell) -> None:
    wide = tech_tree(columns=60)
    page = _compared(open_shell, techTree=wide)
    page.locator("#comparison-tree").click()
    canvas = page.locator(".tree__canvas")
    before = canvas.bounding_box()

    page.locator("#tree-fit").click()

    after = canvas.bounding_box()
    scroller = page.locator(".tree__scroll").bounding_box()
    assert before is not None and after is not None and scroller is not None
    assert after["width"] < before["width"]
    assert after["width"] <= scroller["width"] + 1


def test_a_tree_that_cannot_be_drawn_goes_back_to_the_changes(open_shell: OpenShell) -> None:
    page = _compared(open_shell, techTreeError=True)

    page.locator("#comparison-tree").click()

    expect(page.locator("#toast")).to_contain_text("tech tree")
    expect(page.locator("#comparison-page")).to_be_visible()
