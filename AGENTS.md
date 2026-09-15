# AGENTS.md

Instructions for AI coding agents working on Patch Scout; also a quick orientation for humans. The full contributor guide is [CONTRIBUTING.md](CONTRIBUTING.md): its git conventions, code standards and Definition of Done apply to agents too.

## Project

**Patch Scout** is a Windows desktop tool for *Age of Empires II: Definitive Edition*:
- **Capture** reads a game install into a snapshot.
- **Diff** compares two snapshots.
- **Comparison** shows every gameplay change: civs, availability, bonuses, unit stats, techs, texts, icons. It exports as plain text, HTML or image.

It's for streamers and YouTubers who get pre-release builds without patch notes.

- **Stack:** Python core, pywebview GUI (plain HTML/CSS/JS, no CLI), PyInstaller Windows build, [genieutils-py](https://github.com/SiegeEngineers/genieutils-py) for the `.dat`. Licence GPL-3.0-or-later.
- **Names:** Python package `patch_scout`, entry point `patch-scout`.
- **Status:** M0 done: project scaffold, i18n catalog, pre-commit hooks, CI and the verification spikes are in place; no features yet. Next step: M1 in [docs/roadmap.md](docs/roadmap.md), starting with a spec.

## Where things are documented

| Need | Read |
|---|---|
| Git workflow, commit format, code standards, Definition of Done | [CONTRIBUTING.md](CONTRIBUTING.md) |
| What was decided, and what is still Proposed or Open | [docs/decisions.md](docs/decisions.md) |
| Components, dependency rules, capture and diff flows, GUI overview | [docs/design/architecture.md](docs/design/architecture.md) |
| Window layout and behaviour, colours, theme tokens | [docs/design/ui.md](docs/design/ui.md), [ui-theme.css](docs/design/ui-theme.css) |
| Snapshot JSON schema, library index, raw backups | [docs/design/snapshot-format.md](docs/design/snapshot-format.md) |
| What counts as a change, effect sentences, exports | [docs/design/diff-rules.md](docs/design/diff-rules.md) |
| Reading game files: locations, formats, ID mappings | [docs/reference/game-files.md](docs/reference/game-files.md) |
| genieutils-py API, version handling, layout substitution | [docs/reference/genieutils-py.md](docs/reference/genieutils-py.md) |
| PyInstaller build, loose genieutils files, WebView2 detection | [docs/reference/packaging.md](docs/reference/packaging.md) |
| Licences, Microsoft content rules, embargo | [docs/legal.md](docs/legal.md) |

## Hard rules

1. **Game install folders are read-only.** Never write, move or delete anything inside one, including from tests and exploratory scripts. Layout substitution changes an in-memory copy only.
2. **Never assume where the game is installed.** Detection only proposes a folder; the user confirms or browses. No hardcoded install paths in code, tests or default settings. Tests read `AOE2DE_PATH`.
3. **Never commit game files**: `.dat`, game JSON, string files, DDS/PNG game art.
   - **Never put data from privately shared pre-release builds anywhere public.**
   - **Fixtures:** snapshots from public builds only, synthetic icons, kept in `tests/fixtures/game-derived/` with a `NOTICE`.
   - **Licensing:** game content is © Microsoft and not GPL. Never mix it into code or the app zip ([docs/legal.md](docs/legal.md)).
4. **Wrong output is worse than missing output.** Stats are available only if a layout parses the file, the round trip (on the decompressed stream) is byte-exact, and the sanity cross-checks pass. Otherwise set `stats: null` with a specific reason. Never patch doubtful values.
5. **Snapshots hold raw game data as plain JSON** and are immutable once written.
   - genieutils objects stay inside `capture.stats_tier` and `capture.gates`.
   - Civ bonuses are never applied to unit stats: not stored, and not computed in v1.
   - User-editable metadata lives in `library.json`.
6. **A change to the snapshot schema or diff rules updates its design doc in the same change.** From v1.0 it also bumps the schema version and adds a migration.
7. **Don't write genieutils-py class or field names, effect command types or attribute IDs from memory.** Read the installed source in `.venv\Lib\site-packages\genieutils\`, or Advanced Genie Editor.
8. **No network access in the app and no telemetry.** **No user-visible text hardcoded** outside the i18n catalog.
9. **Facts in `docs/reference/` hold for one build.** If a real install contradicts them, update the doc with `[verified]` and the build number; don't silently special-case.
10. **Proposed and Open decisions are not settled.** Don't build on them, or change a Decided one, without the maintainer's agreement.

## Agent workflow

### 1. Get approval before coding (D-28)
- **Features and design changes:** discuss the options with the maintainer, then get a written **spec** approved, then an **implementation plan** approved.
- **Bug fixes and chores:** get a short plan approved in the conversation.
- **No approval, no code.** If the approved plan turns out to be wrong while coding, stop and ask.
- Issues are optional (D-31); reference one in the pull request when it exists.

### 2. Work on one branch in the main working copy (D-30)
- One task at a time, on a branch named `<type>/<short-topic>` (e.g. `feat/steam-detection`) created from an up-to-date `main`.
- **No git worktrees:** the maintainer's private local files exist only in the main working copy.
- **Test-driven:** write the failing test first, then the code.
- **Small commits** in Conventional Commits format, e.g. `feat(capture): detect Steam libraries`. See [CONTRIBUTING.md](CONTRIBUTING.md#commit-messages-and-pr-titles).
- **Hooks must pass.** Never use `--no-verify`, and never weaken a hook, check or test to get a commit through.

### 3. Before opening a pull request
- **Run the checks and read their output:** `uv run pre-commit run --all-files`, `uv run mypy`, `uv run pytest`. Add `uv run pytest -m game` when capture code changed.
- **Self-review the whole diff** and fix or explicitly answer every finding.
- **Update the docs** the change affects: design docs, `docs/decisions.md`, `docs/reference/`.
- **Check the [Definition of Done](CONTRIBUTING.md#definition-of-done).**

### 4. Git and GitHub: what agents may do (D-29)
- **Allowed:**
  - commit on the task branch and push that branch;
  - open a pull request with a Conventional Commit title and the template filled in: what and why, a design summary, tests run with results, risks.
- **Never, unless the maintainer asks for that specific action:**
  - commit to or push `main`;
  - merge or approve a pull request;
  - force-push, or rebase or amend commits that are already pushed;
  - bypass hooks, CI or branch protection;
  - change repository settings, create tags or releases, delete remote branches.
- **The maintainer reviews and merges every pull request** (D-23).

## Commands

Details in CONTRIBUTING.md.

```powershell
uv sync                              # env + deps
uv run pre-commit install            # once per clone: git hooks
uv run patch-scout --debug           # run the app with WebView dev tools
uv run pre-commit run --all-files    # ruff, Biome, file checks, safety hooks
uv run mypy
uv run pytest                        # tests without the game, with a coverage report
uv run pytest -m game                # needs $env:AOE2DE_PATH; never runs in CI
```

## Glossary

- **Capture / snapshot:** reading one install into an immutable, versioned, plain-JSON snapshot (`*.snapshot.json.gz`).
- **Library index:** `library.json`, holding editable labels, pre-release flags and notes.
- **Diff / change set / export:** comparing two snapshots; the change set is plain data, and exports are its plain-text, HTML or PNG renderings.
- **Files tier / stats tier:** JSON, strings and icons (always read) vs the `.dat` (gated).
- **Gates:** the round trip (re-encoding reproduces the decompressed `.dat`) and the semantic sanity cross-checks against the files tier.
- **Layout substitution:** parsing a `.dat` with an unknown version string by swapping in a known version in memory; flagged `format_verified: false`.
- **Effect sentence:** readable text generated at compare time from an effect command, e.g. for a changed civ bonus.
- **Diagnostics window:** the in-app debug view (environment, capture log, gate details, snapshot inspector, Copy diagnostics).
- **Base civs / Chronicles / Return of Rome:**
  - Base civs have era `base`.
  - Chronicles civs have era `antiquity`, live in the main `.dat`, and use files named `paphos*`.
  - Return of Rome is `modes\Pompeii`, has its own `VER 8.8` `.dat`, and is out of scope for v1.
- **Live / pre-release build:**
  - **PUP** (Public Update Preview) is a public Steam beta branch of the same install; switching to it overwrites the live build.
  - **Builds shared privately with creators** may be under embargo.
  - The user ticks pre-release; the app may prefill it from Steam's branch info (P-23).
- **Baseline pack:** a release asset holding a snapshot of the current live build and its icons. Kept separate from the app zip.
- **Reachable unit:** a unit in a civ's tech tree or building offers, or one of their transform or dismount forms (D-37). Computed at diff time, never used to filter a capture.

## Gotchas (verified on build 101.103.48987.0)

- **The `.dat` is raw DEFLATE:** `zlib.decompress(data, wbits=-15)`. The version bytes are `VER 8.9\0`; strip the NULs.
- **Tech tree `Help String ID`** resolves at `id - 79000`. `Name String ID` resolves directly.
- **Icon folder** is chosen by the node's `Use Type` (`Unit`/`Tech`/`Building` → `units`/`tech`/`buildings`). File extensions are mixed `.DDS`/`.dds`.
- **Optional node keys:** `Node Type`, `Link Node Type` and `Draw Node Type` can be *absent*.
- **`futuravailableunits` keys** are `civilizations.json` `internal_name`s. Skip `FullTechCiv` and `Paphos6`–`Paphos9`.
- **Civ bonus text ID** = `120150 + index − 1` (index in `civilizations.json`, Gaia = 0). Re-verify on every build.
- **String files** have non-numeric keys, trailing `//` comments and duplicate keys: the last one wins, and duplicates are logged.
- **genieutils-py `Version` compares strings,** so `'VER 8.10' < 'VER 8.9'`. Never add enum members at runtime; use layout substitution.
- **Open game JSON and text with `encoding="utf-8"`.** PowerShell's default reading garbles non-ASCII (e.g. "Lü Bu").
- **Steam's PUP is a beta branch of app 813780**, not a separate install: switching branches overwrites the live build in place.
