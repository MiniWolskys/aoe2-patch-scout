# Licensing, game content and embargo

A summary for maintainers and contributors. **This is not legal advice.** Where something matters, read the source texts linked below.

## Our code

- **Licence:** **GPL-3.0-or-later** (D-17). The full text is in [LICENSE](../LICENSE).
- **Declared in** `pyproject.toml` as an SPDX expression: `license = "GPL-3.0-or-later"`, `license-files = ["LICENSE"]`.
- **Each source file** starts with `# SPDX-License-Identifier: GPL-3.0-or-later`.
- **Copyright line:** `Copyright (C) 2026 the Patch Scout contributors`.
- **Contributions** are accepted under the same licence (inbound = outbound). There is no CLA.

## Game content is not ours (P-22)

Everything derived from the game belongs to Microsoft and is used under the Game Content Usage Rules (below). That covers:
- icons converted from game files;
- string texts;
- unit, tech and effect data in snapshots.

**None of it is covered by the GPL.** The GPL allows commercial redistribution, which Microsoft's rules forbid. So game content is always kept apart from our code:

| Where | How game content is kept apart |
|---|---|
| Git repo | No raw game files, ever. Fixture snapshots from public builds (P-09) live in `tests/fixtures/game-derived/`, with a `NOTICE` file saying the content is © Microsoft, used under the rules, and not covered by the GPL. Fixture icons are synthetic. |
| App zip (release) | **No game content at all.** Only our code, dependencies and our own UI assets. |
| Baseline pack (release, P-21) | A separate download with the snapshot, its icons and a `NOTICE`. |
| User exports (archives, HTML, images, text) | Created by the user from their own install. The HTML export carries the Microsoft notice in its footer; export archives include the `NOTICE`. |

## Dependencies

| Component | Licence | Shipped in the Windows build | Notes |
|---|---|---|---|
| [genieutils-py](https://github.com/SiegeEngineers/genieutils-py) | LGPLv3 | Yes | See the obligations below. |
| [pywebview](https://github.com/r0x0r/pywebview) | BSD-3-Clause | Yes | |
| pywebview dependencies on Windows: pythonnet, clr-loader, cffi, pycparser | MIT, MIT, MIT-0, BSD-3-Clause | Yes | Checked in the installed metadata and licence files, 2026-09-15. |
| Other pywebview dependencies: proxy-tools, bottle, typing-extensions | MIT, MIT, PSF-2.0 | Yes | Checked in the installed metadata and licence files, 2026-09-15. |
| Pillow | MIT-CMU *(confirm when added)* | Yes | Wheels bundle native libraries with their own notices. |
| Image export JS library (e.g. modern-screenshot or html-to-image) | MIT *(confirm when chosen)* | Yes | Vendored single file (P-16). |
| CPython | PSF License | Yes (frozen runtime) | Includes third-party notices of its own. |
| PyInstaller | GPL-2.0-or-later with bootloader exception | Build tool only | The exception allows distributing frozen apps under any licence. |
| ruff, mypy, pytest, uv | Various permissive | No | Dev-only. |

**Using an LGPLv3 library from a GPL-3.0-or-later program is allowed.** LGPLv3 is GPLv3 plus extra permissions. See the [GNU licence compatibility FAQ](https://www.gnu.org/licenses/gpl-faq.html#AllCompatibility).

**When adding a runtime dependency:** confirm its licence is GPL-3.0-compatible and open source (SignPath also requires that), add it to this table and to `THIRD_PARTY_NOTICES`, and mention it in the PR.

## Shipping the Windows build: checklist

Every release (D-16) must meet these points.

- [ ] `LICENSE` (GPLv3 text) and `COPYING.LESSER` (LGPLv3 text) in the zip.
- [ ] `THIRD_PARTY_NOTICES`: every bundled package with version, licence, copyright notice and source URL, including Pillow's bundled native libraries and CPython. Generate it from the installed distributions' metadata at build time, then review it by hand.
- [ ] **GPL corresponding source:** release notes and the About screen link to the exact tagged commit. The build script and spec file are in the repo, so the build can be reproduced.
- [ ] **LGPLv3 §4 for genieutils-py:**
  - (a) A prominent notice that genieutils-py is used and is covered by the LGPLv3 (About screen + `THIRD_PARTY_NOTICES`).
  - (b) Copies of the GPL and LGPL texts (above).
  - (d0) Users must be able to rebuild with a modified genieutils-py. Our full source and build script are public, which covers this. Additionally, the one-folder build keeps the `genieutils` package as **loose, replaceable `.py` files** outside PyInstaller's archive (to verify in the M0 packaging spike).
- [ ] **No game content in the app zip.** The baseline pack is a separate asset with its own `NOTICE` (P-21, P-22).
- [ ] The Microsoft notice on the About screen and the release page.
- [ ] SHA-256 checksums of the release assets.
- [ ] Product name and version in the exe's file metadata (needed later for signing).

## Code signing (O-6)

**v1.0 ships unsigned.** Release notes explain the Windows SmartScreen "unknown publisher" warning and how to check the SHA-256 checksum.

**After the first public release**, apply to the [SignPath Foundation](https://signpath.org/apply) for free open-source code signing. Conditions, from [signpath.org/terms](https://signpath.org/terms), to re-check when applying:

- **Eligibility:**
  - OSI-approved licence (GPL-3.0-or-later qualifies) and no proprietary components in the signed package;
  - actively maintained and **already released** in the form to be signed;
  - no malware or potentially unwanted software.
  - SignPath also checks the project's reputation first.
- **Build:** artifacts are built from our own source on **GitHub-hosted runners** and submitted with SignPath's GitHub Action.
- **Project setup:**
  - team roles (authors, reviewers, approvers), all with MFA on GitHub and SignPath;
  - a **code signing policy** page linked from the README and the download page, with the SignPath attribution line from their terms and the team roles;
  - a **privacy statement** (the app sends no data).
- **Exe metadata:** product name and version are required.

**Approval time** isn't published.

## Game content (Microsoft)

### Game Content Usage Rules
Rules: https://www.xbox.com/en-US/developers/rules (dated January 2015). Read them there; the page may change, and Microsoft can withdraw permission at any time.

**Allowed:**
- using game content (screenshots, footage, music and "other elements") in free, personal, non-commercial items;
- sharing them on your own or third-party sites;
- optional donation links.

YouTube/Twitch revenue from videos is explicitly fine, which matters for our users.

**Not allowed:**
- selling the item or making money from it, including ads inside it;
- putting it behind a paywall or on pages that sell things;
- selling it through app stores;
- using Microsoft or game logos, or a name that implies an official product;
- reverse engineering the games to access the assets → accepted risk, **O-2** in [decisions.md](decisions.md).

**Required notice.** It uses Microsoft's template and links to the rules. It appears in the README, the About screen, the release page, the `NOTICE` files and the footer of HTML exports:

> Age of Empires II © Microsoft Corporation. Patch Scout was created under Microsoft's "[Game Content Usage Rules](https://www.xbox.com/en-US/developers/rules)" using assets from Age of Empires II, and it is not endorsed by or affiliated with Microsoft.

**Community practice** (checked 2026-09-15): SiegeEngineers/aoe2techtree publishes ~555 game icons, and aoe2companion and the AoE Fandom wiki host many more, all under these rules.

### What may go where

| Content | Git repo | App zip | Baseline pack | Why |
|---|---|---|---|---|
| Raw game files: `.dat`, game JSON, string files, DDS/PNG art | **Never** | **Never** | **Never** | Copyrighted game files. `.gitignore` blocks the common patterns. |
| Snapshots of **public** builds | Fixtures only, in `tests/fixtures/game-derived/` with `NOTICE` | No | Yes, with `NOTICE` | Derived game content, not GPL. |
| Converted game icons | No (fixtures use synthetic images) | No | Yes, with `NOTICE` | O-1, P-22 |
| Anything from a **privately shared** pre-release build | **Never** | **Never** | **Never** | Embargo (below). |
| Our own UI assets | Yes | Yes | — | GPL-3.0-or-later; must be original, not traced from game art. |

## Pre-release builds and embargo

- **Two kinds of pre-release build:**
  - **PUP (Public Update Preview):** a *public* Steam beta branch anyone can opt into. Not under embargo, but temporary.
  - **Builds shared privately with content creators:** may be under embargo or NDA. Their data never goes anywhere public.
- The tool never uploads anything (D-02). Users are responsible for the terms of their access.
- When exporting a snapshot or report ticked as pre-release, the app shows a reminder to check those terms (P-14).
- **Contributors and maintainers** never put data from privately shared builds in issues, PRs, commits, CI logs or screenshots. That covers snapshots, exports, texts, stat values and file hashes.
  - If a bug only reproduces on such a build, describe it without the data and wait for the public release, or contact a maintainer privately.
- **If embargoed content is pushed by mistake:**
  - Tell a maintainer at once.
  - Removing it takes a history rewrite on every affected branch, plus a request to GitHub Support to purge cached views. Forks and clones may still hold it.
