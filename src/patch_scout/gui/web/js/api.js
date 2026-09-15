// SPDX-License-Identifier: GPL-3.0-or-later
/** The page's only link to Python: pywebview's `window.pywebview.api` (architecture.md). */

/**
 * @typedef {object} Startup
 * @property {string} language
 * @property {Record<string, string>} messages
 * @property {string} app_version
 * @property {Array<object>} versions
 */

/**
 * @typedef {object} Api
 * @property {() => Promise<Startup>} get_startup
 */

/**
 * Wait until pywebview has injected the Python API.
 * @returns {Promise<Api>}
 */
export function connect() {
  if (typeof window.pywebview?.api?.get_startup === "function") {
    return Promise.resolve(window.pywebview.api);
  }
  return new Promise((resolve) => {
    window.addEventListener("pywebviewready", () => resolve(window.pywebview.api), {
      once: true,
    });
  });
}
