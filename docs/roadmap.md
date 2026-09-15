# Roadmap

**Status on 2026-09-15:** documentation phase; no code yet.

**How milestones run:**
- Design that goes beyond `docs/design/` is agreed in an issue first, then recorded in `docs/design/` and `docs/decisions.md` together with the code.
- Proposed decisions (`P-xx`) used by a milestone must be settled before it starts.

## M0: Foundations and verification spikes

Goal: remove the biggest unknowns before building on them. Spike code is throwaway; the findings go into the docs.

**Scaffolding**
- [x] Rename the GitHub repository to `aoe2-patch-scout` (P-11).
- [ ] `pyproject.toml`:
  - PEP 621 metadata, `license = "GPL-3.0-or-later"`, `requires-python = ">=3.12"`;
  - GUI entry point;
  - ruff, mypy and pytest configuration.
- [ ] `.python-version` (3.12), `uv.lock`, `src/patch_scout/` skeleton, `tests/` layout, i18n catalog skeleton.
- [ ] GitHub Actions: ruff + mypy + pytest on `windows-latest` and `ubuntu-latest` (D-11).
- [ ] Branch protection on `main`: PR and green CI required.

**Parse layer** (on the live install, read-only)
- [ ] genieutils-py 0.1.2 parses the live `VER 8.9` file; the round trip on the decompressed stream is byte-exact.
- [ ] **Layout substitution:** in memory, change the version bytes to an unknown string, e.g. `VER 9.0`. Check the VER 8.9 layout is accepted, and that a copy with one corrupted byte in the body is rejected (P-02).
- [ ] Parse time and peak memory, including the cost of a failed attempt.
- [ ] `.dat` civ order matches `civilizations.json` (Gaia = 0).
- [ ] Sanity values against Advanced Genie Editor / in-game: Knight HP, a Blacksmith tech cost.
- [ ] **How civ bonuses are encoded:** effect command types used, how descriptive effect names are. This feeds the effect sentence templates (O-5).
- [ ] Unit slot count and snapshot size with every non-empty unit slot stored as base + overrides (P-03).
- [ ] Units that matter but aren't in the tech trees or building offers (transform and dismount forms…) → reachability rules.

**Files layer**
- [ ] Pillow decodes all three DDS variants (no FourCC, DXT1, DXT5).
- [ ] Map the stat icons in `widgetui\textures\ingame\staticons\` to stat keys.
- [ ] Which duplicate string the game actually shows.
- [ ] Meaning of the fifth `eras.json` age entry; role of `key-value-modded-strings-utf8.txt`.
- [ ] Inspect `sharedbuildings.json`, `dropsites.json`, `objreplacement.json`.
- [ ] **Steam PUP branch:** what the app manifest records when a beta branch is selected (P-23), and whether the exe version and the `.dat` differ.

**Packaging**
- [ ] Minimal pywebview window frozen with PyInstaller (one-folder) on Windows, Python 3.12.
- [ ] WebView2 engine detection and the fallback message.
- [ ] genieutils-py kept as loose, replaceable files (see [legal.md](legal.md)).
- [ ] SmartScreen and antivirus behaviour of the unsigned build.

**Exit criteria**
- Every `[to verify]` in [game-files.md](reference/game-files.md) is resolved or explicitly deferred.
- Decisions affected by the findings are updated in [decisions.md](decisions.md).

## M1: App shell and files-tier capture

**Scope**
- **GUI shell:** window, navigation, WebView2 check.
- **Library screen:** list, click-to-rename, pre-release tickbox, delete (P-14, P-18).
- **Capture screen:**
  - game folder detection (Steam; Microsoft Store / Xbox app), Browse, validation and root suggestion (D-19);
  - label, pre-release tickbox with the PUP reminder;
  - progress and result summary.
- **Diagnostics window:** environment, capture log, snapshot inspector, Copy diagnostics.
- **Readers:** `locate`, string file parser, `civilizations.json`, CivTechTrees, building offers, helper JSONs.
- **Storage:** icon pipeline (tech tree, emblems, unique units, stat icons) and icon store; snapshot schema v1 for the files tier; library index; raw backups (P-19).

**Exit criteria**
- Capturing the live install twice gives identical snapshots, apart from `captured_at` and `capture_id`.
- Detection failure falls back to Browse cleanly.
- Synthetic fixture trees cover every reader; game tests pass locally.
- **Help wanted:** someone with the Microsoft Store / Game Pass version checks detection and folder layout.

## M2: Stats-tier capture

**Scope**
- genieutils-py integration.
- Gates: round trip, sanity cross-checks, layout substitution (P-01, P-02).
- Normalization: `civ_dat`, units as base + overrides, techs, effects; raw data only (D-20).
- Gate details in the Diagnostics window.
- The unit and tech field lists in [snapshot-format.md](design/snapshot-format.md) are frozen.

**Exit criteria**
- The live build captures with `stats_available: true`.
- A faked unknown version string is read through layout substitution and flagged.
- A corrupted byte and a failed sanity check both give `stats: null` with the right reason.

## M3: Diff engine

**Scope**
- Identity matching.
- Allowlist mapping to snapshot fields.
- Per-civ collapsing, categories and priorities.
- Bonus text diffs; effect mapping tables and sentence templates, with raw fallback (O-5).
- String and icon changes; change-volume check.
- Plain-text renderer.
- Golden tests (change-set JSON + plain text).

**Exit criteria (acceptance)**
- Diff two consecutive **public** builds.
- Check the plain-text output against the official patch notes: every gameplay item in the notes is in the output, or the gap is explained and tracked.

## M4: Compare UI and exports

**Scope**
- Compare screen with its three views (Changes, Civ bonuses, Units), filters and search.
- Exports: plain text (clipboard and `.txt`), self-contained HTML, PNG image. Spike: modern-screenshot vs html-to-image, and tall views exported in parts.
- Export/import of snapshot archives; baseline pack import and first-run screen (P-21).

**Exit criteria**
- A streamer-style walkthrough works end to end: capture live, capture PUP, compare, export an image and a text summary.

## M5: Packaging and v1.0

**Scope**
- PyInstaller build on a GitHub-hosted Windows runner on tag.
- `THIRD_PARTY_NOTICES`, the release checklist from [legal.md](legal.md), exe metadata.
- Baseline pack as a separate release asset with `NOTICE` (P-21, P-22).
- README install section.
- Smoke test of the build on Python 3.13 (P-12).
- First public release **`v1.0.0`, unsigned**.

**Exit criteria**
- A non-developer installs from the zip, imports the baseline pack, captures, compares and exports, on a clean Windows 10 machine.

## After v1.0

- Apply to the SignPath Foundation; add the code signing policy page and the signing step to the release workflow (O-6).

## Later (not v1)

- Showing how a unit is affected by its civ's bonuses (D-20, P-17).
- Other languages: language selector defaulting to the game language from Steam (O-3, P-20).
- Return of Rome (`modes\Pompeii`, `VER 8.8`).
- Importing history from aoe2techtree `data/` or `HSZemi/aoe2dat` (partial snapshots).
- Upstream: numeric `Version` comparison in genieutils-py, before the game reaches a two-digit minor version.
- Possible move to another organisation (O-7).
