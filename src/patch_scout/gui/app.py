# SPDX-License-Identifier: GPL-3.0-or-later
"""Start Patch Scout: check for the WebView2 Runtime, then open the main window."""

import argparse
import importlib.metadata
import logging
import threading
import webbrowser
from collections.abc import Callable, Sequence
from typing import Final, Protocol, cast

import webview

from patch_scout.gui.api import Api
from patch_scout.gui.web_files import pin_mime_types, web_root
from patch_scout.gui.webview2 import (
    DOWNLOAD_URL,
    RegistryReader,
    ask_to_open_download_page,
    installed_runtime_version,
    read_registry_value,
)
from patch_scout.gui.window import (
    MIN_SIZE,
    PREFERRED_SIZE,
    Geometry,
    Screen,
    primary_screen,
    window_geometry,
)
from patch_scout.i18n.catalog import Catalog, load_catalog

logger = logging.getLogger(__name__)

LANGUAGE: Final = "en"
# The Forge `bg-base` token (web/styles/theme.css), shown until the page's CSS has loaded.
BACKGROUND_COLOR: Final = "#15120f"

type AskToOpen = Callable[[str, str], bool]
type OpenUrl = Callable[[str], object]
type ChooseScreen = Callable[[], Screen | None]


class Closable(Protocol):
    """A window the renderer check can close."""

    def destroy(self) -> None: ...


def default_screen() -> webview.Screen | None:
    """Return the primary screen from `webview.screens`, before `webview.start` (D-42)."""
    # `webview.screens` is a proxy_tools `module_property`; proxy_tools ships no type
    # information, so mypy sees it as Any. It actually returns list[webview.Screen].
    return primary_screen(cast(Sequence[webview.Screen], webview.screens))


def offer_download_page(catalog: Catalog, ask_to_open: AskToOpen, open_url: OpenUrl) -> None:
    """Explain that WebView2 is needed, and open its download page if the user agrees."""
    title = catalog.text("webview2.missing.title")
    if ask_to_open(title, catalog.text("webview2.missing.text")):
        open_url(DOWNLOAD_URL)


def check_renderer(
    window: Closable,
    catalog: Catalog,
    ask_to_open: AskToOpen,
    open_url: OpenUrl,
    failed: threading.Event,
) -> None:
    """Close the window, then explain, if pywebview fell back from Edge Chromium (D-40).

    pywebview starts this check on its own thread before the window exists, so a message
    box shown first would end up covered by the new window; closing the window first keeps
    the message on top. `failed` is set so that `main` can report exit code 1.
    """
    if webview.renderer == "edgechromium":
        return
    logger.error("pywebview is using %s instead of Edge Chromium", webview.renderer)
    failed.set()
    window.destroy()
    offer_download_page(catalog, ask_to_open, open_url)


def main(
    argv: Sequence[str] | None = None,
    *,
    read_value: RegistryReader = read_registry_value,
    choose_screen: ChooseScreen = default_screen,
    ask_to_open: AskToOpen = ask_to_open_download_page,
    open_url: OpenUrl = webbrowser.open,
) -> int:
    """Open the main window and return the exit code; `--debug` turns on developer tools.

    Exit codes: 0 means the window closed normally; 1 means the WebView2 Runtime is missing,
    or pywebview fell back to another engine after start.
    """
    parser = argparse.ArgumentParser(prog="patch-scout")
    parser.add_argument("--debug", action="store_true")
    debug: bool = parser.parse_args(argv).debug
    logging.basicConfig(level=logging.DEBUG if debug else logging.INFO)
    pin_mime_types()
    catalog = load_catalog(LANGUAGE)

    runtime = installed_runtime_version(read_value)
    if runtime is None:
        logger.warning("the WebView2 Runtime isn't installed")
        offer_download_page(catalog, ask_to_open, open_url)
        return 1
    logger.info("WebView2 Runtime %s", runtime)

    screen = choose_screen()
    if screen is None:
        # No screen information: open at the preferred size, maximized (D-42).
        geometry = Geometry(*PREFERRED_SIZE, maximized=True)
        window = webview.create_window(
            catalog.text("app.title"),
            url=str(web_root() / "index.html"),
            js_api=Api(catalog, LANGUAGE, importlib.metadata.version("patch-scout")),
            width=geometry.width,
            height=geometry.height,
            maximized=geometry.maximized,
            min_size=MIN_SIZE,
            background_color=BACKGROUND_COLOR,
        )
    else:
        geometry = window_geometry(screen.width, screen.height)
        window = webview.create_window(
            catalog.text("app.title"),
            url=str(web_root() / "index.html"),
            js_api=Api(catalog, LANGUAGE, importlib.metadata.version("patch-scout")),
            width=geometry.width,
            height=geometry.height,
            maximized=geometry.maximized,
            min_size=MIN_SIZE,
            background_color=BACKGROUND_COLOR,
            # `screen` is a Screen protocol so tests can supply fakes; the real callable
            # always returns pywebview's own Screen, which create_window expects.
            screen=cast(webview.Screen, screen),
        )
    if window is None:  # pywebview returns None only when a handler cancels the window
        logger.error("the main window wasn't created")
        return 1
    renderer_failed = threading.Event()
    webview.start(
        func=check_renderer,
        args=(window, catalog, ask_to_open, open_url, renderer_failed),
        debug=debug,
    )
    return 1 if renderer_failed.is_set() else 0
