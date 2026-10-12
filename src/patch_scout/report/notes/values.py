# SPDX-License-Identifier: GPL-3.0-or-later
"""A change's values as the patch notes write them (diff-rules.md, Patch notes).

The change set holds values as the comparison shows them: plain numbers ("1.35"), values an
effect sets ("=15"), adds ("+1") or multiplies by ("x1.2"), and words. The notes drop the "=",
write multipliers as percentages, as the official notes do ("+20% HP"), and say whether a number
went up or down only when both sides are numbers of the same form.
"""

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Final, Literal

from patch_scout.diff.effects import TIMES

type Form = Literal["number", "set", "times"]
type Direction = Literal["up", "down"]

# The forms `diff.values` and `diff.effects` write: an optional "=" or times sign, then a decimal
# number with an optional sign. Nothing else is read as a number.
_NUMBER: Final = re.compile(rf"^(?P<mark>[={TIMES}]?)(?P<number>[+-]?\d+(?:\.\d+)?)$")
_FORMS: Final[dict[str, Form]] = {"": "number", "=": "set", TIMES: "times"}
_HUNDRED: Final = Decimal(100)


@dataclass(frozen=True, slots=True)
class _Parsed:
    form: Form
    number: Decimal
    text: str  # the number as the change set wrote it, sign included


def _parse(value: str) -> _Parsed | None:
    match = _NUMBER.match(value.strip())
    if match is None:
        return None
    try:
        number = Decimal(match["number"])
    except InvalidOperation:  # the pattern only lets decimal numbers through
        return None
    return _Parsed(_FORMS[match["mark"]], number, match["number"])


def shown(value: str) -> str:
    """The value as the notes write it: `=15` → `15`, `x0.6` → `-40%`; anything else as it is."""
    parsed = _parse(value)
    if parsed is None:
        return value
    if parsed.form == "times":
        # A factor of zero or below is no change in percent anyone would write ("-200%").
        return _percent(parsed.number) if parsed.number > 0 else value
    return parsed.text


def direction(old: str, new: str) -> Direction | None:
    """Whether a number went up or down; None when the two can't be compared, or are equal."""
    before, after = _parse(old), _parse(new)
    if before is None or after is None or before.form != after.form:
        return None
    if after.number > before.number:
        return "up"
    if after.number < before.number:
        return "down"
    return None


def _percent(factor: Decimal) -> str:
    """A multiplier as a change in percent, exactly: x1.0835 is +8.35%, never +8.350000001%."""
    change = (factor - 1) * _HUNDRED
    text = format(change.normalize(), "f")
    return f"{text}%" if change < 0 else f"+{text}%"
