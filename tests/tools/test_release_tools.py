# SPDX-License-Identifier: GPL-3.0-or-later
"""The release helpers: the app icon and the baseline pack (P-21)."""

import json
import zipfile
from pathlib import Path

import pytest
from support.snapshots import make_snapshot

import make_baseline_pack
import make_icon
from patch_scout.store import DataFolder, Library, LibraryEntry, SnapshotStore


def test_the_icon_is_drawn_at_full_size_with_the_theme_gold() -> None:
    image = make_icon.draw()
    assert image.size == (256, 256) and image.mode == "RGBA"
    assert make_icon.GOLD in {image.getpixel((x, 112)) for x in range(40, 60)}


def _folder(tmp_path: Path, *, prerelease: bool) -> DataFolder:
    folder = DataFolder(tmp_path / "PatchScout")
    folder.create()
    snapshot = make_snapshot()
    SnapshotStore(folder).save(snapshot)
    Library(folder).add(LibraryEntry.for_snapshot(snapshot))
    Library(folder).update(snapshot.capture_id, prerelease=prerelease)
    return folder


def test_a_baseline_pack_is_an_archive_marked_as_a_baseline(tmp_path: Path) -> None:
    folder = _folder(tmp_path, prerelease=False)
    output = tmp_path / "baseline.aoe2snap"
    code = make_baseline_pack.main(["abc", str(output), "--data-folder", str(folder.root)])
    assert code == 0
    with zipfile.ZipFile(output) as zipped:
        assert json.loads(zipped.read("manifest.json"))["baseline"] is True


def test_a_pre_release_version_never_becomes_a_baseline(tmp_path: Path) -> None:
    folder = _folder(tmp_path, prerelease=True)
    with pytest.raises(SystemExit):
        make_baseline_pack.main(
            ["abc", str(tmp_path / "x.aoe2snap"), "--data-folder", str(folder.root)]
        )
    assert not (tmp_path / "x.aoe2snap").exists()
