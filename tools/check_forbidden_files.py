# SPDX-License-Identifier: GPL-3.0-or-later
"""Pre-commit hook: refuse game files and the maintainer's private notes.

Game content is (c) Microsoft and stays out of the repository. The only exceptions are synthetic
stand-ins and public-build snapshots under `tests/fixtures/` (docs/legal.md, D-24).
"""

import sys
from collections.abc import Sequence
from itertools import pairwise
from pathlib import PurePosixPath

# JSON files from the game's resources/_common/dat folder (game-files.md §3).
GAME_JSON_NAMES = frozenset(
    f"{name.lower()}.json"
    for name in (
        "adapterblacklist",
        "AIConsts",
        "airesourcetypes",
        "buttons",
        "chronicles_selection_group_def",
        "civilizations",
        "dropsites",
        "eras",
        "futuravailableunits",
        "hotkeys",
        "linkedTechs",
        "linkedUnits",
        "maps",
        "objreplacement",
        "paphosfutureavailableunits",
        "peru_campaign",
        "selection_group_def",
        "sharedbuildings",
        "sounds",
        "unitcategories",
        "unitlines",
    )
)


def forbidden_reason(path: str) -> str | None:
    """Return why `path` must not be committed, or None if it may be."""
    parts = tuple(part.lower() for part in PurePosixPath(path.replace("\\", "/")).parts)
    name = parts[-1]
    if ".private" in parts or name == "claude.local.md":
        return "the maintainer's private notes"
    if name.endswith(".dat"):
        return "a game data file (.dat)"
    if parts[:2] == ("tests", "fixtures"):
        return None
    if name.endswith(".dds"):
        return "game art (DDS)"
    if name.endswith("-utf8.txt"):
        return "a game string file"
    if name in GAME_JSON_NAMES or "civtechtrees" in parts[:-1]:
        return "a game JSON file"
    if name.endswith((".snapshot.json.gz", ".aoe2snap")):
        return "a snapshot, which may hold pre-release data"
    if ("resources", "_common") in pairwise(parts):
        return "a file copied from a game install"
    return None


def main(argv: Sequence[str] | None = None) -> int:
    """Print each refused path with its reason; return 1 if any path was refused."""
    paths = sys.argv[1:] if argv is None else argv
    refused = [(path, reason) for path in paths if (reason := forbidden_reason(path)) is not None]
    for path, reason in refused:
        sys.stderr.write(f"{path}: {reason}\n")
    if refused:
        sys.stderr.write("These files must not be committed; see docs/legal.md.\n")
    return 1 if refused else 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
