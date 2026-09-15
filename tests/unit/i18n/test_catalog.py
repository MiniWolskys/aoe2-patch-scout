# SPDX-License-Identifier: GPL-3.0-or-later
import json
from pathlib import Path
from typing import NotRequired, TypedDict

import pytest

from patch_scout.errors import PatchScoutError
from patch_scout.i18n.catalog import (
    Catalog,
    CatalogFormatError,
    MessageFormatError,
    MissingMessageError,
    load_catalog,
    parse_messages,
)


def test_text_returns_the_message_for_a_key() -> None:
    catalog = Catalog({"app.title": "Patch Scout"})

    assert catalog.text("app.title") == "Patch Scout"


def test_text_fills_named_placeholders() -> None:
    catalog = Catalog({"capture.reading": "Reading {file}"})

    assert catalog.text("capture.reading", file="civilizations.json") == (
        "Reading civilizations.json"
    )


def test_text_raises_when_a_placeholder_value_is_missing() -> None:
    catalog = Catalog({"capture.reading": "Reading {file}"})

    with pytest.raises(MessageFormatError):
        catalog.text("capture.reading")


def test_text_uses_the_fallback_catalog_for_a_missing_key() -> None:
    english = Catalog({"app.title": "Patch Scout"})
    other = Catalog({}, fallback=english)

    assert other.text("app.title") == "Patch Scout"


def test_text_raises_for_a_key_missing_from_every_catalog() -> None:
    catalog = Catalog({}, fallback=Catalog({}))

    with pytest.raises(MissingMessageError):
        catalog.text("no.such.key")


@pytest.mark.parametrize("error", [CatalogFormatError, MessageFormatError, MissingMessageError])
def test_catalog_errors_are_patch_scout_errors(error: type[Exception]) -> None:
    assert issubclass(error, PatchScoutError)


def test_parse_messages_reads_a_flat_object_of_strings() -> None:
    assert parse_messages('{"app.title": "Patch Scout"}') == {"app.title": "Patch Scout"}


@pytest.mark.parametrize(
    "text",
    ['["app.title"]', '{"app": {"title": "Patch Scout"}}', '{"count": 3}', "not json"],
)
def test_parse_messages_rejects_anything_but_a_flat_object_of_strings(text: str) -> None:
    with pytest.raises(CatalogFormatError):
        parse_messages(text)


def test_load_catalog_reads_the_bundled_english_catalog() -> None:
    assert load_catalog("en").text("app.title") == "Patch Scout"


def test_load_catalog_falls_back_to_english_for_a_language_without_a_catalog() -> None:
    assert load_catalog("xx").text("app.title") == "Patch Scout"


def test_load_catalog_uses_the_language_file_with_english_as_fallback(tmp_path: Path) -> None:
    (tmp_path / "en.json").write_text(
        '{"app.title": "Patch Scout", "app.quit": "Quit"}', encoding="utf-8"
    )
    (tmp_path / "fr.json").write_text('{"app.quit": "Quitter"}', encoding="utf-8")

    catalog = load_catalog("fr", directory=tmp_path)

    assert (catalog.text("app.quit"), catalog.text("app.title")) == ("Quitter", "Patch Scout")


def test_messages_lists_every_message_with_own_messages_overriding_the_fallback() -> None:
    english = Catalog({"app.title": "Patch Scout", "app.quit": "Quit"})
    french = Catalog({"app.quit": "Quitter"}, fallback=english)

    assert french.messages() == {"app.title": "Patch Scout", "app.quit": "Quitter"}


def test_messages_returns_a_copy_that_leaves_the_catalog_unchanged() -> None:
    catalog = Catalog({"app.title": "Patch Scout"})

    catalog.messages()["app.title"] = "Changed"

    assert catalog.text("app.title") == "Patch Scout"


class FormatCase(TypedDict):
    name: str
    template: str
    values: dict[str, object]
    expected: NotRequired[str]
    error: NotRequired[bool]


FORMAT_CASES: list[FormatCase] = json.loads(
    (Path(__file__).parents[2] / "fixtures" / "i18n" / "format-cases.json").read_text(
        encoding="utf-8"
    )
)


@pytest.mark.parametrize("case", FORMAT_CASES, ids=[case["name"] for case in FORMAT_CASES])
def test_text_follows_the_shared_format_cases(case: FormatCase) -> None:
    catalog = Catalog({"case": case["template"]})

    if case.get("error"):
        with pytest.raises(MessageFormatError):
            catalog.text("case", **case["values"])
    else:
        assert catalog.text("case", **case["values"]) == case["expected"]
