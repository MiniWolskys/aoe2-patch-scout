# SPDX-License-Identifier: GPL-3.0-or-later
"""Run one capture: read an install, gate the stats, and write an immutable snapshot.

The flow and its rules are in architecture.md ("Capture flow"). The short version: the files
tier always runs, the stats tier is gated, icons never fail a capture, and the snapshot is
written atomically at the end.
"""

import logging
import threading
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

import genieutils

from patch_scout import locate
from patch_scout.capture import files_tier, icons, stats_tier, strings
from patch_scout.capture.inputs import InputReader
from patch_scout.errors import PatchScoutError
from patch_scout.snapshot import JsonObject, Snapshot
from patch_scout.store import (
    BackupStore,
    DataFolder,
    IconStore,
    Library,
    LibraryEntry,
    SnapshotStore,
)
from patch_scout.store.icons import PIPELINE_VERSION
from patch_scout.store.library import now_iso

logger = logging.getLogger(__name__)

DAT_FILE: Final = "resources/_common/dat/empires2_x2_p1.dat"
# The steps shown in the progress view (ui.md), in order, with the share of the bar each takes.
PHASES: Final = (
    ("folder", 0.02),
    ("files", 0.18),
    ("fingerprints", 0.05),
    ("stats", 0.45),
    ("icons", 0.20),
    ("backup", 0.05),
    ("save", 0.05),
)


class CaptureCancelledError(PatchScoutError):
    """The user stopped the capture."""


@dataclass(frozen=True, slots=True)
class CaptureRequest:
    """What the capture dialog collected."""

    game_folder: Path
    label: str
    prerelease: bool = False
    steam_build_id: str | None = None
    steam_branch: str | None = None
    languages: tuple[str, ...] = ("en",)
    raw_backups: bool = True
    capture_anyway: bool = False


@dataclass(frozen=True, slots=True)
class Progress:
    """One progress report: which step is running and how far the capture has got."""

    phase: str
    fraction: float
    detail: str = ""


@dataclass(slots=True)
class CaptureResult:
    """What a finished capture produced."""

    snapshot: Snapshot | None = None
    entry: LibraryEntry | None = None
    identical_to: str | None = None
    warnings: list[str] = field(default_factory=list)

    @property
    def stopped_early(self) -> bool:
        """Whether the capture stopped because an identical snapshot already exists (P-05)."""
        return self.snapshot is None and self.identical_to is not None


type ProgressCallback = Callable[[Progress], None]


class _Reporter:
    """Turns phase names into the fractions the progress bar shows."""

    def __init__(self, callback: ProgressCallback | None) -> None:
        self._callback = callback
        self._done = 0.0
        self._shares = dict(PHASES)

    def start(self, phase: str, detail: str = "") -> None:
        """Report that a step has begun."""
        if self._callback is not None:
            self._callback(Progress(phase=phase, fraction=round(self._done, 4), detail=detail))

    def finish(self, phase: str) -> None:
        """Mark a step done and move the bar forward."""
        self._done = min(1.0, self._done + self._shares.get(phase, 0.0))


def run(
    request: CaptureRequest,
    folder: DataFolder,
    *,
    on_progress: ProgressCallback | None = None,
    cancelled: threading.Event | None = None,
    capture_id: str | None = None,
) -> CaptureResult:
    """Capture one install into a new snapshot."""
    reporter = _Reporter(on_progress)
    stop = cancelled if cancelled is not None else threading.Event()
    folder.create()
    snapshots = SnapshotStore(folder)
    result = CaptureResult()

    reporter.start("folder")
    root = locate.validate(request.game_folder)
    build = locate.game_build(root)
    reader = InputReader(root)
    reporter.finish("folder")

    reporter.start("files", build or "")
    _check(stop)
    string_section, string_warnings = strings.read(reader, request.languages)
    tier = files_tier.read(reader, string_section)
    result.warnings.extend(string_warnings)
    result.warnings.extend(tier.warnings)
    reporter.finish("files")

    reporter.start("fingerprints")
    _check(stop)
    compressed = reader.read_bytes(DAT_FILE)
    assert compressed is not None  # a missing .dat raises in read_bytes
    identical = _identical_snapshot(snapshots, reader.sources())
    if identical is not None and not request.capture_anyway:
        logger.info("every input matches snapshot %s; stopping early", identical)
        result.identical_to = identical
        return result
    result.identical_to = identical
    reporter.finish("fingerprints")

    reporter.start("stats")
    _check(stop)
    stats = stats_tier.read(compressed, tier.civs, tier.tech_trees, string_section)
    del compressed
    if not stats.available:
        logger.info("stats unavailable: %s", stats.unavailable_reason)
    reporter.finish("stats")

    reporter.start("icons")
    _check(stop)
    pipeline = icons.IconPipeline(reader, IconStore(folder))
    stat_icons = icons.attach(pipeline, tier.civs, tier.tech_trees)
    result.warnings.extend(pipeline.warnings)
    reporter.finish("icons")

    reporter.start("backup")
    _check(stop)
    new_capture_id = capture_id if capture_id is not None else uuid.uuid4().hex
    if request.raw_backups:
        _write_backup(folder, new_capture_id, reader)
    reporter.finish("backup")

    reporter.start("save")
    _check(stop)
    snapshot = _build(
        new_capture_id,
        request,
        root,
        build,
        reader,
        tier,
        stats,
        string_section,
        stat_icons,
        result,
    )
    snapshots.save(snapshot)
    entry = Library(folder).add(LibraryEntry.for_snapshot(snapshot))
    reporter.finish("save")
    reporter.start("done", "")

    result.snapshot = snapshot
    result.entry = entry
    return result


def _build(
    capture_id: str,
    request: CaptureRequest,
    root: Path,
    build: str | None,
    reader: InputReader,
    tier: files_tier.FilesTier,
    stats: stats_tier.StatsResult,
    string_section: JsonObject,
    stat_icons: JsonObject,
    result: CaptureResult,
) -> Snapshot:
    meta: JsonObject = {
        "capture_id": capture_id,
        "tool_version": _tool_version(),
        "captured_at": now_iso(),
        "label_at_capture": request.label,
        "prerelease_at_capture": request.prerelease,
        "source_path": str(root),
        "game_build": build,
        "steam_build_id": request.steam_build_id,
        "steam_branch": request.steam_branch,
        "dat_format_version": stats.format_version,
        "dat_layout_version": stats.layout_version,
        "genieutils_version": _genieutils_version(),
        "languages": list(request.languages),
        "icon_pipeline_version": PIPELINE_VERSION,
    }
    flags: JsonObject = {
        "stats_available": stats.available,
        "stats_unavailable_reason": stats.unavailable_reason,
        "format_verified": stats.format_verified,
        "dat_attempts": [attempt.to_json() for attempt in stats.attempts],
        "sanity_checks": [check.to_json() for check in stats.checks],
        "missing_sections": list(tier.missing_sections),
        "warnings": list(result.warnings),
    }
    return Snapshot(
        meta=meta,
        sources=reader.sources(),
        flags=flags,
        civs=tier.civs,
        tech_trees=tier.tech_trees,
        building_offers=tier.building_offers,
        unit_lines=tier.unit_lines,
        linked_techs=tier.linked_techs,
        linked_units=tier.linked_units,
        eras=tier.eras,
        strings=string_section,
        stat_icons=stat_icons,
        stats=stats.stats,
    )


def _write_backup(folder: DataFolder, capture_id: str, reader: InputReader) -> None:
    """Copy the input files in, skipping content that is already stored (P-19)."""
    backups = BackupStore(folder)
    manifest: dict[str, str] = {}
    for relative, digest, path in reader.backup_entries():
        if relative.startswith("widgetui/") or relative.endswith((".png", ".dds", ".DDS")):
            continue  # icons are not backed up; the converted ones are already kept
        backups.store(digest, path)
        manifest[relative] = digest
    backups.write_manifest(capture_id, manifest)


def _identical_snapshot(snapshots: SnapshotStore, sources: JsonObject) -> str | None:
    """Find a stored snapshot whose inputs all match, comparing only the files read so far."""
    for capture_id in snapshots.capture_ids():
        try:
            stored = snapshots.load(capture_id)
        except PatchScoutError:
            logger.warning("snapshot %s could not be read while comparing inputs", capture_id)
            continue
        if _same_sources(sources, stored.sources):
            return capture_id
    return None


def _same_sources(current: JsonObject, stored: JsonObject) -> bool:
    if not current:
        return False
    return all(stored.get(name) == value for name, value in current.items())


def _check(stop: threading.Event) -> None:
    if stop.is_set():
        raise CaptureCancelledError("the capture was stopped")


def _tool_version() -> str:
    import importlib.metadata

    try:
        return importlib.metadata.version("patch-scout")
    except importlib.metadata.PackageNotFoundError:  # running from a source tree
        return "0.0.0"


def _genieutils_version() -> str | None:
    import importlib.metadata

    try:
        return importlib.metadata.version("genieutils-py")
    except importlib.metadata.PackageNotFoundError:
        return getattr(genieutils, "__version__", None)


def phase_names() -> Sequence[str]:
    """The progress steps, in the order the progress view shows them."""
    return [name for name, _ in PHASES]
