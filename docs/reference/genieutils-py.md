# genieutils-py reference

Facts about the `.dat` reader this project depends on, checked on 2026-09-15 against the upstream sources.

**Re-check this page whenever the pinned version changes.** Never take class or field names from memory or from this page alone: read the installed package source (`.venv\Lib\site-packages\genieutils\`).

- **Repo:** https://github.com/SiegeEngineers/genieutils-py (main author: HSZemi)
- **PyPI:** `genieutils-py`; latest `0.1.2`, released 2026-04-28
- **Licence:** LGPLv3. The LICENSE text is plain LGPL v3; "-only" vs "-or-later" isn't stated.
- **Python:** `>=3.11`. It likely needs 3.11 for `zlib.compress(..., wbits=-15)`; that is an inference.
- **Runtime dependencies:** none (standard library only).
- **Size:** ~4.2k lines in 19 files; `unit.py` alone is ~1.7k.
- **Console script:** `dat-to-json` prints `dataclasses.asdict(DatFile.parse(file))` as JSON.

## Why this library (D-03)

**Rejected alternative: Tapsa/genieutils (C++).** It needs CMake, Boost iostreams, zlib, LZ4 and Iconv (Boost `program_options` only for its tools and tests). It has no Python bindings and no package, so it can't ship to Windows streamers.

**genieutils-py is ahead on DE formats:** VER 8.9 reached genieutils-py on 2026-04-28 and the C++ library on 2026-07-08.

**It has a byte-exact round-trip test**, which the C++ library lacks and our gate design relies on.

**The C++ repo stays useful as a reference:** its version branches (`if (gv >= GV_C27)`…) show which fields moved when a format changes.

## API (as of 0.1.2)

- **Parse a compressed file:** `DatFile.parse(path)` (classmethod, `genieutils.datfile`).
- **Write a compressed file:** `DatFile.save(path)`. We never write `.dat` files, so this is for reference only.
- **Low level:** `DatFile.from_bytes(handler)` reads from a byte handler over the **decompressed** stream. `DatFile.to_bytes()` returns **uncompressed** bytes.
  - Its `version` parameter is ignored; `self.version` (a `str`) is used.
  - The handler is `genieutils.common.ByteHandler(memoryview(raw))`. [verified 0.1.2]
- **`from_bytes` doesn't check that it consumed the whole buffer.** A wrong layout can stop early without any error; see [Measured on the live build](#measured-on-the-live-build). [verified 0.1.2]
- **Reads aren't bounds-checked.** `ByteHandler.consume_range` slices a `memoryview`, which returns fewer bytes past the end, and `int.from_bytes(b'')` is 0. A misread count can then read zeros instead of failing. Read through a `ByteHandler` subclass whose `consume_range` raises at the end of the buffer, as the M0 spike did. [verified 0.1.2]
- **Strings** are decoded as strict UTF-8 after stripping trailing NULs, so invalid bytes raise `UnicodeDecodeError`. **Floats** go through `struct` format `'f'`. [verified 0.1.2]
- **Decompression:** `zlib.decompress(content, wbits=-15)` on load, `zlib.compress(..., level=-1, wbits=-15)` on save.

### `DatFile` top-level fields (in order)
`version`, `float_ptr_terrain_tables`, `terrain_pass_graphic_pointers`, `terrain_restrictions`, `player_colours`, `sounds`, `graphics`, `terrain_block`, `random_maps`, `effects`, `unit_headers`, `civs`, `techs`, `time_slice`, `unit_kill_rate`, `unit_kill_total`, `unit_hit_point_rate`, `unit_hit_point_total`, `razing_kill_rate`, `razing_kill_total`, `tech_tree`.

### `Civ` fields
`player_type`, `name`, `tech_tree_id`, `team_bonus_id`, `resources`, `icon_set`, `units`.

**There is no top-level unit list.** Units live per civ in `civ.units: list[Unit | None]`. Both `civ.units` and `graphics` contain `None` holes.

## Version handling

### Supported versions
`Version` enum members, exactly:

```
UNDEFINED, VER_71 'VER 7.1', VER_72, VER_73, VER_74, VER_75, VER_76, VER_77,
VER_78 'VER 7.8', VER_84 'VER 8.4', VER_88 'VER 8.8', VER_89 'VER 8.9'
```

- There are no members for 7.9–8.3 or 8.5–8.7.
- The README claims support from 7.7.
- The upstream round-trip test covers 7.7, 7.8, 8.4, 8.8 and 8.9.

### Hard gate on unknown versions
`DatFile.from_bytes` does `Version(content.read_string(8))`. `read_string` strips trailing NULs, and any string not in the enum raises `ValueError`, even when the layout didn't change. [verified: `VER 9.0` does, on build 101.103.48987.0]

The version string carries **no game data**. It only tells the parser which layout to expect.

### Landmine: string comparison
```python
def __lt__(self, other: 'Version'):
    return self.value < other.value      # same pattern for __le__, __gt__, __ge__
```

**The problem:** parsing code uses checks like `content.version >= Version.VER_88`. With string ordering, `'VER 8.10' < 'VER 8.9'` and `'VER 10.0' < 'VER 7.1'`. If a two-digit version member were added to the enum, or injected at runtime, version-gated fields would be silently skipped on read *and* write. The file might still round-trip byte-exactly.

**It's latent today:** no such member exists.

**Project rules:**
- Never add or inject enum members at runtime; use layout substitution (next section).
- Propose a numeric comparison upstream before the game reaches `VER 8.10` or `VER 10.x`.

## Unknown version strings: layout substitution

Decision P-02. The goal is to keep offering unit data when a new build only bumps the version string, which is common, without risking wrong numbers.

**Procedure:**
1. Inflate the file and read the 8-byte version string.
2. **Known version:** parse normally. `format_verified = true`.
3. **Unknown version:** build the list of candidate layouts from the installed `Version` enum. Keep the DE layouts the library supports (7.7 and newer), sorted **numerically, newest first**. For each candidate:
   1. Copy the buffer and overwrite its first 8 bytes with the candidate string, padded with NULs (e.g. `VER 8.9\0`).
   2. Parse the copy. On an exception, record `parse_error` and try the next candidate.
   3. Round trip: `to_bytes()` must equal the substituted buffer exactly, including length. Otherwise record `roundtrip_mismatch` with the offset and try the next.
   4. Run the sanity checks. Otherwise record `sanity_failed` and try the next.
   5. The first candidate that passes all three is accepted: `format_verified = false`, and `dat_layout_version` is set to the candidate.
4. **No candidate passes:** `stats: null`, and every attempt is listed in `flags.dat_attempts` for Diagnostics.

**Why this avoids the landmine:** the string genieutils-py sees is always an existing enum member, and the version comparisons behave exactly as for that known version.

**Why the result can be trusted:**
- **A real layout change breaks the round trip.** When fields are added, removed or resized, everything after them shifts, and counts and lengths read as garbage.
  - Parsing usually **doesn't raise**: in M0, every wrong layout parsed without an error and stopped short of the end.
  - Only comparing the whole re-encoded stream with the whole input, length included, rejected them. Never compare just the consumed part.
- **The sanity checks catch shifted-but-plausible data.** They cross-check the parsed data against the files tier, which doesn't depend on the `.dat` format:
  - the civ count and order match `civilizations.json`;
  - every tech tree node points to an existing, non-empty unit, tech or building for that civ;
  - name string IDs of reachable units and techs resolve;
  - values of reachable units lie in plausible ranges (HP, costs, speeds, ranges…);
  - effect and tech references point to existing records.
- **Residual risk:** a change that keeps every size but changes a field's *meaning*, e.g. two same-size fields swapped. That risk exists even when the version string is known. The diff's change-volume check ([diff-rules.md](../design/diff-rules.md#change-volume-check)) is the last line of defence.

**Cost:** an attempt that reads most of the file costs as much as a normal parse, about 20 s on the live build; one that goes wrong early costs about 1 s. See [Measured on the live build](#measured-on-the-live-build).

## Format history

Upstream format-support commits (author date / merge date / release):

| `.dat` version | Commit | Authored | Merged | Release |
|---|---|---|---|---|
| VER 7.8 | `8c6b3eb` | 2024-04-30 | 2024-05-05 | 0.0.4 |
| VER 8.4 | `ed41078` | 2025-04-08 | 2025-04-10 | 0.0.8 |
| VER 8.8 | `c74d984` | 2025-07-21 | 2025-07-22 | 0.0.9 |
| VER 8.9 | `e1ff9db` | 2026-04-28 | 2026-04-28 | 0.1.2 |

**Update frequency:**
- aoe2techtree shipped ~13 "Implement DE Update" commits over the same period, all parsed with existing support.
- So roughly **1 game update in 4 bumps the `.dat` version**, mostly content or expansion patches.

**Consequence for us:**
- Upstream support has landed around the retail release date, not before it.
- Our users run pre-release builds. A new version string will regularly reach them before a genieutils-py release, and before an app update.
- Layout substitution covers the "only the number changed" case. A real layout change still means "stats unavailable" until upstream support lands.

## Other known issues

- **0.1.1 fixed** "Fix length encoding bug for debug strings with non-ASCII characters". Before it, parse + save produced a `.dat` that crashed the game. Our floor is `>=0.1.2` (VER 8.9) and includes the fix.
- **No language-file support** (upstream issue #12). String parsing is ours.
- **Private test data:** the upstream round-trip test reads `.dat` files from `SiegeEngineers/dat-files`, a private repo. We don't commit `.dat` files either; parse-layer tests run locally against a real install (see [CONTRIBUTING.md](../../CONTRIBUTING.md)).
- **Memory:** upstream has already worked on it ("Use dataclass slots to decrease memory usage", "Use struct in unit and task classes"). A parsed DE file still takes about 1 GB; see [Measured on the live build](#measured-on-the-live-build).

## Round trip (our usage)

Minimal shape, to be adapted to the exact signatures of the pinned version:

```python
raw = zlib.decompress(compressed_bytes, wbits=-15)
dat = DatFile.from_bytes(BoundedByteHandler(memoryview(raw)))   # ByteHandler subclass that raises past the end
reencoded = dat.to_bytes()
if reencoded != raw:                                     # whole stream, length included
    offset = first_mismatch(raw, reencoded)              # or length mismatch
    # attempt failed: "round-trip mismatch at byte {offset}"
```

The round trip is **necessary, not sufficient**. It checks the layout, not the values, so the sanity checks must also pass before stats are marked available (measured below).

## Measured on the live build

Build 101.103.48987.0 (`VER 8.9`), genieutils-py 0.1.2, Python 3.12, Windows 10, 2026-09-15. Measured with throwaway spike code; treat the numbers as indicative.

### Parse cost
- **Decompress:** 0.12 s, from 11,076,546 to 86,745,747 bytes.
- **Parse:** about 14 s. **Re-encode:** about 4 s. The parser consumes all 86,745,747 bytes, and the round trip is byte-exact.
- **Memory:** about 960 MB after parsing, 1.1 GB at peak. With two parsed files alive at once, the peak reached 2.1 GB.
- **Consequences:**
  - release each failed attempt before trying the next layout;
  - normalize, then release the `DatFile`;
  - running the stats tier in a child process would also give the memory back to Windows.

### Layout substitution
The version bytes were set to `VER 9.0` in memory, then each candidate layout was tried:

| Layout | Parse error? | Bytes consumed | Result | Time |
|---|---|---|---|---|
| `VER 8.9` | No | All | Round trip exact: accepted | ~20 s |
| `VER 8.8` | No | All but the last 22,449 | Output shorter than the input: rejected | ~20 s |
| `VER 8.4`, `VER 7.8`, `VER 7.7` | No | 5,071,446 | First mismatch at byte 3,391,039: rejected | ~1.2 s each |

### Single-byte corruption
One byte flipped (XOR `0xFF`) at three random positions in each top-level section: 42 attempts.
- **32 re-encoded unchanged**, so the round trip passed. They include every flip in `civs` (unit stats), `techs`, `tech_tree`, `unit_headers`, `terrain_restrictions` and `player_colours`.
- **10 were caught, all as parse errors, none by the byte comparison:**
  - 4 failed the library's internal assertions, 3 of them in the header counts;
  - 4 were flips inside strings, giving invalid UTF-8;
  - 2 made reads run past the end of the buffer. The bounds-checked handler stopped them; the stock handler would have read zeros instead.
- **So:** a wrong value inside a record passes the round trip. Only the sanity checks can catch it, and only when it leaves a plausible range. The diff's change-volume check is the last line of defence.

## Upgrading the pinned version

1. Read the upstream changelog and commits since the current pin.
2. Bump the floor in `pyproject.toml` and run `uv lock`.
3. Run the game tests (`uv run pytest -m game`) on the live install. Capture every raw backup you have, and check the gate results in the Diagnostics window.
4. **Regression check:** capture the same install with the old and new library versions. Snapshots must be identical apart from tool metadata; any difference needs an explanation before merging.
5. Update this page (enum members, API changes, format history).

## Contributing format support upstream

When a new build brings an unknown `VER x.y`:

1. **If layout substitution passed:** open an upstream PR adding the enum member. Cite the passing round trip and the layout used as evidence.
2. **If no candidate passed:** the `roundtrip_mismatch` offsets or parse errors in Diagnostics show where the layout changed. Compare with the C++ repo's version branches and AGE, then open an upstream issue or PR.
3. **Never attach pre-release `.dat` files publicly.** Coordinate privately with the maintainers.
