# Contributing

Thanks for helping! This project is in **M0, foundations** (see [docs/roadmap.md](docs/roadmap.md)). The commands below work, and CI runs the same checks on every pull request.

Using an AI coding agent? It follows [AGENTS.md](AGENTS.md) in addition to this guide, and you remain responsible for everything you submit.

## Ground rules

1. **The game folder is read-only.** No code, test or script may write inside an AoE2:DE install.
2. **Never assume where the game is installed.** Detection proposes a folder and the user confirms or picks another. Tests take the path from `AOE2DE_PATH`.
3. **No game files in the repo**: no `.dat`, game JSON, string files or game art. **No data from privately shared pre-release builds anywhere public**: repo, issues, PRs, CI logs, screenshots. Game-derived content isn't GPL and stays apart from code. Details in [docs/legal.md](docs/legal.md).
4. **Wrong output is worse than missing output.** If data can't be read with certainty, the tool says so; it never guesses.
5. **English** for code, docs, issues and PRs. User-visible app text goes through the i18n catalog.

## Development setup

**Prerequisites:**
- **Windows 10/11** for the app. Pure modules and most tests also run on Linux and macOS.
- **Git.**
- **[uv](https://docs.astral.sh/uv/)**, which installs the pinned Python itself.
- **[Biome](https://biomejs.dev/)** standalone binary, for JavaScript and CSS. No Node.js needed.
- **Optional:** an AoE2:DE install, needed only for game tests.

```powershell
winget install --id astral-sh.uv -e
winget install --id BiomeJS.Biome -e
git clone https://github.com/MiniWolskys/aoe2-patch-scout.git
cd aoe2-patch-scout
uv sync
uv run pre-commit install
```

- `uv sync` installs Python 3.12 if needed, creates `.venv\`, and installs runtime and dev dependencies from `uv.lock`.
- `pre-commit install` sets up the git hooks, once per clone.
  - The hooks run ruff through `uv run`, so its version comes from `uv.lock`, and Biome from your PATH.
  - A safety hook (`tools/check_forbidden_files.py`) refuses game files, snapshots, `.private/` and `CLAUDE.local.md`. Synthetic game files are allowed under `tests/fixtures/`, but `.dat` files never are.

| Task | Command |
|---|---|
| Run the app | `uv run patch-scout` |
| Run the app with WebView developer tools | `uv run patch-scout --debug` |
| All hooks on all files (ruff, Biome, file checks, safety hooks) | `uv run pre-commit run --all-files` |
| Type check | `uv run mypy` |
| Tests with coverage report (no game needed) | `uv run pytest` |
| Game tests | `$env:AOE2DE_PATH = "<game folder>"; uv run pytest -m game` |
| Add a dependency | `uv add <package>` (runtime) · `uv add --dev <package>` (dev) |
| Build the Windows app (M5) | `uv run pyinstaller packaging\patch-scout.spec` |

## Git workflow

### Branches
- **GitHub flow** (D-21): branch from an up-to-date `main`, keep the branch short-lived, one topic per branch.
- **Branch name:** `<type>/<short-topic>`, using the commit types below, e.g. `feat/steam-detection`, `fix/duplicate-strings`, `docs/diff-rules`.
- **`main` is protected**, for admins too: no direct pushes, no force pushes, linear history.
- **Keeping up to date:** run `git merge origin/main` on your branch. Only rebase commits nobody else has pulled, and never force-push a branch under review.

### Commit messages and PR titles
Use [Conventional Commits](https://www.conventionalcommits.org/) (D-22):

```
<type>(<optional scope>)<optional !>: <summary>

<optional body: why the change is needed>

<optional footers: Closes #12, BREAKING CHANGE: ..., Co-Authored-By: ...>
```

| Type | Use for |
|---|---|
| `feat` | A user-visible feature |
| `fix` | A bug fix |
| `docs` | Documentation only |
| `refactor` | Code change with no behaviour change |
| `perf` | Performance improvement |
| `test` | Adding or fixing tests only |
| `build` | Packaging, build scripts, dependency configuration |
| `ci` | CI workflows |
| `chore` | Maintenance: tooling config, housekeeping |
| `revert` | Reverting an earlier commit |

- **Scopes** are optional. Prefer one of: `locate`, `capture`, `stats`, `icons`, `snapshot`, `store`, `diff`, `report`, `gui`, `i18n`, `packaging`, `deps`.
- **Summary:** imperative mood, lower case, no final period, whole line at most 72 characters.
- **Breaking changes** get `!` after the type/scope, plus a `BREAKING CHANGE:` footer. Example: a snapshot schema change without a migration, after v1.0.
- **The PR title uses the same format.** With squash merging it becomes the commit on `main`, and CI checks it (from M0).
- **Examples:** `feat(capture): detect Steam libraries`, `fix(diff): group civs by value pair`, `docs: define review process`.

### Pull requests
- **Keep them small and on one topic.** Aim for under ~400 changed lines, not counting golden or fixture files. Draft PRs are welcome for early feedback.
- **Issues are optional** (D-31). Link one when it exists (`Closes #123`).
- **Design first:** changes to the snapshot schema, diff rules, effect sentences, export wording, capture gates, GUI flows, packaging or licensing need an agreed design before coding. Discuss it with the maintainer, in an issue or in the PR. The agreed design lands in `docs/design/`, plus `docs/decisions.md` for decisions, in the same PR as the code.
- **Fill in the template:**
  - what and why;
  - a design summary;
  - how it was tested, with commands and results;
  - risks;
  - screenshots for UI changes.

### Review and merge
- **The maintainer reviews and merges every pull request** (D-23), using **Squash and merge**. The branch is then deleted automatically.
- **Merging requires** green CI (the required checks, once they exist) and every review conversation resolved.
- **GitHub requires 0 approvals.** GitHub doesn't let authors approve their own PRs, and agent PRs use the maintainer's account. The review itself is still mandatory; it just isn't a GitHub approval.
- **Reviewers check:**
  - correctness and tests;
  - the ground rules;
  - the dependency rules in [docs/design/architecture.md](docs/design/architecture.md);
  - that the docs were updated.

## Definition of Done

A change is done when all of these hold:

- [ ] Behaviour is covered by tests written first; bug fixes include a regression test.
- [ ] `uv run pre-commit run --all-files`, `uv run mypy` and `uv run pytest` pass locally. Game tests pass too when capture code changed.
- [ ] No game files and no data from privately shared builds; no hardcoded install paths; nothing writes inside a game folder.
- [ ] User-visible text goes through the i18n catalog.
- [ ] The docs the change affects are updated in the same PR: design, reference, decisions.
- [ ] If the snapshot schema or diff rules changed: golden files are updated and reviewed; from v1.0, the schema version is bumped and a migration added.
- [ ] If a runtime dependency was added: its licence is checked and listed in [docs/legal.md](docs/legal.md).
- [ ] The PR title follows Conventional Commits, the template is filled in, and the whole diff has been self-reviewed.

## Code standards

### Python
- **Version and typing:** Python 3.12, type hints on everything, `mypy --strict` on `src/` and `tests/`.
  - Avoid `Any`.
  - A `cast` or `# type: ignore[code]` needs a comment explaining why.
- **Format and lint:** `ruff format` (line length 100) and `ruff check`, both run by pre-commit.
  - Initial rule set, finalized in M0: pycodestyle (`E`, `W`), Pyflakes (`F`), isort (`I`), bugbear (`B`), pyupgrade (`UP`), simplify (`SIM`), pathlib (`PTH`), naming (`N`), no print (`T20`), Ruff (`RUF`).
- **Naming:** PEP 8, descriptive names. Accepted domain abbreviations: `civ`, `dat`, `id`, `ui`.
- **Docstrings:** a one-line summary on public modules, classes and functions. Add Google-style `Args:` / `Returns:` / `Raises:` only when names and types don't already say it.
- **Data:** `@dataclass(frozen=True, slots=True)` for internal records. Plain dicts and lists only at JSON boundaries (snapshot I/O).
- **Errors:**
  - Project exceptions derive from `PatchScoutError`, with specific subclasses.
  - No bare `except:`.
  - Catch broad `Exception` only at boundaries (capture attempts, GUI API calls), and always log it and turn it into a user-visible reason. Never swallow errors silently.
- **Logging:** `logger = logging.getLogger(__name__)`, never `print`. Logs feed the Diagnostics window, so:
  - **allowed:** IDs, counts, timings, paths relative to the game folder;
  - **never:** game data values or texts, which may come from a privately shared build.
- **Side effects:**
  - `snapshot`, `diff` and `report` do no I/O; side effects live in `locate`, `capture`, `store` and `gui`.
  - Pass dependencies as parameters; no mutable module-level state.
- **Files and time:** `pathlib.Path` everywhere; always pass `encoding="utf-8"`; timezone-aware UTC datetimes.
- **Comments** explain *why*. Point to docs for format facts, e.g. `# Help String ID is offset by 79000, see game-files.md §5`.
- **Module size:** keep modules focused. If a file grows past a few hundred lines, consider splitting it.

### Frontend (HTML, CSS, JavaScript)
- **Plain technology:** HTML, CSS and JavaScript ES modules. No framework, no bundler, no npm (P-16).
- **Biome** lints and formats JS and CSS (D-26); its configuration is in `biome.json`.
  - Third-party files are vendored in `gui/web/vendor/`, never edited, and excluded from Biome.
- **Theme:** colours, fonts and sizes come from the Forge tokens in [docs/design/ui-theme.css](docs/design/ui-theme.css) (D-35). No colour literals in component CSS. Red and green only mean old and new (D-34).
- **JSDoc** types on exported functions.
- **Text:** every label comes from the i18n catalog.
- **Talking to Python:** only through the exposed API object. No network requests.
- **Event handlers:** use `addEventListener`, not inline handlers such as `onclick`.
- **Accessibility:**
  - semantic elements, and labels on every control;
  - everything reachable with the keyboard;
  - never rely on colour alone to convey a change.

### Testing

| Layer | What it covers | Location | Needs the game |
|---|---|---|---|
| Unit | Parsers, normalization, collapsing, effect sentences, formatting, on synthetic inputs | `tests/unit/` | No |
| Fixture trees | Capturing small **synthetic** game-folder trees: hand-written JSON and strings, generated placeholder DDS/PNG icons | `tests/fixtures/` | No |
| Snapshot pairs + golden outputs | Diffing committed snapshot pairs; change-set JSON and plain-text export compared to expected files | `tests/fixtures/`, `tests/golden/` | No |
| Game | Capturing a real install: gates, layout substitution (the version bytes are changed in memory only), sanity values, determinism | `tests/game/`, marker `game` | Yes (`AOE2DE_PATH`) |

**Conventions:**
- **Layout and naming:** pytest. Test files mirror the source layout (`tests/unit/<package path>/test_<module>.py`). Names describe behaviour, e.g. `test_collapse_groups_civs_by_value_pair`. One behaviour per test.
- **No outside dependencies:** use `tmp_path` for files. No network, no game files, no sleeps.
- **Coverage** (line and branch) is reported by every test run, with no minimum (D-25).
- **Fixtures:**
  - snapshots come from **public** builds only (P-09) and live in `tests/fixtures/game-derived/` with its `NOTICE`, because game content isn't GPL (P-22);
  - icons in fixtures are synthetic, never game art.
- **Golden files** change only deliberately (`uv run pytest --update-golden`), and the reviewer reads the golden diff.
- **Determinism is tested:** capturing the same input twice gives identical snapshots apart from capture metadata.

### Dependencies
- **Runtime dependencies stay few.** Each new one is justified in the PR: why it's needed, what alternatives exist, and its licence per [docs/legal.md](docs/legal.md).
- **Adding them:** `uv add` / `uv add --dev`, and always commit `uv.lock`.
- **Dependabot** (D-27) opens one grouped PR a week for minor and patch updates, plus security fixes at any time. They get reviewed like any PR.
  - **Major updates** come one at a time; read the changelog first.
- **The Biome binary version** is pinned in CI and bumped by hand, because Dependabot can't update it.

### Documentation
- **Language:** English.
- **Timing:** docs change in the same PR as the behaviour they describe.
- **Decisions:** a new or changed decision gets an entry in [docs/decisions.md](docs/decisions.md).
- **Format facts** go into [docs/reference/game-files.md](docs/reference/game-files.md), tagged `[verified]` with the build they were checked on.
- **AGENTS.md** stays short (under 200 lines) and holds only agent rules. The details live here.

## Continuous integration

- **On every PR and push to `main`** (D-11), on `windows-latest` and `ubuntu-latest`:
  - `pre-commit run --all-files`: ruff, Biome, file checks, safety hooks;
  - `mypy`;
  - `pytest` with a coverage report.

  PR titles are also checked against Conventional Commits. GitHub-hosted runners are free for public repositories.
- **Required status checks:** once these jobs exist (M0), they become required on `main`.
- **Game tests never run in CI**, because CI has no game install. Run them locally when capture code changes.
- **From M5:** a tag triggers the Windows release build on a GitHub-hosted runner. SignPath code signing, planned after the first release, requires that (see [docs/legal.md](docs/legal.md)).

## When a game update lands

1. **Capture the new build in the app** (a raw backup is made by default). If you use Steam's PUP branch, capture the live build *before* switching: the switch overwrites the install. Keep anything from a privately shared build private.
2. **Check the Diagnostics window:** stats status, layout used, round-trip and sanity results. If stats are available, run the game tests and spot-check a few values in Advanced Genie Editor.
3. **No layout passed:** follow [Contributing format support upstream](docs/reference/genieutils-py.md#contributing-format-support-upstream).
4. **Re-check the per-build facts** in [game-files.md](docs/reference/game-files.md): civ count, bonus string range, node keys, icon mapping. The game tests automate what they can.
5. **Once the build is public:** refresh the baseline snapshot and any fixtures, then release (D-10).

Upgrading genieutils-py: see [docs/reference/genieutils-py.md](docs/reference/genieutils-py.md#upgrading-the-pinned-version).

## Releases (from M5)

- Semantic versioning; tags `vX.Y.Z` on `main`. Tags and releases are created by the maintainer.
- A GitHub Actions workflow builds the Windows zip on tag. Signing via SignPath is added after the first public release (O-6).
- Each release also publishes a separate **baseline pack**: the snapshot and icons of the current live build, with a `NOTICE`, not inside the app zip (P-21).
- Before publishing, go through the release checklist in [docs/legal.md](docs/legal.md#shipping-the-windows-build-checklist).

## Reporting issues

- Use the issue templates.
- Paste the output of **Copy diagnostics** from the Diagnostics window.
- **Never attach snapshots, exports or values from a privately shared pre-release build.**
