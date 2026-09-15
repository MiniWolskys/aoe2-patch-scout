# SPDX-License-Identifier: GPL-3.0-or-later
import json
from pathlib import Path

import pytest
from playwright.sync_api import Page

FORMAT_CASES: list[dict[str, object]] = json.loads(
    (Path(__file__).parents[1] / "fixtures" / "i18n" / "format-cases.json").read_text(
        encoding="utf-8"
    )
)

TRANSLATE = """
async ([messages, key, values]) => {
  const { createTranslator } = await import("/js/i18n.js");
  try {
    return { text: createTranslator(messages)(key, values) };
  } catch (error) {
    return { error: String(error.message) };
  }
}
"""


def translate(page: Page, template: str, values: object, key: str = "case") -> dict[str, str]:
    result: dict[str, str] = page.evaluate(TRANSLATE, [{"case": template}, key, values])
    return result


@pytest.mark.parametrize("case", FORMAT_CASES, ids=[str(case["name"]) for case in FORMAT_CASES])
def test_t_follows_the_shared_format_cases(blank_page: Page, case: dict[str, object]) -> None:
    result = translate(blank_page, str(case["template"]), case["values"])

    if case.get("error"):
        assert "error" in result
    else:
        assert result == {"text": case["expected"]}


@pytest.mark.parametrize("template", ["{n:>5}", "{n!r}", "{a.b}", "{a[0]}"])
def test_t_rejects_anything_but_plain_names(blank_page: Page, template: str) -> None:
    assert "error" in translate(blank_page, template, {"n": 1, "a": 1})


def test_t_rejects_an_unknown_key(blank_page: Page) -> None:
    result = translate(blank_page, "Patch Scout", {}, key="no.such.key")

    assert "no.such.key" in result["error"]


def test_t_errors_name_the_key(blank_page: Page) -> None:
    result = translate(blank_page, "Reading {file}", {})

    assert '"case"' in result["error"]
