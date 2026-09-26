# SPDX-License-Identifier: GPL-3.0-or-later
"""Two snapshots of the same synthetic install, one build apart, for the diff tests.

Both are produced by the real capture, so the pair exercises the whole pipeline: readers, gates,
normalization and the icon store. Nothing here touches a real game folder (P-09).
"""

from dataclasses import dataclass
from pathlib import Path

from patch_scout.capture import runner
from patch_scout.capture.runner import CaptureRequest
from patch_scout.snapshot import Snapshot
from patch_scout.store import DataFolder
from support import dat as sample_dat
from support import game_tree

# The second build's string file: one text changed, one added.
NEW_STRINGS = (
    game_tree.STRINGS.replace(
        '26083 "A ranged unit." //trailing comment',
        '26083 "A ranged foot soldier." //trailing comment',
    )
    + '99001 "A brand new string"\n'
)


@dataclass(frozen=True, slots=True)
class Pair:
    """Two captures of the same install, and where their data lives."""

    old: Snapshot
    new: Snapshot
    folder: DataFolder


def make(tmp_path: Path) -> Pair:
    """Capture a synthetic install twice, changing the game in between.

    Between the two builds:

    * the Archer (unit 4) gains 5 hit points everywhere, and 10 for the one civ that overrode it;
    * the Archery Range (87) gains 100 hit points in every civ;
    * Fletching (tech 199) costs 20 more food;
    * a civ bonus effect command changes from 1.2 to 1.15;
    * the Bluelanders gain the Archer and Fletching nodes;
    * one help text changes and one string is added;
    * every icon is redrawn.
    """
    folder = DataFolder(tmp_path / "PatchScout")
    old_root = game_tree.write(tmp_path / "old", dat_bytes=sample_dat.sample_bytes())
    old = _capture(old_root, folder, "Live build", "old")
    new_root = game_tree.write(
        tmp_path / "new",
        dat_bytes=sample_dat.sample_bytes(
            archer_hp=35,
            blue_archer_hp=45,
            range_hp=1100,
            fletching_food=120,
            bonus_multiplier=1.15,
        ),
        unavailable_civs=(),
        strings=NEW_STRINGS,
        icon_colour=(120, 40, 80, 255),
    )
    new = _capture(new_root, folder, "PUP build", "new", prerelease=True)
    return Pair(old=old, new=new, folder=folder)


def _capture(
    root: Path, folder: DataFolder, label: str, capture_id: str, *, prerelease: bool = False
) -> Snapshot:
    result = runner.run(
        CaptureRequest(game_folder=root, label=label, prerelease=prerelease, raw_backups=False),
        folder,
        capture_id=capture_id,
    )
    assert result.snapshot is not None, "the synthetic capture must produce a snapshot"
    return result.snapshot
