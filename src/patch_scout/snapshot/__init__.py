# SPDX-License-Identifier: GPL-3.0-or-later
"""The snapshot schema and its file format."""

from patch_scout.snapshot.io import SUFFIX, dumps, loads, read, write
from patch_scout.snapshot.schema import (
    SCHEMA_VERSION,
    JsonObject,
    JsonValue,
    Snapshot,
    SnapshotFormatError,
)

__all__ = [
    "SCHEMA_VERSION",
    "SUFFIX",
    "JsonObject",
    "JsonValue",
    "Snapshot",
    "SnapshotFormatError",
    "dumps",
    "loads",
    "read",
    "write",
]
