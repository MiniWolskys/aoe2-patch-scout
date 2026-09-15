# SPDX-License-Identifier: GPL-3.0-or-later
"""Check that the Microsoft Edge WebView2 Runtime is installed, and offer its download page.

pywebview silently falls back to the deprecated MSHTML engine without the runtime, so the app
checks for itself (D-40, docs/reference/packaging.md).
"""

import sys
from collections.abc import Callable
from typing import Final

DOWNLOAD_URL: Final = "https://developer.microsoft.com/microsoft-edge/webview2/consumer/"

# Microsoft's documented check: the runtime's `pv` value, per machine or per user.
_CLIENT_KEY: Final = r"Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"
RUNTIME_KEYS: Final = (
    ("HKEY_LOCAL_MACHINE", "SOFTWARE\\WOW6432Node\\" + _CLIENT_KEY),
    ("HKEY_CURRENT_USER", "Software\\" + _CLIENT_KEY),
)
_NOT_INSTALLED: Final = frozenset({"", "0.0.0.0"})

# MessageBoxW flags and return value (Microsoft Learn, winuser.h).
_MB_YESNO: Final = 0x4
_MB_ICONWARNING: Final = 0x30
_MB_SETFOREGROUND: Final = 0x10000
_MB_TOPMOST: Final = 0x40000
_IDYES: Final = 6

type RegistryReader = Callable[[str, str, str], str | None]


def installed_runtime_version(read_value: RegistryReader) -> str | None:
    """Return the installed WebView2 Runtime version, or None when it isn't installed."""
    for hive, key_path in RUNTIME_KEYS:
        version = read_value(hive, key_path, "pv")
        if version is not None and version not in _NOT_INSTALLED:
            return version
    return None


def read_registry_value(hive: str, key_path: str, value_name: str) -> str | None:
    """Read a string value from the Windows registry; None if the key or value is missing."""
    if sys.platform != "win32":
        return None
    import winreg

    try:
        with winreg.OpenKey(getattr(winreg, hive), key_path) as key:
            value, _ = winreg.QueryValueEx(key, value_name)
    except OSError:
        return None
    return value if isinstance(value, str) else None


def ask_to_open_download_page(title: str, text: str) -> bool:
    """Show a native Yes/No warning box and return True if the user chose Yes."""
    if sys.platform != "win32":
        raise OSError("the WebView2 message box needs Windows")
    import ctypes

    flags = _MB_YESNO | _MB_ICONWARNING | _MB_SETFOREGROUND | _MB_TOPMOST
    answer: int = ctypes.windll.user32.MessageBoxW(None, text, title, flags)
    return answer == _IDYES
