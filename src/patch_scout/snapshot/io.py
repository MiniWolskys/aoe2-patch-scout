# SPDX-License-Identifier: GPL-3.0-or-later
"""Read and write snapshot files: deterministic JSON in a gzip container."""

import gzip
import json
from pathlib import Path

from patch_scout.snapshot.migrations import migrate
from patch_scout.snapshot.schema import JsonValue, Snapshot, SnapshotFormatError

SUFFIX = ".snapshot.json.gz"


def dumps(snapshot: Snapshot) -> bytes:
    """Serialize a snapshot to UTF-8 JSON bytes, deterministically.

    Keys are sorted and separators are tight, so the same capture always gives the same bytes.
    """
    text = json.dumps(
        snapshot.to_json(),
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return text.encode("utf-8")


def loads(data: bytes) -> Snapshot:
    """Parse snapshot JSON bytes and migrate the result to the current schema (P-15)."""
    try:
        parsed: JsonValue = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SnapshotFormatError(f"not a readable snapshot: {exc}") from exc
    return migrate(Snapshot.from_json(parsed))


def write(path: Path, snapshot: Snapshot) -> None:
    """Write a snapshot atomically: the file is either complete or absent.

    The gzip member gets no timestamp, so identical captures give identical files.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".part")
    payload = gzip.compress(dumps(snapshot), mtime=0)
    temporary.write_bytes(payload)
    temporary.replace(path)


def read(path: Path) -> Snapshot:
    """Read a snapshot file."""
    return loads(gzip.decompress(path.read_bytes()))
