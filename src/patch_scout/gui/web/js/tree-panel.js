// SPDX-License-Identifier: GPL-3.0-or-later
/**
 * A tech tree node's hover panel: the game's own tooltip, then the comparison's changes (D-39).
 *
 * The lines come from the node's help string, the game's tooltip template (tree/tooltip.py):
 * styled text, the cost and the stat row. A value that changed reads old → new in the
 * comparison's colours. Values are before civ bonuses and techs, as in the game's tech tree.
 */

import { fieldCell, values } from "./comparison.js";
import { clear, el } from "./dom.js";
import * as icons from "./icons.js";

const ID = "tree-panel";
const MARGIN = 8;
// The template's stat names, and the snapshot's stat icons that show them.
const STAT_ICONS = {
  hp: "hp",
  attack: "melee_attack",
  armor: "melee_armor",
  piercearmor: "pierce_armor",
  range: "range",
  garrison: "garrison",
};
const RESOURCES = ["food", "wood", "stone", "gold"];

/** @type {HTMLElement | null} */
let panel = null;
/** @type {HTMLElement | null} */
let anchor = null;

/**
 * Show the panel for one node, next to its tile.
 * @param {{t: (key: string, values?: Record<string, unknown>) => string,
 *   changeSet: Record<string, any>}} view
 * @param {Record<string, any>} node
 * @param {HTMLElement} tile
 */
export function show(view, node, tile) {
  const box = element();
  clear(box);
  const tooltip = node.tooltip ?? {};
  const statIcons = view.changeSet.stat_icons ?? {};
  for (const line of tooltip.lines ?? []) {
    const paragraph = el("p", { class: "tree-panel__line" });
    for (const run of line) {
      paragraph.append(piece(view, node, run, statIcons));
    }
    // The stat row and the cost get their own classes, so they can be found and styled.
    if (line.some((/** @type {Record<string, any>} */ run) => run.kind === "stat")) {
      paragraph.classList.add("tree-panel__stats");
    }
    box.append(paragraph);
  }
  if (node.old_name) {
    box.append(
      el("p", {
        class: "tree-panel__renamed",
        text: view.t("tree.renamed_from", { name: node.old_name }),
      }),
    );
  }
  const changes = node.changes ?? [];
  if (changes.length > 0) {
    const list = el("div", { class: "tree-panel__changes" });
    for (const change of changes) {
      const row = el("div", { class: "tree-panel__change" });
      row.append(fieldCell(view, change), values(change));
      list.append(row);
    }
    box.append(list);
  }
  box.append(el("p", { class: "tree-panel__note", text: view.t("tree.note") }));

  anchor?.removeAttribute("aria-describedby");
  anchor = tile;
  tile.setAttribute("aria-describedby", ID);
  box.hidden = false;
  place(box, tile);
}

/** Hide the panel. */
export function hide() {
  if (panel !== null) {
    panel.hidden = true;
  }
  anchor?.removeAttribute("aria-describedby");
  anchor = null;
}

/**
 * The panel, made once and reused.
 * @returns {HTMLElement}
 */
function element() {
  if (panel === null) {
    panel = el("div", { class: "tree-panel", attrs: { id: ID, role: "tooltip" } });
    panel.hidden = true;
    document.body.append(panel);
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        hide();
      }
    });
  }
  return panel;
}

/**
 * One run of a template line.
 * @param {Parameters<typeof show>[0]} view
 * @param {Record<string, any>} node
 * @param {Record<string, any>} run
 * @param {Record<string, any>} statIcons
 * @returns {Node}
 */
function piece(view, node, run, statIcons) {
  if (run.kind === "stat") {
    const key = /** @type {keyof typeof STAT_ICONS} */ (run.stat);
    const stat = (node.tooltip?.stats ?? {})[key] ?? { old: null, new: null };
    return withIcon(statIcons[STAT_ICONS[key]], value(view, node, stat.old, stat.new), key);
  }
  if (run.kind === "cost") {
    return cost(view, node, statIcons);
  }
  if (run.kind === "static_cost") {
    return withIcon(statIcons[run.resource], document.createTextNode(String(run.amount)), null);
  }
  const text = el("span", { text: run.text });
  for (const [flag, name] of [
    ["bold", "is-bold"],
    ["italic", "is-italic"],
    ["grey", "is-grey"],
  ]) {
    if (run[flag]) {
      text.classList.add(name);
    }
  }
  return text;
}

/**
 * The cost, resource by resource, each with its icon.
 * @param {Parameters<typeof show>[0]} view
 * @param {Record<string, any>} node
 * @param {Record<string, any>} statIcons
 * @returns {HTMLElement}
 */
function cost(view, node, statIcons) {
  const amounts = (/** @type {Array<{resource: string, amount: number}> | null} */ list) =>
    new Map((list ?? []).map((item) => [item.resource, String(item.amount)]));
  const before = amounts(node.tooltip?.cost?.old);
  const after = amounts(node.tooltip?.cost?.new);
  const box = el("span", { class: "tree-panel__cost" });
  for (const resource of RESOURCES) {
    if (!before.has(resource) && !after.has(resource)) {
      continue;
    }
    const shown = value(view, node, before.get(resource) ?? null, after.get(resource) ?? null);
    box.append(withIcon(statIcons[resource], shown, null));
  }
  return box;
}

/**
 * An icon and its value.
 * @param {Record<string, any> | undefined} icon
 * @param {Node} shown
 * @param {string | null} stat
 * @returns {HTMLElement}
 */
function withIcon(icon, shown, stat) {
  const box = el("span", { class: "tree-panel__value" });
  const image = icons.element(icon);
  if (image !== null) {
    image.classList.add("tree-panel__icon");
    box.append(image);
  }
  const holder = el("span");
  if (stat !== null) {
    holder.dataset.stat = stat;
  }
  holder.append(shown);
  box.append(holder);
  return box;
}

/**
 * A value in the comparison's colours: old → new when it changed, all new for a gained node,
 * all old for a lost one, `?` when the record doesn't have it.
 * @param {Parameters<typeof show>[0]} view
 * @param {Record<string, any>} node
 * @param {string | null} before
 * @param {string | null} after
 * @returns {Node}
 */
function value(view, node, before, after) {
  const unknown = view.t("tree.unknown_value");
  if (node.mark === "lost") {
    return el("span", { class: "value-old", text: before ?? after ?? unknown });
  }
  if (node.mark === "gained") {
    return el("span", { class: "value-new", text: after ?? before ?? unknown });
  }
  if (before !== null && after !== null && before !== after) {
    const pair = document.createDocumentFragment();
    pair.append(
      el("span", { class: "value-old", text: before }),
      el("span", { class: "tree-panel__arrow", text: "→" }),
      el("span", { class: "value-new", text: after }),
    );
    return pair;
  }
  return document.createTextNode(after ?? before ?? unknown);
}

/**
 * Put the panel next to the tile, inside the window.
 * @param {HTMLElement} box
 * @param {HTMLElement} tile
 */
function place(box, tile) {
  const target = tile.getBoundingClientRect();
  const size = box.getBoundingClientRect();
  let left = target.right + MARGIN;
  if (left + size.width > window.innerWidth - MARGIN) {
    left = target.left - size.width - MARGIN;
  }
  let top = target.top;
  if (top + size.height > window.innerHeight - MARGIN) {
    top = window.innerHeight - size.height - MARGIN;
  }
  box.style.left = `${Math.max(MARGIN, left)}px`;
  box.style.top = `${Math.max(MARGIN, top)}px`;
}
