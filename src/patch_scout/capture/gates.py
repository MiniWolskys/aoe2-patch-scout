# SPDX-License-Identifier: GPL-3.0-or-later
"""The checks a parsed `.dat` must pass before its stats are trusted (D-06, P-01, P-02).

Two independent gates:

* the **round trip** re-encodes the parsed file and compares the whole stream, which catches a
  layout that has shifted;
* the **sanity cross-checks** compare the parsed data against the files tier, which does not
  depend on the `.dat` format at all, and catch data that shifted but stayed plausible.

Both are necessary. A single wrong value inside a record passes the round trip, so only the
sanity checks and, later, the diff's change-volume check can notice it.

The checks look at the records the **tech trees** name, not at every record in the file. Those
are the ones users see, and the file also holds scenario-only objects and unnamed internal techs
whose values and name IDs are deliberately unset. Measured on build 101.103.48987.0: all 10,167
tech tree nodes resolve their name ID, while 813 of the file's 2,921 name IDs overall do not.
"""

import logging
import math
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from genieutils.datfile import DatFile
from genieutils.tech import Tech
from genieutils.unit import Unit

from patch_scout.snapshot import JsonObject, JsonValue

logger = logging.getLogger(__name__)

# Ranges a record the tech trees name stays inside. Measured on build 101.103.48987.0:
# hit points -1000 to 20000, line of sight -1 to 21, speed 0 to 20, garrison 0 to 30,
# research time -1 to 190. The bounds below leave room for a much bigger patch; what they catch
# is shifted data, where floats come out astronomically large or not a number at all.
PLAUSIBLE_UNIT_VALUES: Final = {
    "hit_points": (-32768, 32767),
    "line_of_sight": (-1.0, 512.0),
    "speed": (0.0, 512.0),
    "garrison_capacity": (0, 255),
}
MAX_RESEARCH_TIME: Final = 100_000
MIN_RESEARCH_TIME: Final = -1
# A future build may rename a few records before their strings land; a shifted layout breaks
# far more than that. Measured on build 101.103.48987.0: 0 of 10,167 fail.
TOLERANCE: Final = 0.01


@dataclass(frozen=True, slots=True)
class CheckResult:
    """One sanity check and what it found."""

    name: str
    passed: bool
    detail: str

    def to_json(self) -> JsonObject:
        """The form stored in `flags.sanity_checks`."""
        return {"name": self.name, "passed": self.passed, "detail": self.detail}


def first_mismatch(left: bytes, right: bytes) -> int:
    """The offset of the first differing byte, or the length of the shorter stream."""
    limit = min(len(left), len(right))
    for offset in range(limit):
        if left[offset] != right[offset]:
            return offset
    return limit


def round_trip(dat: DatFile, original: bytes) -> tuple[bool, str]:
    """Re-encode the file and compare the whole stream, length included."""
    encoded = dat.to_bytes()
    if encoded == original:
        return True, f"{len(original)} bytes re-encoded exactly"
    if len(encoded) != len(original):
        return False, (
            f"re-encoded {len(encoded)} bytes against {len(original)}; "
            f"first difference at byte {first_mismatch(original, encoded)}"
        )
    return False, f"round-trip mismatch at byte {first_mismatch(original, encoded)}"


def sanity_checks(
    dat: DatFile,
    civs: Sequence[JsonValue],
    tech_trees: Mapping[str, JsonValue],
    strings: JsonObject,
) -> list[CheckResult]:
    """Cross-check the parsed file against the files tier (P-02)."""
    referenced = list(_referenced(dat, civs, tech_trees))
    return [
        _civ_count(dat, civs),
        _effect_references(dat),
        _tech_tree_references(dat, civs, tech_trees),
        _name_ids_resolve(referenced, strings),
        _values_are_plausible(referenced),
    ]


def _referenced(
    dat: DatFile, civs: Sequence[JsonValue], tech_trees: Mapping[str, JsonValue]
) -> Iterator[tuple[str, Unit | Tech]]:
    """Every `.dat` record a tech tree node names, with a label for the message."""
    for index, civ in enumerate(civs):
        if not isinstance(civ, dict) or index >= len(dat.civs):
            continue
        name = civ.get("internal_name")
        nodes = tech_trees.get(name) if isinstance(name, str) else None
        if not isinstance(nodes, list):
            continue
        units = dat.civs[index].units
        for node in nodes:
            if not isinstance(node, dict):
                continue
            node_id = node.get("node_id")
            if not isinstance(node_id, int) or node_id < 0:
                continue
            if node.get("use_type") == "Tech":
                if node_id < len(dat.techs):
                    yield f"{name} tech {node_id}", dat.techs[node_id]
            elif node_id < len(units) and (unit := units[node_id]) is not None:
                yield f"{name} unit {node_id}", unit


def _civ_count(dat: DatFile, civs: Sequence[JsonValue]) -> CheckResult:
    """The `.dat` must hold the same civs, in the same order, as `civilizations.json` (§6)."""
    expected, found = len(civs), len(dat.civs)
    return CheckResult(
        name="civ_count",
        passed=expected == found,
        detail=f"{found} civs in the .dat against {expected} in civilizations.json",
    )


def _effect_references(dat: DatFile) -> CheckResult:
    """Every civ and tech must point at an effect that exists."""
    count = len(dat.effects)
    bad = [
        f"civ {index}"
        for index, civ in enumerate(dat.civs)
        if not _in_range(civ.tech_tree_id, count) or not _in_range(civ.team_bonus_id, count)
    ]
    bad += [
        f"tech {index}"
        for index, tech in enumerate(dat.techs)
        if not _in_range(tech.effect_id, count)
    ]
    return CheckResult(
        name="effect_references",
        passed=not bad,
        detail=f"{len(bad)} bad references into {count} effects" + _examples(bad),
    )


def _tech_tree_references(
    dat: DatFile, civs: Sequence[JsonValue], tech_trees: Mapping[str, JsonValue]
) -> CheckResult:
    """Every tech tree node must name a record the `.dat` really has for that civ (§5)."""
    bad: list[str] = []
    checked = 0
    for index, civ in enumerate(civs):
        if not isinstance(civ, dict) or index >= len(dat.civs):
            continue
        name = civ.get("internal_name")
        nodes = tech_trees.get(name) if isinstance(name, str) else None
        if not isinstance(nodes, list):
            continue
        units = dat.civs[index].units
        for node in nodes:
            if not isinstance(node, dict):
                continue
            node_id = node.get("node_id")
            if not isinstance(node_id, int):
                continue
            checked += 1
            if node.get("use_type") == "Tech":
                if not 0 <= node_id < len(dat.techs):
                    bad.append(f"{name} tech {node_id}")
            elif not 0 <= node_id < len(units) or units[node_id] is None:
                bad.append(f"{name} unit {node_id}")
    return CheckResult(
        name="tech_tree_references",
        passed=not bad,
        detail=f"{len(bad)} of {checked} tech tree nodes point nowhere" + _examples(bad),
    )


def _name_ids_resolve(
    referenced: Sequence[tuple[str, Unit | Tech]], strings: JsonObject
) -> CheckResult:
    """Records the tech trees name must have name string IDs the string table knows (§9)."""
    table = _english(strings)
    if not table:
        return CheckResult("name_ids_resolve", True, "no string table to check against")
    bad: list[str] = []
    checked = 0
    for label, record in referenced:
        if record.language_dll_name <= 0:
            continue
        checked += 1
        if str(record.language_dll_name) not in table:
            bad.append(f"{label} name {record.language_dll_name}")
    allowed = int(checked * TOLERANCE)
    return CheckResult(
        name="name_ids_resolve",
        passed=len(bad) <= allowed,
        detail=f"{len(bad)} of {checked} name IDs do not resolve (up to {allowed} allowed)"
        + _examples(bad),
    )


def _values_are_plausible(referenced: Sequence[tuple[str, Unit | Tech]]) -> CheckResult:
    """Values must stay inside ranges a real record never leaves, and floats must be numbers."""
    bad: list[str] = []
    checked = 0
    for label, record in referenced:
        checked += 1
        if isinstance(record, Unit):
            bad.extend(_unit_problems(label, record))
        else:
            bad.extend(
                f"{label} research_time={location.research_time}"
                for location in record.research_locations
                if not MIN_RESEARCH_TIME <= location.research_time <= MAX_RESEARCH_TIME
            )
    return CheckResult(
        name="values_are_plausible",
        passed=not bad,
        detail=f"{len(bad)} of {checked} records hold values out of range" + _examples(bad),
    )


def _unit_problems(label: str, unit: Unit) -> Iterator[str]:
    for field, (low, high) in PLAUSIBLE_UNIT_VALUES.items():
        value = getattr(unit, field)
        if value is None:
            continue
        if (isinstance(value, float) and not math.isfinite(value)) or not low <= value <= high:
            yield f"{label} {field}={value}"


def _in_range(value: int, count: int) -> bool:
    """Whether an ID points into a table; negative values mean "none"."""
    return value < 0 or value < count


def _examples(bad: Sequence[str]) -> str:
    return f": {', '.join(bad[:5])}" if bad else ""


def _english(strings: JsonObject) -> Mapping[str, JsonValue]:
    tables = strings.get("tables")
    if not isinstance(tables, dict):
        return {}
    table = tables.get("en")
    return table if isinstance(table, dict) else {}
