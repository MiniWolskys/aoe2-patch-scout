# SPDX-License-Identifier: GPL-3.0-or-later
"""Version archives: one exported snapshot with its icons, and the baseline pack (P-21).

An archive may come from anyone, so importing one trusts nothing in it.
"""

import io
import json
import zipfile
from pathlib import Path

import pytest
from PIL import Image
from support.snapshots import make_snapshot

from patch_scout.snapshot import Snapshot
from patch_scout.store import DataFolder, IconStore, Library, LibraryEntry, SnapshotStore, archive
from patch_scout.store.archive import ArchiveError

CREST = "c" * 64
NOTICE = "Game content is (c) Microsoft."


@pytest.fixture
def folder(tmp_path: Path) -> DataFolder:
    data = DataFolder(tmp_path / "Source")
    data.create()
    return data


@pytest.fixture
def target(tmp_path: Path) -> DataFolder:
    data = DataFolder(tmp_path / "Target")
    data.create()
    return data


def _snapshot(capture_id: str = "abc123") -> Snapshot:
    civ = {"internal_name": "Alpha", "crest_icon": {"hash": CREST, "category": "emblems"}}
    return make_snapshot(
        meta={
            "capture_id": capture_id,
            "captured_at": "2026-09-16T10:00:00Z",
            "game_build": "101.103.54800.0",
            "source_path": "D:/Steam/steamapps/common/AoE2DE",
        },
        civs=[civ],
    )


def _stored(folder: DataFolder, snapshot: Snapshot, *, prerelease: bool = False) -> None:
    SnapshotStore(folder).save(snapshot)
    entry = LibraryEntry.for_snapshot(snapshot)
    Library(folder).add(entry)
    Library(folder).update(snapshot.capture_id, label="Live build", prerelease=prerelease)
    IconStore(folder).put(CREST, Image.new("RGBA", (4, 4), (200, 20, 20, 255)))


def _export(folder: DataFolder, tmp_path: Path, snapshot: Snapshot | None = None) -> Path:
    snapshot = snapshot or _snapshot()
    _stored(folder, snapshot)
    path = tmp_path / "live.aoe2snap"
    archive.export(folder, snapshot.capture_id, path, tool_version="1.2.3", notice=NOTICE)
    return path


# --- export -------------------------------------------------------------------------------------


def test_an_export_holds_the_snapshot_entry_icons_notice_and_manifest(
    folder: DataFolder, tmp_path: Path
) -> None:
    path = _export(folder, tmp_path)
    with zipfile.ZipFile(path) as zipped:
        names = set(zipped.namelist())
        manifest = json.loads(zipped.read("manifest.json"))
        entry = json.loads(zipped.read("library-entry.json"))
        notice = zipped.read("NOTICE").decode("utf-8")
    assert names == {
        "manifest.json",
        "snapshot.json.gz",
        "library-entry.json",
        "NOTICE",
        f"icons/{CREST}.png",
    }
    assert manifest["capture_id"] == "abc123"
    assert manifest["tool_version"] == "1.2.3"
    assert manifest["icons"] == [CREST]
    assert entry == {"label": "Live build", "prerelease": False, "notes": ""}
    assert notice == NOTICE


def test_an_export_leaves_out_the_install_path(folder: DataFolder, tmp_path: Path) -> None:
    path = _export(folder, tmp_path)
    with zipfile.ZipFile(path) as zipped:
        exported = archive.read_snapshot(zipped)
    assert exported.meta["source_path"] is None


# --- import -------------------------------------------------------------------------------------


def test_an_import_adds_the_version_and_its_icons(
    folder: DataFolder, target: DataFolder, tmp_path: Path
) -> None:
    result = archive.import_(target, _export(folder, tmp_path))
    assert (result.capture_id, result.added) == ("abc123", True)
    assert SnapshotStore(target).capture_ids() == ["abc123"]
    entry = Library(target).get("abc123")
    assert entry is not None
    assert (entry.label, entry.origin) == ("Live build", "imported")
    assert IconStore(target).has(CREST)


def test_importing_a_version_already_there_changes_nothing(
    folder: DataFolder, target: DataFolder, tmp_path: Path
) -> None:
    path = _export(folder, tmp_path)
    archive.import_(target, path)
    Library(target).update("abc123", label="My own label")
    result = archive.import_(target, path)
    assert result.added is False
    entry = Library(target).get("abc123")
    assert entry is not None and entry.label == "My own label"


def test_a_baseline_pack_is_marked_as_one(
    folder: DataFolder, target: DataFolder, tmp_path: Path
) -> None:
    snapshot = _snapshot()
    _stored(folder, snapshot)
    path = tmp_path / "baseline.aoe2snap"
    archive.export(
        folder, snapshot.capture_id, path, tool_version="1", notice=NOTICE, baseline=True
    )
    archive.import_(target, path)
    entry = Library(target).get("abc123")
    assert entry is not None and entry.origin == "baseline"


def _zip(tmp_path: Path, files: dict[str, bytes]) -> Path:
    path = tmp_path / "crafted.aoe2snap"
    with zipfile.ZipFile(path, "w") as zipped:
        for name, data in files.items():
            zipped.writestr(name, data)
    return path


def _valid_files(folder: DataFolder, tmp_path: Path) -> dict[str, bytes]:
    with zipfile.ZipFile(_export(folder, tmp_path)) as zipped:
        return {name: zipped.read(name) for name in zipped.namelist()}


def test_a_file_that_is_not_an_archive_is_refused(target: DataFolder, tmp_path: Path) -> None:
    path = tmp_path / "notes.aoe2snap"
    path.write_text("hello", encoding="utf-8")
    with pytest.raises(ArchiveError) as caught:
        archive.import_(target, path)
    assert caught.value.reason == "not_an_archive"


def test_a_broken_snapshot_is_refused_and_nothing_is_added(
    folder: DataFolder, target: DataFolder, tmp_path: Path
) -> None:
    files = _valid_files(folder, tmp_path) | {"snapshot.json.gz": b"\x1f\x8bnot gzip"}
    with pytest.raises(ArchiveError) as caught:
        archive.import_(target, _zip(tmp_path, files))
    assert caught.value.reason == "bad_snapshot"
    assert SnapshotStore(target).capture_ids() == []
    assert Library(target).entries() == []


def test_a_snapshot_from_a_newer_app_is_refused(
    folder: DataFolder, target: DataFolder, tmp_path: Path
) -> None:
    files = _valid_files(folder, tmp_path)
    import gzip

    data = json.loads(gzip.decompress(files["snapshot.json.gz"]))
    data["schema_version"] = 999
    files["snapshot.json.gz"] = gzip.compress(json.dumps(data).encode("utf-8"))
    with pytest.raises(ArchiveError) as caught:
        archive.import_(target, _zip(tmp_path, files))
    assert caught.value.reason == "newer_version"


def test_an_icon_that_is_not_an_image_is_refused(
    folder: DataFolder, target: DataFolder, tmp_path: Path
) -> None:
    files = _valid_files(folder, tmp_path) | {f"icons/{CREST}.png": b"not a png"}
    with pytest.raises(ArchiveError) as caught:
        archive.import_(target, _zip(tmp_path, files))
    assert caught.value.reason == "bad_icon"


def test_an_icon_name_that_is_not_a_hash_is_never_written(
    folder: DataFolder, target: DataFolder, tmp_path: Path
) -> None:
    png = io.BytesIO()
    Image.new("RGBA", (2, 2)).save(png, format="PNG")
    files = _valid_files(folder, tmp_path) | {"icons/../../evil.png": png.getvalue()}
    archive.import_(target, _zip(tmp_path, files))
    assert not (target.root.parent / "evil.png").exists()
    assert not any(path.name == "evil.png" for path in target.root.rglob("*"))


def test_an_oversized_snapshot_is_refused(
    folder: DataFolder, target: DataFolder, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(archive, "MAX_SNAPSHOT_BYTES", 100)
    with pytest.raises(ArchiveError) as caught:
        archive.import_(target, _export(folder, tmp_path))
    assert caught.value.reason == "too_large"
