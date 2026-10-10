# SPDX-License-Identifier: GPL-3.0-or-later
"""Damaged or hostile files degrade with a message; they never stop the app (production audit).

A file can be cut short by a full disk or a crash, quarantined by an antivirus, half synced, or
edited by hand; an archive can come from anyone.
"""

import gzip
import json
import zipfile
from pathlib import Path

import pytest
from support.snapshots import make_snapshot

from patch_scout.snapshot import SnapshotFormatError
from patch_scout.snapshot.io import dumps
from patch_scout.store import DataFolder, Library, LibraryEntry, SnapshotStore, archive
from patch_scout.store.archive import ArchiveError
from patch_scout.store.settings import SettingsStore


@pytest.fixture
def folder(tmp_path: Path) -> DataFolder:
    data = DataFolder(tmp_path / "PatchScout")
    data.create()
    return data


def _write(folder: DataFolder, capture_id: str, payload: bytes) -> None:
    folder.snapshots.mkdir(parents=True, exist_ok=True)
    (folder.snapshots / f"{capture_id}.snapshot.json.gz").write_bytes(payload)


@pytest.mark.parametrize(
    "payload",
    [
        b"",  # an empty file
        b"\x1f\x8b\x08\x00garbage",  # a gzip header, then nothing usable
        b"not gzip at all",
        gzip.compress(b"\xff\xfe not utf-8"),
        gzip.compress(b"[1, 2, 3]"),
        gzip.compress(json.dumps({"meta": None, "sources": {}, "flags": {}}).encode()),
        gzip.compress(json.dumps({"meta": {}, "sources": [], "flags": {}}).encode()),
    ],
)
def test_a_damaged_snapshot_is_a_format_error(folder: DataFolder, payload: bytes) -> None:
    _write(folder, "abc", payload)
    with pytest.raises(SnapshotFormatError):
        SnapshotStore(folder).load("abc")


def test_a_snapshot_under_another_name_is_a_format_error(folder: DataFolder) -> None:
    _write(folder, "other", gzip.compress(dumps(make_snapshot())))  # its capture_id is "abc"
    with pytest.raises(SnapshotFormatError):
        SnapshotStore(folder).load("other")


@pytest.mark.parametrize("capture_id", [r"..\..\x", "../x", "a:b", "", "x" * 65, "CON."])
def test_a_capture_id_that_is_not_a_plain_name_is_refused(capture_id: str) -> None:
    meta = {"capture_id": capture_id, "captured_at": "2026-10-10T00:00:00Z"}
    with pytest.raises(SnapshotFormatError):
        make_snapshot(meta=meta).capture_id  # noqa: B018  # the property validates


def test_the_library_is_rebuilt_without_a_damaged_snapshot(folder: DataFolder) -> None:
    SnapshotStore(folder).save(make_snapshot())
    _write(folder, "broken", b"not gzip")
    library = Library(folder)
    library.rebuild_from(SnapshotStore(folder))
    assert [entry.capture_id for entry in library.entries()] == ["abc"]


@pytest.mark.parametrize("name", ["settings.json", "library.json"])
def test_undecodable_settings_or_library_fall_back(folder: DataFolder, name: str) -> None:
    (folder.root / name).write_bytes(b"\xff\xfe{\x00")
    assert SettingsStore(folder).load() is not None
    assert Library(folder).entries() == []


def test_an_archive_with_a_hostile_capture_id_is_refused(
    folder: DataFolder, tmp_path: Path
) -> None:
    meta = {"capture_id": r"..\..\evil", "captured_at": "2026-10-10T00:00:00Z"}
    path = tmp_path / "evil.aoe2snap"
    with zipfile.ZipFile(path, "w") as zipped:
        zipped.writestr("manifest.json", json.dumps({"format": 1, "icons": []}))
        zipped.writestr("library-entry.json", json.dumps({"label": "x"}))
        zipped.writestr(
            "snapshot.json.gz",
            gzip.compress(json.dumps({"meta": meta, "sources": {}, "flags": {}}).encode()),
        )
    with pytest.raises(ArchiveError) as caught:
        archive.import_(folder, path)
    assert caught.value.reason == "bad_snapshot"
    assert not any(p.name.startswith("evil") for p in tmp_path.rglob("*") if p != path)


def test_an_archive_with_a_corrupt_member_is_refused(folder: DataFolder, tmp_path: Path) -> None:
    good = tmp_path / "good.aoe2snap"
    SnapshotStore(folder).save(make_snapshot())
    Library(folder).add(LibraryEntry.for_snapshot(make_snapshot()))
    archive.export(folder, "abc", good, tool_version="1", notice="n")
    data = bytearray(good.read_bytes())
    start = data.index(b"library-entry.json") + 40  # inside that member's compressed data
    data[start : start + 8] = b"\x00" * 8
    broken = tmp_path / "broken.aoe2snap"
    broken.write_bytes(bytes(data))
    other = DataFolder(tmp_path / "Other")
    other.create()
    with pytest.raises(ArchiveError):
        archive.import_(other, broken)
