# SPDX-License-Identifier: GPL-3.0-or-later
"""Render a change set as one self-contained HTML file (P-13).

Everything is inline: the stylesheet, and the icons as data URIs. The file opens from anywhere,
makes no network request (D-02), and carries the Microsoft notice in its footer (legal.md).
"""

import base64
import html
from collections.abc import Callable, Sequence
from typing import Final

from patch_scout.diff.model import CATEGORIES, Change, ChangeSet, Side
from patch_scout.i18n.catalog import Catalog
from patch_scout.report.text import Filters, scope_text
from patch_scout.snapshot import JsonObject

type IconReader = Callable[[str], bytes | None]

ARROW: Final = "→"

# Forge tokens (docs/design/ui.md); inline, because the file must stand on its own.
STYLESHEET: Final = """
:root { color-scheme: dark; }
body { margin: 0; padding: 32px; background: #15120f; color: #ece3d3;
  font-family: "Barlow Semi Condensed", "Segoe UI", system-ui, sans-serif; font-size: 16px; }
main { max-width: 1040px; margin: 0 auto; }
h1 { font-size: 34px; margin: 0 0 4px; font-weight: 600; }
h2 { font-size: 28px; margin: 32px 0 8px; font-weight: 600; border-bottom: 1px solid #241f19;
  padding-bottom: 6px; }
h3 { font-size: 12px; letter-spacing: 0.07em; text-transform: uppercase; color: #aa9e8a;
  margin: 20px 0 6px; font-weight: 600; }
.sides { color: #aa9e8a; font-size: 15px; margin-bottom: 16px; }
.sides b { color: #ece3d3; font-weight: 600; }
.notice { background: #1a1612; border-left: 3px solid #8fb0c9; padding: 8px 12px;
  margin: 8px 0; color: #8fb0c9; font-size: 15px; }
.notice.warn { border-color: #f0a03e; color: #f0a03e; }
table { width: 100%; border-collapse: collapse; }
td { padding: 6px 8px; border-bottom: 1px solid #241f19; vertical-align: top; }
td.icon { width: 40px; }
td.entity { font-weight: 500; }
td.field { color: #aa9e8a; width: 30%; }
td.values { width: 24%; white-space: nowrap; }
td.scope { color: #aa9e8a; font-size: 13.5px; }
img { width: 40px; height: 40px; border-radius: 2px; outline: 1px solid #51432f;
  outline-offset: 1px; background: #0e0c0a; }
.old { color: #e35b50; }
.new { color: #92dcaa; }
del { color: #e35b50; background: #2c1a16; text-decoration: line-through; }
ins { color: #92dcaa; background: #1b2a20; text-decoration: none; }
.where { color: #8a7f6d; font-weight: 400; }
.tag { font-size: 11.5px; border-radius: 3px; padding: 1px 5px; background: #35291a;
  color: #f0a03e; }
footer { margin-top: 40px; padding-top: 12px; border-top: 1px solid #241f19; color: #8a7f6d;
  font-size: 13.5px; }
footer a { color: #d8b36b; }
"""
# The notice Microsoft's Game Content Usage Rules require (docs/legal.md).
MICROSOFT_NOTICE: Final = (
    "Age of Empires II © Microsoft Corporation. Patch Scout was created under Microsoft's "
    '"<a href="https://www.xbox.com/en-US/developers/rules">Game Content Usage Rules</a>" using '
    "assets from Age of Empires II, and it is not endorsed by or affiliated with Microsoft."
)


def render(
    change_set: ChangeSet,
    catalog: Catalog,
    *,
    icons: IconReader | None = None,
    filters: Filters | None = None,
    tool_version: str = "",
) -> str:
    """Return the whole comparison as one self-contained HTML document."""
    chosen = filters or Filters()
    title = catalog.text("report.title")
    parts = [
        "<!doctype html>",
        '<html lang="en"><head><meta charset="utf-8">',
        f"<title>{html.escape(title)}</title>",
        f"<style>{STYLESHEET}</style>",
        "</head><body><main>",
        f"<h1>{html.escape(title)}</h1>",
        _sides(change_set, catalog),
        _notices(change_set, catalog),
    ]
    if change_set.identical:
        parts.append(f"<p>{html.escape(catalog.text('report.identical'))}</p>")
    else:
        parts.append(_body(change_set, catalog, chosen, icons))
    parts.append(_footer(tool_version))
    parts.append("</main></body></html>")
    return "\n".join(part for part in parts if part) + "\n"


def _sides(change_set: ChangeSet, catalog: Catalog) -> str:
    return (
        '<p class="sides">'
        + _labelled(catalog, "report.side_old", _side(change_set.old, catalog))
        + "<br>"
        + _labelled(catalog, "report.side_new", _side(change_set.new, catalog))
        + "</p>"
    )


def _labelled(catalog: Catalog, key: str, value: str) -> str:
    return f"{html.escape(catalog.text(key, side=''))} <b>{value}</b>"


def _side(side: Side, catalog: Catalog) -> str:
    parts = [html.escape(side.label)]
    if side.game_build:
        parts.append(html.escape(side.game_build))
    parts.append(html.escape(side.captured_at))
    if side.prerelease:
        parts.append(f'<span class="tag">{html.escape(catalog.text("report.prerelease"))}</span>')
    if not side.stats_available:
        parts.append(f'<span class="tag">{html.escape(catalog.text("report.no_stats"))}</span>')
    return " · ".join(parts)


def _notices(change_set: ChangeSet, catalog: Catalog) -> str:
    return "".join(
        f'<p class="notice{" warn" if notice.kind == "unusually_many_changes" else ""}">'
        f"{html.escape(catalog.text(notice.message.key, **notice.message.args))}</p>"
        for notice in change_set.notices
    )


def _body(
    change_set: ChangeSet, catalog: Catalog, filters: Filters, icons: IconReader | None
) -> str:
    pages: list[tuple[str, str | None]] = [(catalog.text("report.overall"), None)]
    pages += [(civ.name, civ.internal_name) for civ in change_set.civs]
    sections: list[str] = []
    for title, internal_name in pages:
        changes = [change for change in change_set.for_civ(internal_name) if filters.keeps(change)]
        if not changes:
            continue
        sections.append(f"<h2>{html.escape(title)}</h2>")
        for category in CATEGORIES:
            in_category = [change for change in changes if change.category == category]
            if not in_category:
                continue
            sections.append(f"<h3>{html.escape(catalog.text(f'category.{category}'))}</h3>")
            sections.append(_table(in_category, catalog, icons))
    if not sections:
        return f"<p>{html.escape(catalog.text('report.no_changes'))}</p>"
    return "".join(sections)


def _table(changes: Sequence[Change], catalog: Catalog, icons: IconReader | None) -> str:
    rows = [_row(change, catalog, icons) for change in changes]
    return "<table>" + "".join(rows) + "</table>"


def _row(change: Change, catalog: Catalog, icons: IconReader | None) -> str:
    entity = change.entity
    name = html.escape(entity.name)
    if change.kind in ("added", "removed"):
        name = f"{html.escape(catalog.text(f'kind.{change.kind}'))} {name}"
    if entity.where:
        name += f' <span class="where">{html.escape(entity.where)}</span>'
    field = html.escape(catalog.text(change.field.key, **change.field.args)) if change.field else ""
    return (
        "<tr>"
        f'<td class="icon">{_icon(entity.icon, icons)}</td>'
        f'<td class="entity">{name}</td>'
        f'<td class="field">{field}</td>'
        f'<td class="values">{_values(change)}</td>'
        f'<td class="scope">{html.escape(scope_text(change.scope, catalog))}</td>'
        "</tr>"
    )


def _values(change: Change) -> str:
    if change.words:
        return "".join(_word(word.kind, word.text) for word in change.words)
    if change.old and change.new:
        return (
            f'<span class="old">{html.escape(change.old)}</span> {ARROW} '
            f'<span class="new">{html.escape(change.new)}</span>'
        )
    if change.new:
        return f'<span class="new">{html.escape(change.new)}</span>'
    if change.old:
        return f'<span class="old">{html.escape(change.old)}</span>'
    return ""


def _word(kind: str, text: str) -> str:
    escaped = html.escape(text)
    if kind == "removed":
        return f"<del>{escaped}</del>"
    if kind == "added":
        return f"<ins>{escaped}</ins>"
    return escaped


def _icon(icon: JsonObject | None, icons: IconReader | None) -> str:
    if icon is None or icons is None:
        return ""
    digest = icon.get("hash")
    if not isinstance(digest, str):
        return ""
    data = icons(digest)
    if data is None:
        return ""
    encoded = base64.b64encode(data).decode("ascii")
    return f'<img alt="" src="data:image/png;base64,{encoded}">'


def _footer(tool_version: str) -> str:
    version = f"Patch Scout {html.escape(tool_version)}" if tool_version else "Patch Scout"
    return f"<footer><p>{version}</p><p>{MICROSOFT_NOTICE}</p></footer>"
