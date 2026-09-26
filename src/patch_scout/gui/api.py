# SPDX-License-Identifier: GPL-3.0-or-later
"""The Python API the page calls through pywebview (`window.pywebview.api`).

Everything the page can do goes through this object, and every return value is plain JSON
(architecture.md). The GUI never reads a game file itself: it asks `capture` (D-13).
"""

import base64
import logging
import platform
import sys
import threading
import traceback
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Final

from patch_scout import locate
from patch_scout.capture import runner
from patch_scout.capture.runner import CaptureRequest, Progress
from patch_scout.diff import Options, SideInfo, compare, order
from patch_scout.errors import PatchScoutError
from patch_scout.i18n.catalog import Catalog
from patch_scout.report import Filters, render_html, render_text
from patch_scout.snapshot import JsonObject, JsonValue, Snapshot
from patch_scout.store import (
    BackupStore,
    DataFolder,
    IconStore,
    Library,
    LibraryEntry,
    SnapshotStore,
)
from patch_scout.store.settings import Settings, SettingsStore

logger = logging.getLogger(__name__)

# How many icons the page may ask for at once; a comparison shows far fewer than this.
MAX_ICONS: Final = 400

type FolderPicker = Callable[[], str | None]
type FileSaver = Callable[[str, str], str | None]


@dataclass(slots=True)
class _Capture:
    """A capture running on its own thread, and the last thing it reported."""

    thread: threading.Thread
    cancel: threading.Event
    label: str
    phase: str = "folder"
    fraction: float = 0.0
    detail: str = ""
    done: bool = False
    result: JsonObject = field(default_factory=dict)

    def to_json(self) -> JsonObject:
        """What the version list and the progress view show."""
        return {
            "running": not self.done,
            "label": self.label,
            "phase": self.phase,
            "fraction": self.fraction,
            "detail": self.detail,
            "result": self.result,
        }


class Api:
    """Methods the page can call; each returns plain JSON values.

    pywebview exposes every public attribute to the page, so internal state is underscored.
    """

    def __init__(
        self,
        catalog: Catalog,
        language: str,
        app_version: str,
        folder: DataFolder | None = None,
    ) -> None:
        self._catalog = catalog
        self._language = language
        self._app_version = app_version
        self._folder = folder or DataFolder.default()
        self._settings = SettingsStore(self._folder)
        self._snapshots = SnapshotStore(self._folder)
        self._library = Library(self._folder)
        self._icons = IconStore(self._folder)
        self._capture: _Capture | None = None
        self._loaded: dict[str, Snapshot] = {}
        self._window: Any = None
        self._log: list[str] = []

    # --- wiring ------------------------------------------------------------------------------

    def attach(self, window: Any) -> None:
        """Remember the window, so the API can open the native file dialogs."""
        self._window = window

    # --- startup -----------------------------------------------------------------------------

    def get_startup(self) -> JsonObject:
        """What the page needs to start: language, messages, app version, versions, settings."""
        with _Guard("get_startup"):
            self._folder.create()
            self._library.rebuild_from(self._snapshots)
            settings = self._settings.load()
            return {
                "language": self._language,
                "messages": dict(self._catalog.messages()),
                "app_version": self._app_version,
                "versions": self._versions(),
                "settings": _settings_json(settings, self._folder),
                "last_comparison": list(settings.last_comparison or ()),
                "capture": self._capture.to_json() if self._capture else None,
            }

    def get_versions(self) -> list[JsonValue]:
        """The version list, newest game build first."""
        with _Guard("get_versions"):
            return self._versions()

    # --- the library -------------------------------------------------------------------------

    def get_version(self, capture_id: str) -> JsonObject:
        """One version's details."""
        with _Guard("get_version"):
            snapshot = self._snapshot(capture_id)
            entry = self._library.get(capture_id)
            return _version_json(snapshot, entry) | {
                "source_path": snapshot.meta.get("source_path"),
                "flags": snapshot.flags,
                "meta": snapshot.meta,
                "civ_count": len(snapshot.civs),
            }

    def update_version(
        self,
        capture_id: str,
        label: str | None = None,
        prerelease: bool | None = None,
        notes: str | None = None,
    ) -> JsonObject:
        """Rename a version, change its pre-release tickbox or its notes (P-18)."""
        with _Guard("update_version"):
            entry = self._library.update(
                capture_id, label=label, prerelease=prerelease, notes=notes
            )
            return _entry_json(entry)

    def delete_version(self, capture_id: str) -> JsonObject:
        """Delete a snapshot and its library entry."""
        with _Guard("delete_version"):
            self._snapshots.delete(capture_id)
            self._library.remove(capture_id)
            self._loaded.pop(capture_id, None)
            return {"versions": self._versions()}

    # --- capture -----------------------------------------------------------------------------

    def detect_game_folders(self) -> list[JsonValue]:
        """Propose install folders; finding none is a normal outcome (D-19)."""
        with _Guard("detect_game_folders"):
            recent = [Path(item) for item in self._settings.load().recent_game_folders]
            return [
                {
                    "path": str(candidate.path),
                    "source": candidate.source,
                    "steam_build_id": candidate.steam_build_id,
                    "steam_branch": candidate.steam_branch,
                    "prerelease_hint": candidate.prerelease_hint,
                    "game_build": locate.game_build(candidate.path),
                }
                for candidate in locate.detect(recent=recent)
            ]

    def browse_for_folder(self) -> str | None:
        """Open the native folder picker and return what the user chose."""
        with _Guard("browse_for_folder"):
            if self._window is None:
                return None
            import webview

            chosen = self._window.create_file_dialog(webview.FOLDER_DIALOG)
            if not chosen:
                return None
            return str(chosen[0])

    def validate_game_folder(self, path: str) -> JsonObject:
        """Check a folder before a capture, and report what was found there (D-19)."""
        with _Guard("validate_game_folder"):
            try:
                root = locate.validate(Path(path))
            except PatchScoutError as error:
                return {"valid": False, "reason": str(error)}
            return {
                "valid": True,
                "path": str(root),
                "game_build": locate.game_build(root),
                "moved": str(root) != str(Path(path)),
            }

    def start_capture(
        self,
        path: str,
        label: str,
        prerelease: bool = False,
        capture_anyway: bool = False,
    ) -> JsonObject:
        """Start a capture on a worker thread; the page polls `get_capture_status`."""
        with _Guard("start_capture"):
            if self._capture is not None and not self._capture.done:
                return {"started": False, "reason": "a capture is already running"}
            settings = self._settings.load()
            request = CaptureRequest(
                game_folder=Path(path),
                label=label,
                prerelease=prerelease,
                raw_backups=settings.raw_backups,
                capture_anyway=capture_anyway,
            )
            cancel = threading.Event()
            state = _Capture(thread=threading.Thread(), cancel=cancel, label=label)
            state.thread = threading.Thread(
                target=self._run_capture, args=(request, state), daemon=True
            )
            self._capture = state
            self._log = []
            state.thread.start()
            return {"started": True}

    def get_capture_status(self) -> JsonObject | None:
        """What the running or last capture is doing."""
        return self._capture.to_json() if self._capture else None

    def cancel_capture(self) -> JsonObject:
        """Stop the running capture."""
        with _Guard("cancel_capture"):
            if self._capture is not None:
                self._capture.cancel.set()
            return {"cancelled": True}

    def clear_capture(self) -> JsonObject:
        """Forget a finished capture, so the list stops showing its row."""
        if self._capture is not None and self._capture.done:
            self._capture = None
        return {"cleared": True}

    # --- comparison --------------------------------------------------------------------------

    def compare_versions(
        self, old_id: str, new_id: str, show_unreachable: bool = False
    ) -> JsonObject:
        """Compare two versions; old and new are assigned by game build (D-32)."""
        with _Guard("compare_versions"):
            first, second = self._snapshot(old_id), self._snapshot(new_id)
            older, newer = order(first, second)
            change_set = compare(
                older,
                newer,
                options=Options(show_unreachable=show_unreachable, language=self._language),
                old_info=self._side_info(older.capture_id),
                new_info=self._side_info(newer.capture_id),
            )
            self._settings.remember_comparison(older.capture_id, newer.capture_id)
            return change_set.to_json()

    def get_icons(self, hashes: Sequence[str]) -> JsonObject:
        """Data URIs for the icons a view is about to show."""
        with _Guard("get_icons"):
            found: JsonObject = {}
            for digest in list(hashes)[:MAX_ICONS]:
                data = self._icons.read_png(digest) if isinstance(digest, str) else None
                if data is not None:
                    found[digest] = "data:image/png;base64," + base64.b64encode(data).decode()
            return found

    # --- export ------------------------------------------------------------------------------

    def export_text(
        self,
        old_id: str,
        new_id: str,
        low_priority: bool = False,
        civs: Sequence[str] | None = None,
    ) -> JsonObject:
        """The plain-text export of the current comparison (P-13)."""
        with _Guard("export_text"):
            change_set, filters = self._for_export(old_id, new_id, low_priority, civs)
            return {"text": render_text(change_set, self._catalog, filters)}

    def save_export(
        self,
        old_id: str,
        new_id: str,
        kind: str = "text",
        low_priority: bool = False,
        civs: Sequence[str] | None = None,
    ) -> JsonObject:
        """Write the export where the user chooses; `kind` is `text` or `html`."""
        with _Guard("save_export"):
            change_set, filters = self._for_export(old_id, new_id, low_priority, civs)
            if kind == "html":
                content = render_html(
                    change_set,
                    self._catalog,
                    icons=self._icons.read_png,
                    filters=filters,
                    tool_version=self._app_version,
                )
                suffix, name = ".html", "patch-scout-comparison.html"
            else:
                content = render_text(change_set, self._catalog, filters)
                suffix, name = ".txt", "patch-scout-comparison.txt"
            path = self._ask_where_to_save(name, suffix)
            if path is None:
                return {"saved": False}
            Path(path).write_text(content, encoding="utf-8")
            return {"saved": True, "path": path}

    # --- settings and diagnostics --------------------------------------------------------------

    def get_settings(self) -> JsonObject:
        """The current settings, and where the data folder is."""
        with _Guard("get_settings"):
            return _settings_json(self._settings.load(), self._folder)

    def update_settings(self, raw_backups: bool | None = None) -> JsonObject:
        """Change a setting the Settings screen offers."""
        with _Guard("update_settings"):
            current = self._settings.load()
            if raw_backups is not None:
                current = replace(current, raw_backups=raw_backups)
            return _settings_json(self._settings.save(current), self._folder)

    def purge_backups(self) -> JsonObject:
        """Delete every raw backup (P-19)."""
        with _Guard("purge_backups"):
            return {"removed": BackupStore(self._folder).purge()}

    def get_diagnostics(self, capture_id: str | None = None) -> JsonObject:
        """Everything the Diagnostics window shows (architecture.md)."""
        with _Guard("get_diagnostics"):
            environment: JsonObject = {
                "app_version": self._app_version,
                "genieutils_version": _package_version("genieutils-py"),
                "pillow_version": _package_version("pillow"),
                "python": sys.version.split()[0],
                "renderer": _renderer(),
                "windows": platform.platform(),
                "data_folder": str(self._folder.root),
            }
            snapshot = self._snapshot(capture_id) if capture_id else None
            log: list[JsonValue] = list(self._log)
            return {
                "environment": environment,
                "log": log,
                "versions": self._versions(),
                "snapshot": _diagnostics_json(snapshot) if snapshot else None,
            }

    def get_snapshot_section(self, capture_id: str, section: str, key: str = "") -> JsonValue:
        """One section of a snapshot, for the Diagnostics inspector."""
        with _Guard("get_snapshot_section"):
            snapshot = self._snapshot(capture_id)
            value = snapshot.to_json().get(section)
            if key and isinstance(value, dict):
                return value.get(key)
            if key and isinstance(value, list) and key.isdigit():
                index = int(key)
                return value[index] if 0 <= index < len(value) else None
            return _trimmed(value)

    # --- internals ---------------------------------------------------------------------------

    def _run_capture(self, request: CaptureRequest, state: _Capture) -> None:
        def on_progress(progress: Progress) -> None:
            state.phase = progress.phase
            state.fraction = progress.fraction
            state.detail = progress.detail
            self._log.append(f"{progress.phase} {progress.fraction:.0%} {progress.detail}".strip())

        try:
            result = runner.run(
                request, self._folder, on_progress=on_progress, cancelled=state.cancel
            )
        except runner.CaptureCancelledError:
            state.result = {"cancelled": True}
        except PatchScoutError as error:
            logger.exception("the capture failed")
            state.result = {"error": str(error)}
        except Exception as error:  # a capture must never take the app down
            logger.exception("the capture failed unexpectedly")
            state.result = {"error": f"{type(error).__name__}: {error}"}
        else:
            self._settings.remember_game_folder(request.game_folder)
            # The capture wrote its library entry through its own Library (capture/runner.py).
            self._library.reload()
            state.result = {
                "capture_id": result.snapshot.capture_id if result.snapshot else None,
                "identical_to": result.identical_to,
                "stopped_early": result.stopped_early,
                "warnings": list(result.warnings),
                "stats_available": result.snapshot.stats_available if result.snapshot else False,
                "stats_reason": (
                    result.snapshot.flags.get("stats_unavailable_reason")
                    if result.snapshot
                    else None
                ),
                "versions": self._versions(),
            }
        finally:
            state.fraction = 1.0
            state.done = True

    def _versions(self) -> list[JsonValue]:
        versions: list[tuple[tuple[int, ...], str, JsonObject]] = []
        for capture_id in self._snapshots.capture_ids():
            try:
                snapshot = self._snapshot(capture_id)
            except PatchScoutError:
                logger.warning("snapshot %s could not be read; leaving it out", capture_id)
                continue
            entry = self._library.get(capture_id)
            versions.append(
                (_build_key(snapshot), snapshot.captured_at, _version_json(snapshot, entry))
            )
        versions.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return [item[2] for item in versions]

    def _snapshot(self, capture_id: str) -> Snapshot:
        if capture_id not in self._loaded:
            self._loaded[capture_id] = self._snapshots.load(capture_id)
        return self._loaded[capture_id]

    def _side_info(self, capture_id: str) -> SideInfo:
        entry = self._library.get(capture_id)
        if entry is None:
            return SideInfo()
        return SideInfo(label=entry.label, prerelease=entry.prerelease)

    def _for_export(
        self, old_id: str, new_id: str, low_priority: bool, civs: Sequence[str] | None
    ) -> tuple[Any, Filters]:
        first, second = self._snapshot(old_id), self._snapshot(new_id)
        older, newer = order(first, second)
        change_set = compare(
            older,
            newer,
            options=Options(language=self._language),
            old_info=self._side_info(older.capture_id),
            new_info=self._side_info(newer.capture_id),
        )
        filters = Filters(
            low_priority=low_priority,
            civs=tuple(civs) if civs else None,
        )
        return change_set, filters

    def _ask_where_to_save(self, name: str, suffix: str) -> str | None:
        if self._window is None:
            return None
        import webview

        chosen = self._window.create_file_dialog(
            webview.SAVE_DIALOG, save_filename=name, file_types=(f"Export (*{suffix})",)
        )
        if not chosen:
            return None
        return str(chosen if isinstance(chosen, str) else chosen[0])


class _Guard:
    """Log and re-raise anything a page call raises, so nothing fails silently."""

    def __init__(self, name: str) -> None:
        self._name = name

    def __enter__(self) -> "_Guard":
        return self

    def __exit__(self, kind: object, error: object, trace: object) -> None:
        """Never suppresses: the page sees the error, and the log keeps the traceback."""
        if isinstance(error, BaseException):
            logger.error("%s failed: %s", self._name, error)
            logger.debug("%s", "".join(traceback.format_exception(error)))


def _version_json(snapshot: Snapshot, entry: LibraryEntry | None) -> JsonObject:
    return {
        "capture_id": snapshot.capture_id,
        "label": entry.label if entry else snapshot.capture_id,
        "prerelease": entry.prerelease if entry else False,
        "notes": entry.notes if entry else "",
        "origin": entry.origin if entry else "imported",
        "game_build": snapshot.game_build,
        "captured_at": snapshot.captured_at,
        "stats_available": snapshot.stats_available,
        "stats_reason": snapshot.flags.get("stats_unavailable_reason"),
        "format_verified": snapshot.flags.get("format_verified"),
    }


def _entry_json(entry: LibraryEntry) -> JsonObject:
    return {
        "capture_id": entry.capture_id,
        "label": entry.label,
        "prerelease": entry.prerelease,
        "notes": entry.notes,
        "origin": entry.origin,
    }


def _settings_json(settings: Settings, folder: DataFolder) -> JsonObject:
    recent: list[JsonValue] = list(settings.recent_game_folders)
    return {
        "raw_backups": settings.raw_backups,
        "language": settings.language,
        "data_folder": str(folder.root),
        "recent_game_folders": recent,
    }


def _diagnostics_json(snapshot: Snapshot) -> JsonObject:
    sections: list[JsonValue] = [name for name in sorted(snapshot.to_json())]
    return {
        "capture_id": snapshot.capture_id,
        "meta": snapshot.meta,
        "flags": snapshot.flags,
        "sections": sections,
        "source_count": len(snapshot.sources),
    }


def _trimmed(value: JsonValue) -> JsonValue:
    """Keep a section small enough to show: the inspector asks for one key at a time."""
    if isinstance(value, dict) and len(value) > 200:
        keys: list[JsonValue] = [name for name in sorted(value)[:2000]]
        return {"_keys": keys, "_count": len(value)}
    if isinstance(value, list) and len(value) > 200:
        return value[:200]
    return value


def _build_key(snapshot: Snapshot) -> tuple[int, ...]:
    build = snapshot.game_build or ""
    return tuple(int(part) if part.isdigit() else -1 for part in build.split("."))


def _package_version(name: str) -> str | None:
    import importlib.metadata

    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def _renderer() -> str:
    try:
        import webview
    except ImportError:  # the API is also used from tests without a GUI
        return "none"
    return str(getattr(webview, "renderer", "unknown"))
