// SPDX-License-Identifier: GPL-3.0-or-later
/** The comparison: header, civ navigation and change rows (D-32, D-33, D-34, ui.md). */

import { byId, clear, el, formatDate, show } from "./dom.js";
import { message } from "./i18n.js";
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
 *   filters: {low: boolean, unreachable: boolean, unnamed: boolean, details: boolean,
 *     technical: boolean, search: string},
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
  const noticeText = byId("comparison-notice-text");
  clear(noticeText);
  for (const notice of notices) {
    noticeText.append(el("span", { text: t(notice.message.key, notice.message.args) }));
  }

  // One entry per entity, page and scope (diff-rules.md); the civ counts count entries too.
  // An entry lists its changes by position in `changes`, so none is sent twice.
  const all = changeSet.changes ?? [];
  // A change below the levels the reader chose is left out; an entry with none left goes too.
  const entries = (changeSet.entries ?? [])
    .map((entry) => ({
      ...entry,
      changes: (entry.changes ?? [])
        .map((index) => all[index])
        .filter((change) => shows(change, view.filters)),
    }))
    .filter((entry) => entry.changes.length > 0 && keeps(entry, view.filters));
  renderCivList(view, entries);
  renderPage(view, entries);
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
 * Is a change's level shown (diff-rules.md, Levels)?
 * @param {Record<string, any>} change
 * @param {{details: boolean, technical: boolean}} filters
 * @returns {boolean}
 */
function shows(change, filters) {
  if (change.level === "detail") {
    return filters.details;
  }
  if (change.level === "technical") {
    return filters.technical;
  }
  return true;
}

/**
 * Does an entry survive the filters the reader chose?
 * @param {Record<string, any>} entry
 * @param {{low: boolean, unnamed: boolean, search: string}} filters
 * @returns {boolean}
 */
function keeps(entry, filters) {
  if (entry.low_priority && !filters.low) {
    return false;
  }
  // Objects the game gives no name are hidden unless asked for (diff-rules.md).
  if (entry.entity?.named === false && !filters.unnamed) {
    return false;
  }
  const needle = filters.search.trim().toLowerCase();
  if (needle === "") {
    return true;
  }
  const values = (entry.changes ?? []).flatMap((change) => [change.old, change.new]);
  const haystack = [entry.entity?.name, entry.entity?.where, ...values]
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
  const civs = view.changeSet.civs ?? [];
  const base = civs.filter((civ) => civ.era !== "antiquity");
  const chronicles = civs.filter((civ) => civ.era === "antiquity");
  // The Chronicles civs have their own tab (D-38): a separate mode to players, like Return of
  // Rome. The open page decides which tab is shown.
  const inChronicles = chronicles.some((civ) => civ.internal_name === view.civ);
  if (chronicles.length > 0) {
    const tabs = el("div", { class: "civ-tabs", attrs: { role: "tablist" } });
    tabs.append(
      civTab(view.t("comparison.tab_main"), !inChronicles, () => view.onCiv(null)),
      civTab(
        view.t("comparison.chronicles"),
        inChronicles,
        () => view.onCiv(chronicles[0].internal_name),
        // What waits behind the tab: NEW for a new civ, else its number of changes.
        chronicles.some((civ) => civ.added)
          ? el("span", { class: "tag tag--new", text: view.t("comparison.new_civ") })
          : el("span", {
              class: "civ-row__count num",
              text: String(
                chronicles.reduce((sum, civ) => sum + (counts.get(civ.internal_name) ?? 0), 0),
              ),
            }),
      ),
    );
    list.append(tabs);
  }
  const shown = inChronicles ? chronicles : base;
  if (!inChronicles) {
    list.append(
      civRow(view, {
        internal_name: null,
        name: view.t("comparison.overall"),
        count: counts.get(null) ?? 0,
        added: false,
        icon: null,
      }),
    );
  }
  for (const civ of shown) {
    list.append(civRow(view, { ...civ, count: counts.get(civ.internal_name) ?? 0 }));
  }
}

/**
 * One tab above the civ list.
 * @param {string} label
 * @param {boolean} selected
 * @param {() => void} onSelect
 * @param {HTMLElement} [badge]
 * @returns {HTMLElement}
 */
function civTab(label, selected, onSelect, badge) {
  const tab = el("button", {
    class: "civ-tab",
    attrs: { type: "button", role: "tab", "aria-selected": String(selected) },
  });
  tab.append(el("span", { text: label }));
  if (badge !== undefined) {
    tab.append(badge);
  }
  tab.addEventListener("click", () => {
    if (!selected) {
      onSelect();
    }
  });
  return tab;
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
 * One entry's row: icon, entity, one field-and-values line per change, and the civs it applies
 * to (ui.md, diff-rules.md "One entry per entity").
 * @param {Parameters<typeof render>[0]} view
 * @param {Record<string, any>} entry
 * @returns {HTMLElement}
 */
function changeRow(view, entry) {
  const row = el("div", { class: "change-row" });
  const image = icons.element(entry.entity?.icon);
  row.append(image ?? el("span", { class: "change-row__no-icon" }));

  const entity = el("div", { class: "change-row__entity" });
  const name = el("span", { class: "change-row__name" });
  if (entry.kind === "added" || entry.kind === "removed") {
    name.append(el("span", { class: "change-row__kind", text: view.t(`kind.${entry.kind}`) }));
  }
  name.append(document.createTextNode(entry.entity?.name ?? ""));
  entity.append(name);
  const where = entry.entity?.where;
  if (typeof where === "string" && where !== "") {
    entity.append(el("span", { class: "change-row__where", text: where }));
  }
  row.append(entity);

  // The lines share the row's field, values and note columns (a subgrid), so arrows line up and
  // each change's detail sits on its own line. The entry's civs head the first line's note.
  const lines = el("div", { class: "change-row__lines" });
  const changes = entry.changes ?? [];
  changes.forEach((change, index) => {
    const note = el("div", { class: "change-row__note" });
    if (index === 0) {
      note.textContent = scopeText(view.t, entry.scope);
    }
    if (change.detail) {
      note.append(
        el("span", {
          class: "change-row__detail",
          text: view.t(change.detail.key, change.detail.args),
        }),
      );
    }
    lines.append(fieldCell(view, change), values(change), note);
  });
  if (entry.hidden > 0) {
    lines.append(
      el("div", {
        class: "change-row__hidden",
        text: view.t("report.hidden", { count: entry.hidden }),
      }),
    );
  }
  row.append(lines);
  return row;
}

/**
 * A change's field label, with its stat icon.
 * @param {Parameters<typeof render>[0]} view
 * @param {Record<string, any>} change
 * @returns {HTMLElement}
 */
function fieldCell(view, change) {
  const field = el("div", { class: "change-row__field" });
  // When the comparison has stat icons, every label gets an icon slot, so labels line up; with
  // none (an older snapshot), no slot, so nothing shifts.
  const statIcons = view.changeSet.stat_icons ?? {};
  if (Object.keys(statIcons).length > 0) {
    const icon = change.stat_icon ? icons.element(statIcons[change.stat_icon]) : null;
    const slot = icon ?? el("span", { attrs: { "aria-hidden": "true" } });
    slot.classList.add("change-row__stat");
    if (icon !== null) {
      icon.dataset.stat = change.stat_icon;
    }
    field.append(slot);
  }
  if (change.field) {
    field.append(document.createTextNode(message(view.t, change.field.key, change.field.args)));
  }
  return field;
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
 * @param {{kind: string, civs: string[], count?: number} | undefined} scope
 * @returns {string}
 */
export function scopeText(t, scope) {
  if (scope === undefined || scope.kind === "global") {
    return "";
  }
  if (scope.kind === "all") {
    return t("scope.all");
  }
  if (scope.kind === "having") {
    return t("scope.having", { count: scope.count ?? 0 });
  }
  const civs = scope.civs ?? [];
  const named =
    civs.length <= 8
      ? civs.join(", ")
      : t("scope.and_more", {
          civs: civs.slice(0, 8).join(", "),
          count: civs.length - 8,
        });
  if (scope.kind === "all_except") {
    return t("scope.all_except", { civs: named });
  }
  if (scope.kind === "having_except") {
    return t("scope.having_except", { count: scope.count ?? 0, civs: named });
  }
  return t("scope.some", { civs: named });
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
  for (const icon of Object.values(changeSet.stat_icons ?? {})) {
    if (icon?.hash) {
      hashes.push(icon.hash);
    }
  }
  return hashes;
}
