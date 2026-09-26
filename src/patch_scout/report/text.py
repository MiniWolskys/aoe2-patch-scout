# SPDX-License-Identifier: GPL-3.0-or-later
"""Render a change set as plain text (P-13).

For video descriptions, chat and forums: Unicode bullets and indentation, no markup. Every word
comes from the message catalog, so the export follows the app's language (P-20).
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Final

from patch_scout.diff.collapse import MAX_NAMED_CIVS
from patch_scout.diff.model import CATEGORIES, Change, ChangeSet, Scope, Side
from patch_scout.i18n.catalog import Catalog

BULLET: Final = "•"
ARROW: Final = "→"
NOTICE: Final = "!"
INDENT: Final = "  "


@dataclass(frozen=True, slots=True)
class Filters:
    """What the reader chose to include, matching what the comparison shows (P-13)."""

    low_priority: bool = False
    civs: tuple[str, ...] | None = None

    def keeps(self, change: Change) -> bool:
        """Whether one change survives the filters."""
        if change.low_priority and not self.low_priority:
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

    pages: list[tuple[str, str | None]] = [(catalog.text("report.overall"), None)]
    pages += [(civ.name, civ.internal_name) for civ in change_set.civs]
    body: list[str] = []
    for title, internal_name in pages:
        changes = [change for change in change_set.for_civ(internal_name) if chosen.keeps(change)]
        if not changes:
            continue
        body += ["", title.upper()]
        body += _category_lines(changes, catalog)
    if not body:
        body = ["", catalog.text("report.no_changes")]
    return "\n".join(lines + body) + "\n"


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


def _category_lines(changes: Sequence[Change], catalog: Catalog) -> list[str]:
    lines: list[str] = []
    for category in CATEGORIES:
        in_category = [change for change in changes if change.category == category]
        if not in_category:
            continue
        lines.append(f"{INDENT}{catalog.text(f'category.{category}')}")
        lines += [f"{INDENT * 2}{BULLET} {line}" for line in _change_lines(in_category, catalog)]
    return lines


def _change_lines(changes: Iterable[Change], catalog: Catalog) -> list[str]:
    return [line(change, catalog) for change in changes]


def line(change: Change, catalog: Catalog) -> str:
    """One change on one line."""
    parts = [_entity(change, catalog)]
    if change.field is not None:
        parts.append(catalog.text(change.field.key, **change.field.args))
    values = _values(change, catalog)
    if values:
        parts.append(values)
    scope = scope_text(change.scope, catalog)
    if scope:
        parts.append(scope)
    return " · ".join(part for part in parts if part)


def _entity(change: Change, catalog: Catalog) -> str:
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
    civs = _civ_list(scope.civs, catalog)
    if scope.kind == "all_except":
        return catalog.text("scope.all_except", civs=civs)
    return catalog.text("scope.some", civs=civs)


def _civ_list(civs: Sequence[str], catalog: Catalog) -> str:
    if len(civs) <= MAX_NAMED_CIVS:
        return ", ".join(civs)
    named = ", ".join(civs[:MAX_NAMED_CIVS])
    return catalog.text("scope.and_more", civs=named, count=len(civs) - MAX_NAMED_CIVS)
