# SPDX-License-Identifier: GPL-3.0-or-later
import pytest
import webview

from patch_scout.gui import app


class FakeWebview:
    """Records what the app asks pywebview to do, without opening a window."""

    def __init__(self) -> None:
        self.window_titles: list[str] = []
        self.debug: bool | None = None

    def create_window(self, title: str) -> None:
        self.window_titles.append(title)

    def start(self, debug: bool = False) -> None:
        self.debug = debug


@pytest.fixture
def fake_webview(monkeypatch: pytest.MonkeyPatch) -> FakeWebview:
    fake = FakeWebview()
    monkeypatch.setattr(webview, "create_window", fake.create_window)
    monkeypatch.setattr(webview, "start", fake.start)
    return fake


def test_main_opens_one_window_titled_from_the_catalog(fake_webview: FakeWebview) -> None:
    app.main([])

    assert fake_webview.window_titles == ["Patch Scout"]


def test_main_starts_without_developer_tools_by_default(fake_webview: FakeWebview) -> None:
    app.main([])

    assert fake_webview.debug is False


def test_main_starts_with_developer_tools_when_debug_is_given(fake_webview: FakeWebview) -> None:
    app.main(["--debug"])

    assert fake_webview.debug is True
