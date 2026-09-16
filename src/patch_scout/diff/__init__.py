# SPDX-License-Identifier: GPL-3.0-or-later
"""Compare two snapshots: a pure function from two snapshots to a change set."""

from patch_scout.diff.engine import Options, SideInfo, compare, order
from patch_scout.diff.model import (
    CATEGORIES,
    LOW_PRIORITY,
    Change,
    ChangeSet,
    CivRef,
    Entity,
    Message,
    Notice,
    Scope,
    Side,
    WordDiff,
)

__all__ = [
    "CATEGORIES",
    "LOW_PRIORITY",
    "Change",
    "ChangeSet",
    "CivRef",
    "Entity",
    "Message",
    "Notice",
    "Options",
    "Scope",
    "Side",
    "SideInfo",
    "WordDiff",
    "compare",
    "order",
]
