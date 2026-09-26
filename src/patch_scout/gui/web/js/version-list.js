// SPDX-License-Identifier: GPL-3.0-or-later
/** The version list: rows, the collapse toggle, and the ways to start a comparison (D-32). */

import { byId, clear, el, formatDate, show } from "./dom.js";

const ACTION_BUTTONS = ".version-list__actions .button, .version-list__bottom .button";

/**
 * Set up the collapse toggle. The rows themselves are filled in by `render`.
 * @param {HTMLElement} element The `.version-list` aside.
 * @param {{t: (key: string, values?: Record<string, unknown>) => string}} options
 */
export function initVersionList(element, { t }) {
  const toggle = byId("version-list-toggle");
  toggle.addEventListener("click", () => {
    setCollapsed(element, toggle, t, !element.hasAttribute("data-collapsed"));
  });
}

/**
 * Draw the rows, newest game build first.
 * @param {{
 *   t: (key: string, values?: Record<string, unknown>) => string,
 *   versions: import("./api.js").Version[],
 *   capture: import("./api.js").CaptureStatus | null,
 *   openId: string | null,
 *   comparison: {oldId: string, newId: string} | null,
 *   onOpen: (captureId: string) => void,
 *   onCompare: (captureId: string) => void,
 *   onOpenCapture: () => void,
 * }} view
 */
export function render(view) {
  const rows = byId("version-rows");
  clear(rows);
  byId("versions-count").textContent = String(view.versions.length);
  show(byId("versions-empty"), view.versions.length === 0 && view.capture === null);

  // A finished capture keeps its row only while it has something to say: an error, a
  // cancellation, or "identical to a version you already have". Once it produced a version,
  // that version's own row replaces it.
  if (view.capture !== null && (view.capture.running || !view.capture.result?.capture_id)) {
    rows.append(captureRow(view));
  }
  for (const version of view.versions) {
    rows.append(versionRow(version, view));
  }
}

/**
 * The row a running capture shows at the top of the list (ui.md).
 * @param {{t: (key: string, values?: Record<string, unknown>) => string,
 *   capture: import("./api.js").CaptureStatus | null,
 *   onOpenCapture: () => void}} view
 * @returns {HTMLElement}
 */
function captureRow(view) {
  const capture = view.capture;
  const item = el("li");
  const row = el("button", {
    class: "version-row version-row--capture",
    attrs: { type: "button" },
  });
  const main = el("span", { class: "version-row__main" });
  main.append(el("span", { class: "version-row__name", text: capture?.label ?? "" }));
  const percent = Math.round((capture?.fraction ?? 0) * 100);
  const state = capture?.running
    ? view.t("version_list.capturing", { percent })
    : view.t("version_list.capture_done");
  main.append(el("span", { class: "version-row__meta", text: state }));
  row.append(main);
  const bar = el("span", { class: "version-row__progress" });
  const fill = el("span", { class: "version-row__progress-bar" });
  fill.style.width = `${percent}%`;
  bar.append(fill);
  row.append(bar);
  row.addEventListener("click", view.onOpenCapture);
  item.append(row);
  return item;
}

/**
 * One version row: label, build and date, flags, and a Compare button on hover.
 * @param {import("./api.js").Version} version
 * @param {Parameters<typeof render>[0]} view
 * @returns {HTMLElement}
 */
function versionRow(version, view) {
  const item = el("li");
  const row = el("button", { class: "version-row", attrs: { type: "button" } });
  const side = sideOf(version.capture_id, view.comparison);
  if (side !== null) {
    row.setAttribute("data-side", side);
  }
  if (view.openId === version.capture_id) {
    row.setAttribute("aria-current", "true");
  }

  const main = el("span", { class: "version-row__main" });
  main.append(el("span", { class: "version-row__name", text: version.label }));
  const meta = [
    version.game_build ?? view.t("version_list.unknown_build"),
    formatDate(version.captured_at),
  ];
  main.append(el("span", { class: "version-row__meta", text: meta.join(" · ") }));
  row.append(main);

  const marks = el("span", { class: "version-row__marks" });
  if (version.prerelease) {
    marks.append(
      el("span", {
        class: "icon icon--warning",
        attrs: {
          title: view.t("version_list.prerelease_flag"),
          "aria-label": view.t("version_list.prerelease_flag"),
        },
      }),
    );
  }
  if (!version.stats_available) {
    // A text tag, not a second warning triangle: only one warning glyph is vendored (D-43).
    marks.append(
      el("span", {
        class: "tag tag--muted",
        text: view.t("version_list.no_stats_short"),
        attrs: { title: view.t("version_list.no_stats_flag") },
      }),
    );
  }
  if (side !== null) {
    marks.append(el("span", { class: `tag tag--${side}`, text: view.t(`comparison.${side}`) }));
  }
  row.append(marks);

  const compare = el("span", {
    class: "version-row__compare button button--ghost button--small",
    text: view.t("version_list.compare"),
    attrs: { role: "button", tabindex: "0" },
  });
  compare.addEventListener("click", (event) => {
    event.stopPropagation();
    view.onCompare(version.capture_id);
  });
  compare.addEventListener("keydown", (event) => {
    if (event instanceof KeyboardEvent && (event.key === "Enter" || event.key === " ")) {
      event.preventDefault();
      event.stopPropagation();
      view.onCompare(version.capture_id);
    }
  });
  row.append(compare);

  row.addEventListener("click", (event) => {
    if (event instanceof MouseEvent && event.ctrlKey) {
      view.onCompare(version.capture_id);
      return;
    }
    view.onOpen(version.capture_id);
  });
  item.append(row);
  return item;
}

/**
 * Which side of the open comparison a version is on, if any.
 * @param {string} captureId
 * @param {{oldId: string, newId: string} | null} comparison
 * @returns {"old" | "new" | null}
 */
function sideOf(captureId, comparison) {
  if (comparison === null) {
    return null;
  }
  if (comparison.oldId === captureId) {
    return "old";
  }
  return comparison.newId === captureId ? "new" : null;
}

/**
 * Collapse the list to the narrow strip, or expand it again.
 * In the strip, the action buttons show only icons, so their names become tooltips.
 * @param {HTMLElement} element
 * @param {HTMLElement} toggle
 * @param {(key: string) => string} t
 * @param {boolean} collapsed
 */
function setCollapsed(element, toggle, t, collapsed) {
  element.toggleAttribute("data-collapsed", collapsed);
  const label = collapsed ? t("version_list.expand") : t("version_list.collapse");
  toggle.setAttribute("aria-expanded", String(!collapsed));
  toggle.setAttribute("aria-label", label);
  toggle.title = label;
  for (const button of element.querySelectorAll(ACTION_BUTTONS)) {
    if (collapsed) {
      button.title = button.getAttribute("aria-label") ?? "";
    } else {
      button.removeAttribute("title");
    }
  }
}
