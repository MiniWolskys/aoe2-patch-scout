# SPDX-License-Identifier: GPL-3.0-or-later
# PyInstaller spec for the Windows build (D-16, docs/reference/packaging.md).
#
# Build it with:  uv run pyinstaller packaging/patch-scout.spec --clean --noconfirm
#
# One folder, windowed. genieutils-py is collected as loose `.py` files so a user can replace it
# without rebuilding, which is what LGPLv3 section 4 asks of us (docs/legal.md).

import importlib.metadata
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

PROJECT = Path(SPECPATH).parent  # noqa: F821  # SPECPATH is injected by PyInstaller
PACKAGE = PROJECT / "src" / "patch_scout"
APP_NAME = "Patch Scout"
VERSION = importlib.metadata.version("patch-scout")


def version_tuple(version: str) -> tuple[int, int, int, int]:
    """The four-part version Windows file metadata needs (docs/legal.md checklist)."""
    parts = [int(part) for part in version.split(".") if part.isdigit()]
    parts += [0] * (4 - len(parts))
    return tuple(parts[:4])  # type: ignore[return-value]


VERSION_INFO = PROJECT / "build" / "version-info.txt"
VERSION_INFO.parent.mkdir(parents=True, exist_ok=True)
VERSION_INFO.write_text(
    f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={version_tuple(VERSION)}, prodvers={version_tuple(VERSION)}),
  kids=[
    StringFileInfo([StringTable('040904B0', [
      StringStruct('CompanyName', 'the Patch Scout contributors'),
      StringStruct('FileDescription', 'Find the gameplay changes between two AoE2:DE builds'),
      StringStruct('FileVersion', '{VERSION}'),
      StringStruct('InternalName', 'patch-scout'),
      StringStruct('LegalCopyright', 'GPL-3.0-or-later'),
      StringStruct('OriginalFilename', 'Patch Scout.exe'),
      StringStruct('ProductName', '{APP_NAME}'),
      StringStruct('ProductVersion', '{VERSION}'),
    ])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])]),
  ],
)
""",
    encoding="utf-8",
)

# The frontend and the message catalog are data, not code; they keep their folder layout.
datas = [
    (str(PACKAGE / "gui" / "web"), "patch_scout/gui/web"),
    (str(PACKAGE / "i18n" / "en.json"), "patch_scout/i18n"),
]
for name in ("LICENSE", "README.md"):
    if (PROJECT / name).is_file():
        datas.append((str(PROJECT / name), "."))
for name in ("THIRD_PARTY_NOTICES", "COPYING.LESSER"):
    if (PROJECT / name).is_file():
        datas.append((str(PROJECT / name), "."))

a = Analysis(  # noqa: F821  # PyInstaller injects its own names into a spec file
    [str(PROJECT / "packaging" / "entry.py")],
    pathex=[str(PROJECT / "src")],
    datas=datas,
    # Every genieutils module, not only the ones imported directly (packaging.md).
    hiddenimports=collect_submodules("genieutils"),
    # ... and as source files outside the archive, so they stay replaceable (LGPLv3 section 4).
    module_collection_mode={"genieutils": "py"},
    excludes=["tkinter", "unittest", "pydoc_data"],
    noarchive=False,
)
pyz = PYZ(a.pure)  # noqa: F821

exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    exclude_binaries=True,
    name=APP_NAME,
    console=False,
    version=str(VERSION_INFO),
)
coll = COLLECT(  # noqa: F821
    exe,
    a.binaries,
    a.datas,
    name="PatchScout",
)
