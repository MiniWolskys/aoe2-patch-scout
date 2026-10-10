# SPDX-License-Identifier: GPL-3.0-or-later
"""Read the game's XS script files (game-files.md, "XS scripts").

`Constants.xs` names the IDs the `.dat` uses: effect command types, unit attributes, unit classes
and armour classes. It is the only file the game ships that names them, so the comparison takes
its labels from here instead of a table written from memory (AGENTS.md rule 7). `Effects.xs`
holds the scripted logic of some techs and bonuses; it is kept as text so a change to it shows.
"""

import re
from typing import Final

from patch_scout.capture.inputs import InputReader
from patch_scout.snapshot import JsonObject, JsonValue

XS_FOLDER: Final = "resources/_common/xs"
CONSTANTS_FILE: Final = f"{XS_FOLDER}/Constants.xs"
EFFECTS_FILE: Final = f"{XS_FOLDER}/Effects.xs"

# A section title is a comment line between two rules (`//====` or `// ====`).
_RULE = re.compile(r"^//\s*=+\s*$")
_COMMENT = re.compile(r"^//\s*(.*?)\s*$")
_CONSTANT = re.compile(
    r"^extern\s+const\s+(int|float|string)\s+(\w+)\s*=\s*(-?\d+(?:\.\d+)?|\"[^\"]*\")\s*;"
)


def read(reader: InputReader) -> tuple[JsonObject, list[str]]:
    """The `scripts` section, and the parts of it that couldn't be read."""
    section: JsonObject = {}
    missing: list[str] = []
    constants = reader.read_text(CONSTANTS_FILE, required=False)
    if constants is None:
        missing.append("scripts.constants")
    else:
        section["constants"] = parse_constants(constants)
    effects = reader.read_text(EFFECTS_FILE, required=False)
    if effects is None:
        missing.append("scripts.effects")
    else:
        section["effects"] = effects
    return section, missing


def parse_constants(text: str) -> JsonObject:
    """Every `extern const` in the file, as [name, value] pairs grouped by section title.

    Sections and constants keep the file's order. Constants before the first title go under "".
    """
    sections: dict[str, list[JsonValue]] = {}
    title = ""
    lines = [line.strip() for line in text.splitlines()]
    for index, stripped in enumerate(lines):
        comment = _COMMENT.match(stripped)
        if comment is not None and not _RULE.match(stripped):
            # A title is a comment between two rules; any other comment is just a comment.
            before = lines[index - 1] if index > 0 else ""
            after = lines[index + 1] if index + 1 < len(lines) else ""
            if comment.group(1) and _RULE.match(before) and _RULE.match(after):
                title = comment.group(1)
            continue
        constant = _CONSTANT.match(stripped)
        if constant is not None:
            kind, name, raw = constant.groups()
            sections.setdefault(title, []).append([name, _value(kind, raw)])
    return dict(sections)


def _value(kind: str, raw: str) -> JsonValue:
    if kind == "string":
        return raw[1:-1]
    if kind == "float" or "." in raw:
        return float(raw)
    return int(raw)
