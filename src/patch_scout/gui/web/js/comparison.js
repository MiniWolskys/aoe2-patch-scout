// SPDX-License-Identifier: GPL-3.0-or-later
/** The comparison: header, civ navigation and change rows (D-32, D-33, D-34, ui.md). */

import { byId, clear, el, formatDate, show } from "./dom.js";
import * as icons from "./icons.js";

// The order categories are shown in (diff-rules.md); the change set uses the same names.
const CATEGORIES = [
  "civilizations",
  "civ_availability",
  "bonuses",
  "unit_stats",
  "techs",
  "other_effects",
  "text",
  "icons",
];

/**
 * Draw a whole comparison.
 * @param {{
 *   t: (key: string, values?: Record<string, unknown>) => string,
 *   changeSet: Record<string, any>,
 *   civ: string | null,
 *   filters: {low: boolean, unreachable: boolean, search: string},
 *   onCiv: (internalName: string | null) => void,
 *   onPick: (side: "old" | "new") => void,
 * }} view
 */
export function render(view) {
  const { changeSet, t } = view;
  picker("old", changeSet.old, t);
  picker("new", changeSet.new, t);

  const notices = changeSet.notices ?? [];
  show(byId("comparison-notice"), notices.length > 0);
  byId("comparison-notice-text").textContent = notices
    .map((notice) => t(notice.message.key, notice.message.args))
    .join(" · ");

  const changes = (changeSet.changes ?? []).filter((change) => keeps(change, view.filters));
  renderCivList(view, changes);
  renderPage(view, changes);
}

/**
 * @param {"old" | "new"} side
 * @param {Record<string, any>} version
 * @param {(key: string, values?: Record<string, unknown>) => string} t
 */
function picker(side, version, t) {
  byId(`picker-${side}-name`).textContent = version?.label ?? "";
  const build = version?.game_build ?? t("version_list.unknown_build");
  const parts = [build, formatDate(version?.captured_at ?? "")];
  if (version?.prerelease) {
    parts.push(t("report.prerelease"));
  }
  byId(`picker-${side}-build`).textContent = parts.join(" · ");
}

/**
 * Does a change survive the filters the reader chose?
 * @param {Record<string, any>} change
 * @param {{low: boolean, search: string}} filters
 * @returns {boolean}
 */
function keeps(change, filters) {
  if (change.low_priority && !filters.low) {
    return false;
  }
  const needle = filters.search.trim().toLowerCase();
  if (needle === "") {
    return true;
  }
  const haystack = [change.entity?.name, change.entity?.where, change.old, change.new]
    .filter((part) => typeof part === "string")
    .join(" ")
    .toLowerCase();
  return haystack.includes(needle);
}

/**
 * Overall first, then every civ with changes; a new civ shows NEW (D-33).
 * @param {Parameters<typeof render>[0]} view
 * @param {Array<Record<string, any>>} changes
 */
function renderCivList(view, changes) {
  const list = byId("civ-list");
  clear(list);
  const counts = new Map();
  for (const change of changes) {
    const key = change.civ ?? null;
    counts.set(key, (counts.get(key) ?? 0) + 1);
  }
  list.append(
    civRow(view, {
      internal_name: null,
      name: view.t("comparison.overall"),
      count: counts.get(null) ?? 0,
      added: false,
      icon: null,
    }),
  );
  const civs = view.changeSet.civs ?? [];
  const base = civs.filter((civ) => civ.era !== "antiquity");
  const chronicles = civs.filter((civ) => civ.era === "antiquity");
  for (const civ of base) {
    list.append(civRow(view, { ...civ, count: counts.get(civ.internal_name) ?? 0 }));
  }
  if (chronicles.length > 0) {
    // The Chronicles civs are kept apart from the base civs (D-38).
    list.append(el("p", { class: "civ-list__group label", text: view.t("comparison.chronicles") }));
    for (const civ of chronicles) {
      list.append(civRow(view, { ...civ, count: counts.get(civ.internal_name) ?? 0 }));
    }
  }
}

/**
 * @param {Parameters<typeof render>[0]} view
 * @param {{internal_name: string | null, name: string, count: number, added: boolean,
 *   icon: Record<string, any> | null}} civ
 * @returns {HTMLElement}
 */
function civRow(view, civ) {
  const row = el("button", { class: "civ-row", attrs: { type: "button" } });
  if (view.civ === civ.internal_name) {
    row.setAttribute("aria-current", "true");
  }
  const image = icons.element(civ.icon);
  if (image !== null) {
    image.classList.add("civ-row__emblem");
    row.append(image);
  }
  row.append(el("span", { class: "civ-row__name", text: civ.name }));
  if (civ.added) {
    row.append(el("span", { class: "tag tag--new", text: view.t("comparison.new_civ") }));
  } else {
    row.append(el("span", { class: "civ-row__count num", text: String(civ.count) }));
  }
  row.addEventListener("click", () => view.onCiv(civ.internal_name));
  return row;
}

/**
 * @param {Parameters<typeof render>[0]} view
 * @param {Array<Record<string, any>>} changes
 */
function renderPage(view, changes) {
  const page = byId("comparison-changes");
  clear(page);
  const civName =
    view.civ === null
      ? view.t("comparison.overall")
      : ((view.changeSet.civs ?? []).find((civ) => civ.internal_name === view.civ)?.name ??
        view.civ);
  byId("comparison-title").textContent = civName;
  byId("comparison-subtitle").textContent =
    view.civ === null ? view.t("comparison.overall_subtitle") : "";

  const mine = changes.filter((change) => (change.civ ?? null) === view.civ);
  if (mine.length === 0) {
    page.append(el("p", { class: "help", text: view.t("comparison.no_changes") }));
    return;
  }
  for (const category of CATEGORIES) {
    const inCategory = mine.filter((change) => change.category === category);
    if (inCategory.length === 0) {
      continue;
    }
    page.append(el("h2", { class: "label page__category", text: view.t(`category.${category}`) }));
    for (const change of inCategory) {
      page.append(changeRow(view, change));
    }
  }
}

/**
 * One change row: icon, entity, field, values, and the civs it applies to (ui.md).
 * @param {Parameters<typeof render>[0]} view
 * @param {Record<string, any>} change
 * @returns {HTMLElement}
 */
function changeRow(view, change) {
  const row = el("div", { class: "change-row" });
  const image = icons.element(change.entity?.icon);
  row.append(image ?? el("span", { class: "change-row__no-icon" }));

  const entity = el("div", { class: "change-row__entity" });
  const name = el("span", { class: "change-row__name" });
  if (change.kind === "added" || change.kind === "removed") {
    name.append(el("span", { class: "change-row__kind", text: view.t(`kind.${change.kind}`) }));
  }
  name.append(document.createTextNode(change.entity?.name ?? ""));
  entity.append(name);
  const where = change.entity?.where;
  if (typeof where === "string" && where !== "") {
    entity.append(el("span", { class: "change-row__where", text: where }));
  }
  row.append(entity);

  const field = el("div", { class: "change-row__field" });
  if (change.stat_icon) {
    field.append(
      el("span", { class: "change-row__stat", attrs: { "data-stat": change.stat_icon } }),
    );
  }
  if (change.field) {
    field.append(document.createTextNode(view.t(change.field.key, change.field.args)));
  }
  row.append(field);

  row.append(values(change));

  const note = el("div", { class: "change-row__note" });
  note.textContent = scopeText(view.t, change.scope);
  if (change.detail) {
    note.append(
      el("span", {
        class: "change-row__detail",
        text: view.t(change.detail.key, change.detail.args),
      }),
    );
  }
  row.append(note);
  return row;
}

/**
 * Old value, arrow, new value; or a word diff for a text change (D-34).
 * @param {Record<string, any>} change
 * @returns {HTMLElement}
 */
function values(change) {
  const box = el("div", { class: "change-values" });
  const words = change.words ?? [];
  if (words.length > 0) {
    const diff = el("div", { class: "change-values__words" });
    for (const word of words) {
      if (word.kind === "removed") {
        diff.append(el("del", { text: word.text }));
      } else if (word.kind === "added") {
        diff.append(el("ins", { text: word.text }));
      } else {
        diff.append(document.createTextNode(word.text));
      }
    }
    box.classList.add("change-values--words");
    box.append(diff);
    return box;
  }
  box.append(el("span", { class: "value-old", text: change.old ?? "" }));
  box.append(
    el("span", { class: "change-values__arrow", text: change.old && change.new ? "→" : "" }),
  );
  box.append(el("span", { class: "value-new", text: change.new ?? "" }));
  return box;
}

/**
 * The civ-list phrase after a change (D-07).
 * @param {(key: string, values?: Record<string, unknown>) => string} t
 * @param {{kind: string, civs: string[]} | undefined} scope
 * @returns {string}
 */
export function scopeText(t, scope) {
  if (scope === undefined || scope.kind === "global") {
    return "";
  }
  if (scope.kind === "all") {
    return t("scope.all");
  }
  const civs = scope.civs ?? [];
  const named =
    civs.length <= 8
      ? civs.join(", ")
      : t("scope.and_more", {
          civs: civs.slice(0, 8).join(", "),
          count: civs.length - 8,
        });
  return scope.kind === "all_except"
    ? t("scope.all_except", { civs: named })
    : t("scope.some", { civs: named });
}

/**
 * Every icon hash a change set refers to, so they can be fetched in one batch.
 * @param {Record<string, any>} changeSet
 * @returns {string[]}
 */
export function iconHashes(changeSet) {
  const hashes = [];
  for (const civ of changeSet.civs ?? []) {
    if (civ.icon?.hash) {
      hashes.push(civ.icon.hash);
    }
  }
  for (const change of changeSet.changes ?? []) {
    if (change.entity?.icon?.hash) {
      hashes.push(change.entity.icon.hash);
    }
  }
  return hashes;
}
