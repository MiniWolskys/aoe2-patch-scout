# SPDX-License-Identifier: GPL-3.0-or-later
"""Turn the game's raw values into words, for what readers see (diff-rules.md, Values).

The change set keeps the game's own values, e.g. a tech tree node status `ResearchRequired`, so
it stays raw data. Every renderer, the app included, shows the words from the catalog instead.
"""

from dataclasses import replace

from patch_scout.diff.model import Change, ChangeSet
from patch_scout.i18n.catalog import Catalog

# Fields whose values are game keywords with a catalog word each: `status.<value>`.
_KEYWORD_FIELDS = frozenset({"field.node_status"})


def present(change_set: ChangeSet, catalog: Catalog) -> ChangeSet:
    """The change set with keyword values in words; entries point at the reworded changes."""
    words = catalog.messages()
    reworded: dict[int, Change] = {}
    for change in change_set.changes:
        if change.field is None or change.field.key not in _KEYWORD_FIELDS:
            continue
        reworded[id(change)] = replace(
            change,
            old=_word(change.old, words),
            new=_word(change.new, words),
        )
    if not reworded:
        return change_set
    changes = tuple(reworded.get(id(change), change) for change in change_set.changes)
    entries = tuple(
        replace(entry, changes=tuple(reworded.get(id(c), c) for c in entry.changes))
        for entry in change_set.entries
    )
    return replace(change_set, changes=changes, entries=entries)


def _word(value: str | None, words: dict[str, str]) -> str | None:
    if not value:
        return value
    return words.get(f"status.{value}", value)
