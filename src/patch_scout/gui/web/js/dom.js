// SPDX-License-Identifier: GPL-3.0-or-later
/** Small DOM helpers the views share. No framework, no build step (P-16). */

/**
 * Look an element up by id.
 * @param {string} id
 * @returns {HTMLElement}
 */
export function byId(id) {
  const element = document.getElementById(id);
  if (element === null) {
    throw new Error(`no element with id ${JSON.stringify(id)}`);
  }
  return element;
}

/**
 * Create an element, with classes, text and attributes.
 * @param {string} tag
 * @param {{class?: string, text?: string, attrs?: Record<string, string>}} [options]
 * @returns {HTMLElement}
 */
export function el(tag, options = {}) {
  const element = document.createElement(tag);
  if (options.class) {
    element.className = options.class;
  }
  if (options.text !== undefined) {
    element.textContent = options.text;
  }
  for (const [name, value] of Object.entries(options.attrs ?? {})) {
    element.setAttribute(name, value);
  }
  return element;
}

/**
 * Remove every child of an element.
 * @param {HTMLElement} element
 */
export function clear(element) {
  element.replaceChildren();
}

/**
 * Show or hide an element.
 * @param {HTMLElement} element
 * @param {boolean} visible
 */
export function show(element, visible) {
  element.hidden = !visible;
}

/**
 * Add a click handler.
 * @param {string} id
 * @param {(event: MouseEvent) => void} handler
 */
export function onClick(id, handler) {
  byId(id).addEventListener("click", /** @type {EventListener} */ (handler));
}

/**
 * Read a checkbox or text input.
 * @param {string} id
 * @returns {HTMLInputElement}
 */
export function input(id) {
  const element = byId(id);
  if (!(element instanceof HTMLInputElement)) {
    throw new Error(`#${id} is not an input`);
  }
  return element;
}

/**
 * Format an ISO timestamp the way the version rows show it.
 * @param {string} iso
 * @returns {string}
 */
export function formatDate(iso) {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return iso;
  }
  return date.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}
