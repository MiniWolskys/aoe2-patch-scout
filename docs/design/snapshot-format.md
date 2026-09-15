# Snapshot format

**Status: draft of schema v1, 2026-09-15.** Field lists are finalized in M1–M2, once genieutils-py has been checked against a real file. Until v1.0 ships, the schema may change without migrations. From v1.0 on, every change bumps `schema_version` and ships a migration (P-15).

A snapshot is the **only** thing the diff reads. It must stay readable after any future game format change, which gives these rules:

- **Plain JSON values only:** objects, arrays, strings, numbers, booleans, null. No pickled or library objects, no enum reprs (D-05).
- **Raw game data only.** A snapshot stores what the game files contain. Nothing computed from several records is stored. In particular, civ bonuses are never applied to unit stats (D-20).
- **We control every field name.** Names start out copied from genieutils-py, but once in the schema they are frozen. An upstream rename is absorbed by the capture code, not by the snapshots.
- **Keyed, not positional.** Readers look fields up by name, so key order never matters. Order is only kept where the game's order means something: civ order, effect command order.
- **Deterministic.** The same install captured twice gives byte-identical JSON, apart from `meta.captured_at` and `meta.capture_id`. Keys are sorted, lists keep source order, and floats are written with Python's shortest `repr`.
- **Keep what you don't understand.** Unknown JSON keys in game files are stored under `extra`, so new game data shows up as a change instead of disappearing.
- **Immutable.** A snapshot file is never modified after it's written. Labels and flags the user edits live in the library index (P-18).

## Container

- **File:** `<capture_id>.snapshot.json.gz`: UTF-8 JSON, gzip-compressed.
- **Size target:** a few MB, to be measured in M0/M2; revisit above ~20 MB (P-03).
- **Icons:** stored outside the snapshot, in the shared icon store, and referenced by hash.

## Top level

```jsonc
{
  "schema_version": 1,
  "meta": { ... },
  "sources": { ... },
  "flags": { ... },
  "civs": [ ... ],
  "tech_trees": { ... },
  "building_offers": { ... },
  "unit_lines": [ ... ],
  "linked_techs": [ ... ],
  "linked_units": [ ... ],
  "eras": [ ... ],
  "strings": { ... },
  "stat_icons": { ... },
  "stats": { ... } | null
}
```

### `meta`

| Field | Type | Notes |
|---|---|---|
| `capture_id` | string | Random ID (UUID4 hex); also the filename. |
| `tool_version` | string | App version that captured it. |
| `captured_at` | string | UTC, ISO 8601. |
| `label_at_capture` | string | Label given at capture. The current label is in the library index. |
| `prerelease_at_capture` | bool | Tickbox state at capture. The current value is in the library index (P-14). |
| `source_path` | string \| null | Absolute install path. **Replaced with `null` on export.** |
| `game_build` | string \| null | From `AoE2DE_s.exe`; `null` if unreadable. |
| `steam_build_id` | string \| null | Steam installs only. |
| `dat_format_version` | string \| null | Version string found in the file, e.g. `"VER 8.9"`, NULs stripped. |
| `dat_layout_version` | string \| null | Layout genieutils-py actually parsed with. Differs from `dat_format_version` when the unknown-version fallback was used (P-02). |
| `genieutils_version` | string \| null | Library version used for the stats tier. |
| `languages` | string[] | String table languages captured, e.g. `["en"]` (O-3). |
| `icon_pipeline_version` | int | P-06. |

### `sources`

Maps each input file (relative path, forward slashes) to `{ "sha256": "...", "size": 123 }`. It covers **every** file read, which is how two captures are recognised as identical (P-05) and how raw backups are addressed (P-19).

### `flags`

| Field | Type | Meaning |
|---|---|---|
| `stats_available` | bool | `true` only if a layout parsed the file, the round trip was byte-exact and the sanity checks passed. |
| `stats_unavailable_reason` | string \| null | Human-readable reason, e.g. `"no known layout could read .dat format 'VER 9.0'"` or `"round-trip mismatch at byte 48213377"`. |
| `format_verified` | bool | `true` if the version string was known to genieutils-py. `false` if stats came from a substituted layout (P-02). |
| `dat_attempts` | object[] | One entry per layout tried: `{ "layout": "VER 8.9", "result": "parse_error" \| "roundtrip_mismatch" \| "sanity_failed" \| "passed", "detail": "..." }`. Shown in Diagnostics. |
| `sanity_checks` | object[] | `{ "name": "...", "passed": true, "detail": "..." }` for the accepted layout. |
| `missing_sections` | string[] | Sections that couldn't be read, e.g. `"linked_techs"`, with reasons in `warnings`. |
| `warnings` | string[] | Non-fatal notes: duplicate string keys, unknown JSON keys, unreadable icons. |

## Files-tier sections

The Britons and Archer examples below use real values from build `101.103.48987.0`. The IDs in the `stats` examples are illustrative only.

### `civs`
One object per `civilizations.json` entry, **in file order** (Gaia first):

```jsonc
{
  "index": 1,                        // position in civilizations.json
  "internal_name": "Britons",        // identity (P-07)
  "tech_tree_name": "BRITONS",
  "data_name": "BRITON-CIV",
  "era": "base",
  "name_string_id": 10271,
  "bonus_string_id": 120150,         // derived: 120150 + index - 1; null for Gaia or if the check failed
  "unique_tech_ids": [ 3, 461 ],     // unique_tech_id_1, unique_tech_id_2
  "unique_unit_id": 8,
  "elite_unique_unit_id": 530,
  "unique_unit_line": -276,
  "unique_unit_upgrade_id": 360,
  "unique_unit_string_ids": [ { "name": 5107, "description": 26107 } ],
  "emblem_icon": { ...icon ref... },
  "unique_unit_icons": [ { ...icon ref... } ],
  "extra": { }                       // unknown keys, verbatim
}
```

### `tech_trees`
Keyed by civ `internal_name`. Each value is a list of nodes, merged from both CivTechTrees arrays with the array name kept:

```jsonc
{
  "array": "civ_techs_units",        // or "civ_techs_buildings"
  "use_type": "Unit",
  "node_id": 4,
  "node_type": "Unit",               // null when the key is absent in the game file
  "node_status": "ResearchedCompleted",
  "name": "Archer",                  // informational; strings table is authoritative
  "name_string_id": 14083,
  "help_string_id": 105083,          // raw value; resolve as id - 79000
  "age_id": 2,
  "building_id": 87,
  "link_id": null,                   // null when the key is absent
  "link_node_type": "BuildingTech",
  "draw_node_type": "UnitTech",
  "trigger_tech_id": null,
  "building_upgraded_from_id": null,
  "building_in_new_column": null,
  "prerequisites": [],               // from Prerequisite IDs/Types, e.g. { "type": "Tech", "id": 101 }; "None" entries dropped
  "icon": { "category": "units", "picture_index": 17, ... },
  "extra": { }
}
```

### `building_offers`
From `futuravailableunits.json` and `paphosfutureavailableunits.json`, keyed by `internal_name`. Placeholder keys (`FullTechCiv`, `Paphos6`–`Paphos9`) are skipped. The value keeps the file's structure with snake_case keys, plus `extra`.

### `unit_lines`, `linked_techs`, `linked_units`, `eras`
Direct normalized copies of the helper JSONs (snake_case keys, `extra` for unknown keys).

### `strings`

```jsonc
{
  "tables": {
    "en": { "5083": "Archer", "IDS_OPT_ESC_MENU": "ESC Menu", ... }  // full tables: main + paphos + non-localized, merged
  },
  "duplicates": { "en": [ "13170", "IDS_BLOCK", ... ] }
}
```

- One table per captured language; v1 captures `en` only. Adding a language adds a key, with no schema change (O-3).
- Keys are strings even when numeric: JSON object keys are always strings.
- Text is stored raw, with tags and placeholders intact.

### `stat_icons`
Maps a stat key to an icon ref. The game's stat icons come from `widgetui\textures\ingame\staticons\` (D-09), e.g. `{ "hp": {…}, "melee_armor": {…} }`. The stat keys are ours; the file mapping is decided in M1. The UI falls back to text labels when an icon is missing.

## Stats-tier section

`stats` is `null` when `flags.stats_available` is `false`. It holds **raw records only** (D-20):

```jsonc
{
  "civ_dat": [                       // one per .dat civ, in .dat order
    { "index": 1, "name": "British", "tech_tree_effect_id": 254, "team_bonus_effect_id": 290,
      "resources": [ ... ], "icon_set": 1, "player_type": 1 }
  ],
  "units": {
    "38": {
      "base": { ...full unit record... },
      "base_civs": [ 1, 2, 3, ... ],         // civs whose record equals base
      "overrides": {
        "11": { "hit_points": 120 }          // dotted paths → full value; lists replaced whole
      },
      "absent_civs": [ 0 ]                   // civs whose slot is null
    }
  },
  "techs":   { "22": { ...tech record... } },
  "effects": { "254": { "name": "...", "commands": [ { "type": 102, "a": 22, "b": 0, "c": 0, "d": 0.0 } ] } }
}
```

**Units** (P-03):
- **Every** non-empty unit slot of every civ is captured.
- **Base record:** the most common full record among the civs that have the slot, compared by canonical JSON; ties go to the lowest civ index.
- **Overrides:** for every other civ, the differing fields, as dotted paths mapped to full values. Lists are replaced whole.
- **Reconstruction:** the diff rebuilds each civ's full record as base + overrides, so the choice of base never affects diff output.
- **Storage only:** this base/override split is a storage technique. It is not where civ bonuses come from: bonuses are the effects, which are stored raw and never applied to unit records.

**Unit and tech records:**
- Full records, graphic and sound IDs included; the diff allowlist filters them (D-08).
- The exact field list is copied from the pinned genieutils-py in M2 and then frozen here.

**Effects:** raw commands, in file order. Sentences are generated at diff time (O-5).

**Civ mapping:** `civ_dat[i]` corresponds to `civs[i]` only if the M0 order check confirms it. The mapping is also a sanity check (P-02).

## Icon references and the icon store

**Icon reference** (used everywhere an icon appears):

```jsonc
{ "category": "units", "picture_index": 17, "source": "widgetui/textures/ingame/units/017_50730.DDS",
  "hash": "a3f9…", "width": 256, "height": 256, "missing_reason": null }
```

- `category` is `units`, `tech` or `buildings` (from the node's `Use Type`), or `emblems`, `unique_units` or `stat_icons`.
- `hash` is the SHA-256 of the decoded full-size RGBA pixels (P-06). It is `null` when the icon is missing or unreadable, and `missing_reason` then says why.

**Icon store:**
- Path: `icons/<hash[0:2]>/<hash>.png`.
- Contents: a downscaled PNG, longest side 128 px.
- Created once, shared by every snapshot that references it.
- If the downscale pipeline changes, `icon_pipeline_version` is bumped and the store regenerates lazily. Hashes don't change, because they come from full-size pixels.

## Library index (P-18)

`library.json` holds what the user can edit after capture, so snapshot files stay immutable:

```jsonc
{
  "version": 1,
  "entries": {
    "<capture_id>": {
      "label": "PUP September",           // renamed from the version details
      "prerelease": true,                  // tickbox, editable any time
      "notes": "",
      "origin": "captured",                // "captured" | "imported" | "baseline"
      "added_at": "2026-09-15T20:14:03Z"
    }
  }
}
```

**Lost or corrupted index:** it is rebuilt from the snapshot files, taking labels and flags from `meta.*_at_capture`.

## Raw backups (D-12, P-19)

- **What:** every input file listed in `sources` is copied to `backups/objects/<sha256[0:2]>/<sha256>` unless an object with that hash already exists. Files unchanged since an earlier capture take no extra space.
- **Manifest:** `backups/<capture_id>.json` maps each relative path to its object hash, so the exact input folder can be rebuilt for re-capture with a fixed extractor.
- **Scope:** icons (DDS) are not backed up; converted icons are already kept. The Settings screen can turn backups off or purge them. Raw backups are never exported.

## Export archive

**Contents:** a zip file (`.aoe2snap`, extension proposed) with:
- `snapshot.json.gz`, with `meta.source_path` set to `null`;
- `library-entry.json`: the current label and pre-release flag;
- the referenced icons (O-1);
- `NOTICE`: game content © Microsoft, used under the Game Content Usage Rules, not covered by the GPL (P-22);
- `manifest.json`: tool version, schema version, list of icon hashes.

**Embargo:** exporting a snapshot ticked as pre-release asks for confirmation (P-14).
