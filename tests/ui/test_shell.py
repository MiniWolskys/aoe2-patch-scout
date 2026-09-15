# SPDX-License-Identifier: GPL-3.0-or-later
from collections.abc import Callable

from playwright.sync_api import Page, expect

type OpenShell = Callable[..., Page]


def test_the_page_becomes_ready_in_the_catalog_language(open_shell: OpenShell) -> None:
    page = open_shell()

    expect(page.locator("html")).to_have_attribute("lang", "en")


def test_the_page_starts_when_the_bridge_arrives_after_loading(open_shell: OpenShell) -> None:
    page = open_shell(late_bridge=True)

    expect(page.locator("body")).to_have_attribute("data-ready", "")


def test_every_translated_element_has_its_text(open_shell: OpenShell) -> None:
    page = open_shell()

    empty = page.locator("[data-i18n]").evaluate_all(
        "elements => elements.filter(e => !e.textContent.trim()).map(e => e.dataset.i18n)"
    )
    assert empty == []


def test_every_translated_attribute_is_filled(open_shell: OpenShell) -> None:
    page = open_shell()

    missing = page.locator("[data-i18n-attr]").evaluate_all(
        """elements => elements.flatMap(e => e.dataset.i18nAttr.trim().split(/\\s+/)
            .map(pair => pair.split(":")[0])
            .filter(attribute => !e.getAttribute(attribute)))"""
    )
    assert missing == []


def test_first_launch_shows_the_headline_and_preview_warning(open_shell: OpenShell) -> None:
    page = open_shell()

    expect(page.get_by_role("heading", level=1)).to_have_text(
        "You need two versions of the game to compare"
    )
    expect(
        page.get_by_text(
            "Getting a preview build? Capture the live version before you switch Steam to it."
        )
    ).to_be_visible()


def test_controls_for_later_features_are_visible_but_disabled(open_shell: OpenShell) -> None:
    page = open_shell()

    expected = [("Capture new version", 2), ("Import", 2), ("Diagnostics", 1), ("Settings", 1)]
    for name, count in expected:
        buttons = page.get_by_role("button", name=name, exact=True)
        expect(buttons).to_have_count(count)
        for index in range(count):
            expect(buttons.nth(index)).to_be_visible()
            expect(buttons.nth(index)).to_be_disabled()


def test_the_bundled_fonts_load(open_shell: OpenShell) -> None:
    page = open_shell()

    loaded = page.evaluate(
        """async () => [
          (await document.fonts.load('600 16px "Barlow Semi Condensed"')).length,
          (await document.fonts.load('12px "Marcellus SC"')).length,
        ]"""
    )
    assert loaded == [1, 1]


def test_the_page_loads_without_console_errors(
    console_errors: list[str], open_shell: OpenShell
) -> None:
    open_shell()

    assert console_errors == []
