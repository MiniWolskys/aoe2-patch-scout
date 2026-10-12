# SPDX-License-Identifier: GPL-3.0-or-later
"""The data the fake pywebview bridge answers with, shared by the UI tests (D-41)."""

from typing import Any

from playwright.sync_api import Page, expect

from patch_scout.i18n.catalog import load_catalog

# A 1x1 PNG, enough for an <img> to load.
PIXEL = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


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
        "level": "headline",
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
    merged = data | overrides
    if "entries" not in overrides:
        merged["entries"] = [entry(item) for item in merged["changes"]]
    # Entries refer to their changes by position, as `ChangeSet.to_json` writes them.
    merged["entries"] = [
        item | {"changes": [merged["changes"].index(change) for change in item["changes"]]}
        for item in merged["entries"]
    ]
    return merged


def entry(*changes: dict[str, Any], **overrides: Any) -> dict[str, Any]:
    """An entry of the given changes; `change_set` turns them into positions."""
    first = changes[0]
    row: dict[str, Any] = {
        "category": first["category"],
        "kind": first["kind"] if len(changes) == 1 else "modified",
        "entity": first["entity"],
        "scope": first["scope"],
        "civ": first["civ"],
        "changes": list(changes),
        "hidden": 0,
        "low_priority": first["low_priority"],
    }
    return row | overrides


def patch_notes(**overrides: Any) -> dict[str, Any]:
    """What `Api.get_patch_notes` answers: the document, as `Notes.to_json` writes it, and text."""

    def item(text: str, *children: dict[str, Any]) -> dict[str, Any]:
        return {"text": text, "children": list(children)}

    data: dict[str, Any] = {
        "title": "Patch notes: Live build → PUP build (pre-release)",
        "disclaimer": "Written by Patch Scout from the game's data. These are not the official"
        " patch notes.",
        "notices": [],
        "sections": [
            {
                "kind": "general",
                "title": "General",
                "groups": [
                    {
                        "title": "Unit stats",
                        "civ": None,
                        "icon": None,
                        "items": [item("Knight hit points increased from 100 → 110.")],
                    }
                ],
            },
            {
                "kind": "civs",
                "title": "Civilizations",
                "groups": [
                    {
                        "title": "Franks",
                        "civ": "Franks",
                        "icon": {"hash": "crest-franks"},
                        "items": [
                            item("NEW: Ordonnance Companies:", item("Cost: 400 food, 250 gold")),
                            item("Gain access to Archer."),
                        ],
                    }
                ],
            },
        ],
        "closing": "1 more change isn't in these notes.",
        "empty": None,
        "text": "Patch notes: Live build → PUP build (pre-release)\n- Knight hit points\n",
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
        "entity": entity_details(),
        "icons": {},
        "exportText": "Patch Scout - what changed\n",
        "patchNotes": patch_notes(),
        "diagnostics": {
            "environment": {"app_version": "0.0.0-test", "python": "3.12.0"},
            "log": ["folder 0% ", "save 95% "],
            "versions": [version("one", "Live build")],
            "snapshot": None,
        },
    }
    return data | overrides


def show_changes(page: Page) -> None:
    """Switch an open comparison from the patch notes, where it opens (D-51), to its changes."""
    expect(page.locator("#comparison-notes")).to_have_attribute("aria-pressed", "true")
    page.locator("#comparison-notes").click()
    expect(page.locator("#comparison-page")).to_be_visible()


def calls(page: Page, name: str) -> list[list[Any]]:
    """Every call the page made to one API method, with its arguments."""
    recorded = page.evaluate("() => window.__calls")
    return [entry["args"] for entry in recorded if entry["name"] == name]


def tree_node(key: str, name: str, column: int, row: int, **overrides: Any) -> dict[str, Any]:
    """One tile of a tech tree, shaped the way `tree.build` writes it."""
    use_type, _, rest = key.partition(":")
    node: dict[str, Any] = {
        "key": key,
        "id": int(rest.partition("@")[0]),
        "kind": use_type.lower(),
        "node_type": "Unit" if use_type == "Unit" else use_type,
        "name": name,
        "old_name": None,
        "available": True,
        "mark": None,
        "icon": None,
        "group": 0,
        "column": column,
        "row": row,
        "tooltip": {
            "lines": [
                [
                    {
                        "kind": "text",
                        "text": name,
                        "bold": True,
                        "italic": False,
                        "grey": False,
                        "stat": None,
                        "resource": None,
                        "amount": None,
                    }
                ]
            ],
            "stats": {},
            "cost": {"old": [], "new": []},
        },
        "changes": [],
    }
    return node | overrides


def _run(kind: str, **fields: Any) -> dict[str, Any]:
    run: dict[str, Any] = {
        "kind": kind,
        "text": "",
        "bold": False,
        "italic": False,
        "grey": False,
        "stat": None,
        "resource": None,
        "amount": None,
    }
    return run | fields


def tech_tree(**overrides: Any) -> dict[str, Any]:
    """Two buildings: an Archery Range with a changed, a gained and a lost node, and a Barracks."""
    archer_tooltip = {
        "lines": [
            [
                _run("text", text="Create "),
                _run("text", text="Archer", bold=True),
                _run("text", text=" ("),
                _run("cost"),
                _run("text", text=")"),
            ],
            [_run("text", text="All-purpose Foot Archer.")],
            [
                _run("stat", stat="hp"),
                _run("text", text=" "),
                _run("stat", stat="attack"),
                _run("text", text=" "),
                _run("stat", stat="range"),
            ],
        ],
        "stats": {
            "hp": {"old": "30", "new": "35"},
            "attack": {"old": "4", "new": "4"},
            "range": {"old": None, "new": None},
        },
        "cost": {
            "old": [{"resource": "wood", "amount": 25}, {"resource": "gold", "amount": 45}],
            "new": [{"resource": "wood", "amount": 25}, {"resource": "gold", "amount": 40}],
        },
    }
    hp = change(entity={"kind": "unit", "id": "4", "name": "Archer", "where": None, "icon": None})
    data: dict[str, Any] = {
        "civ": "Franks",
        "new_civ": False,
        "removed_civ": False,
        "columns": 3,
        "groups": 2,
        "rows": 8,
        "nodes": [
            tree_node("Building:87", "Archery Range", 0, 2, node_type="BuildingTech"),
            tree_node(
                "Unit:4", "Archer", 0, 3, mark="changed", tooltip=archer_tooltip, changes=[hp]
            ),
            tree_node("Unit:24", "Crossbowman", 0, 5, mark="gained", node_type="UnitUpgrade"),
            tree_node("Tech:437", "Thumb Ring", 1, 5, mark="lost", node_type="Research"),
            tree_node("Building:12", "Barracks", 2, 0, group=1, node_type="BuildingTech"),
            tree_node("Unit:74", "Militia", 2, 1, group=1, available=False),
        ],
        "links": [["Unit:24", "Unit:4"]],
    }
    return data | overrides


def detail_row(
    key: str, old: str | None, new: str | None, state: str, **args: Any
) -> dict[str, Any]:
    """One line of the details panel, shaped the way `entity.details` writes it."""
    return {
        "field": {"key": key, "args": args},
        "stat_icon": "hp" if key == "field.hit_points" else None,
        "old": old,
        "new": new,
        "state": state,
    }


def entity_details(**overrides: Any) -> dict[str, Any]:
    """A Militia's details: a changed and an unchanged stat, a civ bonus and a tech."""
    data: dict[str, Any] = {
        "kind": "unit",
        "id": 74,
        "name": "Militia",
        "old_name": None,
        "icon": None,
        "age": 1,
        "civ": "Franks",
        "presence": "both",
        "available": {"old": True, "new": True},
        "stats_missing": {"old": False, "new": False},
        "description": [
            [_run("text", text="All-purpose Infantry.")],
            [_run("text", text="Upgrades: attack (Blacksmith).", grey=True, italic=True)],
        ],
        "sections": [
            {
                "key": "stats",
                "title": {"key": "entity.section.stats", "args": {}},
                "rows": [
                    detail_row("field.hit_points", "40", "45", "changed"),
                    detail_row("field.line_of_sight", "4", "4", "same"),
                ],
            }
        ],
        "groups": [
            {
                "key": "civ",
                "title": {"key": "entity.group.civ", "args": {}},
                "sources": [
                    {
                        "key": "tech:693",
                        "name": {"key": "entity.source", "args": {"name": "Civ bonus: Tough"}},
                        "requires": "Feudal Age",
                        "rows": [
                            detail_row(
                                "effect.attribute",
                                None,
                                "+5",
                                "added",
                                target="Militia",
                                attribute="Hitpoints",
                            )
                        ],
                    }
                ],
            },
            {
                "key": "techs",
                "title": {"key": "entity.group.techs", "args": {}},
                "sources": [
                    {
                        "key": "tech:67",
                        "name": {"key": "entity.source", "args": {"name": "Forging"}},
                        "requires": None,
                        "rows": [
                            detail_row(
                                "effect.attribute",
                                "+1",
                                None,
                                "removed",
                                target="Militia",
                                attribute="Attack",
                            )
                        ],
                    }
                ],
            },
        ],
        "scripts": [],
        "note": {"key": "entity.note", "args": {}},
    }
    return data | overrides
