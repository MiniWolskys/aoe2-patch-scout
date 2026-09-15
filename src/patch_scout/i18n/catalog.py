# SPDX-License-Identifier: GPL-3.0-or-later
"""Look up user-visible text by key, with named placeholders and an English fallback.

A catalog is a flat JSON object per language (`en.json`): dotted keys map to messages, and
placeholders use `str.format` syntax, e.g. `"Reading {file}"` (D-36).
"""

import json
from collections.abc import Mapping
from importlib.resources import files
from importlib.resources.abc import Traversable

from patch_scout.errors import PatchScoutError

FALLBACK_LANGUAGE = "en"


class CatalogFormatError(PatchScoutError):
    """A catalog file is not a flat JSON object of strings."""


class MissingMessageError(PatchScoutError):
    """No catalog, fallback included, has a message for the key."""


class MessageFormatError(PatchScoutError):
    """A message's placeholders don't match the values given."""


class Catalog:
    """The messages of one language, with an optional fallback catalog."""

    def __init__(self, messages: Mapping[str, str], fallback: "Catalog | None" = None) -> None:
        self._messages = dict(messages)
        self._fallback = fallback

    def text(self, key: str, **values: object) -> str:
        """Return the message for `key` with its placeholders filled in."""
        template = self._template(key)
        try:
            return template.format_map(values)
        except (KeyError, IndexError, ValueError) as exc:
            raise MessageFormatError(f"message {key!r}: {exc!r}") from exc

    def messages(self) -> dict[str, str]:
        """Return every message this catalog can resolve; its own override the fallback's."""
        inherited = self._fallback.messages() if self._fallback is not None else {}
        return inherited | self._messages

    def _template(self, key: str) -> str:
        if key in self._messages:
            return self._messages[key]
        if self._fallback is not None:
            return self._fallback._template(key)
        raise MissingMessageError(key)


def parse_messages(text: str) -> dict[str, str]:
    """Parse a catalog file, refusing anything but a flat JSON object of strings."""
    try:
        data: object = json.loads(text)
    except json.JSONDecodeError as exc:
        raise CatalogFormatError(f"not valid JSON: {exc}") from exc
    if not isinstance(data, dict) or not all(isinstance(value, str) for value in data.values()):
        raise CatalogFormatError("a catalog must be a flat JSON object of strings")
    return data


def load_catalog(language: str, directory: Traversable | None = None) -> Catalog:
    """Load the catalog for `language`; missing messages and languages fall back to English."""
    folder = directory if directory is not None else files("patch_scout.i18n")
    english = Catalog(_read(folder, FALLBACK_LANGUAGE))
    if language == FALLBACK_LANGUAGE or not folder.joinpath(f"{language}.json").is_file():
        return english
    return Catalog(_read(folder, language), fallback=english)


def _read(folder: Traversable, language: str) -> dict[str, str]:
    return parse_messages(folder.joinpath(f"{language}.json").read_text(encoding="utf-8"))
