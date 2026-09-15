# SPDX-License-Identifier: GPL-3.0-or-later
"""The local data folder: snapshot files, the library index, icons and raw backups."""

from pathlib import Path

import pytest
from PIL import Image
from support.snapshots import make_snapshot

from patch_scout.errors import PatchScoutError
from patch_scout.store import (
    BackupStore,
    DataFolder,
    IconStore,
    Library,
    LibraryEntry,
    SnapshotNotFoundError,
    SnapshotStore,
)
from patch_scout.store.icons import MAX_SIDE, downscale
from patch_scout.store.paths import default_root


@pytest.fixture
def folder(tmp_path: Path) -> DataFolder:
    data = DataFolder(tmp_path / "PatchScout")
    data.create()
    return data


def test_the_default_root_follows_localappdata(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(Path("C:/Users/someone/AppData/Local")))
    assert default_root().name == "PatchScout"
    assert default_root().parent.name == "Local"


def test_the_default_root_falls_back_to_the_home_folder(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    assert default_root() == Path.home() / ".local" / "share" / "PatchScout"


def test_a_saved_snapshot_can_be_listed_and_read_back(folder: DataFolder) -> None:
    store = SnapshotStore(folder)
    store.save(make_snapshot())
    assert store.capture_ids() == ["abc"]
    assert store.load("abc").capture_id == "abc"


def test_snapshots_are_never_overwritten(folder: DataFolder) -> None:
    store = SnapshotStore(folder)
    store.save(make_snapshot())
    with pytest.raises(PatchScoutError, match="already exists"):
        store.save(make_snapshot())


def test_loading_an_unknown_capture_is_refused(folder: DataFolder) -> None:
    with pytest.raises(SnapshotNotFoundError):
        SnapshotStore(folder).load("nope")


def test_deleting_is_forgiving_and_empties_the_list(folder: DataFolder) -> None:
    store = SnapshotStore(folder)
    store.save(make_snapshot())
    store.delete("abc")
    store.delete("abc")
    assert store.capture_ids() == []


def test_the_library_keeps_what_the_user_edits(folder: DataFolder) -> None:
    library = Library(folder)
    library.add(LibraryEntry.for_snapshot(make_snapshot()))
    library.update("abc", label="PUP October", prerelease=True, notes="embargoed")
    reopened = Library(folder).get("abc")
    assert reopened is not None
    assert (reopened.label, reopened.prerelease, reopened.notes) == (
        "PUP October",
        True,
        "embargoed",
    )


def test_a_new_entry_takes_its_label_from_the_capture(folder: DataFolder) -> None:
    snapshot = make_snapshot(
        meta={
            "capture_id": "abc",
            "captured_at": "t",
            "label_at_capture": "Live",
            "prerelease_at_capture": True,
        }
    )
    entry = LibraryEntry.for_snapshot(snapshot)
    assert (entry.label, entry.prerelease, entry.origin) == ("Live", True, "captured")


def test_an_entry_without_a_label_falls_back_to_its_id(folder: DataFolder) -> None:
    assert LibraryEntry.for_snapshot(make_snapshot()).label == "abc"


def test_removing_an_entry_saves_the_index(folder: DataFolder) -> None:
    library = Library(folder)
    library.add(LibraryEntry.for_snapshot(make_snapshot()))
    library.remove("abc")
    assert Library(folder).entries() == []


def test_the_index_is_rebuilt_from_the_snapshot_files(folder: DataFolder) -> None:
    store = SnapshotStore(folder)
    store.save(make_snapshot())
    library = Library(folder)
    library.rebuild_from(store)
    assert [entry.capture_id for entry in library.entries()] == ["abc"]


def test_rebuilding_drops_entries_whose_snapshot_is_gone(folder: DataFolder) -> None:
    library = Library(folder)
    library.add(LibraryEntry.for_snapshot(make_snapshot()))
    library.rebuild_from(SnapshotStore(folder))
    assert library.entries() == []


def test_a_corrupted_index_reads_as_empty(folder: DataFolder) -> None:
    folder.library_file.write_text("{ not json", encoding="utf-8")
    assert Library(folder).entries() == []


def test_an_index_with_a_strange_shape_reads_as_empty(folder: DataFolder) -> None:
    folder.library_file.write_text('{"entries": [1, 2]}', encoding="utf-8")
    assert Library(folder).entries() == []


def test_an_entry_with_missing_fields_gets_safe_defaults(folder: DataFolder) -> None:
    folder.library_file.write_text('{"entries": {"abc": {}}}', encoding="utf-8")
    entry = Library(folder).get("abc")
    assert entry is not None
    assert (entry.label, entry.prerelease, entry.origin) == ("abc", False, "imported")


def test_an_icon_is_stored_once_and_read_back(folder: DataFolder) -> None:
    store = IconStore(folder)
    image = Image.new("RGBA", (256, 256), (10, 20, 30, 255))
    first = store.put("a3f9beef", image)
    assert store.has("a3f9beef")
    assert store.put("a3f9beef", image) == first
    assert store.read_png("a3f9beef") is not None
    assert first.parent.name == "a3"


def test_reading_an_icon_that_isnt_stored_gives_none(folder: DataFolder) -> None:
    assert IconStore(folder).read_png("missing") is None


def test_icons_are_downscaled_to_the_longest_side() -> None:
    assert downscale(Image.new("RGBA", (512, 256))).size == (MAX_SIDE, MAX_SIDE // 2)


def test_small_icons_keep_their_size_and_gain_an_alpha_channel() -> None:
    downscaled = downscale(Image.new("RGB", (66, 66)))
    assert (downscaled.size, downscaled.mode) == ((66, 66), "RGBA")


def test_a_backup_object_is_stored_once(folder: DataFolder, tmp_path: Path) -> None:
    source = tmp_path / "civilizations.json"
    source.write_text("{}", encoding="utf-8")
    store = BackupStore(folder)
    assert store.store("deadbeef", source) is True
    assert store.store("deadbeef", source) is False
    assert store.object_path("deadbeef").read_text(encoding="utf-8") == "{}"


def test_a_manifest_maps_input_paths_to_object_hashes(folder: DataFolder) -> None:
    path = BackupStore(folder).write_manifest("abc", {"resources/a.json": "deadbeef"})
    assert "deadbeef" in path.read_text(encoding="utf-8")


def test_purging_removes_every_backup(folder: DataFolder, tmp_path: Path) -> None:
    source = tmp_path / "a.json"
    source.write_text("{}", encoding="utf-8")
    store = BackupStore(folder)
    store.store("deadbeef", source)
    store.write_manifest("abc", {"a.json": "deadbeef"})
    assert store.purge() == 2
    assert store.purge() == 0
