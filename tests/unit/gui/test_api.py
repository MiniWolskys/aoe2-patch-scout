# SPDX-License-Identifier: GPL-3.0-or-later
import json
import logging

import pytest

from patch_scout.gui.api import Api
from patch_scout.i18n.catalog import Catalog


def make_api() -> Api:
    english = Catalog({"app.title": "Patch Scout", "app.quit": "Quit"})
    return Api(Catalog({"app.quit": "Quitter"}, fallback=english), "fr", "1.2.3")


def test_get_startup_returns_language_resolved_messages_version_and_no_versions() -> None:
    assert make_api().get_startup() == {
        "language": "fr",
        "messages": {"app.title": "Patch Scout", "app.quit": "Quitter"},
        "app_version": "1.2.3",
        "versions": [],
    }


def test_get_startup_is_plain_json() -> None:
    startup = make_api().get_startup()

    assert json.loads(json.dumps(startup)) == startup


def test_api_exposes_only_its_methods_to_the_page() -> None:
    public = [name for name in dir(make_api()) if not name.startswith("_")]

    assert public == ["get_startup"]


class BrokenCatalog(Catalog):
    def messages(self) -> dict[str, str]:
        raise RuntimeError("catalog broke")


def test_get_startup_logs_and_reraises_errors(caplog: pytest.LogCaptureFixture) -> None:
    api = Api(BrokenCatalog({}), "en", "1.2.3")

    with caplog.at_level(logging.ERROR, logger="patch_scout.gui.api"), pytest.raises(RuntimeError):
        api.get_startup()

    assert "get_startup failed" in caplog.text
