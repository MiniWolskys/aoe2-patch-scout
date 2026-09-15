# SPDX-License-Identifier: GPL-3.0-or-later
"""Serve the frontend over local HTTP for the Playwright tests (D-41)."""

import functools
import threading
from collections.abc import Iterator
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

import pytest
from playwright.sync_api import Page

from patch_scout.gui.web_files import pin_mime_types, web_root


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
