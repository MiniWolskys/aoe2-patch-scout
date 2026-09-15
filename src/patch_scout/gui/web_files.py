# SPDX-License-Identifier: GPL-3.0-or-later
"""Where the frontend files live, and the types they're served with."""

import mimetypes
from importlib.resources import files
from pathlib import Path
from typing import Final

# pywebview serves the page through Bottle, which asks Python's mimetypes. On Windows that also
# reads the registry, which other software can change, and Chromium refuses ES modules served
# as text/plain (docs/reference/packaging.md).
WEB_TYPES: Final = {
    ".js": "text/javascript",
    ".css": "text/css",
    ".svg": "image/svg+xml",
    ".ttf": "font/ttf",
}


def web_root() -> Path:
    """Return the absolute path of the folder holding index.html and its files."""
    return Path(str(files("patch_scout.gui").joinpath("web"))).resolve()


def pin_mime_types() -> None:
    """Register the frontend's file types, overriding whatever the registry says."""
    for extension, mime_type in WEB_TYPES.items():
        mimetypes.add_type(mime_type, extension)
