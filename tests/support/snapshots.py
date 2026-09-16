# SPDX-License-Identifier: GPL-3.0-or-later
"""Small snapshot builders the unit tests share."""

from patch_scout.snapshot.schema import JsonObject, Snapshot


def make_snapshot(**overrides: object) -> Snapshot:
    """A minimal valid snapshot; any section can be replaced by keyword."""
    meta: JsonObject = {
        "capture_id": "abc",
        "captured_at": "2026-09-16T10:00:00Z",
        "game_build": "1.2",
    }
    sections: dict[str, object] = {"meta": meta, "sources": {}, "flags": {"stats_available": False}}
    sections.update(overrides)
    return Snapshot(**sections)  # type: ignore[arg-type]  # tests build plain JSON sections
