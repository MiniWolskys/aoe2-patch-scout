// SPDX-License-Identifier: GPL-3.0-or-later
/**
 * The details of a unit, building or tech, in a drawer on the right (D-49, ui.md "Details
 * panel").
 *
 * Python reads both versions (entity/details.py); this draws what it sends. Every value reads
 * as the comparison reads it: one value when both versions agree, old → new in red and green
 * when they differ, new in green or old struck in red when a line is in one version only. The
 * bonuses and techs are listed, never applied to the values (D-20).
 */

import { fieldCell } from "./comparison.js";
import * as dialogs from "./dialogs.js";
import { byId, clear, el } from "./dom.js";
import { message } from "./i18n.js";
import * as icons from "./icons.js";

const SCRIM = "entity-scrim";

/**
 * @typedef {{oldId: string, newId: string, kind: string, id: number, civ: string | null,
 *   name?: string}} Request
 * @typedef {{internal_name: string, name: string, era?: string}} Civ
 */

/**
 * Wire the drawer once; `open` then shows one entity.
 * @param {{
 *   api: import("./api.js").Api,
 *   t: (key: string, values?: Record<string, unknown>) => string,
 *   civs: () => Civ[],
 *   statIcons: () => Record<string, any>,
 * }} options
 * @returns {{open: (request: Request) => void}}
 */
export function initEntityPanel(options) {
  const { api, t } = options;
  const civSelect = /** @type {HTMLSelectElement} */ (byId("entity-civ"));
  /** @type {Request | null} */
  let current = null;
  // Each fetch gets a number; a slower, older answer never overwrites a newer one.
  let requestNumber = 0;

  byId("entity-close").addEventListener("click", () => dialogs.close(SCRIM));
  // A click on the dimmed page beside the drawer closes it.
  byId(SCRIM).addEventListener("click", (event) => {
    if (event.target === event.currentTarget) {
      dialogs.close(SCRIM);
    }
  });
  civSelect.addEventListener("change", () => {
    if (current !== null) {
      current = { ...current, civ: civSelect.value || null };
      drawLoading(current);
      void load(current);
    }
  });

  /** @returns {boolean} */
  function isOpen() {
    return !byId(SCRIM).hidden;
  }

  /** @param {Request} request */
  function open(request) {
    current = request;
    fillCivs(request.civ);
    drawLoading(request);
    dialogs.open(SCRIM);
    void load(request);
  }

  /** @param {string | null} chosen */
  function fillCivs(chosen) {
    clear(civSelect);
    civSelect.append(el("option", { text: t("entity.no_civ"), attrs: { value: "" } }));
    for (const civ of options.civs()) {
      civSelect.append(el("option", { text: civ.name, attrs: { value: civ.internal_name } }));
    }
    civSelect.value = chosen ?? "";
  }

  /** @param {Request} request */
  function drawLoading(request) {
    const identity = byId("entity-identity");
    clear(identity);
    identity.append(
      el("h2", {
        class: "drawer__title",
        text: request.name ?? t("entity.title"),
        attrs: { id: "entity-title" },
      }),
    );
    const body = byId("entity-body");
    clear(body);
    body.append(el("p", { class: "help", text: t("entity.loading") }));
  }

  /** @param {Request} request */
  async function load(request) {
    const number = ++requestNumber;
    /** @type {Record<string, any> | null} */
    let details = null;
    try {
      details = await api.get_entity_details(
        request.oldId,
        request.newId,
        request.kind,
        request.id,
        request.civ,
      );
    } catch (error) {
      console.error("the details failed", error);
      if (number === requestNumber && isOpen()) {
        dialogs.close(SCRIM);
        dialogs.toast(t("entity.failed"));
      }
      return;
    }
    if (details !== null) {
      // A missing icon only leaves the header without its picture.
      await icons.preload(api, [details.icon?.hash]).catch((error) => {
        console.error("the details icon failed", error);
      });
    }
    if (number !== requestNumber || current !== request || !isOpen()) {
      return; // another entity or civ was asked for meanwhile, or the drawer was closed
    }
    if (details === null) {
      dialogs.close(SCRIM);
      dialogs.toast(t("entity.not_found"));
      return;
    }
    draw(details);
  }

  /** @param {Record<string, any>} details */
  function draw(details) {
    const view = { t, changeSet: { stat_icons: options.statIcons() } };
    drawIdentity(details);
    const body = byId("entity-body");
    clear(body);
    const tags = tagsFor(details);
    if (tags.childElementCount > 0) {
      body.append(tags);
    }
    const missing = missingStats(details);
    if (missing !== null) {
      body.append(el("p", { class: "drawer__notice", text: missing }));
    }
    if ((details.description ?? []).length > 0) {
      body.append(description(details.description, view.changeSet.stat_icons));
    }
    for (const section of details.sections ?? []) {
      body.append(heading("h3", message(t, section.title.key, section.title.args)));
      body.append(rows(view, section.rows));
    }
    for (const group of details.groups ?? []) {
      body.append(heading("h3", message(t, group.title.key, group.title.args)));
      for (const source of group.sources) {
        const block = el("div", { class: "drawer__source" });
        block.append(
          el("h4", {
            class: "drawer__source-name",
            text: message(t, source.name.key, source.name.args),
          }),
        );
        if (source.requires) {
          block.append(
            el("p", {
              class: "drawer__requires",
              text: t("entity.requires", { techs: source.requires }),
            }),
          );
        }
        block.append(rows(view, source.rows));
        body.append(block);
      }
    }
    if (details.civ !== null && (details.groups ?? []).length === 0 && !allMissing(details)) {
      body.append(el("p", { class: "help", text: t("entity.no_effects") }));
    }
    if ((details.scripts ?? []).length > 0) {
      body.append(
        el("p", {
          class: "drawer__notice",
          text: t("entity.scripts", { titles: details.scripts.join("; ") }),
        }),
      );
    }
    body.append(
      el("p", { class: "drawer__note", text: t(details.note.key, details.note.args ?? {}) }),
    );
  }

  /** @param {Record<string, any>} details */
  function drawIdentity(details) {
    const identity = byId("entity-identity");
    clear(identity);
    const image = icons.element(details.icon);
    if (image !== null) {
      image.classList.add("drawer__icon");
      identity.append(image);
    }
    const text = el("div", { class: "drawer__heading" });
    text.append(
      el("h2", { class: "drawer__title", text: details.name, attrs: { id: "entity-title" } }),
    );
    const meta = [t(`entity.kind.${details.kind}`)];
    if (typeof details.age === "number" && details.age >= 1 && details.age <= 4) {
      meta.push(t(`tree.age.${details.age}`));
    }
    text.append(el("p", { class: "drawer__meta", text: meta.join(" · ") }));
    if (details.old_name) {
      text.append(
        el("p", {
          class: "drawer__meta",
          text: t("tree.renamed_from", { name: details.old_name }),
        }),
      );
    }
    identity.append(text);
  }

  /**
   * @param {Record<string, any>} details
   * @returns {HTMLElement}
   */
  function tagsFor(details) {
    const tags = el("div", { class: "drawer__tags" });
    const civName =
      options.civs().find((civ) => civ.internal_name === details.civ)?.name ?? details.civ;
    const was = details.available?.old ?? null;
    const now = details.available?.new ?? null;
    if (details.civ !== null) {
      // Availability in the comparison's colours when it changed, else muted.
      if (was === true && now === false) {
        tags.append(tag("tag--old", t("entity.no_longer_available", { civ: civName })));
      } else if (was === false && now === true) {
        tags.append(tag("tag--new", t("entity.newly_available", { civ: civName })));
      } else if (now === false || (now === null && was === false)) {
        tags.append(tag("tag--muted", t("entity.unavailable", { civ: civName })));
      }
    }
    if (details.presence === "new") {
      tags.append(tag("tag--new", t("entity.only_new")));
    } else if (details.presence === "old") {
      tags.append(tag("tag--old", t("entity.only_old")));
    }
    return tags;
  }

  /**
   * @param {Record<string, any>} details
   * @returns {string | null}
   */
  function missingStats(details) {
    if (allMissing(details)) {
      return t("entity.no_stats_both");
    }
    for (const side of ["old", "new"]) {
      if (details.stats_missing?.[side]) {
        return t("entity.no_stats", { version: t(`entity.version.${side}`) });
      }
    }
    return null;
  }

  return { open };
}

/**
 * @param {Record<string, any>} details
 * @returns {boolean}
 */
function allMissing(details) {
  return Boolean(details.stats_missing?.old && details.stats_missing?.new);
}

/**
 * @param {"h3" | "h4"} level
 * @param {string} text
 * @returns {HTMLElement}
 */
function heading(level, text) {
  return el(level, { class: "label drawer__section", text });
}

/**
 * @param {string} modifier
 * @param {string} text
 * @returns {HTMLElement}
 */
function tag(modifier, text) {
  return el("span", { class: `tag ${modifier}`, text });
}

/**
 * The game's description, styled as in its tooltip.
 * @param {Array<Array<Record<string, any>>>} lines
 * @param {Record<string, any>} statIcons
 * @returns {HTMLElement}
 */
function description(lines, statIcons) {
  const box = el("div", { class: "drawer__description" });
  for (const line of lines) {
    const paragraph = el("p");
    for (const run of line) {
      if (run.kind === "static_cost") {
        const value = el("span", { class: "drawer__static-cost" });
        const image = icons.element(statIcons[run.resource]);
        if (image !== null) {
          image.classList.add("drawer__stat-icon");
          value.append(image);
        }
        value.append(document.createTextNode(String(run.amount)));
        paragraph.append(value);
        continue;
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
      paragraph.append(text);
    }
    box.append(paragraph);
  }
  return box;
}

/**
 * Labelled values, each in the comparison's colours.
 * @param {Parameters<typeof fieldCell>[0]} view
 * @param {Array<Record<string, any>>} list
 * @returns {HTMLElement}
 */
function rows(view, list) {
  const box = el("div", { class: "drawer__rows" });
  for (const row of list) {
    const line = el("div", { class: `drawer__row is-${row.state}` });
    line.append(fieldCell(view, row), value(row));
    box.append(line);
  }
  return box;
}

/**
 * @param {Record<string, any>} row
 * @returns {HTMLElement}
 */
export function value(row) {
  const box = el("div", { class: "drawer__value" });
  if (row.state === "changed") {
    box.append(
      el("span", { class: "value-old", text: row.old ?? "" }),
      el("span", { class: "change-values__arrow", text: "→" }),
      el("span", { class: "value-new", text: row.new ?? "" }),
    );
  } else if (row.state === "added") {
    box.append(el("span", { class: "value-new", text: row.new ?? "" }));
  } else if (row.state === "removed") {
    box.append(el("del", { class: "value-old", text: row.old ?? "" }));
  } else {
    box.append(document.createTextNode(row.new ?? row.old ?? ""));
  }
  return box;
}
