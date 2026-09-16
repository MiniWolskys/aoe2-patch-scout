# SPDX-License-Identifier: GPL-3.0-or-later
"""Read the `.dat` with genieutils-py, gate the result, and normalize it (D-04, P-02).

genieutils objects never leave this module or `gates`: the snapshot holds plain JSON only (D-05).
When anything at all goes wrong the result is `stats: null` with a specific reason, because wrong
output is worse than missing output (D-04).
"""

import dataclasses
import logging
import zlib
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Final

from genieutils.common import ByteHandler
from genieutils.datfile import DatFile
from genieutils.versions import Version

from patch_scout.capture.gates import CheckResult, round_trip, sanity_checks
from patch_scout.errors import PatchScoutError
from patch_scout.snapshot import JsonObject, JsonValue

logger = logging.getLogger(__name__)

VERSION_BYTES: Final = 8
# genieutils-py supports these DE layouts; 7.7 is the oldest the README claims (genieutils-py.md).
OLDEST_DE_LAYOUT: Final = (7, 7)

type Parser = Callable[[bytes], DatFile]


class DatReadError(PatchScoutError):
    """The `.dat` could not be read at all."""


class BoundedByteHandler(ByteHandler):  # type: ignore[misc]  # ByteHandler is untyped
    """A byte handler that stops at the end of the buffer instead of reading short.

    `ByteHandler.consume_range` slices a memoryview, so a misread count returns fewer bytes and
    `int.from_bytes(b"")` is 0: a wrong layout then reads zeros rather than failing
    (genieutils-py.md). Raising instead turns that into a clean parse error.
    """

    def consume_range(self, length: int) -> memoryview:
        """Return the next `length` bytes, refusing to read past the end."""
        end = self.offset + length
        if end > len(self.content):
            raise DatReadError(f"read past the end of the .dat at byte {self.offset}")
        # genieutils-py is untyped, so mypy sees the base method as returning Any.
        sliced: memoryview = super().consume_range(length)
        return sliced


@dataclass(slots=True)
class Attempt:
    """One layout tried, and how far it got."""

    layout: str
    result: str
    detail: str

    def to_json(self) -> JsonObject:
        """The form stored in `flags.dat_attempts`."""
        return {"layout": self.layout, "result": self.result, "detail": self.detail}


@dataclass(slots=True)
class StatsResult:
    """What the stats tier produced, and why, ready for the snapshot's flags."""

    stats: JsonObject | None = None
    format_version: str | None = None
    layout_version: str | None = None
    format_verified: bool = False
    unavailable_reason: str | None = None
    attempts: list[Attempt] = field(default_factory=list)
    checks: list[CheckResult] = field(default_factory=list)

    @property
    def available(self) -> bool:
        """Whether the stats passed every gate."""
        return self.stats is not None


def parse_bytes(raw: bytes) -> DatFile:
    """Parse a decompressed `.dat` stream with bounds checking."""
    return DatFile.from_bytes(BoundedByteHandler(memoryview(raw)))


def inflate(compressed: bytes) -> bytes:
    """Decompress the `.dat`, which is raw DEFLATE with no zlib header (game-files.md §4)."""
    try:
        return zlib.decompress(compressed, wbits=-15)
    except zlib.error as exc:
        raise DatReadError(f"the .dat is not readable DEFLATE data: {exc}") from exc


def format_version(raw: bytes) -> str:
    """The version string the file carries, with its padding NULs stripped."""
    return raw[:VERSION_BYTES].decode("ascii", errors="replace").rstrip("\x00")


def candidate_layouts(version: str) -> list[str]:
    """The layouts to try, newest first.

    A known version is used as it stands. An unknown one falls back to every DE layout the
    library supports, sorted **numerically** so `VER 8.10` would come after `VER 8.9`: the enum
    compares its values as strings, which would order them wrongly (genieutils-py.md).
    """
    known = {member.value for member in Version}
    if version in known:
        return [version]
    layouts = [value for value in known if _numeric(value) >= OLDEST_DE_LAYOUT]
    return sorted(layouts, key=_numeric, reverse=True)


def substitute(raw: bytes, layout: str) -> bytes:
    """Return a copy of the stream whose version bytes name `layout`, padded with NULs."""
    header = layout.encode("ascii").ljust(VERSION_BYTES, b"\x00")
    if len(header) != VERSION_BYTES:
        raise DatReadError(f"{layout!r} does not fit in the version field")
    return header + raw[VERSION_BYTES:]


def read(
    compressed: bytes,
    civs: Sequence[JsonValue],
    tech_trees: Mapping[str, JsonValue],
    strings: JsonObject,
    *,
    parser: Parser = parse_bytes,
) -> StatsResult:
    """Read the `.dat`, trying each candidate layout until one passes every gate.

    Each failed attempt is released before the next one starts: a parsed DE file takes about a
    gigabyte (genieutils-py.md).
    """
    result = StatsResult()
    try:
        raw = inflate(compressed)
    except DatReadError as exc:
        result.unavailable_reason = str(exc)
        return result
    result.format_version = format_version(raw)
    layouts = candidate_layouts(result.format_version)
    logger.info("the .dat says %s; trying %s", result.format_version, ", ".join(layouts))

    for layout in layouts:
        attempt = _try_layout(raw, layout, civs, tech_trees, strings, parser, result)
        result.attempts.append(attempt)
        if attempt.result == "passed":
            result.layout_version = layout
            result.format_verified = layout == result.format_version
            return result
    result.unavailable_reason = _reason(result)
    return result


def _try_layout(
    raw: bytes,
    layout: str,
    civs: Sequence[JsonValue],
    tech_trees: Mapping[str, JsonValue],
    strings: JsonObject,
    parser: Parser,
    result: StatsResult,
) -> Attempt:
    stream = raw if layout == result.format_version else substitute(raw, layout)
    dat = None
    try:
        try:
            dat = parser(stream)
        except Exception as exc:  # any layout mismatch surfaces here, in many shapes
            logger.info("layout %s did not parse: %s", layout, exc)
            return Attempt(layout, "parse_error", f"{type(exc).__name__}: {exc}")
        passed, detail = round_trip(dat, stream)
        if not passed:
            return Attempt(layout, "roundtrip_mismatch", detail)
        checks = sanity_checks(dat, civs, tech_trees, strings)
        failed = [check for check in checks if not check.passed]
        if failed:
            result.checks = checks
            return Attempt(layout, "sanity_failed", "; ".join(check.detail for check in failed))
        result.checks = checks
        result.stats = normalize(dat)
        return Attempt(layout, "passed", detail)
    finally:
        del dat


def _reason(result: StatsResult) -> str:
    if not result.attempts:
        return f"no known layout could read .dat format {result.format_version!r}"
    first = result.attempts[0]
    if len(result.attempts) == 1:
        return f"{first.layout}: {first.detail}"
    return (
        f"no known layout could read .dat format {result.format_version!r}; "
        f"{len(result.attempts)} tried, best was {first.layout} ({first.result})"
    )


def normalize(dat: DatFile) -> JsonObject:
    """Turn a parsed file into plain JSON: civ records, units, techs and effects (D-20)."""
    return {
        "civ_dat": _civ_dat(dat),
        "units": _units(dat),
        "techs": {str(index): plain(tech) for index, tech in enumerate(dat.techs)},
        "effects": {
            str(index): {
                "name": effect.name,
                "commands": [plain(command) for command in effect.effect_commands],
            }
            for index, effect in enumerate(dat.effects)
        },
    }


def plain(value: object) -> JsonValue:
    """Convert a genieutils record to plain JSON values, tuples included."""
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {f.name: plain(getattr(value, f.name)) for f in dataclasses.fields(value)}
    if isinstance(value, list | tuple):
        return [plain(item) for item in value]
    if isinstance(value, bool | int | float | str) or value is None:
        return value
    return str(value)


def _civ_dat(dat: DatFile) -> list[JsonValue]:
    return [
        {
            "index": index,
            "name": civ.name,
            "tech_tree_effect_id": civ.tech_tree_id,
            "team_bonus_effect_id": civ.team_bonus_id,
            "resources": list(civ.resources),
            "icon_set": civ.icon_set,
            "player_type": civ.player_type,
        }
        for index, civ in enumerate(dat.civs)
    ]


def _units(dat: DatFile) -> JsonObject:
    """Store every non-empty unit slot as one base record plus per-civ overrides (P-03).

    Records are grouped by equality first, so only the distinct ones are converted to JSON: the
    live build has about 129,000 unit records but only a few thousand distinct ones.
    """
    slots = max((len(civ.units) for civ in dat.civs), default=0)
    units: JsonObject = {}
    for unit_id in range(slots):
        groups: list[tuple[object, list[int]]] = []
        absent: list[int] = []
        for civ_index, civ in enumerate(dat.civs):
            record = civ.units[unit_id] if unit_id < len(civ.units) else None
            if record is None:
                absent.append(civ_index)
                continue
            for representative, members in groups:
                if representative == record:
                    members.append(civ_index)
                    break
            else:
                groups.append((record, [civ_index]))
        if not groups:
            continue
        groups.sort(key=lambda group: (-len(group[1]), group[1][0]))
        base_record, base_civs = groups[0]
        base = plain(base_record)
        overrides: JsonObject = {}
        for representative, members in groups[1:]:
            difference = _difference(base, plain(representative))
            for member in members:
                overrides[str(member)] = dict(difference)
        stored_base_civs: list[JsonValue] = list(base_civs)
        stored_absent: list[JsonValue] = list(absent)
        units[str(unit_id)] = {
            "base": base,
            "base_civs": stored_base_civs,
            "overrides": overrides,
            "absent_civs": stored_absent,
        }
    return units


def _difference(base: JsonValue, other: JsonValue, prefix: str = "") -> JsonObject:
    """The fields of `other` that differ from `base`, as dotted paths; lists replaced whole."""
    if not isinstance(base, dict) or not isinstance(other, dict):
        return {}
    changed: JsonObject = {}
    for key in other:
        path = f"{prefix}{key}"
        old, new = base.get(key), other[key]
        if old == new:
            continue
        if isinstance(old, dict) and isinstance(new, dict):
            changed.update(_difference(old, new, f"{path}."))
        else:
            changed[path] = new
    return changed


def apply_overrides(entry: Mapping[str, JsonValue], civ_index: int) -> JsonObject | None:
    """Rebuild one civ's full unit record from the stored base and overrides.

    The choice of base is a storage detail, so the diff always reads records through this.
    """
    absent = entry.get("absent_civs")
    if isinstance(absent, list) and civ_index in absent:
        return None
    base = entry.get("base")
    if not isinstance(base, dict):
        return None
    overrides = entry.get("overrides")
    changes = overrides.get(str(civ_index)) if isinstance(overrides, dict) else None
    if not isinstance(changes, dict) or not changes:
        return dict(base)
    record = _deep_copy(base)
    for path, value in changes.items():
        _set_path(record, path.split("."), value)
    return record


def _deep_copy(value: JsonObject) -> JsonObject:
    return {
        key: _deep_copy(item) if isinstance(item, dict) else item for key, item in value.items()
    }


def _set_path(record: JsonObject, path: Sequence[str], value: JsonValue) -> None:
    target: JsonObject = record
    for key in path[:-1]:
        step = target.get(key)
        if not isinstance(step, dict):
            step = {}
            target[key] = step
        target = step
    target[path[-1]] = value


def _numeric(version: str) -> tuple[int, ...]:
    """Sort key for a version string, so `VER 8.10` comes after `VER 8.9`."""
    _, _, number = version.partition(" ")
    parts = []
    for part in number.split("."):
        parts.append(int(part) if part.isdigit() else -1)
    return tuple(parts) if parts else (-1,)
