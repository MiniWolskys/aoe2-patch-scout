# SPDX-License-Identifier: GPL-3.0-or-later
import mimetypes
import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

import pytest
import webview

from patch_scout.gui import app
from patch_scout.gui.api import Api
from patch_scout.gui.webview2 import DOWNLOAD_URL
from patch_scout.i18n.catalog import load_catalog

WEBVIEW2_TITLE = "Patch Scout needs WebView2"


@dataclass(frozen=True, slots=True)
class FakeScreen:
    """A screen in logical pixels, standing in for `webview.screen.Screen` in tests."""

    x: int
    y: int
    width: int
    height: int


DEFAULT_SCREEN = FakeScreen(x=0, y=0, width=1920, height=1080)


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
        # Real pywebview runs `func` on a thread before the window is created; tests that
        # need the renderer check to actually run opt into calling it synchronously.
        self.run_func = False

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
        if self.run_func and func is not None:
            func(*(args or ()))


class Dialog:
    """Stands in for the native message box, always giving the same answer."""

    def __init__(self, answer: bool, window: FakeWindow | None = None) -> None:
        self.answer = answer
        self.shown: list[tuple[str, str]] = []
        # When given the window, records whether it was already destroyed each time the
        # dialog is shown, so tests can check the fallback closes it first.
        self.window = window
        self.destroyed_when_shown: list[bool] = []

    def __call__(self, title: str, text: str) -> bool:
        self.shown.append((title, text))
        if self.window is not None:
            self.destroyed_when_shown.append(self.window.destroyed)
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
    screen: FakeScreen | None = DEFAULT_SCREEN,
    dialog: Dialog | None = None,
    browser: Browser | None = None,
) -> int:
    return app.main(
        list(argv),
        read_value=runtime_installed if installed else runtime_missing,
        choose_screen=lambda: screen,
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
    run(screen=FakeScreen(x=0, y=0, width=1920, height=1080))

    window = fake_webview.windows[0]
    assert (window["width"], window["height"], window["maximized"]) == (1440, 900, False)


def test_main_opens_maximized_on_a_small_screen(fake_webview: FakeWebview) -> None:
    run(screen=FakeScreen(x=0, y=0, width=1366, height=768))

    assert fake_webview.windows[0]["maximized"] is True


def test_main_passes_the_chosen_screen_to_create_window(fake_webview: FakeWebview) -> None:
    screen = FakeScreen(x=0, y=0, width=1920, height=1080)

    run(screen=screen)

    assert fake_webview.windows[0]["screen"] is screen


def test_main_opens_maximized_with_no_screen_information(fake_webview: FakeWebview) -> None:
    run(screen=None)

    window = fake_webview.windows[0]
    assert (window["width"], window["height"], window["maximized"]) == (1440, 900, True)
    assert "screen" not in window


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
    assert isinstance(fake_webview.start_args[-1], threading.Event)


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


def test_main_returns_1_when_pywebview_falls_back_to_another_renderer(
    fake_webview: FakeWebview, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(webview, "renderer", "mshtml")
    fake_webview.run_func = True

    assert run() == 1


def test_main_returns_0_when_the_renderer_is_edge_chromium(
    fake_webview: FakeWebview, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(webview, "renderer", "edgechromium")
    fake_webview.run_func = True

    assert run() == 0


def test_check_renderer_leaves_an_edge_chromium_window_alone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(webview, "renderer", "edgechromium")
    window, dialog = FakeWindow(), Dialog(answer=True)
    failed = threading.Event()

    app.check_renderer(window, load_catalog("en"), dialog, Browser(), failed)

    assert (window.destroyed, dialog.shown, failed.is_set()) == (False, [], False)


def test_check_renderer_closes_the_window_before_explaining_a_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(webview, "renderer", "mshtml")
    window = FakeWindow()
    dialog = Dialog(answer=True, window=window)
    browser = Browser()
    failed = threading.Event()

    app.check_renderer(window, load_catalog("en"), dialog, browser, failed)

    assert window.destroyed is True
    assert dialog.destroyed_when_shown == [True]
    assert failed.is_set() is True
    assert [title for title, _ in dialog.shown] == [WEBVIEW2_TITLE]
    assert browser.opened == [DOWNLOAD_URL]
