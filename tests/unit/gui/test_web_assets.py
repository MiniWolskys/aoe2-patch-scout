# SPDX-License-Identifier: GPL-3.0-or-later
import re
from pathlib import Path

import pytest

from patch_scout.gui import app
from patch_scout.gui.web_files import web_root

CSS_URL = re.compile(r"""url\(\s*["']?([^"')]+)["']?\s*\)""")


def css_references() -> list[tuple[str, str]]:
    return [
        (stylesheet.name, target)
        for stylesheet in sorted((web_root() / "styles").glob("*.css"))
        for target in CSS_URL.findall(stylesheet.read_text(encoding="utf-8"))
    ]


def test_stylesheets_reference_bundled_files() -> None:
    assert ("fonts.css", "../vendor/fonts/marcellus-sc/MarcellusSC-Regular.ttf") in css_references()


@pytest.mark.parametrize(("stylesheet", "target"), css_references())
def test_every_css_url_points_to_a_bundled_file(stylesheet: str, target: str) -> None:
    assert (web_root() / "styles" / Path(target)).resolve().is_file()


@pytest.mark.parametrize(
    "licence",
    [
        "vendor/fonts/barlow-semi-condensed/OFL.txt",
        "vendor/fonts/marcellus-sc/OFL.txt",
        "vendor/lucide/LICENSE",
    ],
)
def test_vendored_files_ship_their_licence(licence: str) -> None:
    assert (web_root() / licence).is_file()


def test_window_background_matches_the_theme_token() -> None:
    theme = (web_root() / "styles" / "theme.css").read_text(encoding="utf-8")

    match = re.search(r"--bg-base:\s*(#[0-9a-fA-F]{6})", theme)
    assert match is not None
    assert match.group(1).lower() == app.BACKGROUND_COLOR


PAGE_LINK = re.compile(r'(?:href|src)="([^"]+)"')


def page_links() -> list[str]:
    return PAGE_LINK.findall((web_root() / "index.html").read_text(encoding="utf-8"))


def test_the_page_loads_its_stylesheets_and_script() -> None:
    assert page_links() == [
        "styles/theme.css",
        "styles/fonts.css",
        "styles/app.css",
        "js/app.js",
    ]


@pytest.mark.parametrize("link", page_links())
def test_every_page_link_points_to_a_bundled_file(link: str) -> None:
    assert (web_root() / link).is_file()
