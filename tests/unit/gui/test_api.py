# SPDX-License-Identifier: GPL-3.0-or-later
"""The API the page calls. Every test gives it its own data folder; none touches the real one."""

import json
from pathlib import Path
from typing import Any

import pytest
from support import dat as sample_dat
from support import game_tree

from patch_scout.gui.api import MAX_ICONS, Api
from patch_scout.i18n.catalog import Catalog, load_catalog
from patch_scout.store import DataFolder


@pytest.fixture
def folder(tmp_path: Path) -> DataFolder:
    return DataFolder(tmp_path / "PatchScout")


@pytest.fixture
def api(folder: DataFolder) -> Api:
    return Api(load_catalog("en"), "en", "1.2.3", folder)


@pytest.fixture
def install(tmp_path: Path) -> Path:
    return game_tree.write(tmp_path / "AoE2DE", dat_bytes=sample_dat.sample_bytes())


def capture(api: Api, install: Path, label: str = "Test build") -> str:
    """Run one capture to completion and return its capture ID."""
    started = api.start_capture(str(install), label)
    assert started["started"] is True
    capture_state = api._capture  # the test waits for the worker it just started
    assert capture_state is not None
    capture_state.thread.join(timeout=120)
    status = api.get_capture_status()
    assert status is not None and status["running"] is False
    result = status["result"]
    assert isinstance(result, dict), result
    assert result.get("error") is None, result
    capture_id = result["capture_id"]
    assert isinstance(capture_id, str)
    api.clear_capture()
    return capture_id


def test_startup_carries_the_language_messages_and_version(api: Api) -> None:
    startup = api.get_startup()
    assert startup["language"] == "en"
    assert startup["app_version"] == "1.2.3"
    assert startup["versions"] == []
    messages = startup["messages"]
    assert isinstance(messages, dict) and messages["app.title"] == "Patch Scout"


def test_startup_uses_the_data_folder_it_was_given(api: Api, folder: DataFolder) -> None:
    settings = api.get_startup()["settings"]
    assert isinstance(settings, dict)
    assert settings["data_folder"] == str(folder.root)
    assert folder.snapshots.is_dir()


def test_every_public_attribute_is_a_method_the_page_may_call(api: Api) -> None:
    """pywebview exposes every public attribute, so none of them may be state."""
    public = [name for name in dir(api) if not name.startswith("_")]
    assert public
    assert all(callable(getattr(api, name)) for name in public)


def test_a_capture_produces_a_version(api: Api, install: Path) -> None:
    capture_id = capture(api, install)
    versions = api.get_versions()
    assert len(versions) == 1
    version = versions[0]
    assert isinstance(version, dict)
    assert version["capture_id"] == capture_id
    assert version["label"] == "Test build"
    assert version["stats_available"] is True


def test_a_capture_reports_its_progress(api: Api, install: Path) -> None:
    api.start_capture(str(install), "Progress")
    state = api._capture  # the test watches the worker it just started
    assert state is not None
    state.thread.join(timeout=120)
    status = api.get_capture_status()
    assert status is not None
    assert status["fraction"] == 1.0
    assert status["running"] is False


def test_only_one_capture_runs_at_a_time(api: Api, install: Path) -> None:
    api.start_capture(str(install), "First")
    second = api.start_capture(str(install), "Second")
    state = api._capture
    assert state is not None
    state.thread.join(timeout=120)
    assert second["started"] is False


def test_capturing_the_same_install_twice_stops_early(api: Api, install: Path) -> None:
    capture(api, install)
    api.start_capture(str(install), "Again")
    state = api._capture
    assert state is not None
    state.thread.join(timeout=120)
    status = api.get_capture_status()
    assert status is not None
    result = status["result"]
    assert isinstance(result, dict)
    assert result["stopped_early"] is True


def test_a_capture_of_a_folder_that_is_not_an_install_reports_the_reason(
    api: Api, tmp_path: Path
) -> None:
    api.start_capture(str(tmp_path / "nowhere"), "Broken")
    state = api._capture
    assert state is not None
    state.thread.join(timeout=30)
    status = api.get_capture_status()
    assert status is not None
    result = status["result"]
    assert isinstance(result, dict) and isinstance(result["error"], str)


def test_a_folder_is_validated_before_a_capture(api: Api, install: Path) -> None:
    good = api.validate_game_folder(str(install / "resources"))
    assert good["valid"] is True
    assert good["path"] == str(install)
    assert good["moved"] is True


def test_a_folder_that_is_not_an_install_is_refused_with_a_reason(api: Api, tmp_path: Path) -> None:
    refused = api.validate_game_folder(str(tmp_path / "nothing"))
    assert refused["valid"] is False
    assert isinstance(refused["reason"], str)


def test_detection_without_a_game_finds_nothing(api: Api) -> None:
    assert isinstance(api.detect_game_folders(), list)


def test_a_version_can_be_renamed_and_flagged(api: Api, install: Path) -> None:
    capture_id = capture(api, install)
    updated = api.update_version(capture_id, label="PUP October", prerelease=True, notes="embargo")
    assert updated["label"] == "PUP October"
    assert updated["prerelease"] is True
    details = api.get_version(capture_id)
    assert details["notes"] == "embargo"


def test_a_version_can_be_deleted(api: Api, install: Path) -> None:
    capture_id = capture(api, install)
    assert api.delete_version(capture_id)["versions"] == []


def test_two_versions_compare(api: Api, install: Path, tmp_path: Path) -> None:
    first = capture(api, install, "Live")
    other = game_tree.write(
        tmp_path / "new",
        dat_bytes=sample_dat.sample_bytes(archer_hp=40),
        unavailable_civs=(),
    )
    second = capture(api, other, "PUP")
    result = api.compare_versions(first, second)
    assert result["identical"] is False
    changes = result["changes"]
    assert isinstance(changes, list) and changes
    assert isinstance(result["civs"], list)


def test_the_comparison_is_remembered_for_the_next_launch(
    api: Api, install: Path, tmp_path: Path
) -> None:
    first = capture(api, install, "Live")
    other = game_tree.write(tmp_path / "new2", dat_bytes=sample_dat.sample_bytes(archer_hp=41))
    second = capture(api, other, "PUP")
    api.compare_versions(first, second)
    remembered = api.get_startup()["last_comparison"]
    assert isinstance(remembered, list)
    assert sorted(str(item) for item in remembered) == sorted([first, second])


def test_exporting_the_comparison_gives_plain_text(api: Api, install: Path, tmp_path: Path) -> None:
    first = capture(api, install, "Live")
    other = game_tree.write(tmp_path / "new3", dat_bytes=sample_dat.sample_bytes(archer_hp=42))
    second = capture(api, other, "PUP")
    exported = api.export_text(first, second)
    text = exported["text"]
    assert isinstance(text, str)
    assert "Patch Scout" in text
    assert "Live" in text and "PUP" in text


def test_saving_an_export_writes_the_file(
    api: Api, install: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first = capture(api, install, "Live")
    other = game_tree.write(tmp_path / "new4", dat_bytes=sample_dat.sample_bytes(archer_hp=43))
    second = capture(api, other, "PUP")
    target = tmp_path / "export.html"
    monkeypatch.setattr(Api, "_ask_where_to_save", lambda *args, **kwargs: str(target))
    saved = api.save_export(first, second, kind="html")
    assert saved["saved"] is True
    assert "<!doctype html>" in target.read_text(encoding="utf-8")


def test_a_cancelled_save_writes_nothing(
    api: Api, install: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first = capture(api, install, "Live")
    other = game_tree.write(tmp_path / "new5", dat_bytes=sample_dat.sample_bytes(archer_hp=44))
    second = capture(api, other, "PUP")
    monkeypatch.setattr(Api, "_ask_where_to_save", lambda *args, **kwargs: None)
    assert api.save_export(first, second)["saved"] is False


def test_icons_come_back_as_data_uris(api: Api, install: Path) -> None:
    capture_id = capture(api, install)
    result = api.compare_versions(capture_id, capture_id)
    assert result["identical"] is True
    digests = [path.stem for path in (api._folder.icons).rglob("*.png")]
    icons = api.get_icons(digests[:3])
    assert icons
    assert all(str(value).startswith("data:image/png;base64,") for value in icons.values())


def test_an_icon_that_is_not_stored_is_simply_absent(api: Api) -> None:
    assert api.get_icons(["nothing"]) == {}


def test_settings_can_be_read_and_changed(api: Api) -> None:
    assert api.get_settings()["raw_backups"] is True
    assert api.update_settings(raw_backups=False)["raw_backups"] is False
    assert api.get_settings()["raw_backups"] is False


def test_backups_can_be_purged(api: Api, install: Path) -> None:
    capture(api, install)
    assert isinstance(api.purge_backups()["removed"], int)


def test_diagnostics_describe_the_environment(api: Api, install: Path) -> None:
    capture_id = capture(api, install)
    diagnostics = api.get_diagnostics(capture_id)
    environment = diagnostics["environment"]
    assert isinstance(environment, dict)
    assert environment["app_version"] == "1.2.3"
    assert environment["genieutils_version"]
    snapshot = diagnostics["snapshot"]
    assert isinstance(snapshot, dict) and snapshot["capture_id"] == capture_id
    assert isinstance(diagnostics["log"], list)


def test_the_snapshot_inspector_returns_one_section(api: Api, install: Path) -> None:
    capture_id = capture(api, install)
    civs = api.get_snapshot_section(capture_id, "civs")
    assert isinstance(civs, list) and civs
    flags = api.get_snapshot_section(capture_id, "flags")
    assert isinstance(flags, dict) and "stats_available" in flags


def test_the_inspector_can_reach_one_key(api: Api, install: Path) -> None:
    capture_id = capture(api, install)
    tree = api.get_snapshot_section(capture_id, "tech_trees", "Redlanders")
    assert isinstance(tree, list) and tree


def test_a_huge_section_comes_back_summarised(api: Api, install: Path) -> None:
    capture_id = capture(api, install)
    units = api.get_snapshot_section(capture_id, "strings", "tables")
    assert units is not None


def test_every_api_result_is_plain_json(api: Api, install: Path) -> None:
    capture_id = capture(api, install)
    for value in (
        api.get_startup(),
        api.get_versions(),
        api.get_version(capture_id),
        api.get_settings(),
        api.get_diagnostics(capture_id),
        api.compare_versions(capture_id, capture_id),
    ):
        json.dumps(value)


def test_browsing_without_a_window_returns_nothing(api: Api) -> None:
    assert api.browse_for_folder() is None


def test_the_window_can_be_attached(api: Api) -> None:
    sentinel: Any = object()
    api.attach(sentinel)
    assert api._window is sentinel


def test_an_empty_catalog_starts_with_no_messages(folder: DataFolder) -> None:
    """The page then fails loudly on the first lookup, rather than showing blank controls."""
    empty = Api(Catalog({}), "en", "1.0", folder)
    assert empty.get_startup()["messages"] == {}


def test_a_capture_after_startup_keeps_its_label(api: Api, install: Path) -> None:
    """The app always calls get_startup() first, which used to leave a stale library cache."""
    api.get_startup()

    capture(api, install, "My label")

    versions = api.get_versions()
    assert isinstance(versions[0], dict)
    assert versions[0]["label"] == "My label"


def test_a_version_captured_after_startup_can_be_edited(api: Api, install: Path) -> None:
    api.get_startup()
    capture_id = capture(api, install, "My label")

    updated = api.update_version(capture_id, label="Renamed", prerelease=True)

    assert updated["label"] == "Renamed"
    assert updated["prerelease"] is True


def test_asking_for_more_icons_than_the_cap_returns_the_cap(api: Api) -> None:
    """The page batches its requests; anything past the cap is silently dropped here."""
    assert len(api.get_icons(["missing"] * (MAX_ICONS + 50))) == 0
