# SPDX-License-Identifier: GPL-3.0-or-later
"""The data the fake pywebview bridge answers with, shared by the UI tests (D-41)."""

from typing import Any

from playwright.sync_api import Page

from patch_scout.i18n.catalog import load_catalog


def version(capture_id: str, label: str, **overrides: Any) -> dict[str, Any]:
    """One row of the version list."""
    row: dict[str, Any] = {
        "capture_id": capture_id,
        "label": label,
        "prerelease": False,
        "notes": "",
        "origin": "captured",
        "game_build": "101.103.48987.0",
        "captured_at": "2026-09-15T10:00:00Z",
        "stats_available": True,
        "stats_reason": None,
        "format_verified": True,
    }
    return row | overrides


def startup_data(**overrides: Any) -> dict[str, Any]:
    """What `Api.get_startup()` returns, with the real English messages."""
    data: dict[str, Any] = {
        "language": "en",
        "messages": load_catalog("en").messages(),
        "app_version": "0.0.0-test",
        "versions": [],
        "settings": {
            "raw_backups": True,
            "language": "en",
            "data_folder": "C:/Users/test/AppData/Local/PatchScout",
            "recent_game_folders": [],
        },
        "last_comparison": [],
        "capture": None,
    }
    return data | overrides


def change(**overrides: Any) -> dict[str, Any]:
    """One change, shaped the way `diff.model.Change.to_json` writes it."""
    row: dict[str, Any] = {
        "category": "unit_stats",
        "kind": "modified",
        "entity": {"kind": "unit", "id": "38", "name": "Knight", "where": "Stable", "icon": None},
        "scope": {"kind": "all", "civs": []},
        "field": {"key": "field.hit_points", "args": {}},
        "stat_icon": "hp",
        "old": "100",
        "new": "110",
        "words": [],
        "detail": None,
        "raw": None,
        "civ": None,
        "low_priority": False,
    }
    return row | overrides


def change_set(**overrides: Any) -> dict[str, Any]:
    """A small change set covering Overall, one civ, a word diff and a notice."""
    data: dict[str, Any] = {
        "old": {
            "capture_id": "old",
            "label": "Live build",
            "game_build": "101.103.48987.0",
            "captured_at": "2026-09-15T10:00:00Z",
            "prerelease": False,
            "stats_available": True,
        },
        "new": {
            "capture_id": "new",
            "label": "PUP build",
            "game_build": "101.103.49000.0",
            "captured_at": "2026-09-16T10:00:00Z",
            "prerelease": True,
            "stats_available": True,
        },
        "identical": False,
        "notices": [],
        "civs": [
            {
                "internal_name": "Franks",
                "name": "Franks",
                "era": "base",
                "icon": None,
                "added": False,
                "count": 1,
            },
            {
                "internal_name": "Spartans",
                "name": "Spartans",
                "era": "antiquity",
                "icon": None,
                "added": True,
                "count": 0,
            },
        ],
        "changes": [
            change(),
            change(
                category="civ_availability",
                kind="availability",
                civ="Franks",
                scope={"kind": "some", "civs": ["Franks"]},
                entity={
                    "kind": "unit",
                    "id": "4",
                    "name": "Archer",
                    "where": "Archery Range",
                    "icon": None,
                },
                field={"key": "field.node_status", "args": {}},
                stat_icon=None,
                old="NotAvailable",
                new="ResearchedCompleted",
            ),
            change(
                category="text",
                kind="text_changed",
                low_priority=True,
                entity={
                    "kind": "string",
                    "id": "26083",
                    "name": "26083",
                    "where": None,
                    "icon": None,
                },
                field={"key": "field.help_text", "args": {}},
                stat_icon=None,
                old=None,
                new=None,
                words=[
                    {"kind": "same", "text": "A ranged "},
                    {"kind": "removed", "text": "unit."},
                    {"kind": "added", "text": "foot soldier."},
                ],
            ),
        ],
        "counts": {"overall": 2, "total": 3},
    }
    return data | overrides


def fixture_data(**overrides: Any) -> dict[str, Any]:
    """Everything the fake bridge answers with."""
    data: dict[str, Any] = {
        "startup": startup_data(),
        "details": {
            "__default": {
                "capture_id": "one",
                "label": "Live build",
                "prerelease": False,
                "notes": "",
                "origin": "captured",
                "game_build": "101.103.48987.0",
                "captured_at": "2026-09-15T10:00:00Z",
                "stats_available": True,
                "stats_reason": None,
                "format_verified": True,
                "source_path": "D:/Games/AoE2DE",
                "civ_count": 60,
                "meta": {"dat_format_version": "VER 8.9", "dat_layout_version": "VER 8.9"},
                "flags": {},
            }
        },
        "candidates": [],
        "browsed": None,
        "validation": {"valid": True, "path": "D:/Games/AoE2DE", "game_build": "101.103.48987.0"},
        "captureStatuses": [],
        "changeSet": change_set(),
        "icons": {},
        "exportText": "Patch Scout - what changed\n",
        "diagnostics": {
            "environment": {"app_version": "0.0.0-test", "python": "3.12.0"},
            "log": ["folder 0% ", "save 95% "],
            "versions": [version("one", "Live build")],
            "snapshot": None,
        },
    }
    return data | overrides


def calls(page: Page, name: str) -> list[list[Any]]:
    """Every call the page made to one API method, with its arguments."""
    recorded = page.evaluate("() => window.__calls")
    return [entry["args"] for entry in recorded if entry["name"] == name]
