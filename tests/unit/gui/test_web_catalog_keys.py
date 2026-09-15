# SPDX-License-Identifier: GPL-3.0-or-later
import re

import pytest

from patch_scout.gui.web_files import web_root
from patch_scout.i18n.catalog import load_catalog

TEXT_KEY = re.compile(r'data-i18n="([^"]+)"')
ATTRIBUTE_KEYS = re.compile(r'data-i18n-attr="([^"]+)"')
T_CALL = re.compile(r"""\bt\(\s*["']([^"']+)["']""")


def referenced_keys() -> list[str]:
    html = (web_root() / "index.html").read_text(encoding="utf-8")
    keys = set(TEXT_KEY.findall(html))
    for pairs in ATTRIBUTE_KEYS.findall(html):
        keys.update(pair.split(":", 1)[1] for pair in pairs.split())
    for script in (web_root() / "js").glob("*.js"):
        keys.update(T_CALL.findall(script.read_text(encoding="utf-8")))
    return sorted(keys)


def test_the_page_takes_its_text_from_the_catalog() -> None:
    assert {"first_launch.title", "version_list.collapse"} <= set(referenced_keys())


@pytest.mark.parametrize("key", referenced_keys())
def test_every_key_the_page_uses_is_in_the_english_catalog(key: str) -> None:
    assert key in load_catalog("en").messages()
