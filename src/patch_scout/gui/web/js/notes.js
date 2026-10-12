// SPDX-License-Identifier: GPL-3.0-or-later
/**
 * The patch notes mode of the comparison (D-51, ui.md "Patch notes"). Python writes every
 * sentence; the page only lays the document out, so it reads exactly like the exported text.
 */

import { clear, el } from "./dom.js";
import * as icons from "./icons.js";

/**
 * @typedef {{text: string, children: NotesItem[]}} NotesItem
 * @typedef {{title: string, civ: string | null, icon: Record<string, any> | null,
 *   items: NotesItem[]}} NotesGroup
 * @typedef {{kind: string, title: string, groups: NotesGroup[]}} NotesSection
 * @typedef {{title: string, disclaimer: string, notices: string[], sections: NotesSection[],
 *   closing: string | null, empty: string | null, text: string}} Notes
 */

/**
 * Draw the patch notes into their container.
 * @param {HTMLElement} container
 * @param {Notes} notes
 */
export function render(container, notes) {
  clear(container);
  const page = el("article", { class: "notes__page" });
  page.append(el("h1", { class: "page__title notes__title", text: notes.title }));
  page.append(el("p", { class: "page__subtitle", text: notes.disclaimer }));
  for (const notice of notes.notices ?? []) {
    const line = el("p", { class: "notes__notice" });
    line.append(el("span", { class: "icon icon--warning", attrs: { "aria-hidden": "true" } }));
    line.append(el("span", { text: notice }));
    page.append(line);
  }
  for (const section of notes.sections ?? []) {
    const block = el("section", { class: "notes__section" });
    block.append(el("h2", { class: "label notes__section-title", text: section.title }));
    for (const group of section.groups ?? []) {
      block.append(groupBlock(group));
    }
    page.append(block);
  }
  if (notes.empty) {
    page.append(el("p", { class: "help", text: notes.empty }));
  }
  if (notes.closing) {
    page.append(el("p", { class: "notes__closing", text: notes.closing }));
  }
  container.append(page);
}

/**
 * One group: a category of General, or a civ with its crest, as in the official notes.
 * @param {NotesGroup} group
 * @returns {HTMLElement}
 */
function groupBlock(group) {
  const block = el("div", { class: "notes__group" });
  if (group.civ) {
    block.id = groupId(group.civ);
    block.classList.add("notes__group--civ");
  }
  const heading = el("h3", { class: "notes__group-title" });
  const crest = group.civ ? icons.element(group.icon) : null;
  if (crest !== null) {
    crest.classList.add("notes__crest");
    heading.append(crest);
  }
  heading.append(el("span", { text: group.title }));
  block.append(heading, list(group.items ?? []));
  return block;
}

/**
 * Bullets, with their own bullets under them.
 * @param {NotesItem[]} items
 * @returns {HTMLElement}
 */
function list(items) {
  const bullets = el("ul", { class: "notes__list" });
  for (const item of items) {
    const bullet = el("li", { text: item.text });
    if ((item.children ?? []).length > 0) {
      bullet.append(list(item.children));
    }
    bullets.append(bullet);
  }
  return bullets;
}

/**
 * Bring a civ's block into view; Overall (null) goes back to the top.
 * @param {HTMLElement} container
 * @param {string | null} civ
 */
export function scrollTo(container, civ) {
  const target = civ === null ? null : container.querySelector(`#${CSS.escape(groupId(civ))}`);
  if (target instanceof HTMLElement) {
    target.scrollIntoView({ block: "start" });
  } else {
    container.scrollTop = 0;
  }
}

/**
 * @param {string} civ
 * @returns {string}
 */
function groupId(civ) {
  return `notes-civ-${civ}`;
}
