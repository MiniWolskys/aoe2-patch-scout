# SPDX-License-Identifier: GPL-3.0-or-later
"""Failures a real user can hit say what went wrong and leave the app working (production audit).

A file locked by an antivirus or OneDrive, a full disk, a read-only folder, a second copy of the
app: none of them may turn a success into an error, leave a half-written file, or go unexplained.
"""

import sys
from pathlib import Path
from typing import Any

import pytest
from support import dat as sample_dat
from support import game_tree

from patch_scout.gui.api import Api
from patch_scout.gui.instance import SingleInstance
from patch_scout.i18n.catalog import load_catalog
from patch_scout.store import DataFolder, SnapshotStore
from patch_scout.store.settings import Settings, SettingsStore


@pytest.fixture
def folder(tmp_path: Path) -> DataFolder:
    return DataFolder(tmp_path / "PatchScout")


@pytest.fixture
def api(folder: DataFolder) -> Api:
    return Api(load_catalog("en"), "en", "1.2.3", folder)


def _capture(api: Api, tmp_path: Path, label: str) -> dict[str, Any]:
    install = game_tree.write(tmp_path / label, dat_bytes=sample_dat.sample_bytes())
    assert api.start_capture(str(install), label)["started"] is True
    state = api._capture
    assert state is not None
    state.thread.join(timeout=120)
    status = api.get_capture_status()
    assert status is not None
    api.clear_capture()
    result = status["result"]
    assert isinstance(result, dict)
    return result


def _locked(*_: object, **__: object) -> None:
    raise PermissionError("locked by another program")


@pytest.mark.skipif(sys.platform != "win32", reason="the guard is a Windows named mutex")
def test_a_second_copy_of_the_app_is_noticed() -> None:
    first = SingleInstance("patch-scout-test-guard")
    second = SingleInstance("patch-scout-test-guard")
    try:
        assert first.acquire() is True
        assert second.acquire() is False
    finally:
        first.release()
        second.release()
    third = SingleInstance("patch-scout-test-guard")
    assert third.acquire() is True
    third.release()


def test_settings_are_written_whole_or_not_at_all(
    folder: DataFolder, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = SettingsStore(folder)
    store.save(Settings(raw_backups=True))
    before = folder.settings_file.read_bytes()
    monkeypatch.setattr(Path, "replace", _locked)
    with pytest.raises(PermissionError):
        SettingsStore(folder).save(Settings(raw_backups=False))
    assert folder.settings_file.read_bytes() == before
    assert not list(folder.root.glob("*.part"))


def test_a_capture_succeeds_even_if_its_folder_cant_be_remembered(
    api: Api, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(SettingsStore, "remember_game_folder", _locked)
    result = _capture(api, tmp_path, "Live")
    assert isinstance(result.get("capture_id"), str)
    assert result.get("error") is None


def test_a_comparison_succeeds_even_if_it_cant_be_remembered(
    api: Api, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first = _capture(api, tmp_path, "Old")["capture_id"]
    second = _capture(api, tmp_path, "New")
    second_id = second.get("capture_id") or second.get("identical_to")
    monkeypatch.setattr(SettingsStore, "remember_comparison", _locked)
    change_set = api.compare_versions(str(first), str(second_id))
    assert "changes" in change_set


def test_a_version_that_cant_be_deleted_says_why(
    api: Api, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    capture_id = _capture(api, tmp_path, "Live")["capture_id"]
    monkeypatch.setattr(SnapshotStore, "delete", _locked)
    answer = api.delete_version(str(capture_id))
    assert answer["deleted"] is False
    assert "locked" in str(answer["error"])
    assert [v["capture_id"] for v in api.get_versions() if isinstance(v, dict)] == [capture_id]


def test_an_import_that_cant_be_written_says_why(
    api: Api, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    capture_id = _capture(api, tmp_path, "Live")["capture_id"]
    path = tmp_path / "live.aoe2snap"
    api.export_version(str(capture_id), str(path))
    other = Api(load_catalog("en"), "en", "1.2.3", DataFolder(tmp_path / "Other"))
    monkeypatch.setattr(SnapshotStore, "save", _locked)
    assert other.import_version(str(path)) == {"imported": False, "error": "write_failed"}


@pytest.mark.parametrize(
    "method", ["export_version", "save_export", "save_patch_notes", "save_images"]
)
def test_an_export_to_a_place_that_cant_be_written_says_why(
    api: Api, tmp_path: Path, method: str
) -> None:
    capture_id = str(_capture(api, tmp_path, "Live")["capture_id"])
    target = tmp_path / "missing folder" / "out.file"  # its folder doesn't exist
    if method == "export_version":
        answer = api.export_version(capture_id, str(target))
    elif method == "save_export":
        answer = api.save_export(capture_id, capture_id, "text", path=str(target))
    elif method == "save_patch_notes":
        answer = api.save_patch_notes(capture_id, capture_id, path=str(target))
    else:
        answer = api.save_images([_png()], "Overall", str(target))
    assert answer["saved"] is False
    assert answer["error"]
    assert not target.parent.exists()


def _png() -> str:
    import base64
    import io

    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (2, 2)).save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")
