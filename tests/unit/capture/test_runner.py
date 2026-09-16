# SPDX-License-Identifier: GPL-3.0-or-later
"""A whole capture, from a synthetic game folder to a stored snapshot."""

import threading
from dataclasses import replace
from pathlib import Path

import pytest
from support import dat as sample_dat
from support import game_tree

from patch_scout.capture import runner
from patch_scout.capture.runner import CaptureCancelledError, CaptureRequest, Progress
from patch_scout.locate import InvalidInstallError
from patch_scout.store import BackupStore, DataFolder, Library, SnapshotStore


@pytest.fixture
def install(tmp_path: Path) -> Path:
    return game_tree.write(tmp_path / "AoE2DE", dat_bytes=sample_dat.sample_bytes())


@pytest.fixture
def folder(tmp_path: Path) -> DataFolder:
    return DataFolder(tmp_path / "PatchScout")


def request_for(install: Path, **overrides: object) -> CaptureRequest:
    base = CaptureRequest(game_folder=install, label="Test build", steam_build_id="24094652")
    return replace(base, **overrides)  # type: ignore[arg-type]  # the tests pass matching types


def test_a_capture_writes_a_snapshot_and_a_library_entry(install: Path, folder: DataFolder) -> None:
    result = runner.run(request_for(install), folder)
    assert result.snapshot is not None
    assert result.entry is not None and result.entry.label == "Test build"
    assert SnapshotStore(folder).capture_ids() == [result.snapshot.capture_id]


def test_the_stats_tier_passes_its_gates_on_the_synthetic_dat(
    install: Path, folder: DataFolder
) -> None:
    snapshot = runner.run(request_for(install), folder).snapshot
    assert snapshot is not None
    assert snapshot.stats_available is True
    assert snapshot.flags["stats_unavailable_reason"] is None
    assert snapshot.flags["format_verified"] is True
    assert snapshot.stats is not None


def test_a_dat_that_cannot_be_read_still_gives_a_snapshot(
    tmp_path: Path, folder: DataFolder
) -> None:
    install = game_tree.write(tmp_path / "AoE2DE")  # the placeholder .dat parses nowhere
    snapshot = runner.run(request_for(install), folder).snapshot
    assert snapshot is not None
    assert snapshot.stats is None
    assert snapshot.stats_available is False
    assert snapshot.flags["stats_unavailable_reason"]
    assert snapshot.civs  # the files tier still ran


def test_the_snapshot_records_what_it_read(install: Path, folder: DataFolder) -> None:
    snapshot = runner.run(request_for(install), folder).snapshot
    assert snapshot is not None
    assert snapshot.meta["label_at_capture"] == "Test build"
    assert snapshot.meta["steam_build_id"] == "24094652"
    assert snapshot.meta["dat_format_version"] == "VER 8.9"
    assert snapshot.meta["languages"] == ["en"]
    assert "resources/_common/dat/civilizations.json" in snapshot.sources
    assert "resources/_common/dat/empires2_x2_p1.dat" in snapshot.sources


def test_the_icons_end_up_in_the_store(install: Path, folder: DataFolder) -> None:
    snapshot = runner.run(request_for(install), folder).snapshot
    assert snapshot is not None
    nodes = snapshot.tech_trees["Redlanders"]
    assert isinstance(nodes, list) and isinstance(nodes[0], dict)
    icon = nodes[0]["icon"]
    assert isinstance(icon, dict) and isinstance(icon["hash"], str)
    assert list(folder.icons.rglob("*.png"))


def test_capturing_the_same_install_twice_gives_the_same_snapshot(
    install: Path, folder: DataFolder
) -> None:
    first = runner.run(request_for(install), folder, capture_id="one").snapshot
    second = runner.run(
        request_for(install, capture_anyway=True), folder, capture_id="two"
    ).snapshot
    assert first is not None and second is not None
    volatile = {"capture_id", "captured_at"}
    assert {k: v for k, v in first.meta.items() if k not in volatile} == {
        k: v for k, v in second.meta.items() if k not in volatile
    }
    assert first.to_json() | {"meta": {}} == second.to_json() | {"meta": {}}


def test_an_identical_install_stops_the_capture_early(install: Path, folder: DataFolder) -> None:
    first = runner.run(request_for(install), folder).snapshot
    assert first is not None
    again = runner.run(request_for(install), folder)
    assert again.snapshot is None
    assert again.identical_to == first.capture_id
    assert again.stopped_early is True


def test_capture_anyway_writes_a_second_snapshot(install: Path, folder: DataFolder) -> None:
    runner.run(request_for(install), folder)
    again = runner.run(request_for(install, capture_anyway=True), folder)
    assert again.snapshot is not None
    assert len(SnapshotStore(folder).capture_ids()) == 2


def test_a_changed_input_is_not_identical(install: Path, folder: DataFolder) -> None:
    runner.run(request_for(install), folder)
    (install / "resources/en/strings/key-value/key-value-strings-utf8.txt").write_text(
        game_tree.STRINGS + '99 "new text"\n', encoding="utf-8"
    )
    again = runner.run(request_for(install), folder)
    assert again.snapshot is not None
    assert again.identical_to is None


def test_the_raw_backup_keeps_the_inputs_but_not_the_icons(
    install: Path, folder: DataFolder
) -> None:
    result = runner.run(request_for(install), folder)
    assert result.snapshot is not None
    manifest = (folder.backups / f"{result.snapshot.capture_id}.json").read_text(encoding="utf-8")
    assert "civilizations.json" in manifest
    assert ".DDS" not in manifest
    assert list(BackupStore(folder).objects.rglob("*"))


def test_backups_can_be_turned_off(install: Path, folder: DataFolder) -> None:
    result = runner.run(request_for(install, raw_backups=False), folder)
    assert result.snapshot is not None
    assert not (folder.backups / f"{result.snapshot.capture_id}.json").exists()


def test_progress_is_reported_for_every_step(install: Path, folder: DataFolder) -> None:
    seen: list[Progress] = []
    runner.run(request_for(install), folder, on_progress=seen.append)
    assert [step.phase for step in seen] == [*runner.phase_names(), "done"]
    assert seen[0].fraction == 0.0
    assert all(0.0 <= step.fraction <= 1.0 for step in seen)


def test_the_first_step_reports_the_game_build(install: Path, folder: DataFolder) -> None:
    seen: list[Progress] = []
    runner.run(request_for(install), folder, on_progress=seen.append)
    assert seen[1].phase == "files"  # the build is unknown without the exe, so the detail is empty


def test_a_cancelled_capture_writes_nothing(install: Path, folder: DataFolder) -> None:
    stop = threading.Event()
    stop.set()
    with pytest.raises(CaptureCancelledError):
        runner.run(request_for(install), folder, cancelled=stop)
    assert SnapshotStore(folder).capture_ids() == []


def test_a_folder_that_is_not_an_install_is_refused(tmp_path: Path, folder: DataFolder) -> None:
    with pytest.raises(InvalidInstallError):
        runner.run(request_for(tmp_path / "empty"), folder)


def test_warnings_from_every_stage_reach_the_snapshot(install: Path, folder: DataFolder) -> None:
    (install / "resources/_common/dat/eras.json").unlink()
    snapshot = runner.run(request_for(install), folder).snapshot
    assert snapshot is not None
    warnings = snapshot.flags["warnings"]
    assert isinstance(warnings, list)
    assert any("duplicate keys" in str(warning) for warning in warnings)
    assert snapshot.flags["missing_sections"] == ["eras"]


def test_the_library_entry_can_be_read_back(install: Path, folder: DataFolder) -> None:
    result = runner.run(request_for(install, prerelease=True), folder)
    assert result.snapshot is not None
    entry = Library(folder).get(result.snapshot.capture_id)
    assert entry is not None and entry.prerelease is True and entry.origin == "captured"
