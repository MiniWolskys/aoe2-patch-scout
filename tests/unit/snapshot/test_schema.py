# SPDX-License-Identifier: GPL-3.0-or-later
"""The snapshot schema: what a snapshot must hold, and what it refuses."""

import pytest
from support.snapshots import make_snapshot

from patch_scout.snapshot.schema import SCHEMA_VERSION, Snapshot, SnapshotFormatError


def test_a_new_snapshot_carries_the_current_schema_version() -> None:
    assert make_snapshot().schema_version == SCHEMA_VERSION


def test_capture_id_and_build_come_from_meta() -> None:
    snapshot = make_snapshot()
    assert snapshot.capture_id == "abc"
    assert snapshot.game_build == "1.2"
    assert snapshot.captured_at == "2026-09-16T10:00:00Z"


def test_an_unreadable_game_build_is_none() -> None:
    assert make_snapshot(meta={"capture_id": "a", "captured_at": "t"}).game_build is None


def test_a_missing_capture_id_is_refused() -> None:
    with pytest.raises(SnapshotFormatError, match="capture_id"):
        _ = make_snapshot(meta={}).capture_id


def test_stats_available_reads_the_flag() -> None:
    assert make_snapshot(flags={"stats_available": True}).stats_available is True
    assert make_snapshot(flags={}).stats_available is False


def test_to_json_and_from_json_round_trip() -> None:
    snapshot = make_snapshot(civs=[{"internal_name": "Franks"}])
    assert Snapshot.from_json(snapshot.to_json()) == snapshot


def test_from_json_refuses_a_non_object() -> None:
    with pytest.raises(SnapshotFormatError, match="JSON object"):
        Snapshot.from_json([1, 2, 3])


def test_from_json_refuses_unknown_sections() -> None:
    with pytest.raises(SnapshotFormatError, match="mystery"):
        Snapshot.from_json({"meta": {}, "sources": {}, "flags": {}, "mystery": 1})


def test_from_json_refuses_missing_sections() -> None:
    with pytest.raises(SnapshotFormatError, match="flags, sources"):
        Snapshot.from_json({"meta": {}})
