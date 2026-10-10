# SPDX-License-Identifier: GPL-3.0-or-later
"""The game's tooltip template, as styled lines.

A tech tree node's help string is the game's own tooltip: markup (`<b>`, `<i>`, `<GREY>`,
`<DEFAULT>`), the two-character line break, and placeholders for its cost and stats. On
101.103.54800.0 these are the only tags the 636 tech tree help strings use; any other tag is
kept as text.
"""

import re
from dataclasses import dataclass
from typing import Final, Literal

STATS: Final = ("hp", "attack", "armor", "piercearmor", "range", "garrison")
_LINE_BREAK: Final = r"\n"
_STYLE_TAGS: Final = frozenset({"b", "/b", "i", "/i", "GREY", "DEFAULT"})
_TAG: Final = re.compile(r"<(/?[A-Za-z_]+(?:=([A-Za-z]+),(\d+))?)>")

type RunKind = Literal["text", "stat", "cost", "static_cost"]


@dataclass(frozen=True, slots=True)
class Run:
    """A piece of a line: styled text, a stat, the cost, or a fixed cost."""

    kind: RunKind
    text: str = ""
    bold: bool = False
    italic: bool = False
    grey: bool = False
    stat: str | None = None
    resource: str | None = None
    amount: int | None = None

    def to_json(self) -> dict[str, object]:
        """The form the page draws."""
        return {
            "kind": self.kind,
            "text": self.text,
            "bold": self.bold,
            "italic": self.italic,
            "grey": self.grey,
            "stat": self.stat,
            "resource": self.resource,
            "amount": self.amount,
        }


type Line = tuple[Run, ...]


def parse(template: str) -> list[Line]:
    """The template's lines. A style carries over to the next line, as in the game."""
    if not template:
        return []
    style = {"bold": False, "italic": False, "grey": False}
    lines: list[Line] = []
    for source in template.split(_LINE_BREAK):
        runs: list[Run] = []
        position = 0
        for match in _TAG.finditer(source):
            tag = match.group(1)
            special = _special(tag, match)
            if special is None and tag not in _STYLE_TAGS:
                continue  # an unknown tag stays in the text
            _text(runs, source[position : match.start()], style)
            position = match.end()
            if special is not None:
                runs.append(special)
            else:
                _restyle(style, tag)
        _text(runs, source[position:], style)
        lines.append(tuple(runs))
    return lines


def _special(tag: str, match: re.Match[str]) -> Run | None:
    if tag == "cost":
        return Run("cost")
    if tag in STATS:
        return Run("stat", stat=tag)
    if tag.startswith("static_cost=") and match.group(2) is not None:
        return Run("static_cost", resource=match.group(2).lower(), amount=int(match.group(3)))
    return None


def _restyle(style: dict[str, bool], tag: str) -> None:
    # The game toggles bold and italic with the same tag ("<b>Archer<b>").
    if tag in ("b", "i"):
        key = "bold" if tag == "b" else "italic"
        style[key] = not style[key]
    elif tag in ("/b", "/i"):
        style["bold" if tag == "/b" else "italic"] = False
    else:
        style["grey"] = tag == "GREY"


def _text(runs: list[Run], text: str, style: dict[str, bool]) -> None:
    if not text:
        return
    if runs and runs[-1].kind == "text" and _same_style(runs[-1], style):
        last = runs[-1]
        runs[-1] = Run("text", last.text + text, last.bold, last.italic, last.grey)
        return
    runs.append(Run("text", text, style["bold"], style["italic"], style["grey"]))


def _same_style(run: Run, style: dict[str, bool]) -> bool:
    return (run.bold, run.italic, run.grey) == (style["bold"], style["italic"], style["grey"])
