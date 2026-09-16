# SPDX-License-Identifier: GPL-3.0-or-later
"""Render a change set: plain text and self-contained HTML (P-13)."""

from patch_scout.report.html import render as render_html
from patch_scout.report.text import Filters
from patch_scout.report.text import render as render_text

__all__ = ["Filters", "render_html", "render_text"]
