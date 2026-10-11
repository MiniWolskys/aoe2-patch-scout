// SPDX-License-Identifier: GPL-3.0-or-later
/** Start the page, hold the app's state, and show the right view (ui.md). */

import { connect } from "./api.js";
import { initCapture } from "./capture.js";
import * as comparison from "./comparison.js";
import * as details from "./details.js";
import * as dialogs from "./dialogs.js";
import { byId, clear, el, input, onClick, show } from "./dom.js";
import { initEntityPanel } from "./entity-panel.js";
import { applyTranslations, createTranslator } from "./i18n.js";
import * as icons from "./icons.js";
import { initDiagnostics, initExport, initPicker, initSettings } from "./panels.js";
import * as techTree from "./tree.js";
import * as treePanel from "./tree-panel.js";
import { initVersionList, render as renderVersions } from "./version-list.js";

const VIEWS = ["first-launch", "capture-view", "details-view", "comparing-view", "comparison-view"];

async function start() {
  const api = await connect();
  const startup = await api.get_startup();
  document.documentElement.lang = startup.language;
  const t = createTranslator(startup.messages);
  applyTranslations(document, t);
  dialogs.listen();
  // A call that fails anywhere else still says so, instead of doing nothing.
  window.addEventListener("unhandledrejection", (event) => {
    console.error("unexpected error", event.reason);
    dialogs.toast(t("error.unexpected"));
  });

  /** @type {{
   *   versions: import("./api.js").Version[],
   *   openId: string | null,
   *   comparison: {oldId: string, newId: string, changeSet: Record<string, any>,
   *     civ: string | null, view: "changes" | "tree", treeCiv: string | null,
   *     trees: Map<string, Record<string, any>>} | null,
   *   capture: import("./api.js").CaptureStatus | null,
   *   filters: {low: boolean, unreachable: boolean, unnamed: boolean, details: boolean,
   *     technical: boolean, search: string},
   *   view: string,
   *   treeFit: boolean,
   * }} */
  const state = {
    versions: startup.versions,
    openId: null,
    comparison: null,
    capture: startup.capture,
    filters: {
      low: false,
      unreachable: false,
      unnamed: false,
      details: false,
      technical: false,
      search: "",
    },
    view: "first-launch",
    treeFit: false,
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

  /** Add a version from an archive or the baseline pack (P-21), then open it. */
  async function importVersion() {
    const path = await api.choose_archive();
    if (!path) {
      return;
    }
    // A real archive takes seconds to check and store: say so meanwhile.
    const previous = state.view;
    byId("comparing-title").textContent = t("import.running");
    byId("comparing-meta").textContent = path;
    showView("comparing-view");
    let result;
    try {
      result = await api.import_version(path);
    } catch (error) {
      console.error("the import failed", error);
      result = { imported: false, error: "write_failed" };
    } finally {
      byId("comparing-title").textContent = t("comparison.loading");
    }
    if (!result.imported) {
      showView(previous);
      if (result.error) {
        dialogs.toast(t(`import.error.${result.error}`));
      }
      return;
    }
    await refreshVersions();
    await openVersion(String(result.capture_id));
    dialogs.toast(t(result.added ? "import.added" : "import.already"));
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

  // Each comparison asked for gets a number; a slower, older one never overwrites a newer one.
  let comparisonRequest = 0;

  async function openComparison(firstId, secondId) {
    const request = ++comparisonRequest;
    const previous = state.view;
    byId("comparing-title").textContent = t("comparison.loading");
    const label = (id) => state.versions.find((version) => version.capture_id === id)?.label ?? "";
    byId("comparing-meta").textContent = t("comparison.loading_meta", {
      first: label(firstId),
      second: label(secondId),
    });
    showView("comparing-view");
    let changeSet;
    try {
      changeSet = await api.compare_versions(firstId, secondId, state.filters.unreachable);
      await icons.preload(api, comparison.iconHashes(changeSet));
    } catch (error) {
      console.error("the comparison failed", error);
      if (request === comparisonRequest) {
        showView(previous === "comparing-view" ? "first-launch" : previous);
        dialogs.toast(t("comparison.failed"));
      }
      return;
    }
    if (request !== comparisonRequest) {
      return;
    }
    // The same pair again (the unreachable filter reopens it): stay on the same civ and view.
    const before = state.comparison;
    const same =
      before !== null &&
      before.oldId === changeSet.old.capture_id &&
      before.newId === changeSet.new.capture_id
        ? before
        : null;
    state.comparison = {
      oldId: changeSet.old.capture_id,
      newId: changeSet.new.capture_id,
      changeSet,
      civ: same?.civ ?? null,
      view: same?.view ?? "changes",
      treeCiv: same?.treeCiv ?? null,
      // The tree ignores unreachable units, so the trees already drawn still hold.
      trees: same?.trees ?? new Map(),
    };
    state.openId = null;
    drawComparison();
    showView("comparison-view");
    drawVersionList();
  }

  function drawComparison() {
    const current = state.comparison;
    if (current === null) {
      return;
    }
    const inTree = current.view === "tree";
    comparison.render({
      t,
      changeSet: current.changeSet,
      // The tree and the changes share one civ list (D-39): the tree shows the civ chosen last.
      civ: inTree ? current.treeCiv : current.civ,
      treeMode: inTree,
      filters: state.filters,
      onCiv: selectCiv,
      onEntity: (entity) => {
        // A civ page opens it for that civ; Overall, for the civ chosen last, if any.
        openEntity(entity.kind, Number(entity.id), current.civ ?? current.treeCiv, entity.name);
      },
      onPick: (side) => {
        const current = side === "old" ? state.comparison?.oldId : state.comparison?.newId;
        if (current !== undefined) {
          picker.open(current);
        }
      },
    });
    show(byId("comparison-page"), !inTree);
    show(byId("tree-view"), inTree);
    show(byId("comparison-export"), !inTree);
    treePanel.hide();
    const toggle = byId("comparison-tree");
    toggle.textContent = t(inTree ? "tree.back" : "tree.open");
    toggle.setAttribute("aria-pressed", String(inTree));
    if (inTree) {
      void drawTree();
    }
  }

  /**
   * Choose a civ in the list. In the tree, Overall and the Main game tab mean its first civ.
   * @param {string | null} internalName
   */
  function selectCiv(internalName) {
    const current = state.comparison;
    if (current === null) {
      return;
    }
    if (current.view === "tree") {
      const civ = internalName ?? firstCiv(current.changeSet, false);
      current.treeCiv = civ;
      current.civ = civ;
    } else {
      current.civ = internalName;
      if (internalName !== null) {
        current.treeCiv = internalName;
      }
    }
    drawComparison();
  }

  /**
   * The first civ of the Main game or the Chronicles tab.
   * @param {Record<string, any>} changeSet
   * @param {boolean} chronicles
   * @returns {string | null}
   */
  function firstCiv(changeSet, chronicles) {
    const civs = changeSet.civs ?? [];
    const found = civs.find(
      (/** @type {Record<string, any>} */ civ) => (civ.era === "antiquity") === chronicles,
    );
    return found?.internal_name ?? civs[0]?.internal_name ?? null;
  }

  function toggleTree() {
    const current = state.comparison;
    if (current === null) {
      return;
    }
    if (current.view === "tree") {
      current.view = "changes";
    } else {
      // From Overall, the civ chosen last, as the game does; else the first civ.
      current.treeCiv = current.civ ?? current.treeCiv ?? firstCiv(current.changeSet, false);
      current.view = "tree";
    }
    drawComparison();
  }

  let treeRequest = 0;
  /** @type {{comparison: unknown, key: string} | null} */
  let treeShown = null;

  async function drawTree() {
    const current = state.comparison;
    if (current === null) {
      return;
    }
    const civ = current.treeCiv;
    const filters = state.filters;
    const key = [civ, filters.details, filters.technical, filters.low].join("|");
    const container = byId("tree-view");
    const request = ++treeRequest;
    let tree = current.trees.get(key);
    if (tree === undefined) {
      clear(container);
      container.append(el("p", { class: "help", text: t("tree.loading") }));
      let answer = null;
      try {
        answer =
          civ === null
            ? null
            : await api.get_tech_tree(
                current.oldId,
                current.newId,
                civ,
                filters.details,
                filters.technical,
                filters.low,
              );
        if (answer !== null) {
          await icons.preload(api, techTree.iconHashes(answer));
        }
      } catch (error) {
        console.error("the tech tree failed", error);
        answer = null;
      }
      if (request !== treeRequest || state.comparison !== current) {
        return; // another civ or comparison was asked for meanwhile
      }
      if (answer === null) {
        dialogs.toast(t("tree.failed"));
        current.view = "changes";
        drawComparison();
        return;
      }
      tree = answer;
      current.trees.set(key, tree);
    }
    // Search and redraws that change nothing the tree shows leave it as it is.
    const shownKey = `${key}|${state.treeFit}`;
    if (
      treeShown !== null &&
      treeShown.comparison === current &&
      treeShown.key === shownKey &&
      container.querySelector(".tree__canvas") !== null
    ) {
      return;
    }
    treeShown = { comparison: current, key: shownKey };
    const civs = current.changeSet.civs ?? [];
    const named = civs.find((/** @type {Record<string, any>} */ c) => c.internal_name === civ);
    techTree.render({
      t,
      container,
      tree,
      civName: named?.name ?? civ ?? "",
      civIcon: named?.icon ?? null,
      // The age shields travel with the stat icons, and were fetched with the comparison.
      ageIcons: current.changeSet.stat_icons ?? {},
      fit: state.treeFit,
      onFit: () => {
        state.treeFit = !state.treeFit;
        void drawTree();
      },
      onNode: (node, tile, shown) => {
        if (shown) {
          treePanel.show({ t, changeSet: current.changeSet }, node, tile);
        } else {
          treePanel.hide();
        }
      },
      onOpen: (node) => {
        treePanel.hide();
        openEntity(node.kind, node.id, civ, node.name);
      },
    });
  }

  /**
   * Open the details of a unit, building or tech of the open comparison (D-49).
   * @param {string} kind
   * @param {number} id
   * @param {string | null} civ
   * @param {string} [name]
   */
  function openEntity(kind, id, civ, name) {
    const current = state.comparison;
    if (current === null || !Number.isInteger(id)) {
      return;
    }
    entityPanel.open({ oldId: current.oldId, newId: current.newId, kind, id, civ, name });
  }

  const entityPanel = initEntityPanel({
    api,
    t,
    civs: () => state.comparison?.changeSet.civs ?? [],
    statIcons: () => state.comparison?.changeSet.stat_icons ?? {},
  });

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
    // From the first-launch screen there is nothing else to show: open the progress.
    onStarted: () => {
      if (state.view === "first-launch") {
        showView("capture-view");
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
        unnamed: state.filters.unnamed,
        details: state.filters.details,
        technical: state.filters.technical,
        civs: state.comparison.civ === null ? null : [state.comparison.civ],
        prerelease: sides.some((side) => side?.prerelease === true),
        // The page on screen, for the image export.
        page: comparison.currentPage({
          t,
          changeSet: state.comparison.changeSet,
          civ: state.comparison.civ,
          filters: state.filters,
          onCiv: () => {},
          onPick: () => {},
        }),
        // "Label · build", without the build when the label already says it.
        versions: sides
          .map((side) => {
            const label = side?.label ?? "";
            const build = side?.game_build ?? "";
            return build && !label.includes(build) ? `${label} · ${build}` : label;
          })
          .join(" → "),
      };
    },
  });

  const settings = initSettings({ api, t, version: startup.app_version });
  const diagnostics = initDiagnostics({ api, t });

  initVersionList(byId("version-list"), { t });
  onClick("capture-button", () => void capture.openDialog());
  onClick("first-launch-capture", () => void capture.openDialog());
  onClick("import-button", () => void importVersion());
  onClick("first-launch-import", () => void importVersion());
  onClick("settings-button", () => void settings.open());
  onClick("diagnostics-button", () => void diagnostics.open(state.openId));
  onClick("comparison-export", () => void exporter.open());
  onClick("comparison-tree", toggleTree);
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
  for (const [id, name] of /** @type {const} */ ([
    ["filter-unnamed", "unnamed"],
    ["filter-details", "details"],
    ["filter-technical", "technical"],
  ])) {
    input(id).addEventListener("change", (event) => {
      const target = event.target;
      if (target instanceof HTMLInputElement) {
        state.filters[name] = target.checked;
        drawComparison();
      }
    });
  }
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
    // A comparison takes seconds: show the page now, with "Comparing…", not a blank window.
    document.body.dataset.ready = "";
    await openComparison(startup.last_comparison[0], startup.last_comparison[1]);
    return;
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

start().catch(async (error) => {
  console.error("Patch Scout couldn't start the page", error);
  await showStartupError(error);
});

/**
 * Say why the page couldn't start, rather than leaving the window blank.
 * @param {unknown} error
 */
async function showStartupError(error) {
  /** @type {(key: string, values?: Record<string, unknown>) => string} */
  let t = (key) => key;
  try {
    const api = await connect();
    t = createTranslator((await api.get_messages()).messages);
  } catch (lookup) {
    console.error("the messages are unavailable too", lookup);
  }
  const reason = error instanceof Error ? error.message : String(error);
  byId("startup-error-title").textContent = t("app.start_failed");
  byId("startup-error-text").textContent = t("app.start_failed_detail", { reason });
  show(byId("startup-error"), true);
  document.body.dataset.failed = "";
  document.body.dataset.ready = "";
}
