# SPDX-License-Identifier: GPL-3.0-or-later
"""Serve the frontend over local HTTP for the Playwright tests (D-41)."""

import functools
import json
import threading
from collections.abc import Callable, Iterator
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

import pytest
from playwright.sync_api import Page

from patch_scout.gui.web_files import pin_mime_types, web_root
from patch_scout.i18n.catalog import load_catalog


class QuietHandler(SimpleHTTPRequestHandler):
    """Serves files without logging every request."""

    def log_message(self, format: str, *args: object) -> None:
        pass


@pytest.fixture(scope="session")
def web_server() -> Iterator[str]:
    """Serve gui/web/ on 127.0.0.1 with the app's file types; yield the base URL."""
    pin_mime_types()
    handler = functools.partial(QuietHandler, directory=str(web_root()))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    server.server_close()


@pytest.fixture
def blank_page(page: Page, web_server: str) -> Page:
    """A page at index.html, for testing JS modules on their own."""
    page.goto(f"{web_server}/index.html")
    return page


FAKE_BRIDGE = """
(() => {
  const api = { get_startup: () => Promise.resolve(%(startup)s) };
  if (%(late)s) {
    window.pywebview = { api: {} };
    window.addEventListener("load", () => {
      Object.assign(window.pywebview.api, api);
      window.dispatchEvent(new CustomEvent("pywebviewready"));
    });
  } else {
    window.pywebview = { api };
  }
})();
"""


def startup_data(**overrides: object) -> dict[str, object]:
    """What Api.get_startup() returns, with the real English messages."""
    data: dict[str, object] = {
        "language": "en",
        "messages": load_catalog("en").messages(),
        "app_version": "0.0.0-test",
        "versions": [],
    }
    return data | overrides


@pytest.fixture
def console_errors(page: Page) -> list[str]:
    """Console errors and uncaught exceptions; request it before `open_shell`."""
    errors: list[str] = []
    page.on(
        "console",
        lambda message: errors.append(message.text) if message.type == "error" else None,
    )
    page.on("pageerror", lambda error: errors.append(str(error)))
    return errors


@pytest.fixture
def open_shell(page: Page, web_server: str) -> Callable[..., Page]:
    """Open the shell with a fake pywebview bridge; returns once the page is ready."""

    def open_(startup: dict[str, object] | None = None, *, late_bridge: bool = False) -> Page:
        data = startup if startup is not None else startup_data()
        page.add_init_script(
            FAKE_BRIDGE % {"startup": json.dumps(data), "late": json.dumps(late_bridge)}
        )
        page.goto(f"{web_server}/index.html")
        page.wait_for_selector("body[data-ready]", state="attached")
        return page

    return open_
