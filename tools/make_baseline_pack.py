# SPDX-License-Identifier: GPL-3.0-or-later
"""Write the baseline pack for a release (P-21): one stored version, marked as a baseline.

Capture the current **public live** build in the app first, then run, e.g.:
    uv run python tools/make_baseline_pack.py <capture id> PatchScout-baseline-<build>.aoe2snap

The pack is a separate release asset, never part of the app zip (P-22). Never make one from a
build shared privately with creators (AGENTS.md rule 3).
"""

import argparse
import importlib.metadata
from pathlib import Path

from patch_scout.store import DataFolder, Library, archive


def main(argv: list[str] | None = None) -> int:
    """Export one version of the data folder as a baseline pack; returns the exit code."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("capture_id", help="the version to publish, from Diagnostics")
    parser.add_argument("output", type=Path, help=f"where to write the pack (*{archive.SUFFIX})")
    parser.add_argument("--data-folder", type=Path, help="default: the app's data folder")
    args = parser.parse_args(argv)
    folder = DataFolder(args.data_folder) if args.data_folder else DataFolder.default()
    entry = Library(folder).get(args.capture_id)
    if entry is None:
        parser.error(f"no version {args.capture_id} in {folder.root}")
    if entry.prerelease:
        parser.error("that version is marked pre-release; a baseline pack is a public live build")
    archive.export(
        folder,
        args.capture_id,
        args.output,
        tool_version=importlib.metadata.version("patch-scout"),
        notice=archive.NOTICE_TEXT,
        baseline=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
