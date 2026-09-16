# SPDX-License-Identifier: GPL-3.0-or-later
"""Serve the frontend over local HTTP and fake the Python bridge, for the UI tests (D-41)."""

import functools
import json
import threading
from collections.abc import Callable, Iterator
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import pytest
from playwright.sync_api import Page
from support.ui_data import fixture_data

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


# A fake `window.pywebview.api`. Every call is recorded in `window.__calls`, and the answers come
# from the fixture data the test injected, so the page is exercised without Python.
FAKE_BRIDGE = """
(() => {
  const data = %(data)s;
  const late = %(late)s;
  window.__calls = [];
  const record = (name, args) => window.__calls.push({ name, args: [...args] });
  const answer = (name, value) => (...args) => {
    record(name, args);
    return Promise.resolve(typeof value === "function" ? value(...args) : value);
  };
  const api = {
    get_startup: answer("get_startup", data.startup),
    get_versions: answer("get_versions", () => data.startup.versions),
    get_version: answer("get_version", (id) => data.details[id] ?? data.details.__default),
    update_version: answer("update_version", (id, label, prerelease, notes) => ({
      capture_id: id, label: label ?? "", prerelease: prerelease ?? false, notes: notes ?? "",
      origin: "captured",
    })),
    delete_version: answer("delete_version", { versions: [] }),
    detect_game_folders: answer("detect_game_folders", data.candidates),
    browse_for_folder: answer("browse_for_folder", data.browsed),
    validate_game_folder: answer("validate_game_folder", data.validation),
    start_capture: answer("start_capture", { started: true }),
    get_capture_status: answer("get_capture_status", () => {
      const statuses = data.captureStatuses ?? [];
      return statuses.length > 1 ? statuses.shift() : (statuses[0] ?? null);
    }),
    cancel_capture: answer("cancel_capture", { cancelled: true }),
    clear_capture: answer("clear_capture", { cleared: true }),
    compare_versions: answer("compare_versions", data.changeSet),
    get_icons: answer("get_icons", data.icons ?? {}),
    export_text: answer("export_text", { text: data.exportText ?? "" }),
    save_export: answer("save_export", { saved: true, path: "C:/tmp/export.txt" }),
    get_settings: answer("get_settings", data.startup.settings),
    update_settings: answer("update_settings", data.startup.settings),
    purge_backups: answer("purge_backups", { removed: 3 }),
    get_diagnostics: answer("get_diagnostics", data.diagnostics),
    get_snapshot_section: answer("get_snapshot_section", { example: true }),
  };
  if (late) {
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

    def open_(
        startup: dict[str, Any] | None = None,
        *,
        late_bridge: bool = False,
        data: dict[str, Any] | None = None,
    ) -> Page:
        fixture = data if data is not None else fixture_data()
        if startup is not None:
            fixture = fixture | {"startup": startup}
        page.add_init_script(
            FAKE_BRIDGE % {"data": json.dumps(fixture), "late": json.dumps(late_bridge)}
        )
        page.goto(f"{web_server}/index.html")
        page.wait_for_selector("body[data-ready]", state="attached")
        # `data-ready` only means the page's own script ran; a stylesheet can still be in flight,
        # and a half-styled page has different hit targets.
        page.wait_for_load_state("load")
        return page

    return open_
