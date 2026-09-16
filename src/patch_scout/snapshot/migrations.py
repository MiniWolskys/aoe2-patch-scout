# SPDX-License-Identifier: GPL-3.0-or-later
"""Bring a snapshot up to the current schema version in memory (P-15).

Until v1.0 ships, schema v1 changes without migrations. From v1.0 on, each bump adds a step
here and every step is covered by a test with a snapshot written by the older version.
"""

from collections.abc import Callable
from dataclasses import replace

from patch_scout.errors import PatchScoutError
from patch_scout.snapshot.schema import SCHEMA_VERSION, Snapshot


class UnsupportedSchemaError(PatchScoutError):
    """The snapshot was written by a newer version of the app."""


# version -> step that returns the snapshot at version + 1. Empty while v1 is the only version.
STEPS: dict[int, Callable[[Snapshot], Snapshot]] = {}


def migrate(snapshot: Snapshot) -> Snapshot:
    """Return the snapshot at the current schema version."""
    version = snapshot.schema_version
    if version > SCHEMA_VERSION:
        raise UnsupportedSchemaError(
            f"snapshot schema v{version} needs a newer Patch Scout"
            f" (this one reads v{SCHEMA_VERSION})"
        )
    while version < SCHEMA_VERSION:
        step = STEPS.get(version)
        if step is None:
            raise UnsupportedSchemaError(f"no migration from snapshot schema v{version}")
        snapshot = step(snapshot)
        version += 1
    return replace(snapshot, schema_version=SCHEMA_VERSION)
