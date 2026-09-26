// SPDX-License-Identifier: GPL-3.0-or-later
/** The capture dialog and the progress view (ui.md, "Capture"). */

import * as dialogs from "./dialogs.js";
import { byId, clear, el, input, show } from "./dom.js";

// The steps the progress view lists, in the order the capture runs them (capture/runner.py).
const STEPS = ["folder", "files", "fingerprints", "stats", "icons", "backup", "save"];
const POLL_MS = 250;

/**
 * Wire the capture dialog and the progress view.
 * @param {{
 *   api: import("./api.js").Api,
 *   t: (key: string, values?: Record<string, unknown>) => string,
 *   onStatus: (status: import("./api.js").CaptureStatus | null) => void,
 *   onFinished: (result: Record<string, unknown>) => void,
 * }} deps
 * @returns {{openDialog: () => Promise<void>, showProgress: (status:
 *   import("./api.js").CaptureStatus) => void, watch: () => void}}
 */
export function initCapture(deps) {
  let pollTimer = 0;
  /** @type {string | null} */
  let chosenFolder = null;
  let captureAnyway = false;

  async function openDialog() {
    captureAnyway = false;
    input("capture-label").value = "";
    input("capture-prerelease").checked = false;
    byId("capture-folder-help").textContent = deps.t("capture.detecting");
    input("capture-folder").value = "";
    dialogs.open("capture-scrim");
    const candidates = await deps.api.detect_game_folders();
    if (candidates.length === 0) {
      byId("capture-folder-help").textContent = deps.t("capture.not_found");
      return;
    }
    const first = candidates[0];
    chosenFolder = first.path;
    input("capture-folder").value = first.path;
    input("capture-prerelease").checked = first.prerelease_hint;
    await describeFolder(first.path);
    suggestLabel(first.game_build);
  }

  /**
   * Validate a folder and say what was found there.
   * @param {string} path
   */
  async function describeFolder(path) {
    if (!path) {
      byId("capture-folder-help").textContent = deps.t("capture.not_found");
      return;
    }
    const checked = await deps.api.validate_game_folder(path);
    if (checked.valid !== true) {
      byId("capture-folder-help").textContent = deps.t("capture.invalid", {
        reason: String(checked.reason ?? ""),
      });
      return;
    }
    chosenFolder = String(checked.path);
    input("capture-folder").value = chosenFolder;
    const build = checked.game_build;
    byId("capture-folder-help").textContent =
      typeof build === "string"
        ? deps.t("capture.found_build", { build })
        : deps.t("capture.found_no_build");
    suggestLabel(typeof build === "string" ? build : null);
  }

  /**
   * Default label: `<game build> · <date>` (P-14).
   * @param {string | null} build
   */
  function suggestLabel(build) {
    const field = input("capture-label");
    if (field.value.trim() !== "") {
      return;
    }
    const date = new Date().toLocaleDateString(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
    field.value = build ? `${build} · ${date}` : date;
  }

  /**
   * Draw the progress view for one status report.
   * @param {import("./api.js").CaptureStatus} status
   */
  function showProgress(status) {
    byId("capture-view-title").textContent = status.label;
    const percent = Math.round(status.fraction * 100);
    byId("capture-progress").setAttribute("aria-valuenow", String(percent));
    byId("capture-progress-bar").style.width = `${percent}%`;
    byId("capture-view-meta").textContent = status.running
      ? deps.t("progress.running", { percent })
      : deps.t("progress.finished");

    const list = byId("capture-steps");
    clear(list);
    const current = STEPS.indexOf(status.phase);
    STEPS.forEach((name, index) => {
      const state = !status.running || current === -1 ? "done" : stateOf(index, current);
      const step = el("li", { class: "step", attrs: { "data-state": state } });
      step.append(el("span", { class: "step__mark", text: mark(state) }));
      step.append(el("span", { class: "step__name", text: deps.t(`progress.step.${name}`) }));
      const detail = index === current ? status.detail : "";
      step.append(el("span", { class: "step__detail", text: detail }));
      list.append(step);
    });

    show(byId("capture-cancel"), status.running);
    const result = status.result ?? {};
    byId("capture-result").textContent = status.running ? "" : resultText(result);
    show(byId("capture-open"), !status.running && typeof result.capture_id === "string");
    show(byId("capture-anyway"), !status.running && result.stopped_early === true);
  }

  /**
   * @param {Record<string, unknown>} result
   * @returns {string}
   */
  function resultText(result) {
    if (typeof result.error === "string") {
      return deps.t("progress.failed", { reason: result.error });
    }
    if (result.cancelled === true) {
      return deps.t("progress.cancelled");
    }
    if (result.stopped_early === true) {
      return deps.t("progress.identical");
    }
    if (result.stats_available === false) {
      return deps.t("progress.no_stats", { reason: String(result.stats_reason ?? "") });
    }
    return deps.t("progress.done");
  }

  /** Poll the capture until it finishes, reporting every status to the app. */
  function watch() {
    window.clearInterval(pollTimer);
    pollTimer = window.setInterval(async () => {
      const status = await deps.api.get_capture_status();
      deps.onStatus(status);
      if (status !== null && !status.running) {
        window.clearInterval(pollTimer);
        deps.onFinished(status.result ?? {});
      }
    }, POLL_MS);
  }

  byId("capture-browse").addEventListener("click", async () => {
    const chosen = await deps.api.browse_for_folder();
    if (typeof chosen === "string") {
      await describeFolder(chosen);
    }
  });
  input("capture-folder").addEventListener("change", (event) => {
    const target = event.target;
    if (target instanceof HTMLInputElement) {
      void describeFolder(target.value.trim());
    }
  });
  byId("capture-dialog-cancel").addEventListener("click", () => dialogs.close("capture-scrim"));
  byId("capture-start").addEventListener("click", async () => {
    const path = chosenFolder ?? input("capture-folder").value.trim();
    if (!path) {
      byId("capture-folder-help").textContent = deps.t("capture.not_found");
      return;
    }
    const label = input("capture-label").value.trim() || path;
    const started = await deps.api.start_capture(
      path,
      label,
      input("capture-prerelease").checked,
      captureAnyway,
    );
    if (started.started !== true) {
      dialogs.toast(deps.t("capture.already_running"));
      return;
    }
    dialogs.close("capture-scrim");
    watch();
  });
  byId("capture-cancel").addEventListener("click", () => {
    void deps.api.cancel_capture();
  });
  byId("capture-anyway").addEventListener("click", async () => {
    captureAnyway = true;
    const path = chosenFolder ?? input("capture-folder").value.trim();
    const label = input("capture-label").value.trim() || path;
    await deps.api.start_capture(path, label, input("capture-prerelease").checked, true);
    watch();
  });

  return { openDialog, showProgress, watch };
}

/**
 * @param {number} index
 * @param {number} current
 * @returns {"done" | "running" | "pending"}
 */
function stateOf(index, current) {
  if (index < current) {
    return "done";
  }
  return index === current ? "running" : "pending";
}

/**
 * @param {string} state
 * @returns {string}
 */
function mark(state) {
  if (state === "done") {
    return "✓";
  }
  return state === "running" ? "●" : "○";
}
