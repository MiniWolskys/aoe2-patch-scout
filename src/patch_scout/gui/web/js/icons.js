// SPDX-License-Identifier: GPL-3.0-or-later
/** Game icons: asked for in batches and cached, so a long list loads once (D-09). */

/** @type {Map<string, string>} */
const cache = new Map();

/**
 * Fetch the icons a view is about to show, keeping what was already fetched.
 * @param {import("./api.js").Api} api
 * @param {Array<string | null | undefined>} hashes
 * @returns {Promise<void>}
 */
export async function preload(api, hashes) {
  const wanted = [
    ...new Set(hashes.filter((hash) => typeof hash === "string" && !cache.has(hash))),
  ];
  if (wanted.length === 0) {
    return;
  }
  const found = await api.get_icons(/** @type {string[]} */ (wanted));
  for (const [hash, dataUri] of Object.entries(found)) {
    cache.set(hash, dataUri);
  }
}

/**
 * Build the framed image for an icon reference, or nothing when it has no icon.
 * @param {{hash?: string | null} | null | undefined} icon
 * @returns {HTMLImageElement | null}
 */
export function element(icon) {
  const hash = icon?.hash;
  if (typeof hash !== "string") {
    return null;
  }
  const source = cache.get(hash);
  if (source === undefined) {
    return null;
  }
  const image = document.createElement("img");
  image.className = "game-icon";
  image.src = source;
  image.alt = "";
  return image;
}

/** Forget every cached icon; used when the data folder changes. */
export function reset() {
  cache.clear();
}
