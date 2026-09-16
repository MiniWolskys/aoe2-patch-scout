# SPDX-License-Identifier: GPL-3.0-or-later
"""Build a small synthetic game folder for the reader tests.

Everything here is made up: no game file, no game art and no text from the real game (P-09).
The tree is written under `tmp_path`, so nothing is committed and no real install is touched.
"""

import json
import struct
import zlib
from pathlib import Path
from typing import Any

CIVILIZATIONS: list[dict[str, Any]] = [
    {
        "internal_name": "Gaia",
        "tech_tree_name": "",
        "data_name": "GAIA-CIV",
        "era": "base",
        "name_string_id": 10102,
        "unique_tech_id_1": -1,
        "unique_tech_id_2": -1,
        "unique_unit_id": -1,
        "elite_unique_unit_id": -1,
        "unique_unit_line": 0,
        "unique_unit_upgrade_id": -1,
        "unique_unit_string_ids": [],
        "emblem_image_path": "",
        "unique_unit_image_paths": [],
    },
    {
        "internal_name": "Redlanders",
        "tech_tree_name": "REDLANDERS",
        "data_name": "RED-CIV",
        "era": "base",
        "name_string_id": 10103,
        "unique_tech_id_1": 3,
        "unique_tech_id_2": 461,
        "unique_unit_id": 8,
        "elite_unique_unit_id": 530,
        "unique_unit_line": -276,
        "unique_unit_upgrade_id": 360,
        "unique_unit_string_ids": [{"name": 5107, "description": 26107}],
        "emblem_image_path": "emblems/red",
        "unique_unit_image_paths": ["uniticons/017_50730"],
        "hud_style": "CivWest",
        "mystery_key": 7,
    },
    {
        "internal_name": "Bluelanders",
        "tech_tree_name": "BLUELANDERS",
        "data_name": "BLUE-CIV",
        "era": "base",
        "name_string_id": 10104,
        "unique_tech_id_1": 4,
        "unique_tech_id_2": 462,
        "unique_unit_id": 9,
        "elite_unique_unit_id": 531,
        "unique_unit_line": -277,
        "unique_unit_upgrade_id": 361,
        "unique_unit_string_ids": [{"name": 5108, "description": 26108}],
        "emblem_image_path": "emblems/blue",
        "unique_unit_image_paths": [],
    },
    {
        "internal_name": "Ancients",
        "tech_tree_name": "ANCIENTS",
        "data_name": "ANCIENT-CIV",
        "era": "antiquity",
        "name_string_id": 10105,
        "unique_tech_id_1": 5,
        "unique_tech_id_2": -1,
        "unique_unit_id": 10,
        "elite_unique_unit_id": -1,
        "unique_unit_line": -278,
        "unique_unit_upgrade_id": -1,
        "unique_unit_string_ids": [],
        "emblem_image_path": "",
        "unique_unit_image_paths": [],
    },
]


def tech_tree_nodes(available: bool = True) -> dict[str, Any]:
    """One civ tech tree file, with a unit node, a tech node and a building node."""
    status = "ResearchedCompleted" if available else "NotAvailable"
    return {
        "civ_id": "REDLANDERS",
        "civ_techs_units": [
            {
                "Name": "Archer",
                "Use Type": "Unit",
                "Node Status": status,
                "Node Type": "Unit",
                "Name String ID": 14083,
                "Age ID": 2,
                "Building ID": 87,
                "Help String ID": 105083,
                "Node ID": 4,
                "Picture Index": 17,
                "Link ID": 87,
                "Link Node Type": "BuildingTech",
                "Draw Node Type": "UnitTech",
                "Prerequisite IDs": [101, -1, -1, -1, -1],
                "Prerequisite Types": ["Tech", "None", "None", "None", "None"],
            }
        ],
        "civ_techs_buildings": [
            {
                "Name": "Archery Range",
                "Use Type": "Building",
                "Node Status": "ResearchedCompleted",
                "Name String ID": 14128,
                "Age ID": 2,
                "Building ID": 87,
                "Help String ID": 105128,
                "Node ID": 87,
                "Picture Index": 23,
            },
            {
                "Name": "Fletching",
                "Use Type": "Tech",
                "Node Status": status,
                "Node Type": "Research",
                "Name String ID": 14199,
                "Age ID": 2,
                "Building ID": 12,
                "Help String ID": 105199,
                "Node ID": 199,
                "Picture Index": 0,
                "Surprise Key": "kept in extra",
            },
        ],
    }


STRINGS = """\
// A synthetic string file, nothing from the real game.
5083 "Archer"
5004 "Archer"        // the name ID the synthetic .dat unit 4 carries
5087 "Archery Range" // the name ID the synthetic .dat unit 87 carries
14083 "Archer"
26083 "A ranged unit." //trailing comment
105083 "unused direct hit"
14128 "Archery\\nRange"
26128 "Build an Archery Range."
14199 "Fletching"
26199 "Adds range."
5107 "Red Champion"
26107 "A unique unit."
10103 "Redlanders"
10104 "Bluelanders"
10105 "Ancients"
120150 "Archer civilization\\n\\n• Villagers work faster\\n\\n<b>Unique Unit:<b> Red Champion"
120151 "Cavalry civilization\\n\\n• Knights cost less"
120152 "Ancient civilization\\n\\n• Nothing yet"
IDS_OPT_ESC_MENU "ESC Menu"
13170 "first text"
13170 "second text wins"
"""

PAPHOS_STRINGS = '407088 "Post-Imperial Age"\n'
NON_LOCALIZED = 'IDS_TOOL "Tool"\n'


def write(
    root: Path,
    *,
    dat_bytes: bytes | None = None,
    unavailable_civs: tuple[str, ...] = ("Bluelanders",),
    strings: str | None = None,
    icon_colour: tuple[int, int, int, int] = (0, 40, 80, 255),
) -> Path:
    """Write the synthetic install under `root` and return it.

    The keyword arguments let a test write a second, slightly different build.
    """
    dat = root / "resources" / "_common" / "dat"
    dat.mkdir(parents=True, exist_ok=True)
    (dat / "empires2_x2_p1.dat").write_bytes(
        dat_bytes if dat_bytes is not None else minimal_dat_bytes()
    )
    _json(dat / "civilizations.json", {"civilization_list": CIVILIZATIONS})

    trees = dat / "CivTechTrees"
    trees.mkdir(exist_ok=True)
    for civ in CIVILIZATIONS:
        name = civ["tech_tree_name"]
        if not name:
            continue
        nodes = tech_tree_nodes(available=civ["internal_name"] not in unavailable_civs)
        nodes["civ_id"] = name
        _json(trees / f"{name}.json", nodes)

    _json(
        dat / "futuravailableunits.json",
        {
            "Redlanders": {"Buildings": [_building_offer()]},
            "Bluelanders": {"Buildings": [_building_offer()]},
            "FullTechCiv": {"Buildings": []},
        },
    )
    _json(
        dat / "paphosfutureavailableunits.json",
        {"Ancients": {"Buildings": [_building_offer()]}, "Paphos6": {"Buildings": []}},
    )
    _json(
        dat / "unitlines.json",
        {
            "Hint": "synthetic",
            "UnitLines": [{"Name": "Archer", "LineID": -299, "IDChain": [4, 24]}],
        },
    )
    _json(
        dat / "linkedTechs.json",
        {
            "LinkedTechs": [
                {"NameId": 1, "Comment": "c", "Type": "MutuallyExclusive", "Techs": [3, 4]}
            ]
        },
    )
    _json(dat / "linkedUnits.json", {"Data": [{"Name": "Villagers", "Units": [83, 293]}]})
    _json(dat / "unitcategories.json", {"SiegeWeapons": [{"Name": "Ram", "ID": 35}]})
    _json(
        dat / "eras.json",
        [
            {"Name": "base", "Ages": [{"NameId": 4201}, {"NameId": 4205}]},
            {"Name": "antiquity", "Ages": [{"NameId": 407001}, {"NameId": 407088}]},
        ],
    )

    english = root / "resources" / "en" / "strings" / "key-value"
    english.mkdir(parents=True, exist_ok=True)
    (english / "key-value-strings-utf8.txt").write_text(
        strings if strings is not None else STRINGS, encoding="utf-8"
    )
    (english / "key-value-paphos-strings-utf8.txt").write_text(PAPHOS_STRINGS, encoding="utf-8")
    shared = root / "resources" / "_common" / "strings" / "key-value"
    shared.mkdir(parents=True, exist_ok=True)
    (shared / "non-localized-key-value-strings-utf8.txt").write_text(
        NON_LOCALIZED, encoding="utf-8"
    )

    icons = root / "widgetui" / "textures" / "ingame"
    for folder, names in (
        ("units", ["017_50730.DDS"]),
        ("tech", ["000_fletching.dds"]),
        ("buildings", ["023_range_1.DDS"]),
        ("emblems", ["red.DDS", "blue.DDS"]),
        ("staticons", ["hp.png", "damage.png"]),
    ):
        path = icons / folder
        path.mkdir(parents=True, exist_ok=True)
        for index, name in enumerate(names):
            red, green, blue, alpha = icon_colour
            colour = (min(255, red + 9 * index), green, blue, alpha)
            if name.endswith(".png"):
                (path / name).write_bytes(png_bytes(4, 4, colour))
            else:
                (path / name).write_bytes(dds_bytes(4, 4, colour))

    unit_icons = root / "resources" / "_common" / "wpfg" / "resources" / "uniticons"
    unit_icons.mkdir(parents=True, exist_ok=True)
    (unit_icons / "017_50730.png").write_bytes(png_bytes(4, 4, (200, 30, 30, 255)))
    return root


def _building_offer() -> dict[str, Any]:
    return {
        "ID": 87,
        "Name": "Archery Range",
        "RequiredAge": 2,
        "Techs": [199],
        "Units": [4],
        "PrereqTech": -1,
        "Mystery Key": 1,
    }


def _json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, indent=1), encoding="utf-8")


def dds_bytes(width: int, height: int, colour: tuple[int, int, int, int]) -> bytes:
    """An uncompressed 32-bit DDS with an explicit R,G,B,A channel order."""
    header = bytearray(124)
    struct.pack_into("<I", header, 0, 124)  # dwSize
    struct.pack_into("<I", header, 4, 0x1 | 0x2 | 0x4 | 0x1000 | 0x8)  # flags incl. pitch
    struct.pack_into("<I", header, 8, height)
    struct.pack_into("<I", header, 12, width)
    struct.pack_into("<I", header, 16, width * 4)  # pitch
    struct.pack_into("<I", header, 72, 32)  # pixel format size
    struct.pack_into("<I", header, 76, 0x41)  # DDPF_RGB | DDPF_ALPHAPIXELS
    struct.pack_into("<I", header, 84, 32)  # bit count
    struct.pack_into("<I", header, 88, 0x000000FF)  # red mask
    struct.pack_into("<I", header, 92, 0x0000FF00)  # green mask
    struct.pack_into("<I", header, 96, 0x00FF0000)  # blue mask
    struct.pack_into("<I", header, 100, 0xFF000000)  # alpha mask
    struct.pack_into("<I", header, 108, 0x1000)  # caps: texture
    pixels = bytes(colour) * (width * height)
    return b"DDS " + bytes(header) + pixels


def png_bytes(width: int, height: int, colour: tuple[int, int, int, int]) -> bytes:
    """A tiny RGBA PNG, written by hand so the fixtures need no image library."""
    raw = b"".join(b"\x00" + bytes(colour) * width for _ in range(height))
    return b"".join(
        [
            b"\x89PNG\r\n\x1a\n",
            _chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)),
            _chunk(b"IDAT", zlib.compress(raw)),
            _chunk(b"IEND", b""),
        ]
    )


def _chunk(kind: bytes, payload: bytes) -> bytes:
    body = kind + payload
    return struct.pack(">I", len(payload)) + body + struct.pack(">I", zlib.crc32(body))


def minimal_dat_bytes() -> bytes:
    """A placeholder `.dat`: valid DEFLATE, a version string, and nothing a parser can use."""
    return zlib.compress(b"VER 8.9\x00" + b"\x00" * 64, level=-1, wbits=-15)
