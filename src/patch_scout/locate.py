# SPDX-License-Identifier: GPL-3.0-or-later
"""Propose and validate a game folder, and read the version identifiers from it (D-19).

Nothing here assumes where the game is installed: detection only *proposes* folders, the user
confirms one, and every folder is validated before a capture reads it. The game folder is
strictly read-only (D-02).
"""

import logging
import struct
import sys
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal

from patch_scout import vdf
from patch_scout.errors import PatchScoutError

logger = logging.getLogger(__name__)

STEAM_APP_ID: Final = "813780"
# The two files a capture cannot do without; the rest is optional (game-files.md §1).
REQUIRED_FILES: Final = (
    Path("resources/_common/dat/empires2_x2_p1.dat"),
    Path("resources/_common/dat/civilizations.json"),
)
EXE_NAME: Final = "AoE2DE_s.exe"
# Folders a user may pick by mistake; the real root is then one or more levels up.
_ROOT_HINTS: Final = ("resources", "widgetui", "_common", "dat", "modes")
_MAX_ROOT_SEARCH_DEPTH: Final = 4

type Source = Literal["steam", "microsoft_store", "recent"]
type RegistryReader = Callable[[str, str, str], str | None]


class InvalidInstallError(PatchScoutError):
    """The chosen folder is not an Age of Empires II: DE install."""


@dataclass(frozen=True, slots=True)
class Candidate:
    """A folder detection proposes, with whatever the platform could tell us about it."""

    path: Path
    source: Source
    steam_build_id: str | None = None
    steam_branch: str | None = None
    game_language: str | None = None

    @property
    def prerelease_hint(self) -> bool:
        """Whether the platform says this install is on a pre-release branch (P-23)."""
        return bool(self.steam_branch)


def looks_like_install(path: Path) -> bool:
    """Whether a folder holds the files every capture needs."""
    return all((path / relative).is_file() for relative in REQUIRED_FILES)


def suggest_root(path: Path) -> Path | None:
    """Find the real install root near a folder the user picked slightly off.

    Looks at the folder itself, then upwards past the known sub-folder names, then one level
    down. Returns None when nothing nearby looks like an install.
    """
    if looks_like_install(path):
        return path
    current = path
    for _ in range(_MAX_ROOT_SEARCH_DEPTH):
        if current.name.casefold() not in _ROOT_HINTS:
            break
        current = current.parent
        if looks_like_install(current):
            return current
    try:
        children = sorted(child for child in path.iterdir() if child.is_dir())
    except OSError:
        return None
    for child in children:
        if looks_like_install(child):
            return child
    return None


def validate(path: Path) -> Path:
    """Return the install root for a chosen folder, or explain why it is not one."""
    if not path.is_dir():
        raise InvalidInstallError(f"{path} is not a folder")
    root = suggest_root(path)
    if root is None:
        missing = [str(relative) for relative in REQUIRED_FILES if not (path / relative).is_file()]
        raise InvalidInstallError(f"{path} is missing {', '.join(missing)}")
    return root


def detect(
    *,
    read_value: RegistryReader | None = None,
    recent: Sequence[Path] = (),
    drives: Sequence[Path] | None = None,
) -> list[Candidate]:
    """Propose install folders: Steam first, then Microsoft Store, then folders used before.

    Finding nothing is a normal outcome, not an error (D-19).
    """
    reader = read_value if read_value is not None else read_registry_value
    candidates: list[Candidate] = []
    seen: set[Path] = set()
    for candidate in (*steam_candidates(reader), *store_candidates(drives), *_recent(recent)):
        if not looks_like_install(candidate.path):
            continue
        resolved = candidate.path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        candidates.append(candidate)
    return candidates


def steam_candidates(read_value: RegistryReader) -> list[Candidate]:
    """Every Steam library holding app 813780, with what its manifest says."""
    candidates: list[Candidate] = []
    for library in _steam_libraries(read_value):
        manifest_path = library / "steamapps" / f"appmanifest_{STEAM_APP_ID}.acf"
        if not manifest_path.is_file():
            continue
        state = vdf.block(_read_vdf(manifest_path), "AppState")
        install_dir = vdf.string(state, "installdir") or "AoE2DE"
        candidates.append(
            Candidate(
                path=library / "steamapps" / "common" / install_dir,
                source="steam",
                steam_build_id=vdf.string(state, "buildid"),
                steam_branch=_steam_branch(state),
                game_language=_steam_language(state),
            )
        )
    if candidates:
        return candidates
    # Fallback: the uninstall entry records the install root directly (game-files.md §1).
    location = read_value(
        "HKEY_LOCAL_MACHINE",
        rf"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Steam App {STEAM_APP_ID}",
        "InstallLocation",
    )
    if location:
        candidates.append(Candidate(path=Path(location), source="steam"))
    return candidates


def store_candidates(drives: Sequence[Path] | None = None) -> list[Candidate]:
    """Microsoft Store / Xbox app libraries, read from each drive's `.GamingRoot`.

    Unverified: no test install was available (game-files.md §1). Anything unreadable is skipped,
    so a wrong guess costs nothing but a missing proposal.
    """
    candidates: list[Candidate] = []
    for drive in drives if drives is not None else _drive_roots():
        for library in _gaming_roots(drive / ".GamingRoot"):
            try:
                children = sorted(child for child in library.iterdir() if child.is_dir())
            except OSError:
                continue
            for child in children:
                content = child / "Content"
                if looks_like_install(content):
                    candidates.append(Candidate(path=content, source="microsoft_store"))
    return candidates


def game_build(root: Path) -> str | None:
    """The game build from the executable's version resource, or None when it cannot be read."""
    exe = root / EXE_NAME
    if not exe.is_file():
        logger.info("no %s in the game folder; the build stays unknown", EXE_NAME)
        return None
    return file_version(exe)


def file_version(path: Path) -> str | None:
    """Read a Windows executable's FileVersion, e.g. `101.103.48987.0`."""
    if sys.platform != "win32":
        return None
    import ctypes
    import ctypes.wintypes

    version_dll = ctypes.WinDLL("version")
    size = version_dll.GetFileVersionInfoSizeW(str(path), None)
    if not size:
        return None
    buffer = ctypes.create_string_buffer(size)
    if not version_dll.GetFileVersionInfoW(str(path), 0, size, buffer):
        return None
    pointer = ctypes.c_void_p()
    length = ctypes.wintypes.UINT()
    if not version_dll.VerQueryValueW(buffer, "\\", ctypes.byref(pointer), ctypes.byref(length)):
        return None
    if not pointer.value or length.value < 16:
        return None
    return fixed_file_info_version(ctypes.string_at(pointer.value, length.value))


def fixed_file_info_version(data: bytes) -> str | None:
    """Pull the four-part FileVersion out of a `VS_FIXEDFILEINFO` block."""
    if len(data) < 16:
        return None
    signature, _struct_version, most, least = struct.unpack_from("<IIII", data, 0)
    if signature != 0xFEEF04BD:  # VS_FFI_SIGNATURE (Microsoft Learn, verrsrc.h)
        return None
    return f"{most >> 16}.{most & 0xFFFF}.{least >> 16}.{least & 0xFFFF}"


def read_registry_value(hive: str, key_path: str, value_name: str) -> str | None:
    """Read a string value from the 64-bit registry view; None when it is not there."""
    if sys.platform != "win32":
        return None
    import winreg

    try:
        with winreg.OpenKey(
            getattr(winreg, hive), key_path, 0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY
        ) as key:
            value, _ = winreg.QueryValueEx(key, value_name)
    except OSError:
        return None
    return value if isinstance(value, str) else None


def _recent(recent: Iterable[Path]) -> list[Candidate]:
    return [Candidate(path=path, source="recent") for path in recent]


def _steam_libraries(read_value: RegistryReader) -> list[Path]:
    steam_path = read_value("HKEY_CURRENT_USER", r"Software\Valve\Steam", "SteamPath")
    if not steam_path:
        return []
    root = Path(steam_path)
    folders = _read_vdf(root / "steamapps" / "libraryfolders.vdf")
    listed = [
        Path(path)
        for entry in vdf.block(folders, "libraryfolders").values()
        if isinstance(entry, dict) and (path := vdf.string(entry, "path"))
    ]
    # Steam lists its own folder as library "0", so the same library can appear twice.
    libraries: list[Path] = []
    seen: set[str] = set()
    for library in (root, *listed):
        key = str(library).casefold().replace("/", "\\").rstrip("\\")
        if key not in seen:
            seen.add(key)
            libraries.append(library)
    return libraries


def _steam_branch(state: vdf.Block) -> str | None:
    """The selected beta branch, when the manifest records one (P-23, deferred in M0)."""
    branch = vdf.string(state, "betakey")
    if branch:
        return branch
    for section in ("UserConfig", "MountedConfig"):
        branch = vdf.string(vdf.block(state, section), "betakey")
        if branch:
            return branch
    return None


def _steam_language(state: vdf.Block) -> str | None:
    for section in ("UserConfig", "MountedConfig"):
        language = vdf.string(vdf.block(state, section), "language")
        if language:
            return language
    return None


def _read_vdf(path: Path) -> vdf.Block:
    try:
        return vdf.parse(path.read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return {}


def _gaming_roots(marker: Path) -> list[Path]:
    """Read a drive's `.GamingRoot`: a magic value, a version, then UTF-16LE library paths."""
    try:
        data = marker.read_bytes()
    except OSError:
        return []
    if len(data) < 8:
        return []
    text = data[8:].decode("utf-16-le", errors="ignore")
    drive = marker.parent
    return [drive / part for part in text.split("\x00") if part.strip()]


def _drive_roots() -> list[Path]:
    if sys.platform != "win32":
        return []
    return [
        Path(f"{letter}:/") for letter in "CDEFGHIJKLMNOPQRSTUVWXYZ" if Path(f"{letter}:/").is_dir()
    ]
