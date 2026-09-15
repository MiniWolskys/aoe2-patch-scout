// SPDX-License-Identifier: GPL-3.0-or-later
/** The version list: its count, empty state and collapse toggle (docs/design/ui.md). */

const ACTION_BUTTONS = ".version-list__actions .button, .version-list__bottom .button";

/**
 * Set up the version list.
 * @param {HTMLElement} element The `.version-list` aside.
 * @param {{ t: (key: string) => string, versions: Array<object> }} options
 */
export function initVersionList(element, { t, versions }) {
  element.querySelector("#versions-count").textContent = String(versions.length);
  element.querySelector("#versions-empty").hidden = versions.length > 0;

  const toggle = element.querySelector("#version-list-toggle");
  toggle.addEventListener("click", () => {
    setCollapsed(element, toggle, t, !element.hasAttribute("data-collapsed"));
  });
}

/**
 * Collapse the list to the narrow strip, or expand it again.
 * In the strip, the action buttons show only icons, so their names become tooltips.
 * @param {HTMLElement} element
 * @param {HTMLButtonElement} toggle
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
