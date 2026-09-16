// SPDX-License-Identifier: GPL-3.0-or-later
/** Start the page, hold the app's state, and show the right view (ui.md). */

import { connect } from "./api.js";
import { initCapture } from "./capture.js";
import * as comparison from "./comparison.js";
import * as details from "./details.js";
import * as dialogs from "./dialogs.js";
import { byId, input, onClick, show } from "./dom.js";
import { applyTranslations, createTranslator } from "./i18n.js";
import * as icons from "./icons.js";
import { initDiagnostics, initExport, initPicker, initSettings } from "./panels.js";
import { initVersionList, render as renderVersions } from "./version-list.js";

const VIEWS = ["first-launch", "capture-view", "details-view", "comparison-view"];

async function start() {
  const api = await connect();
  const startup = await api.get_startup();
  document.documentElement.lang = startup.language;
  const t = createTranslator(startup.messages);
  applyTranslations(document, t);
  dialogs.listen();

  /** @type {{
   *   versions: import("./api.js").Version[],
   *   openId: string | null,
   *   comparison: {oldId: string, newId: string, changeSet: Record<string, any>,
   *     civ: string | null} | null,
   *   capture: import("./api.js").CaptureStatus | null,
   *   filters: {low: boolean, unreachable: boolean, search: string},
   *   view: string,
   * }} */
  const state = {
    versions: startup.versions,
    openId: null,
    comparison: null,
    capture: startup.capture,
    filters: { low: false, unreachable: false, search: "" },
    view: "first-launch",
  };

  function showView(name) {
    state.view = name;
    for (const id of VIEWS) {
      show(byId(id), id === name);
    }
  }

  function drawVersionList() {
    renderVersions({
      t,
      versions: state.versions,
      capture: state.capture,
      openId: state.openId,
      comparison: state.comparison,
      onOpen: (captureId) => void openVersion(captureId),
      onCompare: (captureId) => void compareWith(captureId),
      onOpenCapture: () => {
        if (state.capture !== null) {
          capture.showProgress(state.capture);
          showView("capture-view");
        }
      },
    });
  }

  async function refreshVersions() {
    state.versions = await api.get_versions();
    drawVersionList();
  }

  async function openVersion(captureId) {
    state.openId = captureId;
    await detailsView.show(captureId, state.comparison !== null);
    showView("details-view");
    drawVersionList();
  }

  /**
   * Compare a version with whatever is open: the open version, or the newest other one.
   * @param {string} captureId
   */
  async function compareWith(captureId) {
    const other =
      state.openId !== null && state.openId !== captureId
        ? state.openId
        : state.versions.find((version) => version.capture_id !== captureId)?.capture_id;
    if (other === undefined) {
      dialogs.toast(t("comparison.needs_two"));
      return;
    }
    await openComparison(other, captureId);
  }

  async function openComparison(firstId, secondId) {
    const changeSet = await api.compare_versions(firstId, secondId, state.filters.unreachable);
    await icons.preload(api, comparison.iconHashes(changeSet));
    state.comparison = {
      oldId: changeSet.old.capture_id,
      newId: changeSet.new.capture_id,
      changeSet,
      civ: null,
    };
    state.openId = null;
    drawComparison();
    showView("comparison-view");
    drawVersionList();
  }

  function drawComparison() {
    if (state.comparison === null) {
      return;
    }
    comparison.render({
      t,
      changeSet: state.comparison.changeSet,
      civ: state.comparison.civ,
      filters: state.filters,
      onCiv: (internalName) => {
        if (state.comparison !== null) {
          state.comparison.civ = internalName;
          drawComparison();
        }
      },
      onPick: (side) => {
        const current = side === "old" ? state.comparison?.oldId : state.comparison?.newId;
        if (current !== undefined) {
          picker.open(current);
        }
      },
    });
  }

  const capture = initCapture({
    api,
    t,
    onStatus: (status) => {
      state.capture = status;
      drawVersionList();
      if (status !== null && state.view === "capture-view") {
        capture.showProgress(status);
      }
    },
    onFinished: async (result) => {
      await refreshVersions();
      if (state.view === "capture-view") {
        const status = await api.get_capture_status();
        if (status !== null) {
          capture.showProgress(status);
        }
      }
      // When a capture finishes, open it compared with the previous newest version (D-32).
      const captureId = result.capture_id;
      if (typeof captureId === "string") {
        await api.clear_capture();
        state.capture = null;
        const previous = state.versions.find((version) => version.capture_id !== captureId);
        if (previous !== undefined) {
          await openComparison(previous.capture_id, captureId);
        } else {
          await openVersion(captureId);
        }
      }
    },
  });

  const detailsView = details.initDetails({
    api,
    t,
    onChanged: refreshVersions,
    onDeleted: async () => {
      state.openId = null;
      state.comparison = null;
      await refreshVersions();
      showView(state.versions.length === 0 ? "first-launch" : "details-view");
      if (state.versions.length > 0) {
        await openVersion(state.versions[0].capture_id);
      }
    },
    onCompare: (captureId) => picker.open(captureId),
    onDiagnostics: (captureId) => void diagnostics.open(captureId),
    onBack: () => showView("comparison-view"),
  });

  const picker = initPicker({
    t,
    versions: () => state.versions,
    onPicked: (captureId) => {
      const other = state.openId ?? state.comparison?.newId;
      if (other !== undefined && other !== null) {
        void openComparison(other, captureId);
      }
    },
  });

  const exporter = initExport({
    api,
    t,
    current: () => {
      if (state.comparison === null) {
        return null;
      }
      const sides = [state.comparison.changeSet.old, state.comparison.changeSet.new];
      return {
        oldId: state.comparison.oldId,
        newId: state.comparison.newId,
        low: state.filters.low,
        civs: state.comparison.civ === null ? null : [state.comparison.civ],
        prerelease: sides.some((side) => side?.prerelease === true),
      };
    },
  });

  const settings = initSettings({ api, t });
  const diagnostics = initDiagnostics({ api, t });

  initVersionList(byId("version-list"), { t });
  onClick("capture-button", () => void capture.openDialog());
  onClick("first-launch-capture", () => void capture.openDialog());
  onClick("settings-button", () => void settings.open());
  onClick("diagnostics-button", () => void diagnostics.open(state.openId));
  onClick("comparison-export", () => void exporter.open());
  onClick("comparison-swap", () => {
    if (state.comparison !== null) {
      void openComparison(state.comparison.newId, state.comparison.oldId);
    }
  });
  onClick("picker-old", () => picker.open(state.comparison?.newId ?? ""));
  onClick("picker-new", () => picker.open(state.comparison?.oldId ?? ""));
  onClick("comparison-filters", () => {
    const panel = byId("filters-panel");
    const open = panel.hidden;
    show(panel, open);
    byId("comparison-filters").setAttribute("aria-expanded", String(open));
  });
  input("filter-low").addEventListener("change", (event) => {
    const target = event.target;
    if (target instanceof HTMLInputElement) {
      state.filters.low = target.checked;
      drawComparison();
    }
  });
  input("filter-unreachable").addEventListener("change", async (event) => {
    const target = event.target;
    if (target instanceof HTMLInputElement && state.comparison !== null) {
      state.filters.unreachable = target.checked;
      await openComparison(state.comparison.oldId, state.comparison.newId);
    }
  });
  input("filter-search").addEventListener("input", (event) => {
    const target = event.target;
    if (target instanceof HTMLInputElement) {
      state.filters.search = target.value;
      drawComparison();
    }
  });
  onClick("capture-open", () => {
    const captureId = state.capture?.result?.capture_id;
    if (typeof captureId === "string") {
      void openVersion(captureId);
    }
  });

  drawVersionList();
  const unfinished = state.capture !== null && !state.capture.result?.capture_id;
  if (state.capture?.running || unfinished) {
    capture.showProgress(state.capture);
    showView("capture-view");
    if (state.capture?.running) {
      capture.watch();
    }
  } else if (startup.versions.length === 0) {
    showView("first-launch");
  } else if (startup.last_comparison.length === 2 && reopenable(startup)) {
    await openComparison(startup.last_comparison[0], startup.last_comparison[1]);
  } else {
    await openVersion(startup.versions[0].capture_id);
  }
  document.body.dataset.ready = "";
}

/**
 * Whether the comparison that was open last time can be reopened (ui.md, "On launch").
 * @param {import("./api.js").Startup} startup
 * @returns {boolean}
 */
function reopenable(startup) {
  const known = new Set(startup.versions.map((version) => version.capture_id));
  return startup.last_comparison.every((captureId) => known.has(captureId));
}

start().catch((error) => {
  console.error("Patch Scout couldn't start the page", error);
});
