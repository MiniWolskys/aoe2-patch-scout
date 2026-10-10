# SPDX-License-Identifier: GPL-3.0-or-later
import mimetypes

import pytest

from patch_scout.gui.web_files import WEB_TYPES, pin_mime_types, web_root


def test_web_root_is_an_absolute_folder_holding_the_page() -> None:
    root = web_root()

    assert root.is_absolute()
    assert (root / "index.html").is_file()


def test_web_types_cover_the_files_the_page_loads() -> None:
    assert WEB_TYPES == {
        ".js": "text/javascript",
        ".css": "text/css",
        ".svg": "image/svg+xml",
        ".ttf": "font/ttf",
    }


@pytest.mark.parametrize(("extension", "mime_type"), sorted(WEB_TYPES.items()))
def test_pin_mime_types_overrides_a_wrong_registry_type(extension: str, mime_type: str) -> None:
    mimetypes.add_type("text/plain", extension)

    pin_mime_types()

    assert mimetypes.guess_type(f"file{extension}") == (mime_type, None)


def test_the_file_server_queues_the_pages_parallel_requests() -> None:
    from wsgiref.simple_server import WSGIServer

    from patch_scout.gui.web_files import LISTEN_BACKLOG, allow_parallel_loads

    allow_parallel_loads()
    assert WSGIServer.request_queue_size == LISTEN_BACKLOG >= 32
