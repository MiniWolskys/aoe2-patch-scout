# SPDX-License-Identifier: GPL-3.0-or-later
"""One copy of the app per data folder: a second one would overwrite the first one's changes.

Each copy keeps the library and the settings in memory and rewrites the whole file on a change,
so two copies would silently undo each other's labels and notes. A Windows named mutex marks
the running copy; it disappears with the process, even after a crash.
"""

import hashlib
import sys
from pathlib import Path
from typing import Final

# winerror.h, winuser.h
_ERROR_ALREADY_EXISTS: Final = 183
_MB_ICONINFORMATION: Final = 0x40
_MB_SETFOREGROUND: Final = 0x10000


class SingleInstance:
    """The running-copy marker for one name; `acquire` is False when another copy holds it."""

    def __init__(self, name: str) -> None:
        self._name = name
        self._handle: int | None = None

    @classmethod
    def for_folder(cls, root: Path) -> "SingleInstance":
        """The marker for one data folder: two copies on two data folders don't conflict."""
        digest = hashlib.sha256(str(root).casefold().encode("utf-8")).hexdigest()[:16]
        return cls(f"PatchScout-{digest}")

    def acquire(self) -> bool:
        """Mark this copy as the running one; False when another copy already is."""
        if sys.platform != "win32":
            return True  # the build is Windows-only; elsewhere (CI, development) don't block
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateMutexW.restype = wintypes.HANDLE
        kernel32.CreateMutexW.argtypes = (wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR)
        handle = kernel32.CreateMutexW(None, False, f"Local\\{self._name}")
        error = ctypes.get_last_error()
        if not handle:
            return True  # can't tell: better a second copy than no app at all
        if error == _ERROR_ALREADY_EXISTS:
            kernel32.CloseHandle(handle)
            return False
        self._handle = handle
        return True

    def release(self) -> None:
        """Let another copy start; called when the window closes."""
        if self._handle is None or sys.platform != "win32":
            return
        import ctypes

        ctypes.WinDLL("kernel32").CloseHandle(self._handle)
        self._handle = None


def tell_already_running(title: str, text: str) -> None:
    """A native message box saying another copy is running; nothing on other systems."""
    if sys.platform != "win32":
        return
    import ctypes

    ctypes.windll.user32.MessageBoxW(None, text, title, _MB_ICONINFORMATION | _MB_SETFOREGROUND)
