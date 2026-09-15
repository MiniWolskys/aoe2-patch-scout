# Decision log

One entry per decision, grouped by topic. **IDs are permanent.** The prefix (`D` design, `P` proposal, `O` open question) only records how an entry started; the status says where it stands.

**Statuses:**
- **Decided:** agreed; change only with a new entry or an explicit amendment.
- **Proposed:** suggested, waiting for maintainer approval.
- **Open:** needs a maintainer decision.
- **Rejected:** considered and declined; kept for the record.

---

## Product and scope

### D-01 Goal and audience: Decided
The tool diffs AoE2:DE game data between two builds and reports every gameplay-relevant change. Its main users are streamers and YouTubers who get pre-release builds without patch notes. Most use Windows and aren't developers.

### D-02 Offline, read-only, private: Decided
- No network access at runtime, no telemetry, no automatic upload of anything.
- The game folder is strictly read-only.
- Captured data stays on the user's machine unless the user exports it.

### D-14 Game content in scope: Decided
- **In scope:** the main game, including the Chronicles (`antiquity` era) civs that live in the main `.dat`.
- **Out of scope for v1:** Return of Rome (`modes\Pompeii`, with its own `VER 8.8` `.dat`). The reader takes a "data root" so it can be added later.
- **Shown apart:** the comparison keeps the Chronicles civs apart from the base civs (D-38).

### D-38 Chronicles civs are shown apart: Decided
Chosen by the maintainer on 2026-09-15.
- **Why:** Chronicles: Battle for Greece is a solo mode, available only in campaigns through a DLC. Its civs are unlikely to change. To users it feels like a separate mode, much like Return of Rome, even though its civs live in the main `.dat`.
- **Capture and diff:** unchanged. The Chronicles civs are captured and compared like every other civ (D-14), and their era (`antiquity` in `civilizations.json`) is kept.
- **Comparison:** they're kept apart from the base civs. The exact form, e.g. their own group or a filter, is designed with the comparison screen (M4; [ui.md](design/ui.md#open-questions)).

### D-39 Civ overview after v1.0: Decided
Chosen by the maintainer on 2026-09-15.
- **What:** a view of one civ's full tech tree in one version: availability, civ and team bonuses, unit and tech stats, with a comparison's changes highlighted.
- **Why:** a single change, such as a new unit, only makes sense next to what the civ already has and lacks.
- **When:** after v1.0. v1 shows changes only.
- **Constraint from now on:** snapshots already hold everything the overview needs: every tech tree node with its status, building offers, bonus texts, units, techs and effects. Captures (M1–M2) must keep all of it, so the overview also works on older snapshots.
- **Not the same as P-17:** it shows the context and doesn't compute bonus-applied stats (D-20).

### D-15 GUI in v1: Decided
v1 ships a pywebview desktop GUI.

### P-08 Developer CLI: Rejected
There is no CLI. The GUI has a **Diagnostics window** instead:
- environment information;
- capture log with timings;
- gate details (version string, layout used, round-trip result, sanity checks);
- snapshot inspector;
- Copy diagnostics.

Tests call the Python API directly, and developers can start the app with `--debug` for the WebView developer tools.

### D-16 Standalone Windows executable from v1: Decided
v1 is distributed as a Windows build on GitHub Releases, so users don't need Python. The LGPLv3 obligations for bundling genieutils-py apply from the first release (see [legal.md](legal.md)).

### P-13 Presentation and exports: Decided (amended)
- **In the app:** the UI is the main output, good enough to show directly in a video.
- **Exports:**
  - **plain text** (Unicode bullets, no markup) for descriptions and chat;
  - **self-contained HTML**;
  - **PNG image** of the current view or a selected section.
- **No Markdown export**: most users wouldn't know what to do with it.


### O-3 Languages: Decided
**English only for v1**, but designed for more languages from the start (P-20).

### P-20 Designed for several languages: Decided
- Snapshots store string tables per language (`strings.tables.<lang>`).
- Every user-visible label and generated sentence comes from an i18n message catalog; no hardcoded English in code.
- Game names are looked up in the chosen language, falling back to English.
- Steam's app manifest records the game's language, which a later language selector can use as its default.

### D-36 Message catalog format: Decided
- **One flat JSON object per language** in `patch_scout/i18n/`, e.g. `en.json`. Dotted keys such as `capture.dialog.title` map to messages.
- **Placeholders** use Python `str.format` syntax with names only: `"Reading {file}"`. Literal braces are doubled.
- **Missing text:** a message missing from a language falls back to English. A key missing from English, or a placeholder without a value, raises an error.
- **Why:** Python and the frontend can read the same files, with no dependency and no build step (P-16).
- **Chosen over** nested JSON, and gettext `.po` files, which need a compile step and are awkward in JavaScript.

### O-7 Project home: Decided
Hosted under `MiniWolskys` for now; a move (e.g. to SiegeEngineers) may be considered later.

### P-11 Project name: Decided
**Patch Scout.**

| Thing | Name |
|---|---|
| Product | Patch Scout |
| GitHub repo | `MiniWolskys/aoe2-patch-scout` (renamed from `aoe2-techtree-diff-tool` on 2026-09-15) |
| Python package | `patch_scout` |
| Entry point | `patch-scout` |
| Data folder | `%LOCALAPPDATA%\PatchScout\` |

- **Availability**, checked on GitHub and PyPI on 2026-09-15: `aoe2-patch-scout` and `patch-scout` were free. An unrelated academic security project is called "PatchScout".
- **Constraints:** no "Age of Empires" in the product name, and nothing implying an official tool (Microsoft's rules). The "aoe2" repo prefix follows community practice.


---

## Architecture and data

### D-03 `.dat` reader: genieutils-py: Decided
- Use [genieutils-py](https://github.com/SiegeEngineers/genieutils-py) as a normal dependency with a version floor (currently `>=0.1.2`).
- Never vendor or fork it; format fixes go upstream.
- Tapsa/genieutils (C++) is a reference only.

### D-04 Two tiers: Decided
- The **files tier** (JSON, strings, icons) always runs.
- The **stats tier** (`.dat`) is attempted and gated.

Partial output is acceptable; wrong output is not.

### D-05 Capture and diff are separate stages: Decided
Capture writes a normalized, versioned snapshot; the diff compares two snapshots. Snapshots contain plain JSON values only, never library objects.

### D-06 Round-trip gate is mandatory: Decided
Refined by P-01 and P-02.

### P-01 Where the round-trip gate runs: Decided
- It runs during capture, on the **decompressed** stream.
- The result is stored in the snapshot.
- The diff compares stats only when both snapshots passed.

### P-02 Unknown version strings and sanity checks: Decided (amended)
The version string carries no game data; it only selects the parser layout. When it's unknown:
1. The tool overwrites it **in memory** with a known version, newest first, and parses (**layout substitution**).
2. The layout is accepted only if:
   - the round trip is byte-exact, and
   - the **sanity cross-checks** against the files tier pass: civ count and order, tech tree references resolve, name IDs resolve, values in plausible ranges.
3. Stats are then available, flagged `format_verified: false`, and the UI shows a mild notice naming the layout used.

**Never:** adding enum members at runtime, which avoids genieutils-py's string-comparison bug.

Details: [genieutils-py.md](reference/genieutils-py.md#unknown-version-strings-layout-substitution). Entities are matched by ID across versions (P-07), and snapshot fields are looked up by name, so field order never matters.

### P-03 Capture wide, filter at diff time: Decided
- Every non-empty unit slot of every civ is stored, as base + per-civ overrides.
- Reachability and the allowlist are applied at diff time.

### D-07 Per-civ collapsing: Decided
A change is grouped by value across civs: "(all civs)", "(Franks only)"…, based on raw unit values (D-20).

### D-08 Diff fields come from an allowlist: Decided

### D-37 Unit reachability: Decided
Chosen by the maintainer on 2026-09-15, from the M0 link spike ([game-files.md §7](reference/game-files.md#7-futuravailableunitsjson--paphosfutureavailableunitsjson)).
- **Seeds:** a civ's tech tree nodes and building offers, in either snapshot.
- **Also reachable:** transform forms, and named dismount-style forms (`blood_unit_id`). These links are followed until nothing new is added.
- **Projectiles** are reported on the unit that fires them, not as units of their own.
- **Not followed:** corpses and rubble, tracking units, drop sites, annexes, stack units, and the reverse train-location link.
- **Object swaps** (`objreplacement.json`, added 2026-09-15): not followed.
  - The replacements that matter, such as Port, Mule Cart and Settlement, are already tech tree nodes of their civs.
  - The female Villager is a variant of the Villager and isn't reported on its own.
- **Variants** (added 2026-09-15): the Town Center replacement (444) is present in every civ and swapped in by a game setting, like the female Villager. It isn't reported on its own.
- **Unit tasks** (`Bird.tasks`, added 2026-09-15): not followed.
  - Their links to other units (task type 155) point to the units an ability affects, e.g. Centurion → infantry, Monaspa → Knights, Hippeus → Polemarch. They don't name unit forms.
  - That reading is inferred from the targets.
- **Open:** how the Spartan Polemarch variants become reachable.
  - The maintainer wants them counted for the Spartans, but none of the followed links leads to them.
  - Their source (starting units, upgrade techs…) is to be found in M3.

Details: [diff-rules.md](design/diff-rules.md#reachability-d-37).

### D-20 Raw data only; civ bonuses never applied to units: Decided
- Snapshots store raw game data: unit records, techs, effects (including civ and team bonuses), civ records.
- Civ bonuses are **never applied to unit stats** in v1, neither at capture nor at compare. Bonuses can depend on age, researched techs and unit class, and applying them would add a lot of complexity.
- The app shows bonuses and units separately, as the game does:
  - a **civ bonuses** view (bonus text + effect sentences);
  - a **units** view (raw stats).
- Showing how a unit is affected by its civ's bonuses may come later.


### P-17 Effective (bonus-applied) stats: Decided, not in v1
Superseded by D-20. Kept on the roadmap under "Later".

### O-5 Showing bonus and effect changes: Decided
For every changed effect:
1. the game's own text diff, when the bonus or help text changed;
2. a **generated sentence** when a template exists for the command type;
3. otherwise, the **raw effect command**.


### P-04 Full English string tables in every snapshot: Decided

### P-05 Fingerprint all inputs: Decided
A new capture counts as identical only if every input file's hash matches.

### P-06 Icon identity uses full-size pixels: Decided

### P-07 Entity identity: Decided
- Units, techs and effects are matched by numeric ID.
- Civs by `internal_name`.
- Tech tree nodes by (civ, `Use Type`, `Node ID`).
- A name change under the same ID is a rename.

### P-15 Snapshot schema migrations: Decided

### P-16 Frontend without a build step: Decided
Third-party JavaScript, e.g. an image export library, is vendored as a single file.

### D-13 Stack: Decided
- Python backend.
- UI in HTML/CSS/JS through pywebview.
- Extraction is isolated: the UI never reads game files.

### D-40 WebView2 Runtime: rely on Windows' copy: Decided
Chosen by the maintainer on 2026-09-15, in the app shell spec.
- **What:** the app uses the Evergreen WebView2 Runtime that Windows provides. It isn't bundled.
- **Why:**
  - Microsoft preinstalls it on every Windows 11 device, pushed it to eligible Windows 10 devices, and keeps it updated.
  - The Fixed Version is over 250 MB, never updates itself, needs extra `icacls` permissions on Windows 10, and is proprietary, which conflicts with SignPath's rule (P-21).
- **When it's missing:**
  - before opening the window, the app checks Microsoft's documented registry values;
  - a native message box explains it and offers to open Microsoft's download page in the user's browser, then the app exits. The app itself makes no connection (D-02);
  - if pywebview still falls back to another engine after start, the window closes, then the same message shows, and the app exits with code 1.
- **Details:** [packaging.md](reference/packaging.md#webview2-engine-detection-verified).

### D-19 Never assume where the game is installed: Decided
- Detection (Steam; Microsoft Store / Xbox app; folders used before) only **proposes** a folder in an editable field.
- The user can always browse to another folder, and every folder is validated.
- When detection finds nothing, that's a normal outcome.
- No hardcoded install paths anywhere.


### P-18 Editable metadata in a library index: Decided
Snapshot files are immutable. Labels, the pre-release flag and notes live in `library.json`, so renaming or re-ticking never rewrites a snapshot. The index can be rebuilt from the snapshot files.

### P-19 Raw backups on by default, content-addressed: Decided
- A build's type can't be detected reliably, so every capture keeps a raw backup (~15 MB per new build) of its input files.
- Files are stored by hash, so unchanged files are stored once.
- Backups can be turned off or purged in Settings.

Amends D-12.

### D-12 Optional raw backup: Decided
The raw `.dat`, JSON and string files are kept as a safety net against extractor bugs, and never exported. Default: see P-19.

### P-10 Local data location: Decided
`%LOCALAPPDATA%\PatchScout\`, changeable in settings.

---

## Library and pre-release builds

### P-14 Labels and pre-release flag: Decided (amended)
- A **pre-release tickbox** at capture, editable later in the version details (D-32).
- **Click a version's name in its details to rename it.**
- Default label: `<game build> · <date>`.


### P-23 Prefill the pre-release tickbox from Steam: Decided
Steam's Public Update Preview (PUP) is a **beta branch of the same app**: switching overwrites the live install in place.
- **Prefill:** if Steam's app manifest shows a beta branch is selected, prefill the tickbox. Whether and where the manifest records that is to verify while on the PUP branch; on the live branch no such field exists.
- **Reminder:** the capture dialog and the first-launch screen remind users to capture the live build *before* switching branches.

---

## User interface

Chosen by the maintainer on 2026-09-15 after three rounds of mockups. Details: [ui.md](design/ui.md).

### D-32 One window with a version list: Decided
The window has no navigation rail. A **version list** on the left replaces the separate Library, Capture and Compare screens.
- **Top:** **Capture new version** and **Import**. **Bottom:** Diagnostics and Settings. The list can collapse to a narrow strip.
- **Click a version** to open its details: rename, pre-release tickbox, notes, export, delete.
- **To compare two versions:**
  - hover another version and click its **Compare** button;
  - or Ctrl+click it;
  - or use **Compare with…** in the details.
- **In a comparison:**
  - both versions are tagged OLD and NEW in the list;
  - the header pickers change either side or swap them;
  - clicking a version in the list opens its details, with a link back to the comparison.
- **Old and new are assigned automatically:** the lower game build is old; for the same build, the earlier capture is old.
- **Capture** opens a dialog: game folder, label, pre-release tickbox. The capture then runs as a row at the top of the list, and the app stays usable. When it finishes, the new version opens compared with the previous newest version.

### D-33 Comparisons are navigated by civilization: Decided
- The comparison lists **Overall** first: changes to every civ, with exceptions noted. Then comes each civ that has changes.
- A civ added in the new build is marked **NEW**.
- This replaces navigation by change category. The change set keeps its categories and ordering ([diff-rules.md](design/diff-rules.md)); how they show inside a civ's page is still to be designed.

### D-34 Red means old, green means new: Decided
- **Red marks the old value and green the new value**, whatever the direction of the change. The same colours mark removed and added text, the OLD/NEW tags and the NEW civ badge, and nothing else.
- **The app doesn't judge changes as buffs or nerfs:** many changes can't be judged reliably, and a wrong judgement would be wrong output. A buff/nerf indicator may come later; it isn't planned.
- **Colour is never the only signal:** the old value always comes first, before an arrow, and removed text is struck through.

### D-35 Dark theme, Forge: Decided
- The app has one dark theme, **Forge**: warm iron neutrals with a brass accent. Game icons are the only other colour.
- **Status colours avoid red and green:** success is a neutral check, warnings and pre-release are orange, notices are steel blue.
- **Tokens:** [ui-theme.css](design/ui-theme.css). Typography, sizes and contrast: [ui.md](design/ui.md).
- **Chosen over:** a light editorial theme, an icon-tile theme, and three other dark palettes (Keep, Byzantium, Graphite).

### D-42 Window size: Decided
Chosen by the maintainer on 2026-09-15, in the app shell spec.
- The window opens at **1440×900**, centred on the primary screen, when that screen has room for it (at least 1440×980, leaving space for the title bar and the taskbar); otherwise it opens maximized.
- **Which screen:** the size is chosen for, and the window is placed on, the primary screen. With no screen information at all (an empty screen list), it opens maximized at the preferred size instead.
- **Minimum size: 1120×640.** It fits 1366×768 screens and 1080p laptops at 150% scaling, which have about 1280×680 of usable space.
- **Units:** logical pixels; pywebview multiplies them by the screen's scaling factor.
- **Consequence for M4:** the comparison must work at 1120px wide. Collapsing the version list frees 216px.

---

## Icons and game content

### D-09 Icons: Decided (amended)
- **Extraction:** all icons, including the game's **stat icons** (HP, attack, armour…), are extracted at capture from the install being captured and kept in the shared content-addressed icon store.
- **No self-drawn stat icons:** an earlier plan to draw our own pictograms, to avoid game art, was dropped once game icons were allowed (O-1).
- **App assets:** the app bundles only simple UI assets of its own (placeholder image, badges).
- **Fallback:** text labels when an icon is missing.

### O-1 Game icons in exports and baselines: Decided (option B)
Exports and baseline snapshots include the converted game icons, so users recognise what they know from the game.

**Legal context** (not legal advice): Microsoft's Game Content Usage Rules allow game content in free, non-commercial, ad-free items that carry their notice. aoe2techtree (~555 icons), aoe2companion and the community wiki host game icons that way.

**Conditions:** see P-22.

### P-22 Keep game content apart from GPL code: Decided
Game-derived content (icons, strings, data values) is © Microsoft and can't be licensed under the GPL, which allows commercial use; Microsoft's rules don't.
- It lives in separate files or folders with a notice saying so, both in the repo (fixture snapshots) and in releases (baseline pack).
- The app zip contains no game content.

Details: [legal.md](legal.md).

### D-10 Baseline snapshots: Decided
Every release publishes a snapshot of the current live build, so a user who installs after a patch can still diff.

### O-4 Baseline delivery: Decided (A + B)
- (A) A new release when a game patch needs it.
- (B) Baseline snapshots are also published as separate downloads that users import with the **Import** button (D-32).

### P-21 Baseline pack is a separate download: Decided
The baseline (snapshot + icons) is a separate **baseline pack** on the release page, not inside the app zip. Together with P-22, this keeps the GPL software free of game content and satisfies SignPath's rule against proprietary components in signed packages. The first-launch screen offers both: capture your game, or import the baseline pack from the release page (D-32).

### O-2 The "no reverse engineering" clause: Decided (accepted risk)
The clause: *"You can't reverse engineer our games to access the assets"* (Microsoft, Game Content Usage Rules).
- **Position:** reading the game's data files is accepted as common community practice (aoe2techtree, genieutils-py, the modding tools Microsoft ships with the game).
- **Response plan:** if Microsoft objects, we comply.


---

## Development, licensing and releases

### D-17 Licence: GPL-3.0-or-later: Decided
Covers our code only; game content is excluded (P-22).

### D-18 Development tooling: uv: Decided

### P-12 Python version: Decided
- Python **3.12** for development and builds: `.python-version` 3.12, `requires-python = ">=3.12"`.
- **3.13 status (checked 2026-09-15):** every dependency declares support and ships wheels, but pywebview's own CI tests Windows on 3.12 only.
- **When to revisit:** after an M5 build smoke test on 3.13. Avoid free-threaded builds.

### D-11 Testing and CI: Decided (amended)
- **CI:** GitHub Actions on GitHub-hosted runners (free for public repositories), on `windows-latest` and `ubuntu-latest`:
  - pre-commit on all files: ruff, Biome, file checks, safety hooks (D-24, D-26);
  - `mypy`;
  - `pytest` with a coverage report (D-25).

  PR titles are checked against Conventional Commits (D-22).
- **Game tests** need a real install and run locally only.
- **Fixtures:** the diff layer is covered by committed snapshot-pair fixtures.


### P-09 Fixtures come from public builds only: Decided
Fixture snapshots come from released live builds, and icons in fixtures are synthetic.

### O-6 Code signing: Decided (option B, after the first release)
- **Plan:** SignPath Foundation's free signing for open-source projects.
- **Timing:** SignPath requires an existing public release and does a reputation check, so **v1.0 ships unsigned** and we apply afterwards.
- **Requirements to prepare:**
  - release builds on GitHub-hosted runners;
  - a code signing policy page with team roles;
  - MFA for team members;
  - a privacy statement ("the app sends no data");
  - product name and version metadata in the exe;
  - no proprietary components in the signed package (P-21).

---

## Development process

### D-21 Git workflow: Decided
- **GitHub flow:** short-lived branches from `main`, one topic per pull request.
- **Squash merges:** the PR title becomes the commit subject on `main`, and the branch is deleted after merging.
- **Enforced by GitHub** (repository settings, 2026-09-15):
  - squash merge is the only merge method, and merged branches are deleted automatically;
  - on `main`: a pull request is required, history must be linear, and conversations must be resolved;
  - no force pushes or deletions on `main`;
  - the rules apply to admins too.

### D-22 Conventional Commits: Decided
Commit messages and PR titles follow [Conventional Commits](https://www.conventionalcommits.org/) (`type(scope): summary`).
- CI checks PR titles, because they become the commits on `main`.
- It also makes generated release notes and version bumps possible later.

### D-23 Review and merge: Decided
- Every change to `main` goes through a pull request with green CI and resolved conversations.
- **The maintainer reviews and merges every pull request.** Agents never merge.
- **GitHub requires 0 approvals:** agents open PRs with the maintainer's account, and GitHub doesn't let authors approve their own PRs. Revisit when a second maintainer joins.
- **Required status checks** are added to branch protection once the CI jobs exist and have run (M0).

### D-24 Pre-commit hooks: Decided
pre-commit is a dev dependency, installed in each clone. It runs:
- ruff and Biome;
- file hygiene checks;
- safety hooks that refuse game data files, `.private/` and `CLAUDE.local.md`.

CI runs the same hooks on all files as a backstop.

### D-25 Coverage is reported, not gated: Decided
CI reports line and branch coverage (pytest-cov). There is no minimum.

### D-26 Frontend checks with Biome: Decided
The Biome standalone binary lints and formats JavaScript and CSS, locally through pre-commit and in CI, without any Node toolchain.

### D-27 Dependency updates with Dependabot: Decided
- **Security:** alerts and automatic security-fix PRs are enabled (2026-09-15).
- **Version updates:** one grouped PR a week per ecosystem (uv, GitHub Actions) for minor and patch updates. Major updates come as separate PRs. Commit prefix `chore(deps)`.
- **Setup:** configured in M0, once `uv.lock` exists.

### D-28 Agent approval gates: Decided
- **Features and design changes:** an approved spec, then an approved implementation plan, before coding.
- **Bug fixes and chores:** an approved short plan.
- Nothing starts without explicit approval.

### D-29 Agent git autonomy: Decided
- **Allowed:** commit on the task branch, push it, open a pull request.
- **Never, without an explicit request:** commit to `main`, merge, force-push, bypass hooks or branch protection, change repository settings.

### D-30 One working copy, no worktrees: Decided
Agents work in the main working copy, one task branch at a time. Worktrees would lack the maintainer's local, untracked files.

### D-31 Issues are optional: Decided
Pull request descriptions carry the context; an issue is linked when one exists.
