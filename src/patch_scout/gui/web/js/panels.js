// SPDX-License-Identifier: GPL-3.0-or-later
/** The export, settings and diagnostics panels (P-13, P-10, P-19, P-08). */

import * as dialogs from "./dialogs.js";
import { byId, clear, el, input, show } from "./dom.js";

/**
 * Wire the export panel.
 * @param {{
 *   api: import("./api.js").Api,
 *   t: (key: string, values?: Record<string, unknown>) => string,
 *   current: () => {oldId: string, newId: string, low: boolean, civs: string[] | null,
 *     prerelease: boolean} | null,
 * }} deps
 * @returns {{open: () => Promise<void>}}
 */
export function initExport(deps) {
  async function openPanel() {
    const state = deps.current();
    if (state === null) {
      return;
    }
    show(byId("export-embargo"), state.prerelease);
    byId("export-status").textContent = "";
    byId("export-preview").textContent = deps.t("export.loading");
    dialogs.open("export-scrim");
    const exported = await deps.api.export_text(state.oldId, state.newId, state.low, state.civs);
    byId("export-preview").textContent = exported.text;
  }

  byId("export-close").addEventListener("click", () => dialogs.close("export-scrim"));
  byId("export-copy").addEventListener("click", async () => {
    const text = byId("export-preview").textContent ?? "";
    try {
      await navigator.clipboard.writeText(text);
      byId("export-status").textContent = deps.t("export.copied");
    } catch (error) {
      console.error("the clipboard refused the export", error);
      byId("export-status").textContent = deps.t("export.copy_failed");
    }
  });
  for (const [id, kind] of [
    ["export-text", "text"],
    ["export-html", "html"],
  ]) {
    byId(id).addEventListener("click", async () => {
      const state = deps.current();
      if (state === null) {
        return;
      }
      const saved = await deps.api.save_export(
        state.oldId,
        state.newId,
        kind,
        state.low,
        state.civs,
      );
      byId("export-status").textContent = saved.saved
        ? deps.t("export.saved", { path: String(saved.path ?? "") })
        : deps.t("export.not_saved");
    });
  }

  return { open: openPanel };
}

/**
 * Wire the settings panel.
 * @param {{
 *   api: import("./api.js").Api,
 *   t: (key: string, values?: Record<string, unknown>) => string,
 * }} deps
 * @returns {{open: () => Promise<void>}}
 */
export function initSettings(deps) {
  async function openPanel() {
    const settings = await deps.api.get_settings();
    byId("settings-folder").textContent = settings.data_folder;
    input("settings-backups").checked = settings.raw_backups;
    byId("settings-status").textContent = "";
    dialogs.open("settings-scrim");
  }

  byId("settings-close").addEventListener("click", () => dialogs.close("settings-scrim"));
  input("settings-backups").addEventListener("change", async (event) => {
    const target = event.target;
    if (target instanceof HTMLInputElement) {
      await deps.api.update_settings(target.checked);
    }
  });
  byId("settings-purge").addEventListener("click", async () => {
    const result = await deps.api.purge_backups();
    byId("settings-status").textContent = deps.t("settings.purged", { count: result.removed });
  });

  return { open: openPanel };
}

/**
 * Wire the diagnostics panel: environment, gates, capture log and the snapshot inspector.
 * @param {{
 *   api: import("./api.js").Api,
 *   t: (key: string, values?: Record<string, unknown>) => string,
 * }} deps
 * @returns {{open: (captureId?: string | null) => Promise<void>}}
 */
export function initDiagnostics(deps) {
  /** @type {Record<string, any>} */
  let latest = {};

  async function openPanel(captureId = null) {
    latest = await deps.api.get_diagnostics(captureId);
    const environment = byId("diagnostics-environment");
    clear(environment);
    for (const [name, value] of Object.entries(latest.environment ?? {})) {
      environment.append(el("dt", { class: "label", text: name }));
      environment.append(el("dd", { class: "mono", text: String(value ?? "") }));
    }
    byId("diagnostics-log").textContent = (latest.log ?? []).join("\n");
    renderGates(latest.snapshot);
    fillVersions(latest.versions ?? [], captureId);
    dialogs.open("diagnostics-scrim");
    await refreshSection();
  }

  /**
   * @param {Record<string, any> | null | undefined} snapshot
   */
  function renderGates(snapshot) {
    const box = byId("diagnostics-gates");
    clear(box);
    if (!snapshot) {
      box.append(el("p", { class: "help", text: deps.t("diagnostics.no_snapshot") }));
      return;
    }
    const flags = snapshot.flags ?? {};
    box.append(
      el("p", {
        text: flags.stats_available
          ? deps.t("diagnostics.stats_ok")
          : deps.t("diagnostics.stats_missing", {
              reason: String(flags.stats_unavailable_reason ?? ""),
            }),
      }),
    );
    for (const attempt of flags.dat_attempts ?? []) {
      box.append(
        el("p", {
          class: "mono",
          text: `${attempt.layout}: ${attempt.result} — ${attempt.detail}`,
        }),
      );
    }
    for (const check of flags.sanity_checks ?? []) {
      box.append(
        el("p", {
          class: "mono",
          text: `${check.passed ? "✓" : "✗"} ${check.name} — ${check.detail}`,
        }),
      );
    }
  }

  /**
   * @param {Array<Record<string, any>>} versions
   * @param {string | null} captureId
   */
  function fillVersions(versions, captureId) {
    const select = byId("diagnostics-version");
    if (!(select instanceof HTMLSelectElement)) {
      return;
    }
    clear(select);
    for (const version of versions) {
      const option = document.createElement("option");
      option.value = version.capture_id;
      option.textContent = version.label;
      select.append(option);
    }
    if (captureId !== null) {
      select.value = captureId;
    }
    const sections = byId("diagnostics-section");
    if (sections instanceof HTMLSelectElement && sections.options.length === 0) {
      for (const name of latest.snapshot?.sections ?? ["meta", "flags", "civs"]) {
        const option = document.createElement("option");
        option.value = name;
        option.textContent = name;
        sections.append(option);
      }
    }
  }

  async function refreshSection() {
    const version = byId("diagnostics-version");
    const section = byId("diagnostics-section");
    if (!(version instanceof HTMLSelectElement) || !(section instanceof HTMLSelectElement)) {
      return;
    }
    if (version.value === "" || section.value === "") {
      return;
    }
    const value = await deps.api.get_snapshot_section(version.value, section.value);
    byId("diagnostics-section-body").textContent = JSON.stringify(value, null, 2) ?? "";
  }

  byId("diagnostics-close").addEventListener("click", () => dialogs.close("diagnostics-scrim"));
  byId("diagnostics-version").addEventListener("change", () => void refreshSection());
  byId("diagnostics-section").addEventListener("change", () => void refreshSection());
  byId("diagnostics-copy").addEventListener("click", async () => {
    // Copy diagnostics carries no game data values (CONTRIBUTING.md).
    const text = [
      ...Object.entries(latest.environment ?? {}).map(([name, value]) => `${name}: ${value}`),
      "",
      ...(latest.log ?? []),
    ].join("\n");
    try {
      await navigator.clipboard.writeText(text);
      dialogs.toast(deps.t("diagnostics.copied"));
    } catch (error) {
      console.error("the clipboard refused the diagnostics", error);
      dialogs.toast(deps.t("export.copy_failed"));
    }
  });

  return { open: openPanel };
}

/**
 * Wire the "compare with..." picker.
 * @param {{
 *   t: (key: string, values?: Record<string, unknown>) => string,
 *   versions: () => import("./api.js").Version[],
 *   onPicked: (captureId: string) => void,
 * }} deps
 * @returns {{open: (exclude: string) => void}}
 */
export function initPicker(deps) {
  function openPanel(exclude) {
    const list = byId("pick-list");
    clear(list);
    const others = deps.versions().filter((version) => version.capture_id !== exclude);
    show(byId("pick-empty"), others.length === 0);
    for (const version of others) {
      const item = el("li");
      const button = el("button", { class: "pick-row", attrs: { type: "button" } });
      button.append(el("span", { class: "pick-row__name", text: version.label }));
      button.append(
        el("span", {
          class: "pick-row__meta",
          text: version.game_build ?? deps.t("version_list.unknown_build"),
        }),
      );
      button.addEventListener("click", () => {
        dialogs.close("pick-scrim");
        deps.onPicked(version.capture_id);
      });
      item.append(button);
      list.append(item);
    }
    dialogs.open("pick-scrim");
  }

  byId("pick-cancel").addEventListener("click", () => dialogs.close("pick-scrim"));
  return { open: openPanel };
}
