# SPDX-License-Identifier: GPL-3.0-or-later
"""The tech tree view: opening it, the shared civ, marks, fit (D-39, ui.md "Tech tree")."""

from collections.abc import Callable
from typing import Any

from playwright.sync_api import Page, expect
from support.ui_data import (
    PIXEL,
    calls,
    change_set,
    fixture_data,
    show_changes,
    startup_data,
    tech_tree,
    version,
)

type OpenShell = Callable[..., Page]


def _compared(open_shell: OpenShell, **overrides: Any) -> Page:
    """The app with a comparison open, its tech tree answering with the sample tree."""
    rows = [version("new", "PUP build"), version("old", "Live build")]
    data = fixture_data(startup=startup_data(versions=rows), techTree=tech_tree()) | overrides
    page = open_shell(data=data)
    page.locator(".version-row").nth(1).click(modifiers=["Control"])
    show_changes(page)
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


def _open_tree(open_shell: OpenShell, **overrides: Any) -> Page:
    page = _compared(open_shell, **overrides)
    page.locator("#comparison-tree").click()
    expect(page.locator(".tree-node").first).to_be_visible()
    return page


def test_each_age_shows_its_shield_above_its_name(open_shell: OpenShell) -> None:
    shields = {f"age_{age}": {"hash": str(age) * 64, "category": "ages"} for age in range(1, 5)}
    page = _open_tree(
        open_shell,
        changeSet=change_set(stat_icons=shields),
        icons={str(age) * 64: PIXEL for age in range(1, 5)},
    )

    labels = page.locator(".tree__age-label")
    expect(labels.locator("img.tree__age-shield")).to_have_count(4)
    expect(labels.nth(1)).to_contain_text("Feudal Age")
    # Decoration: the age name is the text.
    assert labels.nth(1).locator("img").get_attribute("alt") == ""


def test_without_shields_the_ages_show_their_names_alone(open_shell: OpenShell) -> None:
    page = _open_tree(open_shell)

    expect(page.locator(".tree__age-shield")).to_have_count(0)
    expect(page.locator(".tree__age-label")).to_have_text(
        ["Dark Age", "Feudal Age", "Castle Age", "Imperial Age"]
    )


def test_hovering_a_node_shows_the_games_tooltip_with_old_and_new_values(
    open_shell: OpenShell,
) -> None:
    page = _open_tree(open_shell)

    page.locator(".tree-node.mark-changed").hover()

    panel = page.locator("#tree-panel")
    expect(panel).to_be_visible()
    expect(panel).to_contain_text("All-purpose Foot Archer.")
    expect(panel.locator(".is-bold")).to_have_text("Archer")
    expect(panel.locator(".tree-panel__stats .value-old")).to_have_text(["30"])
    expect(panel.locator(".tree-panel__stats .value-new")).to_have_text(["35"])
    expect(panel.locator(".tree-panel__cost .value-old")).to_have_text(["45"])
    expect(panel.locator(".tree-panel__cost .value-new")).to_have_text(["40"])
    expect(panel.locator(".tree-panel__changes .change-values")).to_have_count(1)
    expect(panel).to_contain_text("before civilization bonuses")


def test_a_missing_value_reads_as_a_question_mark(open_shell: OpenShell) -> None:
    page = _open_tree(open_shell)

    page.locator(".tree-node.mark-changed").hover()

    expect(page.locator("#tree-panel [data-stat='range']")).to_have_text("?")


def test_moving_away_hides_the_panel(open_shell: OpenShell) -> None:
    page = _open_tree(open_shell)
    page.locator(".tree-node.mark-changed").hover()
    expect(page.locator("#tree-panel")).to_be_visible()

    page.mouse.move(5, 5)

    expect(page.locator("#tree-panel")).to_be_hidden()


def test_keyboard_focus_shows_the_panel_and_escape_hides_it(open_shell: OpenShell) -> None:
    page = _open_tree(open_shell)

    page.locator(".tree-node", has_text="Crossbowman").focus()

    panel = page.locator("#tree-panel")
    expect(panel).to_be_visible()
    expect(page.locator(".tree-node", has_text="Crossbowman")).to_have_attribute(
        "aria-describedby", "tree-panel"
    )
    page.keyboard.press("Escape")
    expect(panel).to_be_hidden()


def test_the_panel_stays_on_screen_next_to_the_right_edge(open_shell: OpenShell) -> None:
    page = _open_tree(open_shell)
    page.set_viewport_size({"width": 1100, "height": 600})
    scroller = page.locator(".tree__scroll")
    scroller.evaluate("element => { element.scrollLeft = element.scrollWidth }")
    target = page.locator(".tree-node", has_text="Militia")
    target.scroll_into_view_if_needed()

    target.hover()

    box = page.locator("#tree-panel").bounding_box()
    assert box is not None
    assert box["x"] >= 0 and box["y"] >= 0
    assert box["x"] + box["width"] <= 1100
    assert box["y"] + box["height"] <= 600


def test_a_renamed_node_says_its_old_name(open_shell: OpenShell) -> None:
    tree = tech_tree()
    tree["nodes"][2] |= {"mark": "renamed", "old_name": "Longboat"}
    page = _open_tree(open_shell, techTree=tree)

    page.locator(".tree-node", has_text="Crossbowman").hover()

    expect(page.locator("#tree-panel")).to_contain_text("Formerly Longboat")


def test_the_unreachable_filter_keeps_the_tree_and_its_civ(open_shell: OpenShell) -> None:
    page = _compared(open_shell)
    _civ(page, "Franks")
    page.locator("#comparison-tree").click()
    expect(page.locator(".tree-node").first).to_be_visible()

    page.locator("#comparison-filters").click()
    page.locator("#filter-unreachable").check()

    expect(page.locator("#tree-view")).to_be_visible()
    expect(page.locator(".tree-node").first).to_be_visible()
    assert calls(page, "get_tech_tree")[-1][2] == "Franks"


def test_searching_while_the_tree_shows_does_not_redraw_it(open_shell: OpenShell) -> None:
    page = _open_tree(open_shell)
    page.locator(".tree-node").first.evaluate("node => { node.dataset.kept = 'yes' }")

    page.locator("#comparison-filters").click()
    page.locator("#filter-search").fill("arch")

    expect(page.locator(".tree-node").first).to_have_attribute("data-kept", "yes")


def test_a_node_the_civ_cannot_get_says_so(open_shell: OpenShell) -> None:
    page = _open_tree(open_shell)

    expect(page.locator(".tree-node.is-unavailable")).to_have_attribute(
        "aria-label", "Militia, Not available"
    )


def test_the_left_panel_shows_the_civ_bonuses_with_their_changes_and_the_key(
    open_shell: OpenShell,
) -> None:
    bonus = [
        {"kind": "same", "text": "Archer civilization\n• Foot archers "},
        {"kind": "removed", "text": "+1"},
        {"kind": "added", "text": "+2"},
    ]
    page = _open_tree(open_shell, techTree=tech_tree(bonus=bonus))

    side = page.locator(".tree__side")
    expect(side.locator(".tree__civ-name")).to_have_text("Franks")
    expect(side.locator(".tree__bonus del")).to_have_text("+1")
    expect(side.locator(".tree__bonus ins")).to_have_text("+2")
    expect(side.locator(".tree__key")).to_contain_text("Regional")
