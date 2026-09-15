# SPDX-License-Identifier: GPL-3.0-or-later
import re
from string import Formatter

import pytest

from patch_scout.i18n.catalog import load_catalog

MESSAGES = load_catalog("en").messages()


@pytest.mark.parametrize("key", sorted(MESSAGES))
def test_placeholders_are_plain_names_so_js_can_format_them(key: str) -> None:
    for _, field, spec, conversion in Formatter().parse(MESSAGES[key]):
        if field is not None:
            assert re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", field), f"{key}: {{{field}}}"
            assert (spec, conversion) == ("", None), f"{key}: {{{field}}}"
