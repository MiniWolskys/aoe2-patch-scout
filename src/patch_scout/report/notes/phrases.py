# SPDX-License-Identifier: GPL-3.0-or-later
"""The words of the patch notes: labels, clauses and lists, all from the catalog (P-20).

"Onager melee attack increased from 50 → 55": the subject, the field label with its first
letter lowered (the catalog decides, `notes.field_case`), and a clause built from the two values.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from patch_scout.diff.model import Message
from patch_scout.i18n.catalog import Catalog
from patch_scout.report.notes.values import direction, shown
from patch_scout.snapshot import JsonValue

_PROJECTILE = "field.projectile"


@dataclass(frozen=True, slots=True)
class Also:
    """The second subject of a pair, "(Elite) Throwing Axeman", when its values differ."""

    prefix: str
    old: str
    new: str


class Words:
    """The catalog, with the few rules the notes add on top of it."""

    def __init__(self, catalog: Catalog) -> None:
        self._catalog = catalog
        self._lower = catalog.text("notes.field_case") == "lower"

    def text(self, key: str, **values: object) -> str:
        """A catalog message."""
        return self._catalog.text(key, **values)

    def message(self, message: Message | Mapping[str, JsonValue]) -> str:
        """A message from the change set, nested messages resolved."""
        if isinstance(message, Message):
            return self._catalog.message(message.key, message.args)
        key, args = message.get("key"), message.get("args")
        return self._catalog.message(str(key), args if isinstance(args, dict) else {})

    def value(self, value: JsonValue) -> str:
        """An argument that is either a plain value or a nested message."""
        if isinstance(value, dict) and "key" in value:
            return self.message(value)
        return "" if value is None else str(value)

    def lowered(self, label: str) -> str:
        """A label as it reads mid-sentence: "Line of sight" → "line of sight", "HP" stays."""
        if not self._lower or len(label) < 2 or label[1].isupper():
            return label
        return label[0].lower() + label[1:]

    def attribute(self, value: JsonValue) -> str:
        """An effect's attribute as it reads mid-sentence.

        A label of the catalog's is lowered like a field ("pierce attack"); a name derived from
        `Constants.xs` is in title case, so it is lowered whole ("Line Of Sight" → "line of
        sight").
        """
        if isinstance(value, dict):
            return self.lowered(self.value(value))
        text = self.value(value)
        return text.lower() if self._lower else text

    def field(self, field: Message) -> str:
        """A field label as it reads after its subject: "Onager melee attack"."""
        if field.key == _PROJECTILE:
            inner = field.args.get("field")
            return self.text("notes.projectile_field", field=self.lowered(self.value(inner)))
        return self.lowered(self.message(field))

    def clause(self, label: str, old: str, new: str, also: Also | None = None) -> str:
        """One field's change: "line of sight increased from 3 → 5", with a pair's values."""
        if old and new:
            way = direction(old, new)
            if also is not None and also.old and also.new and direction(also.old, also.new) != way:
                way = None  # the two subjects moved differently: say "changed" for both
            key = {"up": "notes.clause.up", "down": "notes.clause.down"}.get(
                way or "", "notes.clause.changed"
            )
            text = self.text(key, field=label, old=shown(old), new=shown(new))
        elif new:
            text = self.text("notes.clause.added", field=label, new=shown(new))
        elif old:
            text = self.text("notes.clause.removed", field=label, old=shown(old))
        else:
            text = label
        if also is None:
            return text
        if also.old and also.new:
            return text + self.text(
                "notes.also", prefix=also.prefix, old=shown(also.old), new=shown(also.new)
            )
        return text + self.text("notes.also_value", prefix=also.prefix, value=shown(also.new))

    def listed(self, names: Sequence[str]) -> str:
        """Names as a list: "Battering Ram, Capped Ram and Siege Ram"."""
        if len(names) <= 1:
            return "".join(names)
        separator = self.text("notes.list_separator")
        return self.text("notes.and", first=separator.join(names[:-1]), last=names[-1])

    def paired(self, prefix: str, name: str) -> str:
        """Two subjects as one: "(Elite) Throwing Axeman"."""
        return self.text("notes.paired", prefix=prefix, name=name)
