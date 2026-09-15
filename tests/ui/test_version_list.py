# SPDX-License-Identifier: GPL-3.0-or-later
from collections.abc import Callable

from playwright.sync_api import Page, expect

type OpenShell = Callable[..., Page]

ACTION_BUTTONS = ".version-list__actions .button, .version-list__bottom .button"


def width_of(page: Page, selector: str) -> float:
    box = page.locator(selector).bounding_box()
    assert box is not None
    return box["width"]


def test_the_list_shows_a_zero_count_and_the_empty_text(open_shell: OpenShell) -> None:
    page = open_shell()

    expect(page.locator("#versions-count")).to_have_text("0")
    expect(page.get_by_text("No versions yet.")).to_be_visible()


def test_the_toggle_collapses_the_list_to_the_strip(open_shell: OpenShell) -> None:
    page = open_shell()
    toggle = page.locator("#version-list-toggle")

    toggle.click()

    expect(page.locator("#version-list")).to_have_attribute("data-collapsed", "")
    expect(toggle).to_have_attribute("aria-expanded", "false")
    expect(toggle).to_have_attribute("aria-label", "Expand the version list")
    expect(toggle).to_have_attribute("title", "Expand the version list")
    expect(page.locator("#versions-heading")).to_be_hidden()
    assert width_of(page, "#version-list") == 64


def test_the_toggle_expands_the_strip_again(open_shell: OpenShell) -> None:
    page = open_shell()
    toggle = page.locator("#version-list-toggle")

    toggle.click()
    toggle.click()

    assert page.locator("#version-list").get_attribute("data-collapsed") is None
    expect(toggle).to_have_attribute("aria-expanded", "true")
    expect(toggle).to_have_attribute("aria-label", "Collapse the version list")
    expect(page.locator("#versions-heading")).to_be_visible()
    assert width_of(page, "#version-list") == 280


def test_strip_buttons_keep_their_names_and_show_them_as_tooltips(open_shell: OpenShell) -> None:
    page = open_shell()
    buttons = page.locator(ACTION_BUTTONS)
    names = ["Capture new version", "Import", "Diagnostics", "Settings"]
    assert [buttons.nth(i).get_attribute("title") for i in range(4)] == [None] * 4

    page.locator("#version-list-toggle").click()

    for index, name in enumerate(names):
        expect(page.get_by_role("button", name=name, exact=True).first).to_be_visible()
        expect(buttons.nth(index)).to_have_attribute("title", name)

    page.locator("#version-list-toggle").click()

    assert [buttons.nth(i).get_attribute("title") for i in range(4)] == [None] * 4


def test_the_toggle_is_the_first_keyboard_stop_and_works_with_enter_and_space(
    open_shell: OpenShell,
) -> None:
    page = open_shell()
    toggle = page.locator("#version-list-toggle")

    page.keyboard.press("Tab")
    expect(toggle).to_be_focused()
    page.keyboard.press("Enter")

    expect(page.locator("#version-list")).to_have_attribute("data-collapsed", "")

    page.keyboard.press("Enter")

    expect(toggle).to_have_attribute("aria-expanded", "true")

    page.keyboard.press("Space")

    expect(page.locator("#version-list")).to_have_attribute("data-collapsed", "")


def test_the_shell_fits_the_minimum_window(page: Page, open_shell: OpenShell) -> None:
    page.set_viewport_size({"width": 1120, "height": 640})
    open_shell()

    overflow = page.evaluate(
        """() => {
          const main = document.querySelector("main");
          const root = document.documentElement;
          return [root.scrollWidth - root.clientWidth, main.scrollWidth - main.clientWidth];
        }"""
    )
    assert overflow == [0, 0]
    first = page.locator(".card").nth(0).bounding_box()
    second = page.locator(".card").nth(1).bounding_box()
    assert first is not None and second is not None
    assert first["y"] == second["y"]
    assert second["x"] >= first["x"] + first["width"]
