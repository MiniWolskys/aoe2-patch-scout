// SPDX-License-Identifier: GPL-3.0-or-later
/**
 * A civ's tech tree with the comparison's changes marked on it (D-39, ui.md "Tech tree").
 *
 * Python lays the tree out (tree/layout.py): each node has a column and a row. Here a column is
 * a tile's width, groups of columns are spaced apart, and each age is two rows: its buildings,
 * then its units and techs. Lines go down from a node to the one that comes from it.
 */

import { clear, el } from "./dom.js";
import * as icons from "./icons.js";

/** A tile and the space around it. */
export const CELL = { width: 86, height: 102 };
/** The tile itself. */
export const TILE = { width: 76, height: 86 };
/** Space between two building groups. */
export const GROUP_GAP = 24;
/** The age labels on the left. */
export const LABEL_WIDTH = 120;
const PAD = 12;
const SVG = "http://www.w3.org/2000/svg";
const MARKS = ["gained", "lost", "changed", "renamed"];

/**
 * Draw one civ's tree.
 * @param {{
 *   t: (key: string, values?: Record<string, unknown>) => string,
 *   container: HTMLElement,
 *   tree: Record<string, any>,
 *   civName: string,
 *   fit: boolean,
 *   onFit: () => void,
 *   onNode?: (node: Record<string, any>, tile: HTMLElement, shown: boolean) => void,
 * }} view
 */
export function render(view) {
  const { t, container, tree } = view;
  clear(container);
  container.append(header(view));
  for (const [flag, key] of [
    ["new_civ", "tree.new_civ"],
    ["removed_civ", "tree.removed_civ"],
  ]) {
    if (tree[flag]) {
      container.append(el("p", { class: "tree__note", text: t(key) }));
    }
  }

  const width = LABEL_WIDTH + (tree.columns ?? 0) * CELL.width + (tree.groups ?? 1) * GROUP_GAP;
  const height = (tree.rows ?? 8) * CELL.height + PAD;
  const scroller = el("div", { class: "tree__scroll" });
  const sizer = el("div", { class: "tree__sizer" });
  const canvas = el("div", { class: "tree__canvas" });
  canvas.style.width = `${width}px`;
  canvas.style.height = `${height}px`;
  for (let age = 1; age <= 4; age += 1) {
    const band = el("div", { class: "tree__age" });
    band.style.top = `${(age - 1) * 2 * CELL.height}px`;
    band.style.height = `${2 * CELL.height}px`;
    band.append(el("span", { class: "tree__age-label label", text: t(`tree.age.${age}`) }));
    canvas.append(band);
  }
  /** @type {Map<string, {x: number, y: number}>} */
  const places = new Map();
  for (const node of tree.nodes ?? []) {
    places.set(node.key, position(node));
  }
  canvas.append(lines(tree.links ?? [], places, width, height));
  for (const node of tree.nodes ?? []) {
    canvas.append(tile(view, node, places.get(node.key) ?? { x: 0, y: 0 }));
  }
  sizer.append(canvas);
  scroller.append(sizer);
  container.append(scroller);
  // Fit scales the whole tree to the width, for a stream that shows it all at once. The view is
  // on screen when it is drawn, so the width can be read now.
  const scale =
    view.fit && scroller.clientWidth > 0 ? Math.min(1, scroller.clientWidth / width) : 1;
  canvas.style.transform = scale < 1 ? `scale(${scale})` : "";
  sizer.style.width = `${width * scale}px`;
  sizer.style.height = `${height * scale}px`;
}

/**
 * The title, the legend and the Fit toggle.
 * @param {Parameters<typeof render>[0]} view
 * @returns {HTMLElement}
 */
function header(view) {
  const { t } = view;
  const bar = el("div", { class: "tree__header" });
  bar.append(el("h1", { class: "page__title", text: t("tree.title", { civ: view.civName }) }));
  const legend = el("ul", { class: "tree__legend" });
  for (const mark of ["gained", "lost", "changed"]) {
    const item = el("li", { class: `tree__legend-item mark-${mark}` });
    item.append(el("span", { class: "tree__swatch", attrs: { "aria-hidden": "true" } }));
    item.append(el("span", { text: t(`tree.legend.${mark}`) }));
    legend.append(item);
  }
  bar.append(legend);
  const fit = el("button", {
    class: "button button--ghost",
    text: t("tree.fit"),
    attrs: { type: "button", id: "tree-fit", "aria-pressed": String(view.fit) },
  });
  fit.addEventListener("click", () => view.onFit());
  bar.append(fit);
  return bar;
}

/**
 * Where a node's tile goes, from its column, group and row.
 * @param {Record<string, any>} node
 * @returns {{x: number, y: number}}
 */
function position(node) {
  return {
    x:
      LABEL_WIDTH +
      node.column * CELL.width +
      node.group * GROUP_GAP +
      (CELL.width - TILE.width) / 2,
    y: PAD + node.row * CELL.height,
  };
}

/**
 * One node: a focusable tile with its icon, its name and its mark.
 * @param {Parameters<typeof render>[0]} view
 * @param {Record<string, any>} node
 * @param {{x: number, y: number}} at
 * @returns {HTMLElement}
 */
function tile(view, node, at) {
  const unique = String(node.node_type ?? "").startsWith("Unique");
  const button = el("button", {
    class: `tree-node tree-node--${unique ? "unique" : node.kind}`,
    attrs: { type: "button" },
  });
  if (!node.available) {
    button.classList.add("is-unavailable");
  }
  if (MARKS.includes(node.mark)) {
    button.classList.add(`mark-${node.mark}`);
    button.setAttribute("aria-label", `${node.name}, ${view.t(`tree.legend.${node.mark}`)}`);
  }
  button.style.left = `${at.x}px`;
  button.style.top = `${at.y}px`;
  const image = icons.element(node.icon);
  button.append(image ?? el("span", { class: "tree-node__no-icon" }));
  button.append(el("span", { class: "tree-node__name", text: node.name }));
  const onNode = view.onNode;
  if (onNode !== undefined) {
    button.addEventListener("mouseenter", () => onNode(node, button, true));
    button.addEventListener("focus", () => onNode(node, button, true));
    button.addEventListener("mouseleave", () => onNode(node, button, false));
    button.addEventListener("blur", () => onNode(node, button, false));
  }
  return button;
}

/**
 * The lines from each node to the one it comes from: down, across, down, like the game.
 * @param {Array<[string, string]>} links
 * @param {Map<string, {x: number, y: number}>} places
 * @param {number} width
 * @param {number} height
 * @returns {SVGSVGElement}
 */
function lines(links, places, width, height) {
  const svg = document.createElementNS(SVG, "svg");
  svg.setAttribute("class", "tree__lines");
  svg.setAttribute("width", String(width));
  svg.setAttribute("height", String(height));
  svg.setAttribute("aria-hidden", "true");
  for (const [childKey, parentKey] of links) {
    const child = places.get(childKey);
    const parent = places.get(parentKey);
    if (child === undefined || parent === undefined) {
      continue;
    }
    const path = document.createElementNS(SVG, "path");
    path.setAttribute("d", route(parent, child));
    svg.append(path);
  }
  return svg;
}

/**
 * The path of one line. Below its parent: down, across, down. In the same row (an upgrade the
 * civ gets in the same age, such as the Armenians' Long Swordsman): side to side.
 * @param {{x: number, y: number}} parent
 * @param {{x: number, y: number}} child
 * @returns {string}
 */
function route(parent, child) {
  if (child.y <= parent.y) {
    const y = Math.min(parent.y, child.y) + TILE.height / 2;
    const leftToRight = child.x > parent.x;
    const fromX = leftToRight ? parent.x + TILE.width : parent.x;
    const toX = leftToRight ? child.x : child.x + TILE.width;
    return `M${fromX} ${parent.y + TILE.height / 2} H${(fromX + toX) / 2} V${y} H${toX}`;
  }
  const fromX = parent.x + TILE.width / 2;
  const fromY = parent.y + TILE.height;
  const toX = child.x + TILE.width / 2;
  const middle = child.y - (CELL.height - TILE.height) / 2;
  return `M${fromX} ${fromY} V${middle} H${toX} V${child.y}`;
}

/**
 * Every icon a tree shows, to fetch before drawing it.
 * @param {Record<string, any>} tree
 * @returns {string[]}
 */
export function iconHashes(tree) {
  return (tree.nodes ?? []).map((/** @type {Record<string, any>} */ node) => node.icon?.hash);
}
