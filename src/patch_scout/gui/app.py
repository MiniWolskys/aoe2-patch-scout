# SPDX-License-Identifier: GPL-3.0-or-later
"""Start the Patch Scout window."""

import argparse
from collections.abc import Sequence

import webview

from patch_scout.i18n.catalog import load_catalog


def main(argv: Sequence[str] | None = None) -> None:
    """Open the main window; `--debug` turns on the WebView developer tools."""
    parser = argparse.ArgumentParser(prog="patch-scout")
    parser.add_argument("--debug", action="store_true")
    debug: bool = parser.parse_args(argv).debug
    catalog = load_catalog("en")
    webview.create_window(catalog.text("app.title"))
    webview.start(debug=debug)
