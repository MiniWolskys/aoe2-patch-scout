# SPDX-License-Identifier: GPL-3.0-or-later
"""A small reader for Valve's KeyValues text files (`libraryfolders.vdf`, `appmanifest_*.acf`).

Only what Patch Scout needs: quoted keys and values, nested blocks, `//` comments. Anything it
can't make sense of is skipped rather than raising, because these files belong to Steam.
"""

import re
from typing import Final

type Block = dict[str, "str | Block"]

_TOKEN: Final = re.compile(r'"((?:[^"\\]|\\.)*)"|([{}])|//[^\n]*')
_ESCAPE: Final = re.compile(r"\\(.)")


def parse(text: str) -> Block:
    """Parse a KeyValues document into nested dictionaries of strings."""
    root: Block = {}
    stack: list[Block] = [root]
    pending: str | None = None
    for match in _TOKEN.finditer(text):
        quoted, brace = match.group(1), match.group(2)
        if brace == "{":
            block: Block = {}
            if pending is not None:
                stack[-1][pending] = block
                pending = None
            stack.append(block)
        elif brace == "}":
            if len(stack) > 1:
                stack.pop()
            pending = None
        elif quoted is not None:
            value = _ESCAPE.sub(r"\1", quoted)
            if pending is None:
                pending = value
            else:
                stack[-1][pending] = value
                pending = None
    return root


def block(source: Block, *keys: str) -> Block:
    """Follow nested keys case-insensitively, returning an empty block when the path is absent."""
    current = source
    for key in keys:
        found = _lookup(current, key)
        if not isinstance(found, dict):
            return {}
        current = found
    return current


def string(source: Block, key: str) -> str | None:
    """Return a string value looked up case-insensitively, or None."""
    value = _lookup(source, key)
    return value if isinstance(value, str) else None


def _lookup(source: Block, key: str) -> "str | Block | None":
    if key in source:
        return source[key]
    lowered = key.casefold()
    for name, value in source.items():
        if name.casefold() == lowered:
            return value
    return None
