// SPDX-License-Identifier: GPL-3.0-or-later
/** Version details: rename, pre-release tickbox, notes, and the actions (ui.md, P-14, P-18). */

import * as dialogs from "./dialogs.js";
import { byId, clear, el, formatDate, input, show } from "./dom.js";

/**
 * Wire the details view.
 * @param {{
 *   api: import("./api.js").Api,
 *   t: (key: string, values?: Record<string, unknown>) => string,
 *   onChanged: () => Promise<void>,
 *   onDeleted: () => Promise<void>,
 *   onCompare: (captureId: string) => void,
 *   onDiagnostics: (captureId: string) => void,
 *   onBack: () => void,
 * }} deps
 * @returns {{show: (captureId: string, hasComparison: boolean) => Promise<void>}}
 */
export function initDetails(deps) {
  /** @type {string | null} */
  let openId = null;

  async function showVersion(captureId, hasComparison) {
    openId = captureId;
    const version = await deps.api.get_version(captureId);
    byId("details-title").textContent = String(version.label ?? "");
    show(byId("details-prerelease-badge"), version.prerelease === true);
    show(byId("details-back"), hasComparison);
    const build = version.game_build ?? deps.t("version_list.unknown_build");
    byId("details-meta").textContent =
      `${build} · ${formatDate(String(version.captured_at ?? ""))}`;

    const fields = byId("details-fields");
    clear(fields);
    addField(fields, deps.t("details.source"), sourceText(deps.t, version));
    addField(fields, deps.t("details.civs"), String(version.civ_count ?? ""));
    addField(fields, deps.t("details.stats"), statsText(deps.t, version));
    const meta = /** @type {Record<string, unknown>} */ (version.meta ?? {});
    if (typeof meta.dat_format_version === "string") {
      addField(fields, deps.t("details.dat_format"), formatText(deps.t, meta, version));
    }

    input("details-prerelease").checked = version.prerelease === true;
    const notes = byId("details-notes");
    if (notes instanceof HTMLTextAreaElement) {
      notes.value = String(version.notes ?? "");
    }
  }

  byId("details-title").addEventListener("click", () => void rename());
  byId("details-title").addEventListener("keydown", (event) => {
    if (event instanceof KeyboardEvent && (event.key === "Enter" || event.key === " ")) {
      event.preventDefault();
      void rename();
    }
  });

  /** Rename the open version in place (P-14). */
  async function rename() {
    if (openId === null) {
      return;
    }
    const title = byId("details-title");
    const field = document.createElement("input");
    field.className = "input";
    field.value = title.textContent ?? "";
    title.replaceWith(field);
    field.focus();
    field.select();
    const finish = async () => {
      const value = field.value.trim();
      const replacement = el("span", { text: value, attrs: { tabindex: "0", role: "button" } });
      replacement.id = "details-title";
      field.replaceWith(replacement);
      replacement.addEventListener("click", () => void rename());
      if (value !== "" && openId !== null) {
        await deps.api.update_version(openId, value);
        await deps.onChanged();
      }
    };
    field.addEventListener("blur", () => void finish(), { once: true });
    field.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        field.blur();
      }
    });
  }

  input("details-prerelease").addEventListener("change", async (event) => {
    const target = event.target;
    if (openId === null || !(target instanceof HTMLInputElement)) {
      return;
    }
    await deps.api.update_version(openId, null, target.checked);
    show(byId("details-prerelease-badge"), target.checked);
    await deps.onChanged();
  });

  byId("details-notes").addEventListener("change", async (event) => {
    const target = event.target;
    if (openId === null || !(target instanceof HTMLTextAreaElement)) {
      return;
    }
    await deps.api.update_version(openId, null, null, target.value);
  });

  byId("details-compare").addEventListener("click", () => {
    if (openId !== null) {
      deps.onCompare(openId);
    }
  });
  byId("details-diagnostics").addEventListener("click", () => {
    if (openId !== null) {
      deps.onDiagnostics(openId);
    }
  });
  byId("details-back").addEventListener("click", () => deps.onBack());
  byId("details-delete").addEventListener("click", async () => {
    if (openId === null) {
      return;
    }
    const label = byId("details-title").textContent ?? "";
    const agreed = await dialogs.confirm({
      title: deps.t("details.delete_title"),
      text: deps.t("details.delete_text", { label }),
      confirm: deps.t("details.delete"),
    });
    if (!agreed) {
      return;
    }
    await deps.api.delete_version(openId);
    openId = null;
    await deps.onDeleted();
  });

  return { show: showVersion };
}

/**
 * @param {HTMLElement} list
 * @param {string} name
 * @param {string} value
 */
function addField(list, name, value) {
  list.append(el("dt", { class: "label", text: name }));
  list.append(el("dd", { text: value }));
}

/**
 * @param {(key: string, values?: Record<string, unknown>) => string} t
 * @param {Record<string, any>} version
 * @returns {string}
 */
function sourceText(t, version) {
  if (version.origin === "captured" && typeof version.source_path === "string") {
    return t("details.source_captured", { path: version.source_path });
  }
  return t(`details.source_${version.origin ?? "imported"}`);
}

/**
 * @param {(key: string, values?: Record<string, unknown>) => string} t
 * @param {Record<string, any>} version
 * @returns {string}
 */
function statsText(t, version) {
  if (version.stats_available === true) {
    return t("details.stats_ok");
  }
  return t("details.stats_missing", { reason: String(version.stats_reason ?? "") });
}

/**
 * @param {(key: string, values?: Record<string, unknown>) => string} t
 * @param {Record<string, unknown>} meta
 * @param {Record<string, any>} version
 * @returns {string}
 */
function formatText(t, meta, version) {
  const found = String(meta.dat_format_version ?? "");
  const used = String(meta.dat_layout_version ?? "");
  if (version.format_verified === false && used !== "") {
    return t("details.dat_substituted", { found, used });
  }
  return found;
}
