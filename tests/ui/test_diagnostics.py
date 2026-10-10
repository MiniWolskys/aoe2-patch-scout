# SPDX-License-Identifier: GPL-3.0-or-later
"""The Diagnostics window: readable boxes, selectable text, copy buttons (ui.md)."""

from collections.abc import Callable
from typing import Any

from playwright.sync_api import Page, expect
from support.ui_data import fixture_data

type OpenShell = Callable[..., Page]


def _diagnostics(open_shell: OpenShell, **diagnostics: Any) -> Page:
    data = fixture_data()
    data["diagnostics"] = data["diagnostics"] | diagnostics
    page = open_shell(data=data)
    page.context.grant_permissions(["clipboard-read", "clipboard-write"])
    page.locator("#diagnostics-button").click()
    expect(page.locator("#diagnostics-scrim")).to_be_visible()
    return page


def test_the_log_and_the_problems_are_tall_enough_to_read(open_shell: OpenShell) -> None:
    """They collapsed to a sliver in the dialog's column, showing only their scroll arrows."""
    lines = [f"line {index}" for index in range(30)]
    page = _diagnostics(open_shell, log=lines, problems=lines)

    for box in ("#diagnostics-log", "#diagnostics-problems"):
        size = page.locator(box).bounding_box()
        assert size is not None and size["height"] >= 100, box


def test_an_empty_capture_log_says_so(open_shell: OpenShell) -> None:
    page = _diagnostics(open_shell, log=[])

    expect(page.locator("#diagnostics-log")).to_have_text(
        "No capture has run since the app started."
    )


def test_the_environment_reads_in_words(open_shell: OpenShell) -> None:
    page = _diagnostics(
        open_shell, environment={"app_version": "0.0.0-test", "pillow_version": None}
    )

    environment = page.locator("#diagnostics-environment")
    expect(environment).to_contain_text("App version")
    expect(environment).to_contain_text("Pillow version")
    expect(environment).to_contain_text("unknown")
    expect(environment).not_to_contain_text("app_version")


def test_the_text_boxes_can_be_selected(open_shell: OpenShell) -> None:
    """pywebview turns text selection off for the whole page; these boxes turn it back on."""
    page = _diagnostics(open_shell)

    for box in ("#diagnostics-log", "#diagnostics-problems", "#diagnostics-section-body"):
        selectable = page.locator(box).evaluate("element => getComputedStyle(element).userSelect")
        assert selectable == "text", box


def test_each_box_copies_its_whole_content(open_shell: OpenShell) -> None:
    """The browser's right-click menu is off in the app, so each box has its own Copy button."""
    page = _diagnostics(open_shell, log=["folder 0%", "save 95%"])
    expect(page.locator("#diagnostics-section-body")).to_contain_text("example")

    for box, button in (
        ("#diagnostics-log", "#diagnostics-log-copy"),
        ("#diagnostics-problems", "#diagnostics-problems-copy"),
        ("#diagnostics-section-body", "#diagnostics-section-copy"),
    ):
        page.locator(button).click()
        copied: str = page.evaluate("() => navigator.clipboard.readText()")
        # Windows' clipboard writes line breaks as CRLF.
        assert copied.replace("\r\n", "\n") == page.locator(box).inner_text(), box
        expect(page.locator("#toast")).to_be_visible()
