# SPDX-License-Identifier: GPL-3.0-or-later
"""Patch notes: a comparison written the way the official notes are (D-51, diff-rules.md)."""

from patch_scout.report.notes.build import build
from patch_scout.report.notes.model import Group, Item, Notes, Section
from patch_scout.report.notes.text import render

__all__ = ["Group", "Item", "Notes", "Section", "build", "render"]
