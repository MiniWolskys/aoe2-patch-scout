# SPDX-License-Identifier: GPL-3.0-or-later
"""Render a change set as plain text (P-13).

For video descriptions, chat and forums: Unicode bullets and indentation, no markup. Every word
comes from the message catalog, so the export follows the app's language (P-20).
"""

from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Final

from patch_scout.diff.collapse import MAX_NAMED_CIVS
from patch_scout.diff.model import CATEGORIES, Change, ChangeSet, Entry, Scope, Side
from patch_scout.i18n.catalog import Catalog

BULLET: Final = "•"
DASH: Final = "-"
ARROW: Final = "→"
NOTICE: Final = "!"
INDENT: Final = "  "


@dataclass(frozen=True, slots=True)
class Filters:
    """What the reader chose to include, matching what the comparison shows (P-13)."""

    low_priority: bool = False
    civs: tuple[str, ...] | None = None
    unnamed: bool = False

    def keeps(self, change: Change | Entry) -> bool:
        """Whether one change, or one entry, survives the filters."""
        if change.low_priority and not self.low_priority:
            return False
        if not change.entity.named and not self.unnamed:
            return False
        if self.civs is None:
            return True
        return change.civ is None or change.civ in self.civs


def render(change_set: ChangeSet, catalog: Catalog, filters: Filters | None = None) -> str:
    """Return the whole comparison as plain text."""
    chosen = filters or Filters()
    lines: list[str] = [catalog.text("report.title"), ""]
    lines += _header(change_set, catalog)
    lines += _notices(change_set, catalog)
    if change_set.identical:
        lines += ["", catalog.text("report.identical")]
        return "\n".join(lines) + "\n"

    body: list[str] = []
    for title, entries in pages(change_set, catalog, chosen):
        body += ["", title.upper()]
        body += _category_lines(entries, catalog)
    if not body:
        body = ["", catalog.text("report.no_changes")]
    return "\n".join(lines + body) + "\n"


def pages(
    change_set: ChangeSet, catalog: Catalog, filters: Filters
) -> list[tuple[str, list[Entry]]]:
    """The sections an export prints, each with its entries; empty sections are left out.

    Overall, then "Several civilizations", then each civ. The app shows a change shared by a few
    civs on each of their pages (D-44); an export prints it once, in "Several civilizations",
    unless it is limited to some civs, where each civ's section keeps everything it has.
    """
    kept = [entry for entry in change_set.entries if filters.keeps(entry)]
    once = filters.civs is None
    sections: list[tuple[str, list[Entry]]] = [
        (catalog.text("report.overall"), [entry for entry in kept if entry.civ is None])
    ]
    if once:
        seen: set[str] = set()
        several: list[Entry] = []
        for entry in kept:
            key = _shared_key(entry)
            if key is not None and key not in seen:
                seen.add(key)
                several.append(entry)
        sections.append((catalog.text("report.several_civs"), several))
    for civ in change_set.civs:
        mine = [
            entry
            for entry in kept
            if entry.civ == civ.internal_name and not (once and _shared_key(entry) is not None)
        ]
        sections.append((civ.name, mine))
    return [(title, entries) for title, entries in sections if entries]


def _shared_key(entry: Entry) -> str | None:
    """The same key for each civ's copy of an entry shared by several civs; None otherwise."""
    if entry.civ is None or entry.scope.kind != "some" or len(entry.scope.civs) < 2:
        return None
    return repr(
        (replace(entry, civ=None, changes=()), [replace(c, civ=None) for c in entry.changes])
    )


def _header(change_set: ChangeSet, catalog: Catalog) -> list[str]:
    return [
        catalog.text("report.side_old", side=_side(change_set.old, catalog)),
        catalog.text("report.side_new", side=_side(change_set.new, catalog)),
    ]


def _side(side: Side, catalog: Catalog) -> str:
    parts = [side.label]
    if side.game_build:
        parts.append(side.game_build)
    parts.append(side.captured_at)
    if side.prerelease:
        parts.append(catalog.text("report.prerelease"))
    if not side.stats_available:
        parts.append(catalog.text("report.no_stats"))
    return " · ".join(parts)


def _notices(change_set: ChangeSet, catalog: Catalog) -> list[str]:
    if not change_set.notices:
        return []
    return [""] + [
        f"{NOTICE} {catalog.text(notice.message.key, **notice.message.args)}"
        for notice in change_set.notices
    ]


def _category_lines(entries: Sequence[Entry], catalog: Catalog) -> list[str]:
    lines: list[str] = []
    for category in CATEGORIES:
        in_category = [entry for entry in entries if entry.category == category]
        if not in_category:
            continue
        lines.append(f"{INDENT}{catalog.text(f'category.{category}')}")
        for entry in in_category:
            lines += _entry_lines(entry, catalog)
    return lines


def _entry_lines(entry: Entry, catalog: Catalog) -> list[str]:
    """One entry: a single line for a single change, else a header and one line per field."""
    if len(entry.changes) == 1 and not entry.hidden:
        return [f"{INDENT * 2}{BULLET} {line(entry.changes[0], catalog)}"]
    head = [_entity(entry, catalog), scope_text(entry.scope, catalog)]
    lines = [f"{INDENT * 2}{BULLET} " + " · ".join(part for part in head if part)]
    for change in entry.changes:
        values = change.new or "" if entry.kind == "added" else _values(change, catalog)
        parts = [field_text(change, catalog), values]
        lines.append(f"{INDENT * 4}{DASH} " + " · ".join(part for part in parts if part))
    if entry.hidden:
        lines.append(f"{INDENT * 4}{DASH} " + catalog.text("report.hidden", count=entry.hidden))
    return lines


def field_text(change: Change, catalog: Catalog) -> str:
    """A change's field label, resolving a nested field such as "Projectile: {field}"."""
    return catalog.message(change.field.key, change.field.args) if change.field else ""


def line(change: Change, catalog: Catalog) -> str:
    """One change on one line."""
    parts = [_entity(change, catalog), field_text(change, catalog)]
    values = _values(change, catalog)
    if values:
        parts.append(values)
    scope = scope_text(change.scope, catalog)
    if scope:
        parts.append(scope)
    return " · ".join(part for part in parts if part)


def _entity(change: Change | Entry, catalog: Catalog) -> str:
    entity = change.entity
    name = entity.name
    kind = catalog.text(f"kind.{change.kind}") if change.kind in ("added", "removed") else ""
    where = entity.where
    label = f"{kind} {name}".strip() if kind else name
    return f"{label} ({where})" if where else label


def _values(change: Change, catalog: Catalog) -> str:
    if change.words:
        return "".join(_word(word.kind, word.text) for word in change.words).strip()
    if change.old and change.new:
        return f"{change.old} {ARROW} {change.new}"
    lone = change.new or change.old or ""
    if not lone or change.kind in ("added", "removed"):
        # "Added: <entity>" already says which way it went.
        return lone
    if change.new:
        return catalog.text("report.value_added", value=change.new)
    return catalog.text("report.value_removed", value=lone)


def _word(kind: str, text: str) -> str:
    if kind == "removed":
        return f"[-{text}-]"
    if kind == "added":
        return f"[+{text}+]"
    return text


def scope_text(scope: Scope, catalog: Catalog) -> str:
    """The civ-list phrase after a change, e.g. "(all civs except Franks, Persians)"."""
    if scope.kind == "global":
        return ""
    if scope.kind == "all":
        return catalog.text("scope.all")
    if scope.kind == "having":
        return catalog.text("scope.having", count=scope.count)
    civs = _civ_list(scope.civs, catalog)
    if scope.kind == "all_except":
        return catalog.text("scope.all_except", civs=civs)
    if scope.kind == "having_except":
        return catalog.text("scope.having_except", count=scope.count, civs=civs)
    return catalog.text("scope.some", civs=civs)


def _civ_list(civs: Sequence[str], catalog: Catalog) -> str:
    if len(civs) <= MAX_NAMED_CIVS:
        return ", ".join(civs)
    named = ", ".join(civs[:MAX_NAMED_CIVS])
    return catalog.text("scope.and_more", civs=named, count=len(civs) - MAX_NAMED_CIVS)
