# SPDX-License-Identifier: GPL-3.0-or-later
"""Write the patch notes as light Markdown (D-51, P-13 amended).

"Light": `-` bullets and plain heading lines, no `#` or `**`. It reads as plain text in a video
description and as lists on Reddit and Discord. Nested bullets are indented four spaces, which
both CommonMark and old Reddit read as a nested list. Names are not escaped: a backslash would
show in plain text, and game names don't hold the Markdown that matters in a list item.
"""

from typing import Final

from patch_scout.report.notes.model import Item, Notes

BULLET: Final = "- "
INDENT: Final = "    "


def render(notes: Notes) -> str:
    """The whole notes as text, ending with a newline."""
    lines: list[str] = [notes.title, notes.disclaimer]
    if notes.notices:
        lines += ["", *(f"! {notice}" for notice in notes.notices)]
    for section in notes.sections:
        lines += ["", section.title.upper()]
        for group in section.groups:
            lines += ["", group.title, ""]
            for item in group.items:
                lines += _item(item, 0)
    if notes.empty:
        lines += ["", notes.empty]
    if notes.closing:
        lines += ["", notes.closing]
    return "\n".join(lines) + "\n"


def _item(item: Item, depth: int) -> list[str]:
    lines = [f"{INDENT * depth}{BULLET}{item.text}"]
    for child in item.children:
        lines += _item(child, depth + 1)
    return lines
