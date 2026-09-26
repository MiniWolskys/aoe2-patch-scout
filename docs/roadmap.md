# Roadmap

**Status on 2026-09-16:** M0 done. M1, M2 and M3 are done. M4 is done apart from the image export and snapshot archives, and M5 has a working build but no release yet. The checks that need a PUP branch or a Microsoft Store install are still deferred.

The app captures a real install, gates the `.dat`, compares two versions and exports the result as text or HTML. What is left before v1.0 is listed under each milestone below.

**How milestones run:**
- Design that goes beyond `docs/design/` is agreed in an issue first, then recorded in `docs/design/` and `docs/decisions.md` together with the code.
- Proposed decisions (`P-xx`) used by a milestone must be settled before it starts.

## M0: Foundations and verification spikes

Goal: remove the biggest unknowns before building on them. Spike code is throwaway; the findings go into the docs.

**Scaffolding**
- [x] Rename the GitHub repository to `aoe2-patch-scout` (P-11).
- [x] `pyproject.toml`:
  - PEP 621 metadata, `license = "GPL-3.0-or-later"`, `requires-python = ">=3.12"`;
  - GUI entry point;
  - ruff, mypy and pytest configuration.
- [x] `.python-version` (3.12), `uv.lock`, `src/patch_scout/` skeleton, `tests/` layout, i18n catalog skeleton (D-36).
- [x] Dev tooling: pre-commit config with ruff, Biome and safety hooks (D-24, D-26); `biome.json`; pytest-cov (D-25).
- [x] GitHub Actions on `windows-latest` and `ubuntu-latest` (D-11):
  - pre-commit on all files;
  - mypy;
  - pytest with a coverage report;
  - a PR title check (D-22).
- [x] Dependabot version updates (D-27), once `uv.lock` exists.
- [x] Merge settings and branch protection on `main` (D-21, D-23).
- [ ] Add the CI jobs as required status checks once they have run (D-23).

**Parse layer** (on the live install, read-only)
- [x] genieutils-py 0.1.2 parses the live `VER 8.9` file; the round trip on the decompressed stream is byte-exact.
- [x] **Layout substitution:** in memory, change the version bytes to an unknown string, e.g. `VER 9.0`. Check the VER 8.9 layout is accepted, and that a copy with one corrupted byte in the body is rejected (P-02).
  - **Result:** VER 8.9 is accepted and the older layouts are rejected. A corrupted byte is rejected only when it breaks the structure: most flipped values re-encode unchanged, so only the sanity checks can catch them ([genieutils-py.md](reference/genieutils-py.md#measured-on-the-live-build)).
- [x] Parse time and peak memory, including the cost of a failed attempt.
- [x] `.dat` civ order matches `civilizations.json` (Gaia = 0).
- [x] Sanity values against Advanced Genie Editor / in-game: Knight HP, a Blacksmith tech cost.
- [x] **How civ bonuses are encoded:** effect command types used, how descriptive effect names are. This feeds the effect sentence templates (O-5).
- [x] Unit slot count and snapshot size with every non-empty unit slot stored as base + overrides (P-03).
- [x] Units that matter but aren't in the tech trees or building offers (transform and dismount forms…) → reachability rules.
  - Findings are in [game-files.md §7](reference/game-files.md#7-futuravailableunitsjson--paphosfutureavailableunitsjson), and the rules in D-37 ([diff-rules.md](design/diff-rules.md#reachability-d-37)). Unit task links aren't followed. How the Spartan Polemarch variants become reachable stays open until M3.

**Files layer**
- [x] Pillow decodes all three DDS variants (no FourCC, DXT1, DXT5).
  - Pillow is slow on uncompressed DDS, about 110 ms per file; see [game-files.md §10](reference/game-files.md#tech-tree-icons-verified).
- [x] Map the stat icons in `widgetui\textures\ingame\staticons\` to stat keys.
- [x] Which duplicate string the game actually shows.
  - The last one, as the parser assumes: the Pirotechnia tooltip shows +15% ([game-files.md §9](reference/game-files.md#9-string-files-key-value)).
- [x] Meaning of the fifth `eras.json` age entry; role of `key-value-modded-strings-utf8.txt`.
- [x] Inspect `sharedbuildings.json`, `dropsites.json`, `objreplacement.json`.
- [ ] **Steam PUP branch:** what the app manifest records when a beta branch is selected (P-23), and whether the exe version and the `.dat` differ.
  - **Deferred:** this needs a live PUP branch. Switching Steam to it overwrites the live install, so back that up first.

**Packaging**
- [x] Minimal pywebview window frozen with PyInstaller (one-folder) on Windows, Python 3.12.
- [x] WebView2 engine detection and the fallback message.
- [x] genieutils-py kept as loose, replaceable files (see [legal.md](legal.md)).
- [x] SmartScreen and antivirus behaviour of the unsigned build.
  - The Defender scan found no threats. SmartScreen warns once per downloaded copy, and "Run anyway" works. Details: [packaging.md](reference/packaging.md#antivirus-and-smartscreen).

**Exit criteria**
- Every `[to verify]` in [game-files.md](reference/game-files.md) is resolved or explicitly deferred.
- Decisions affected by the findings are updated in [decisions.md](decisions.md).

## M1: App shell and files-tier capture

**Slices** (each with its own spec, plan and pull request, D-28):
1. [x] App shell: WebView2 check, window size, Forge theme, collapsible version list, first-launch screen.
2. [x] Snapshot schema, store and library index; version details.
3. [x] Readers, capture dialog and progress.
4. [x] Diagnostics: environment, capture log, gate details and the snapshot inspector, as a panel in the main window rather than a second window. A separate window buys nothing while the app has one screen at a time; revisit if it grows.

**Scope**
- **GUI shell:** one window with the version list (D-32), the Forge theme (D-35), WebView2 check.
- **Version list and details:** click to open, rename, pre-release tickbox, notes, delete (P-14, P-18).
- **Capture dialog:**
  - game folder detection (Steam; Microsoft Store / Xbox app), Browse, validation and root suggestion (D-19);
  - label, pre-release tickbox with the PUP reminder;
  - progress row in the list, progress view and result summary.
- **Diagnostics window:** environment, capture log, snapshot inspector, Copy diagnostics.
- **Readers:** `locate`, string file parser, `civilizations.json`, CivTechTrees, building offers, helper JSONs.
- **Storage:** icon pipeline (tech tree, emblems, unique units, stat icons) and icon store; snapshot schema v1 for the files tier; library index; raw backups (P-19).

**Exit criteria**
- [x] Capturing the live install twice gives identical snapshots, apart from `captured_at` and `capture_id`.
- [x] Detection failure falls back to Browse cleanly.
- [x] Synthetic fixture trees cover every reader; game tests pass locally (13 tests, `AOE2DE_PATH`).
- [ ] **Still open:** importing snapshot archives and the baseline pack (P-21); the Import button is visible but disabled.
- **Help wanted:** someone with the Microsoft Store / Game Pass version checks detection and folder layout.

## M2: Stats-tier capture

**Scope**
- genieutils-py integration.
- Gates: round trip, sanity cross-checks, layout substitution (P-01, P-02).
- Normalization: `civ_dat`, units as base + overrides, techs, effects; raw data only (D-20).
- Gate details in the Diagnostics window.
- The unit and tech field lists in [snapshot-format.md](design/snapshot-format.md) are frozen.

**Exit criteria**
- [x] The live build captures with `stats_available: true` (build 101.103.48987.0, 27 s for the whole capture).
- [x] A faked unknown version string is read through layout substitution and flagged.
- [x] A structurally corrupted stream (a broken count or string, or a truncated file) and a failed sanity check each give `stats: null` with the right reason.
- **Known limit:** a corrupted value that stays plausible can't be detected; see [genieutils-py.md](reference/genieutils-py.md#measured-on-the-live-build).

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
- [ ] **Not done:** diff two consecutive **public** builds and check the plain-text output against the official patch notes. Only one build is installed, so the engine has so far been checked against synthetic pairs and against one real build compared with a deliberately altered copy of itself.
- [ ] **Not done:** effect sentences (O-5 layer 2). Every changed effect command falls back to the raw command, because the command type, attribute and unit class names live inside the Advanced Genie Editor executable and were not going to be written from memory (AGENTS.md rule 7).

## M4: Compare UI and exports

**Scope**
- Comparison: the Compare button, Ctrl+click and Compare with… (D-32); navigation by civilization (D-33), with the Chronicles civs kept apart (D-38); civ bonus and unit stats views (D-20); filters and search. Opening the new version compared with the previous one when a capture finishes.
- Exports: plain text (clipboard and `.txt`), self-contained HTML, PNG image. Spike: modern-screenshot vs html-to-image, and tall views exported in parts.
- Export/import of snapshot archives; baseline pack import and first-launch screen (P-21).

**Exit criteria**
- [x] Capture, compare and export text or HTML work end to end in the app.
- [ ] **Not done:** the PNG image export, and export/import of snapshot archives and the baseline pack (P-21).

## M5: Packaging and v1.0

**Scope**
- PyInstaller build on a GitHub-hosted Windows runner on tag.
- `THIRD_PARTY_NOTICES`, the release checklist from [legal.md](legal.md), exe metadata.
- Baseline pack as a separate release asset with `NOTICE` (P-21, P-22).
- README install section.
- Release notes and versioning: evaluate release-please, which builds them from Conventional Commits. It needs a token other than `GITHUB_TOKEN`, so that its release PRs trigger CI.
- Smoke test of the build on Python 3.13 (P-12).
- First public release **`v1.0.0`, unsigned**.

**Exit criteria**
- [x] `uv run pyinstaller packaging/patch-scout.spec` produces a one-folder build that runs and compares real captures (217 files, 40.8 MB).
- [ ] **Not done:** `COPYING.LESSER` (the LGPLv3 text), an exe icon, the baseline pack, release notes, the 3.13 smoke test, and the walkthrough on a clean machine.

## After v1.0

- Apply to the SignPath Foundation; add the code signing policy page and the signing step to the release workflow (O-6).
- **Civ overview** (D-39): one civ's full tech tree, bonuses and stats in a version, with a comparison's changes highlighted.

## Later (not v1)

- Showing how a unit is affected by its civ's bonuses (D-20, P-17).
- Other languages: language selector defaulting to the game language from Steam (O-3, P-20).
- Return of Rome (`modes\Pompeii`, `VER 8.8`).
- Importing history from aoe2techtree `data/` or `HSZemi/aoe2dat` (partial snapshots).
- Upstream: numeric `Version` comparison in genieutils-py, before the game reaches a two-digit minor version.
- Possible move to another organisation (O-7).
