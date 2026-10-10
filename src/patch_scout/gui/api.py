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
from patch_scout.diff import ChangeSet, Options, SideInfo, compare, order
from patch_scout.errors import PatchScoutError
from patch_scout.gui.logs import RecentProblems
from patch_scout.i18n.catalog import Catalog
from patch_scout.report import Filters, render_html, render_text
from patch_scout.report.present import present
from patch_scout.snapshot import JsonObject, JsonValue, Snapshot
from patch_scout.store import (
    BackupStore,
    DataFolder,
    IconStore,
    Library,
    LibraryEntry,
    SnapshotStore,
    archive,
)
from patch_scout.store.settings import Settings, SettingsStore
from patch_scout.store.snapshots import SnapshotIndex
from patch_scout.tree import build as tree_build

logger = logging.getLogger(__name__)

# How many icons the page may ask for at once; a comparison shows far fewer than this.
# Whole snapshots kept in memory: a comparison needs two.
MAX_LOADED: Final = 2
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
        *,
        recent: RecentProblems | None = None,
        log_file: Path | None = None,
    ) -> None:
        self._catalog = catalog
        self._recent = recent
        self._log_file = log_file
        self._language = language
        self._app_version = app_version
        self._folder = folder or DataFolder.default()
        self._settings = SettingsStore(self._folder)
        self._snapshots = SnapshotStore(self._folder)
        self._library = Library(self._folder)
        self._icons = IconStore(self._folder)
        self._capture: _Capture | None = None
        # Insertion-ordered: the first key is the snapshot used least recently.
        self._loaded: dict[str, Snapshot] = {}
        self._window: Any = None
        self._last_comparison: tuple[tuple[object, ...], ChangeSet] | None = None
        self._log: list[str] = []
        # pywebview runs each call from the page on its own thread. Loading and comparing take
        # seconds and hundreds of MB, so they run one at a time: a second caller waits and then
        # reuses the first one's result. Starting a capture is checked and set under its own lock.
        self._work_lock = threading.RLock()
        self._capture_lock = threading.Lock()

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

    def get_messages(self) -> JsonObject:
        """The language and its messages: all the page needs to say that it couldn't start."""
        return {"language": self._language, "messages": dict(self._catalog.messages())}

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
            return _version_json(SnapshotIndex.of(snapshot), entry) | {
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
        """Delete a snapshot, its library entry, and the raw backups no other version uses."""
        with _Guard("delete_version"):
            try:
                self._snapshots.delete(capture_id)
            except OSError as exc:  # locked by an antivirus or a sync tool: nothing is lost
                logger.error("version %s couldn't be deleted: %s", capture_id, exc)
                return {"deleted": False, "error": str(exc), "versions": self._versions()}
            self._library.remove(capture_id)
            with self._work_lock:
                self._loaded.pop(capture_id, None)
            try:
                BackupStore(self._folder).forget(capture_id)
            except OSError as exc:  # the version is gone; leftover backups only cost disk space
                logger.warning("backups of %s couldn't all be deleted: %s", capture_id, exc)
            return {"deleted": True, "versions": self._versions()}

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
        with _Guard("start_capture"), self._capture_lock:
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
            change_set = self._compared(older, newer, show_unreachable=show_unreachable)
            try:
                self._settings.remember_comparison(older.capture_id, newer.capture_id)
            except OSError as exc:  # only reopening it at the next launch is lost
                logger.warning("the comparison couldn't be remembered: %s", exc)
            return present(change_set, self._catalog).to_json()

    def get_tech_tree(
        self,
        old_id: str,
        new_id: str,
        civ: str,
        details: bool = False,
        technical: bool = False,
        low_priority: bool = False,
    ) -> JsonObject | None:
        """One civ's tech tree with the comparison's changes marked on it (D-39)."""
        with _Guard("get_tech_tree"):
            first, second = self._snapshot(old_id), self._snapshot(new_id)
            older, newer = order(first, second)
            if civ not in older.tech_trees and civ not in newer.tech_trees:
                return None
            change_set = self._compared(older, newer, show_unreachable=False)
            return tree_build.build(
                older,
                newer,
                present(change_set, self._catalog),
                civ,
                details=details,
                technical=technical,
                low_priority=low_priority,
                language=self._language,
            )

    def get_icons(self, hashes: Sequence[str]) -> JsonObject:
        """Data URIs for the icons a view is about to show."""
        with _Guard("get_icons"):
            found: JsonObject = {}
            for digest in list(hashes)[:MAX_ICONS]:
                try:
                    data = self._icons.read_png(digest) if isinstance(digest, str) else None
                except OSError:  # locked by an antivirus, say: that icon only is missing
                    logger.warning("icon %s could not be read", digest)
                    continue
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
        unnamed: bool = False,
        details: bool = False,
        technical: bool = False,
    ) -> JsonObject:
        """The plain-text export of the current comparison (P-13)."""
        with _Guard("export_text"):
            filters = _filters(low_priority, civs, unnamed, details, technical)
            change_set = self._for_export(old_id, new_id)
            return {"text": render_text(change_set, self._catalog, filters)}

    def save_export(
        self,
        old_id: str,
        new_id: str,
        kind: str = "text",
        low_priority: bool = False,
        civs: Sequence[str] | None = None,
        unnamed: bool = False,
        details: bool = False,
        technical: bool = False,
        path: str | None = None,
    ) -> JsonObject:
        """Write the export where the user chooses; `kind` is `text` or `html`."""
        with _Guard("save_export"):
            filters = _filters(low_priority, civs, unnamed, details, technical)
            change_set = self._for_export(old_id, new_id)
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
            chosen = path or self._ask_where_to_save(name, suffix)
            if chosen is None:
                return {"saved": False}
            try:
                Path(chosen).write_text(content, encoding="utf-8")
            except OSError as exc:
                return _not_saved("save_export", chosen, exc)
            return {"saved": True, "path": chosen}

    def save_images(self, images: Sequence[str], name: str, path: str | None = None) -> JsonObject:
        """Write the image export: PNG data URLs drawn by the page; asks where unless `path`.

        Several parts of one page are numbered: `<name>-1.png`, `<name>-2.png`...
        """
        with _Guard("save_images"):
            decoded = [_png(image) for image in images]
            chosen = path or self._ask_where_to_save(_file_name(name) + ".png", ".png")
            if chosen is None or not decoded:
                return {"saved": False}
            target = Path(chosen)
            paths = (
                [target]
                if len(decoded) == 1
                else [
                    target.with_name(f"{target.stem}-{index}{target.suffix or '.png'}")
                    for index in range(1, len(decoded) + 1)
                ]
            )
            try:
                for file, data in zip(paths, decoded, strict=True):
                    file.write_bytes(data)
            except OSError as exc:
                for file in paths:  # no half set of parts
                    file.unlink(missing_ok=True)
                return _not_saved("save_images", chosen, exc)
            return {"saved": True, "path": str(paths[0])}

    # --- archives (P-21) -----------------------------------------------------------------------

    def export_version(self, capture_id: str, path: str | None = None) -> JsonObject:
        """Write one version as an archive; asks where unless `path` is given."""
        with _Guard("export_version"):
            entry = self._library.get(capture_id)
            name = _file_name(entry.label if entry else capture_id) + archive.SUFFIX
            chosen = path or self._ask_where_to_save(name, archive.SUFFIX)
            if chosen is None:
                return {"saved": False}
            try:
                archive.export(
                    self._folder,
                    capture_id,
                    Path(chosen),
                    tool_version=self._app_version,
                    notice=archive.NOTICE_TEXT,
                )
            except OSError as exc:
                return _not_saved("export_version", chosen, exc)
            return {"saved": True, "path": chosen}

    def import_version(self, path: str | None = None) -> JsonObject:
        """Add the version an archive holds; asks for the file unless `path` is given.

        An archive the app can't use is an answer, not an error: `error` names why, and the
        page shows the matching message.
        """
        with _Guard("import_version"):
            chosen = path or self._ask_which_archive()
            if chosen is None:
                return {"imported": False, "error": None}
            try:
                result = archive.import_(self._folder, Path(chosen))
            except archive.ArchiveError as exc:
                logger.warning("import of %s refused: %s", chosen, exc)
                return {"imported": False, "error": exc.reason}
            except (OSError, PatchScoutError) as exc:  # the data folder can't take it
                logger.error("import of %s couldn't be written: %s", chosen, exc)
                return {"imported": False, "error": "write_failed"}
            self._library.reload()
            return {"imported": True, "capture_id": result.capture_id, "added": result.added}

    def choose_archive(self) -> str | None:
        """Open the native file picker for an archive; None when the user cancels."""
        with _Guard("choose_archive"):
            return self._ask_which_archive()

    def _ask_which_archive(self) -> str | None:
        if self._window is None:
            return None
        import webview

        chosen = self._window.create_file_dialog(
            webview.OPEN_DIALOG, file_types=(f"Patch Scout version (*{archive.SUFFIX})",)
        )
        if not chosen:
            return None
        return str(chosen if isinstance(chosen, str) else chosen[0])

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
                "pillow_version": _package_version("pillow", module="PIL"),
                "python": sys.version.split()[0],
                "renderer": _renderer(),
                "windows": platform.platform(),
                "data_folder": str(self._folder.root),
                "log_file": str(self._log_file) if self._log_file else "",
            }
            snapshot = self._snapshot(capture_id) if capture_id else None
            log: list[JsonValue] = list(self._log)
            return {
                "environment": environment,
                "log": log,
                "problems": list(self._recent.lines()) if self._recent else [],
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
            try:
                self._settings.remember_game_folder(request.game_folder)
            except OSError as exc:  # only the folder suggestion is lost, not the capture
                logger.warning("the game folder couldn't be remembered: %s", exc)
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
                index = self._snapshots.index(capture_id)  # never the whole snapshot
            except PatchScoutError:
                logger.warning("snapshot %s could not be read; leaving it out", capture_id)
                continue
            entry = self._library.get(capture_id)
            versions.append(
                (_build_key(index.game_build), index.captured_at, _version_json(index, entry))
            )
        versions.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return [item[2] for item in versions]

    def _snapshot(self, capture_id: str) -> Snapshot:
        """A whole snapshot; only the two used last stay in memory (~164 MB each)."""
        with self._work_lock:
            snapshot = self._loaded.pop(capture_id, None) or self._snapshots.load(capture_id)
            self._loaded[capture_id] = snapshot
            while len(self._loaded) > MAX_LOADED:
                self._loaded.pop(next(iter(self._loaded)))
            return snapshot

    def _side_info(self, capture_id: str) -> SideInfo:
        entry = self._library.get(capture_id)
        if entry is None:
            return SideInfo()
        return SideInfo(label=entry.label, prerelease=entry.prerelease)

    def _for_export(self, old_id: str, new_id: str) -> ChangeSet:
        first, second = self._snapshot(old_id), self._snapshot(new_id)
        older, newer = order(first, second)
        return self._compared(older, newer, show_unreachable=False)

    def _compared(self, older: Snapshot, newer: Snapshot, *, show_unreachable: bool) -> ChangeSet:
        """Compare two snapshots, reusing the last result: a real comparison takes seconds.

        Labels and pre-release flags are part of the result, so they are part of the key too.
        """
        old_info = self._side_info(older.capture_id)
        new_info = self._side_info(newer.capture_id)
        key = (older.capture_id, newer.capture_id, show_unreachable, old_info, new_info)
        with self._work_lock:
            if self._last_comparison is not None and self._last_comparison[0] == key:
                return self._last_comparison[1]
            change_set = compare(
                older,
                newer,
                options=Options(show_unreachable=show_unreachable, language=self._language),
                old_info=old_info,
                new_info=new_info,
            )
            self._last_comparison = (key, change_set)
            return change_set

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


def _version_json(index: SnapshotIndex, entry: LibraryEntry | None) -> JsonObject:
    return {
        "capture_id": index.capture_id,
        "label": entry.label if entry else index.capture_id,
        "prerelease": entry.prerelease if entry else False,
        "notes": entry.notes if entry else "",
        "origin": entry.origin if entry else "imported",
        "game_build": index.game_build,
        "captured_at": index.captured_at,
        "stats_available": index.stats_available,
        "stats_reason": index.stats_unavailable_reason,
        "format_verified": index.format_verified,
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


def _build_key(build: str | None) -> tuple[int, ...]:
    return tuple(int(part) if part.isdigit() else -1 for part in (build or "").split("."))


def _package_version(name: str, module: str | None = None) -> str | None:
    """A package's version, from its metadata, else from the module's own `__version__`.

    The packaged build doesn't carry every package's metadata: Pillow's is missing there.
    """
    import importlib
    import importlib.metadata

    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        pass
    if module is None:
        return None
    try:
        version = getattr(importlib.import_module(module), "__version__", None)
    except ImportError:
        return None
    return version if isinstance(version, str) else None


def _renderer() -> str:
    try:
        import webview
    except ImportError:  # the API is also used from tests without a GUI
        return "none"
    return str(getattr(webview, "renderer", "unknown"))


def _filters(
    low_priority: bool,
    civs: Sequence[str] | None,
    unnamed: bool,
    details: bool,
    technical: bool,
) -> Filters:
    return Filters(
        low_priority=low_priority,
        civs=tuple(civs) if civs else None,
        unnamed=unnamed,
        details=details,
        technical=technical,
    )


def _file_name(label: str) -> str:
    """A label made safe as a Windows file name."""
    cleaned = "".join("_" if char in r'<>:"/\|?*' or ord(char) < 32 else char for char in label)
    return cleaned.strip(" .") or "version"


MAX_IMAGE_BYTES: Final = 20_000_000
_PNG_URL: Final = "data:image/png;base64,"
PNG_SIGNATURE: Final = bytes([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A])


def _png(data_url: str) -> bytes:
    """The bytes of a PNG data URL drawn by the page, refusing anything else."""
    if not data_url.startswith(_PNG_URL) or len(data_url) > MAX_IMAGE_BYTES * 4 // 3 + 64:
        raise ValueError("not a PNG image from the page")
    data = base64.b64decode(data_url[len(_PNG_URL) :], validate=True)
    if not data.startswith(PNG_SIGNATURE):
        raise ValueError("not a PNG image from the page")
    return data


def _not_saved(call: str, path: str, error: OSError) -> JsonObject:
    """A save the system refused (read-only folder, full disk, locked file): say why."""
    logger.error("%s couldn't write %s: %s", call, path, error)
    return {"saved": False, "error": error.strerror or str(error)}
