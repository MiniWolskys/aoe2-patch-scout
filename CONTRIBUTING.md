# Contributing

Thanks for helping! This project is in its **documentation phase**: the commands below take effect once the M0 scaffolding lands (see [docs/roadmap.md](docs/roadmap.md)).

## Ground rules

1. **The game folder is read-only.** No code, test or script may write inside an AoE2:DE install.
2. **Never assume where the game is installed.** Detection proposes a folder and the user confirms or picks another. Tests take the path from `AOE2DE_PATH`.
3. **No game files in the repo**: no `.dat`, game JSON, string files or game art. **No data from privately shared pre-release builds anywhere public**: repo, issues, PRs, CI logs, screenshots. Game-derived content isn't GPL and stays apart from code. Details in [docs/legal.md](docs/legal.md).
4. **Wrong output is worse than missing output.** If data can't be read with certainty, the tool says so; it never guesses.
5. **English** for code, docs, issues and PRs. User-visible app text goes through the i18n catalog.

## Development setup

Prerequisites:
- **Windows 10/11** for the app. Pure modules and most tests also run on Linux and macOS.
- **Git.**
- **[uv](https://docs.astral.sh/uv/)**, which installs the pinned Python itself.
- **Optional:** an AoE2:DE install, needed only for game tests.

```powershell
winget install --id astral-sh.uv -e
git clone https://github.com/MiniWolskys/aoe2-patch-scout.git
cd aoe2-patch-scout
uv sync
```

`uv sync` installs Python 3.12 if needed, creates `.venv\`, and installs runtime and dev dependencies from `uv.lock`.

| Task | Command |
|---|---|
| Run the app | `uv run patch-scout` |
| Run the app with WebView developer tools | `uv run patch-scout --debug` |
| Tests (no game needed) | `uv run pytest` |
| Game tests | `$env:AOE2DE_PATH = "<game folder>"; uv run pytest -m game` |
| Lint | `uv run ruff check .` |
| Format | `uv run ruff format .` |
| Type check | `uv run mypy` |
| Add a dependency | `uv add <package>` (runtime) · `uv add --dev <package>` (dev) |
| Build the Windows app (M5) | `uv run pyinstaller packaging\patch-scout.spec` |

## Workflow

1. **Open an issue first** for anything beyond a typo: bugs, features, allowlist changes, format findings.
2. **Branch from `main`**: `feat/<topic>`, `fix/<topic>`, `docs/<topic>`, `chore/<topic>`. `main` is protected; every change goes through a PR.
3. **Design before code** when a change touches any of these:
   - snapshot schema;
   - diff rules, effect sentences or export wording;
   - capture gates;
   - GUI flows;
   - packaging or licensing.

   Describe the design in the issue and agree on it before coding. The agreed design is recorded in `docs/design/` (and `docs/decisions.md` for decisions) in the same PR as the code.
4. **Test first.** Write a failing test, make it pass, then clean up. Bug fixes start with a test that reproduces the bug.
5. **Before pushing:** `ruff format`, `ruff check`, `mypy` and `pytest` must all be clean. CI runs them too, but game tests only ever run on your machine.
6. **Keep docs in the same PR:**
   - A new or changed decision gets an entry in [docs/decisions.md](docs/decisions.md).
   - A new format fact goes into [docs/reference/game-files.md](docs/reference/game-files.md), tagged `[verified]` with the build it was checked on.
   - A behaviour change goes into the design doc it affects.
7. **Pull request:**
   - Fill in the template and state which tests you ran; keep one topic per PR.
   - Merging needs a green CI and one maintainer approval.
   - PRs are squash-merged. The commit subject is imperative and at most 72 characters, e.g. `Add key-value string parser`.

## Continuous integration

- **On every PR and push to `main`:** `ruff format --check`, `ruff check`, `mypy` and `pytest`, on `windows-latest` and `ubuntu-latest` (D-11). GitHub-hosted runners are free for public repositories.
- **Game tests never run in CI**, because CI has no game install. Run them locally when capture code changes.
- **From M5**, a tag triggers the Windows release build on a GitHub-hosted runner. SignPath code signing, planned after the first release, requires that (see [docs/legal.md](docs/legal.md)).

## Testing

| Layer | What it covers | Location | Needs the game |
|---|---|---|---|
| Unit | Parsers, normalization, collapsing, effect sentences, formatting, on synthetic inputs | `tests/unit/` | No |
| Fixture trees | Capturing small **synthetic** game-folder trees: hand-written JSON and strings, generated placeholder DDS/PNG icons | `tests/fixtures/` | No |
| Snapshot pairs + golden outputs | Diffing committed snapshot pairs; change-set JSON and plain-text export compared to expected files | `tests/fixtures/`, `tests/golden/` | No |
| Game | Capturing a real install: gates, layout substitution (the version bytes are changed in memory only), sanity values, determinism | `tests/game/`, marker `game` | Yes (`AOE2DE_PATH`) |

**Rules:**
- Fixture snapshots come from **public** builds only (P-09) and live in `tests/fixtures/game-derived/` with its `NOTICE`: game content isn't GPL (P-22). Icons in fixtures are synthetic, never game art.
- Golden files change only deliberately (`uv run pytest --update-golden`), and a reviewer reads the golden diff in the PR.
- Determinism is tested: capturing the same input twice gives identical snapshots apart from capture metadata.
- If you change capture code, run the game tests and say so in the PR.

## Code style

- Python 3.12 with type hints everywhere; `mypy --strict` on `src/`.
- `ruff format` (line length 100) and `ruff check`.
- Small modules with one job each. Follow the dependency rules in [docs/design/architecture.md](docs/design/architecture.md): only capture code reads game files or imports `genieutils`.
- `pathlib` everywhere. Never hardcode install paths, not even as defaults.
- Always pass `encoding="utf-8"` when opening text files.
- No user-visible strings in code: use the i18n catalog.
- Use `logging`, not `print`. Capture logs feed the Diagnostics window.
- No network calls and no telemetry.
- Comments explain *why*. Point to docs for format facts, e.g. `# Help String ID is offset by 79000, see game-files.md §5`.

## When a game update lands

1. **Capture the new build in the app** (a raw backup is made by default). If you use Steam's PUP branch, capture the live build *before* switching: the switch overwrites the install. Keep anything from a privately shared build private.
2. **Check the Diagnostics window:** stats status, layout used, round-trip and sanity results. If stats are available, run the game tests and spot-check a few values in Advanced Genie Editor.
3. **No layout passed:** follow [Contributing format support upstream](docs/reference/genieutils-py.md#contributing-format-support-upstream).
4. **Re-check the per-build facts** in [game-files.md](docs/reference/game-files.md): civ count, bonus string range, node keys, icon mapping. The game tests automate what they can.
5. **Once the build is public:** refresh the baseline snapshot and any fixtures, then release (D-10).

Upgrading genieutils-py: see [docs/reference/genieutils-py.md](docs/reference/genieutils-py.md#upgrading-the-pinned-version).

## Releases (from M5)

- Semantic versioning; tags `vX.Y.Z` on `main`.
- A GitHub Actions workflow builds the Windows zip on tag. Signing via SignPath is added after the first public release (O-6).
- Each release also publishes a separate **baseline pack**: the snapshot and icons of the current live build, with a `NOTICE`, not inside the app zip (P-21).
- Before publishing, go through the release checklist in [docs/legal.md](docs/legal.md#shipping-the-windows-build-checklist).

## Reporting issues

- Use the issue templates.
- Paste the output of **Copy diagnostics** from the Diagnostics window.
- **Never attach snapshots, exports or values from a privately shared pre-release build.**
