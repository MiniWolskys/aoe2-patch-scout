// SPDX-License-Identifier: GPL-3.0-or-later
/** Game icons: asked for in batches and cached, so a long list loads once (D-09). */

/** @type {Map<string, string>} */
const cache = new Map();

// Must stay at or below `MAX_ICONS` in gui/api.py, which silently drops anything past it.
const BATCH = 200;

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
  // Python answers at most MAX_ICONS at a time, so a big comparison is asked for in batches.
  for (let start = 0; start < wanted.length; start += BATCH) {
    const found = await api.get_icons(/** @type {string[]} */ (wanted.slice(start, start + BATCH)));
    for (const [hash, dataUri] of Object.entries(found)) {
      cache.set(hash, dataUri);
    }
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
