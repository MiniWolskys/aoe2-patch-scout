# SPDX-License-Identifier: GPL-3.0-or-later
"""The Python API the page calls through pywebview (`window.pywebview.api`)."""

import logging

from patch_scout.i18n.catalog import Catalog

logger = logging.getLogger(__name__)


class Api:
    """Methods the page can call; each returns plain JSON values.

    pywebview exposes every public attribute to the page, so internal state is underscored.
    """

    def __init__(self, catalog: Catalog, language: str, app_version: str) -> None:
        self._catalog = catalog
        self._language = language
        self._app_version = app_version

    def get_startup(self) -> dict[str, object]:
        """Return what the page needs to start: language, messages, app version, versions."""
        try:
            return {
                "language": self._language,
                "messages": self._catalog.messages(),
                "app_version": self._app_version,
                "versions": [],
            }
        except Exception:
            logger.exception("get_startup failed")
            raise
