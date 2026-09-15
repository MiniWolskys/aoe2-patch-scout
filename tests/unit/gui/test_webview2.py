# SPDX-License-Identifier: GPL-3.0-or-later
import sys

import pytest

from patch_scout.gui.webview2 import (
    DOWNLOAD_URL,
    RUNTIME_KEYS,
    RegistryReader,
    installed_runtime_version,
    read_registry_value,
)

PER_MACHINE, PER_USER = RUNTIME_KEYS


def registry(values: dict[tuple[str, str], str]) -> RegistryReader:
    """A fake registry holding `pv` values by (hive, key path)."""

    def read(hive: str, key_path: str, value_name: str) -> str | None:
        assert value_name == "pv"
        return values.get((hive, key_path))

    return read


def test_runtime_keys_are_microsofts_documented_locations() -> None:
    assert RUNTIME_KEYS == (
        (
            "HKEY_LOCAL_MACHINE",
            r"SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients"
            r"\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}",
        ),
        (
            "HKEY_CURRENT_USER",
            r"Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}",
        ),
    )


def test_version_comes_from_the_per_machine_install() -> None:
    assert installed_runtime_version(registry({PER_MACHINE: "153.0.4234.32"})) == "153.0.4234.32"


def test_version_comes_from_the_per_user_install_when_there_is_no_per_machine_one() -> None:
    assert installed_runtime_version(registry({PER_USER: "152.0.1.2"})) == "152.0.1.2"


def test_per_machine_version_wins_when_both_are_installed() -> None:
    reader = registry({PER_MACHINE: "153.0.4234.32", PER_USER: "152.0.1.2"})

    assert installed_runtime_version(reader) == "153.0.4234.32"


def test_a_zero_per_machine_version_falls_through_to_the_per_user_install() -> None:
    reader = registry({PER_MACHINE: "0.0.0.0", PER_USER: "152.0.1.2"})

    assert installed_runtime_version(reader) == "152.0.1.2"


@pytest.mark.parametrize("value", ["", "0.0.0.0"])
def test_empty_or_zero_versions_mean_not_installed(value: str) -> None:
    assert installed_runtime_version(registry({PER_MACHINE: value, PER_USER: value})) is None


def test_missing_keys_mean_not_installed() -> None:
    assert installed_runtime_version(registry({})) is None


def test_read_registry_value_returns_none_for_a_missing_key() -> None:
    missing_key = r"Software\PatchScoutTests\NoSuchKey"

    assert read_registry_value("HKEY_CURRENT_USER", missing_key, "pv") is None


@pytest.mark.skipif(sys.platform != "win32", reason="reads the Windows registry")
def test_read_registry_value_reads_a_real_key() -> None:
    # The skipif above already keeps this from running elsewhere; this guard additionally
    # lets mypy prune the win32-only `winreg` calls below under `--platform linux`, the way
    # `read_registry_value` itself does.
    if sys.platform != "win32":
        return
    import winreg

    key_path = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion"

    product_name = read_registry_value("HKEY_LOCAL_MACHINE", key_path, "ProductName")
    assert isinstance(product_name, str)
    assert product_name != ""

    # Confirm CurrentMajorVersionNumber really is a REG_DWORD, so the assertion below tests
    # that read_registry_value (which only returns strings) reports it as absent, not that
    # the value happens to be missing.
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as key:
        _, value_type = winreg.QueryValueEx(key, "CurrentMajorVersionNumber")
    assert value_type == winreg.REG_DWORD

    major_version = read_registry_value("HKEY_LOCAL_MACHINE", key_path, "CurrentMajorVersionNumber")
    assert major_version is None


def test_download_url_is_microsofts_consumer_page() -> None:
    assert DOWNLOAD_URL == "https://developer.microsoft.com/microsoft-edge/webview2/consumer/"
