# SPDX-License-Identifier: GPL-3.0-or-later
"""Snapshot files: deterministic bytes, atomic writes, and a readable round trip."""

from dataclasses import replace
from pathlib import Path

import pytest
from support.snapshots import make_snapshot

from patch_scout.snapshot import dumps, loads, read, write
from patch_scout.snapshot.migrations import UnsupportedSchemaError, migrate
from patch_scout.snapshot.schema import SnapshotFormatError


def test_serializing_twice_gives_the_same_bytes() -> None:
    snapshot = make_snapshot(civs=[{"b": 1, "a": 2}])
    assert dumps(snapshot) == dumps(make_snapshot(civs=[{"a": 2, "b": 1}]))


def test_a_snapshot_survives_the_round_trip(tmp_path: Path) -> None:
    snapshot = make_snapshot(strings={"tables": {"en": {"1": "Archer"}}}, stats={"units": {}})
    path = tmp_path / "one.snapshot.json.gz"
    write(path, snapshot)
    assert read(path) == snapshot


def test_writing_the_same_snapshot_twice_gives_identical_files(tmp_path: Path) -> None:
    snapshot = make_snapshot()
    write(tmp_path / "a.gz", snapshot)
    write(tmp_path / "b.gz", snapshot)
    assert (tmp_path / "a.gz").read_bytes() == (tmp_path / "b.gz").read_bytes()


def test_writing_leaves_no_partial_file_behind(tmp_path: Path) -> None:
    write(tmp_path / "one.snapshot.json.gz", make_snapshot())
    assert [path.name for path in tmp_path.iterdir()] == ["one.snapshot.json.gz"]


def test_unreadable_bytes_are_refused() -> None:
    with pytest.raises(SnapshotFormatError):
        loads(b"not json")


def test_a_newer_schema_is_refused() -> None:
    with pytest.raises(UnsupportedSchemaError, match="newer Patch Scout"):
        migrate(replace(make_snapshot(), schema_version=99))


def test_a_schema_without_a_migration_is_refused() -> None:
    with pytest.raises(UnsupportedSchemaError, match="no migration"):
        migrate(replace(make_snapshot(), schema_version=0))
