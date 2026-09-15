# SPDX-License-Identifier: GPL-3.0-or-later
import mimetypes
from collections.abc import Callable, Sequence
from pathlib import Path

import pytest
import webview

from patch_scout.gui import app
from patch_scout.gui.api import Api
from patch_scout.gui.webview2 import DOWNLOAD_URL
from patch_scout.i18n.catalog import load_catalog

WEBVIEW2_TITLE = "Patch Scout needs WebView2"


class FakeWindow:
    """Stands in for a pywebview window."""

    def __init__(self) -> None:
        self.destroyed = False

    def destroy(self) -> None:
        self.destroyed = True


class FakeWebview:
    """Records what the app asks pywebview to do, without opening a window."""

    def __init__(self) -> None:
        self.windows: list[dict[str, object]] = []
        self.window: FakeWindow | None = FakeWindow()
        self.started = False
        self.start_func: Callable[..., None] | None = None
        self.start_args: Sequence[object] | None = None
        self.debug: bool | None = None

    def create_window(self, title: str, **options: object) -> FakeWindow | None:
        self.windows.append({"title": title, **options})
        return self.window

    def start(
        self,
        func: Callable[..., None] | None = None,
        args: Sequence[object] | None = None,
        debug: bool = False,
    ) -> None:
        self.started = True
        self.start_func = func
        self.start_args = args
        self.debug = debug


class Dialog:
    """Stands in for the native message box, always giving the same answer."""

    def __init__(self, answer: bool) -> None:
        self.answer = answer
        self.shown: list[tuple[str, str]] = []

    def __call__(self, title: str, text: str) -> bool:
        self.shown.append((title, text))
        return self.answer


class Browser:
    """Records the URLs the app asks the default browser to open."""

    def __init__(self) -> None:
        self.opened: list[str] = []

    def __call__(self, url: str) -> bool:
        self.opened.append(url)
        return True


def runtime_installed(hive: str, key_path: str, value_name: str) -> str | None:
    return "153.0.4234.32"


def runtime_missing(hive: str, key_path: str, value_name: str) -> str | None:
    return None


@pytest.fixture
def fake_webview(monkeypatch: pytest.MonkeyPatch) -> FakeWebview:
    fake = FakeWebview()
    monkeypatch.setattr(webview, "create_window", fake.create_window)
    monkeypatch.setattr(webview, "start", fake.start)
    return fake


def run(
    argv: Sequence[str] = (),
    *,
    installed: bool = True,
    screen: tuple[int, int] = (1920, 1080),
    dialog: Dialog | None = None,
    browser: Browser | None = None,
) -> int:
    return app.main(
        list(argv),
        read_value=runtime_installed if installed else runtime_missing,
        screen_size=lambda: screen,
        ask_to_open=dialog if dialog is not None else Dialog(answer=False),
        open_url=browser if browser is not None else Browser(),
    )


def test_main_opens_one_window_titled_from_the_catalog(fake_webview: FakeWebview) -> None:
    assert run() == 0

    assert [window["title"] for window in fake_webview.windows] == ["Patch Scout"]


def test_main_loads_the_bundled_page_by_absolute_path(fake_webview: FakeWebview) -> None:
    run()

    page = Path(str(fake_webview.windows[0]["url"]))
    assert page.is_absolute()
    assert page.name == "index.html"
    assert page.is_file()


def test_main_exposes_the_api_to_the_page(fake_webview: FakeWebview) -> None:
    run()

    assert isinstance(fake_webview.windows[0]["js_api"], Api)


def test_main_sets_the_minimum_size_and_dark_background(fake_webview: FakeWebview) -> None:
    run()

    window = fake_webview.windows[0]
    assert (window["min_size"], window["background_color"]) == ((1120, 640), "#15120f")


def test_main_opens_at_the_preferred_size_on_a_large_screen(fake_webview: FakeWebview) -> None:
    run(screen=(1920, 1080))

    window = fake_webview.windows[0]
    assert (window["width"], window["height"], window["maximized"]) == (1440, 900, False)


def test_main_opens_maximized_on_a_small_screen(fake_webview: FakeWebview) -> None:
    run(screen=(1366, 768))

    assert fake_webview.windows[0]["maximized"] is True


def test_main_starts_without_developer_tools_by_default(fake_webview: FakeWebview) -> None:
    run()

    assert fake_webview.debug is False


def test_main_starts_with_developer_tools_when_debug_is_given(fake_webview: FakeWebview) -> None:
    run(["--debug"])

    assert fake_webview.debug is True


def test_main_pins_the_frontend_file_types(fake_webview: FakeWebview) -> None:
    mimetypes.add_type("text/plain", ".js")

    run()

    assert mimetypes.guess_type("app.js") == ("text/javascript", None)


def test_main_runs_the_renderer_check_on_the_window(fake_webview: FakeWebview) -> None:
    run()

    assert fake_webview.start_func is app.check_renderer
    assert fake_webview.start_args is not None
    assert fake_webview.start_args[0] is fake_webview.window


def test_main_without_the_runtime_explains_and_opens_no_window(
    fake_webview: FakeWebview,
) -> None:
    dialog, browser = Dialog(answer=False), Browser()

    assert run(installed=False, dialog=dialog, browser=browser) == 1

    assert [title for title, _ in dialog.shown] == [WEBVIEW2_TITLE]
    assert (fake_webview.windows, fake_webview.started, browser.opened) == ([], False, [])


def test_main_without_the_runtime_opens_the_download_page_on_yes(
    fake_webview: FakeWebview,
) -> None:
    browser = Browser()

    assert run(installed=False, dialog=Dialog(answer=True), browser=browser) == 1

    assert browser.opened == [DOWNLOAD_URL]


def test_main_returns_1_when_pywebview_cancels_the_window(fake_webview: FakeWebview) -> None:
    fake_webview.window = None

    assert run() == 1

    assert fake_webview.started is False


def test_check_renderer_leaves_an_edge_chromium_window_alone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(webview, "renderer", "edgechromium")
    window, dialog = FakeWindow(), Dialog(answer=True)

    app.check_renderer(window, load_catalog("en"), dialog, Browser())

    assert (window.destroyed, dialog.shown) == (False, [])


def test_check_renderer_explains_and_closes_a_fallback_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(webview, "renderer", "mshtml")
    window, dialog, browser = FakeWindow(), Dialog(answer=True), Browser()

    app.check_renderer(window, load_catalog("en"), dialog, browser)

    assert window.destroyed is True
    assert [title for title, _ in dialog.shown] == [WEBVIEW2_TITLE]
    assert browser.opened == [DOWNLOAD_URL]
