# SPDX-License-Identifier: GPL-3.0-or-later
"""The version list and the identical-input check read a small index, not whole snapshots.

A snapshot is ~164 MB in memory: listing 20 of them used to need gigabytes and seconds of blank
window (production audit).
"""

import json
from pathlib import Path

import pytest
from support.snapshots import make_snapshot

from patch_scout.gui.api import Api
from patch_scout.i18n.catalog import load_catalog
from patch_scout.snapshot import Snapshot
from patch_scout.store import DataFolder, SnapshotStore
from patch_scout.store.snapshots import SnapshotIndex


@pytest.fixture
def folder(tmp_path: Path) -> DataFolder:
    data = DataFolder(tmp_path / "PatchScout")
    data.create()
    return data


def _snapshot(capture_id: str, build: str) -> Snapshot:
    return make_snapshot(
        meta={
            "capture_id": capture_id,
            "captured_at": "2026-10-10T10:00:00Z",
            "game_build": build,
            "label_at_capture": f"Build {build}",
            "prerelease_at_capture": False,
        },
        sources={"resources/_common/dat/civilizations.json": {"sha256": "x", "size": 1}},
        flags={"stats_available": True, "format_verified": True},
    )


def test_saving_a_snapshot_writes_its_index(folder: DataFolder) -> None:
    store = SnapshotStore(folder)
    store.save(_snapshot("abc", "1.2"))
    index = store.index("abc")
    assert (index.game_build, index.stats_available, index.label_at_capture) == (
        "1.2",
        True,
        "Build 1.2",
    )
    assert index.sources == {"resources/_common/dat/civilizations.json": {"sha256": "x", "size": 1}}


def test_an_index_is_rebuilt_when_missing_or_damaged(folder: DataFolder) -> None:
    store = SnapshotStore(folder)
    store.save(_snapshot("abc", "1.2"))
    path = folder.snapshots / "abc.index.json"
    path.unlink()
    assert store.index("abc").game_build == "1.2"
    assert path.is_file()
    path.write_text("{broken", encoding="utf-8")
    assert store.index("abc").game_build == "1.2"
    assert json.loads(path.read_text(encoding="utf-8"))["game_build"] == "1.2"


def test_deleting_a_version_removes_its_index(folder: DataFolder) -> None:
    store = SnapshotStore(folder)
    store.save(_snapshot("abc", "1.2"))
    store.delete("abc")
    assert list(folder.snapshots.iterdir()) == []


def test_the_version_list_never_loads_a_snapshot(
    folder: DataFolder, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = SnapshotStore(folder)
    for index in range(5):
        store.save(_snapshot(f"v{index}", f"1.{index}"))
    api = Api(load_catalog("en"), "en", "1.2.3", folder)

    def refuse(self: SnapshotStore, capture_id: str) -> Snapshot:
        raise AssertionError(f"loaded {capture_id}")

    monkeypatch.setattr(SnapshotStore, "load", refuse)
    versions = api.get_startup()["versions"]
    assert isinstance(versions, list)
    assert [v["game_build"] for v in versions if isinstance(v, dict)] == [
        "1.4",
        "1.3",
        "1.2",
        "1.1",
        "1.0",
    ]


def test_at_most_two_snapshots_stay_in_memory(folder: DataFolder) -> None:
    store = SnapshotStore(folder)
    for index in range(4):
        store.save(_snapshot(f"v{index}", f"1.{index}"))
    api = Api(load_catalog("en"), "en", "1.2.3", folder)
    for index in range(4):
        api.get_version(f"v{index}")
    assert len(api._loaded) <= 2


def test_an_index_from_another_snapshot_is_not_trusted(folder: DataFolder) -> None:
    store = SnapshotStore(folder)
    store.save(_snapshot("abc", "1.2"))
    path = folder.snapshots / "abc.index.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["capture_id"] = "other"
    path.write_text(json.dumps(data), encoding="utf-8")
    assert store.index("abc").capture_id == "abc"
    assert SnapshotIndex.from_json(data) is not None
