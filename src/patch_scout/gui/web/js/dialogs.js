// SPDX-License-Identifier: GPL-3.0-or-later
/** Modal dialogs and the toast, built on the theme's `.scrim` and `.dialog` (ui.md). */

import { byId, show } from "./dom.js";

/** @type {string[]} */
const openStack = [];
/** @type {HTMLElement | null} */
let lastFocused = null;

/**
 * Open a dialog, remember what had focus, and move focus inside it.
 * @param {string} scrimId
 */
export function open(scrimId) {
  const scrim = byId(scrimId);
  if (!openStack.includes(scrimId)) {
    openStack.push(scrimId);
  }
  if (document.activeElement instanceof HTMLElement) {
    lastFocused = document.activeElement;
  }
  show(scrim, true);
  const first = scrim.querySelector("input, textarea, select, button");
  if (first instanceof HTMLElement) {
    first.focus();
  }
}

/**
 * Close a dialog and give focus back.
 * @param {string} scrimId
 */
export function close(scrimId) {
  show(byId(scrimId), false);
  const index = openStack.indexOf(scrimId);
  if (index !== -1) {
    openStack.splice(index, 1);
  }
  if (openStack.length === 0 && lastFocused !== null) {
    lastFocused.focus();
    lastFocused = null;
  }
}

/** Close whichever dialog is on top. Bound to Escape by `listen`. */
export function closeTop() {
  const top = openStack[openStack.length - 1];
  if (top !== undefined) {
    close(top);
  }
}

/**
 * Whether a dialog is open.
 * @returns {boolean}
 */
export function anyOpen() {
  return openStack.length > 0;
}

/** Wire Escape to close the top dialog, and keep focus inside it. */
export function listen() {
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && anyOpen()) {
      event.preventDefault();
      closeTop();
    }
    if (event.key === "Tab" && anyOpen()) {
      trapFocus(event);
    }
  });
}

/**
 * Keep Tab inside the open dialog.
 * @param {KeyboardEvent} event
 */
function trapFocus(event) {
  const top = openStack[openStack.length - 1];
  if (top === undefined) {
    return;
  }
  const focusable = [
    ...byId(top).querySelectorAll("a[href], button, input, textarea, select, [tabindex]"),
  ].filter((node) => node instanceof HTMLElement && !node.hasAttribute("disabled") && !node.hidden);
  if (focusable.length === 0) {
    return;
  }
  const first = /** @type {HTMLElement} */ (focusable[0]);
  const last = /** @type {HTMLElement} */ (focusable[focusable.length - 1]);
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first.focus();
  }
}

/**
 * Ask the user to confirm something, e.g. deleting a version.
 * @param {{title: string, text: string, confirm?: string}} options
 * @returns {Promise<boolean>}
 */
export function confirm(options) {
  byId("confirm-title").textContent = options.title;
  byId("confirm-text").textContent = options.text;
  const yes = byId("confirm-yes");
  if (options.confirm) {
    yes.textContent = options.confirm;
  }
  open("confirm-scrim");
  return new Promise((resolve) => {
    const finish = (answer) => {
      close("confirm-scrim");
      yes.removeEventListener("click", onYes);
      byId("confirm-no").removeEventListener("click", onNo);
      resolve(answer);
    };
    const onYes = () => finish(true);
    const onNo = () => finish(false);
    yes.addEventListener("click", onYes);
    byId("confirm-no").addEventListener("click", onNo);
  });
}

let toastTimer = 0;

/**
 * Show a short message at the bottom of the window.
 * @param {string} text
 */
export function toast(text) {
  const element = byId("toast");
  element.textContent = text;
  show(element, true);
  window.clearTimeout(toastTimer);
  toastTimer = window.setTimeout(() => show(element, false), 3200);
}
