# SPDX-License-Identifier: GPL-3.0-or-later
"""The patch notes as a document: every string already in the reader's language (D-51).

The page draws it and `notes.text` writes it out, so both show exactly the same words.
"""

from dataclasses import dataclass
from typing import Literal

from patch_scout.snapshot import JsonObject

type SectionKind = Literal["general", "civs", "chronicles"]


@dataclass(frozen=True, slots=True)
class Item:
    """One bullet, with its own bullets under it, e.g. a new tech's cost and effect."""

    text: str
    children: tuple["Item", ...] = ()

    def to_json(self) -> JsonObject:
        """The form the page reads."""
        return {"text": self.text, "children": [child.to_json() for child in self.children]}


@dataclass(frozen=True, slots=True)
class Group:
    """A heading and its bullets: a category in General, or one civ."""

    title: str
    items: tuple[Item, ...]
    # The civ a civ group is about (internal name), and its crest; None in General.
    civ: str | None = None
    icon: JsonObject | None = None

    def to_json(self) -> JsonObject:
        """The form the page reads."""
        return {
            "title": self.title,
            "civ": self.civ,
            "icon": self.icon,
            "items": [item.to_json() for item in self.items],
        }


@dataclass(frozen=True, slots=True)
class Section:
    """General, Civilizations or Chronicles."""

    kind: SectionKind
    title: str
    groups: tuple[Group, ...]

    def to_json(self) -> JsonObject:
        """The form the page reads."""
        return {
            "kind": self.kind,
            "title": self.title,
            "groups": [group.to_json() for group in self.groups],
        }


@dataclass(frozen=True, slots=True)
class Notes:
    """The whole patch notes of one comparison."""

    title: str
    disclaimer: str
    notices: tuple[str, ...]
    sections: tuple[Section, ...]
    # What the notes leave out, as a sentence; None when they leave nothing out.
    closing: str | None
    # Said instead of the sections when there is nothing to say.
    empty: str | None = None

    def to_json(self) -> JsonObject:
        """The form the page reads."""
        return {
            "title": self.title,
            "disclaimer": self.disclaimer,
            "notices": list(self.notices),
            "sections": [section.to_json() for section in self.sections],
            "closing": self.closing,
            "empty": self.empty,
        }
