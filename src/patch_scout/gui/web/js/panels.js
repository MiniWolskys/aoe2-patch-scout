// SPDX-License-Identifier: GPL-3.0-or-later
/** The export, settings and diagnostics panels (P-13, P-10, P-19, P-08). */

import * as dialogs from "./dialogs.js";
import { byId, clear, el, input, show } from "./dom.js";
import * as image from "./image.js";

/**
 * Wire the export panel.
 * @param {{
 *   api: import("./api.js").Api,
 *   t: (key: string, values?: Record<string, unknown>) => string,
 *   current: () => {oldId: string, newId: string, low: boolean, unnamed: boolean,
 *     details: boolean, technical: boolean, civs: string[] | null, prerelease: boolean,
 *     page: Parameters<typeof image.draw>[0]["page"], versions: string} | null,
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
    const exported = await deps.api.export_text(
      state.oldId,
      state.newId,
      state.low,
      state.civs,
      state.unnamed,
      state.details,
      state.technical,
    );
    byId("export-preview").textContent = exported.text;
  }

  byId("export-close").addEventListener("click", () => dialogs.close("export-scrim"));
  // The page on screen as PNG images for a video (P-13); a long page comes out in parts.
  byId("export-image").addEventListener("click", async () => {
    const state = deps.current();
    if (state === null) {
      return;
    }
    byId("export-status").textContent = deps.t("export.image_drawing");
    const images = await image.draw({
      page: state.page,
      versions: state.versions,
      notice: deps.t("about.microsoft"),
      t: deps.t,
    });
    const saved = await deps.api.save_images(images, state.page.title);
    byId("export-status").textContent = saved.saved
      ? deps.t("export.image_saved", { count: images.length, path: String(saved.path ?? "") })
      : notSaved(deps.t, saved);
  });
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
        state.unnamed,
        state.details,
        state.technical,
      );
      byId("export-status").textContent = saved.saved
        ? deps.t("export.saved", { path: String(saved.path ?? "") })
        : notSaved(deps.t, saved);
    });
  }

  return { open: openPanel };
}

/**
 * Why nothing was saved: the user cancelled, or the system refused (read-only folder, full disk).
 * @param {(key: string, values?: Record<string, unknown>) => string} t
 * @param {{saved: boolean, error?: string}} answer
 * @returns {string}
 */
export function notSaved(t, answer) {
  return answer.error ? t("export.save_failed", { reason: answer.error }) : t("export.not_saved");
}

/**
 * Wire the settings panel.
 * @param {{
 *   api: import("./api.js").Api,
 *   t: (key: string, values?: Record<string, unknown>) => string,
 *   version: string,
 * }} deps
 * @returns {{open: () => Promise<void>}}
 */
export function initSettings(deps) {
  byId("about-version").textContent = deps.t("about.version", { version: deps.version });

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
      // In words when the catalog knows the key; a new key still shows, as it is.
      let label = String(name);
      try {
        label = deps.t(`diagnostics.env.${name}`);
      } catch {
        // a key the catalog doesn't name yet: shown as it is
      }
      environment.append(el("dt", { class: "label", text: label }));
      const known = value !== null && value !== undefined && value !== "";
      environment.append(
        el("dd", { class: "mono", text: known ? String(value) : deps.t("diagnostics.unknown") }),
      );
    }
    byId("diagnostics-log").textContent =
      (latest.log ?? []).join("\n") || deps.t("diagnostics.no_log");
    byId("diagnostics-problems").textContent =
      (latest.problems ?? []).join("\n") || deps.t("diagnostics.no_problems");
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
    if (!(sections instanceof HTMLSelectElement)) {
      return;
    }
    // Rebuilt every time: opening Diagnostics without a version gives a short fallback list, and
    // opening one afterwards must widen it to that snapshot's real sections.
    const names = latest.snapshot?.sections ?? ["meta", "flags", "civs"];
    const chosen = sections.value;
    clear(sections);
    for (const name of names) {
      const option = document.createElement("option");
      option.value = name;
      option.textContent = name;
      sections.append(option);
    }
    if (names.includes(chosen)) {
      sections.value = chosen;
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
  // The app has no right-click menu outside debug mode, so each box copies its whole content.
  for (const [button, box] of [
    ["diagnostics-log-copy", "diagnostics-log"],
    ["diagnostics-problems-copy", "diagnostics-problems"],
    ["diagnostics-section-copy", "diagnostics-section-body"],
  ]) {
    byId(button).addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(byId(box).textContent ?? "");
        dialogs.toast(deps.t("diagnostics.box_copied"));
      } catch (error) {
        console.error("the clipboard refused the text", error);
        dialogs.toast(deps.t("export.copy_failed"));
      }
    });
  }
  byId("diagnostics-version").addEventListener("change", () => void refreshSection());
  byId("diagnostics-section").addEventListener("change", () => void refreshSection());
  byId("diagnostics-copy").addEventListener("click", async () => {
    // Copy diagnostics carries no game data values (CONTRIBUTING.md).
    const text = [
      ...Object.entries(latest.environment ?? {}).map(([name, value]) => `${name}: ${value}`),
      "",
      ...(latest.log ?? []),
      "",
      ...(latest.problems ?? []),
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
