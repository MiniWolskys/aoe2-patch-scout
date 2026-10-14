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
import * as notesView from "./notes.js";
import { initDiagnostics, initExport, initPicker, initSettings } from "./panels.js";
import * as techTree from "./tree.js";
import * as treePanel from "./tree-panel.js";
import { initVersionList, render as renderVersions } from "./version-list.js";

const VIEWS = ["first-launch", "capture-view", "details-view", "comparing-view", "comparison-view"];
// An answer quicker than this (a comparison Python kept) updates the page without a status.
const UPDATING_DELAY_MS = 200;

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
   *     alone: boolean,
   *     civ: string | null, view: "changes" | "tree" | "notes", treeCiv: string | null,
   *     from: "changes" | "notes",
   *     trees: Map<string, Record<string, any>>,
   *     notes: import("./notes.js").Notes | null} | null,
   *   capture: import("./api.js").CaptureStatus | null,
   *   filters: {low: boolean, unreachable: boolean, unnamed: boolean, details: boolean,
   *     technical: boolean, search: string},
   *   view: string,
   *   listView: "changes" | "notes",
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
    // What a comparison opens on: the patch notes (D-51), or the changes once a reader chose them.
    listView: "notes",
    treeFit: false,
  };

  function showView(name) {
    state.view = name;
    for (const id of VIEWS) {
      show(byId(id), id === name);
    }
  }

  /** The version shown alone (D-52), if that is what is open. */
  function aloneId() {
    return state.comparison?.alone ? state.comparison.oldId : null;
  }

  function drawVersionList() {
    renderVersions({
      t,
      versions: state.versions,
      capture: state.capture,
      // A version alone is the open row, not a side of a comparison.
      openId: state.openId ?? aloneId(),
      comparison: state.comparison?.alone ? null : state.comparison,
      onOpen: (captureId) => void openVersion(captureId),
      onCompare: (captureId) => void compareWith(captureId),
      onDetails: (captureId) => void openDetails(captureId),
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
    drawHint();
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

  /**
   * Open a version on its own: its tech tree (D-52). It is the version compared with itself.
   * @param {string} captureId
   */
  async function openVersion(captureId) {
    await openComparison(captureId, captureId);
  }

  /**
   * Open a version's details page, from its gear button (D-52).
   * @param {string} captureId
   */
  async function openDetails(captureId) {
    state.openId = captureId;
    const back = state.comparison === null ? null : state.comparison.alone ? "tree" : "comparison";
    await detailsView.show(captureId, back);
    showView("details-view");
    drawVersionList();
  }

  /**
   * Compare a version with whatever is open: the open version, else the newest other one.
   * @param {string} captureId
   */
  async function compareWith(captureId) {
    const open = state.openId ?? aloneId();
    const other =
      open !== null && open !== captureId
        ? open
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
    cancelFilterUpdate();
    const previous = state.view;
    const label = (id) => state.versions.find((version) => version.capture_id === id)?.label ?? "";
    const alone = firstId === secondId;
    byId("comparing-title").textContent = t(alone ? "version.loading" : "comparison.loading");
    byId("comparing-meta").textContent = alone
      ? label(firstId)
      : t("comparison.loading_meta", { first: label(firstId), second: label(secondId) });
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
    // The same pair again (swapping the sides reopens it): stay on the same civ and view.
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
      alone,
      civ: same?.civ ?? null,
      // A version alone shows its tree (D-52). A comparison opens on the patch notes (D-51); a
      // reader who chose the detailed changes keeps them.
      view: alone ? "tree" : (same?.view ?? state.listView),
      // Where the tree goes back to.
      from: same?.from ?? state.listView,
      // Going from one version alone to another keeps the civ on screen.
      treeCiv:
        same?.treeCiv ??
        (alone ? ((before?.alone ? before.treeCiv : null) ?? firstCiv(changeSet, false)) : null),
      // The tree and the patch notes ignore unreachable units, so what was drawn still holds.
      trees: same?.trees ?? new Map(),
      notes: same?.notes ?? null,
    };
    state.openId = null;
    drawComparison();
    showView("comparison-view");
    drawVersionList();
  }

  // The unreachable units filter needs another comparison (diff-rules.md, Reachability): it
  // is asked for while the page stays, and the last click wins.
  let filterRequest = 0;
  let updating = false;
  /** @type {ReturnType<typeof setTimeout> | undefined} */
  let updatingTimer;

  /**
   * Say what is coming, unless the answer comes first; the changes being replaced are dimmed.
   * @param {string} message
   */
  function showUpdating(message) {
    clearTimeout(updatingTimer);
    byId("comparison-updating-text").textContent = message;
    updatingTimer = setTimeout(() => {
      updating = true;
      drawUpdating();
    }, UPDATING_DELAY_MS);
  }

  function hideUpdating() {
    clearTimeout(updatingTimer);
    updating = false;
    drawUpdating();
  }

  /** The status shows over the changes and the tree, not over the patch notes it can't affect. */
  function drawUpdating() {
    show(byId("comparison-updating"), updating && state.comparison?.view !== "notes");
    const page = byId("comparison-page");
    if (updating) {
      page.setAttribute("aria-busy", "true");
    } else {
      page.removeAttribute("aria-busy");
    }
  }

  function cancelFilterUpdate() {
    filterRequest += 1;
    hideUpdating();
  }

  /**
   * Show or hide the units a civ can't get, in place.
   * @param {boolean} wanted
   */
  async function updateUnreachable(wanted) {
    const current = state.comparison;
    if (current === null) {
      return;
    }
    const request = ++filterRequest;
    state.filters.unreachable = wanted;
    showUpdating(t(wanted ? "comparison.unreachable_adding" : "comparison.unreachable_hiding"));
    let changeSet;
    try {
      changeSet = await api.compare_versions(current.oldId, current.newId, wanted);
      await icons.preload(api, comparison.iconHashes(changeSet));
    } catch (error) {
      console.error("the comparison for the unreachable filter failed", error);
      if (request === filterRequest) {
        hideUpdating();
        state.filters.unreachable = !wanted;
        input("filter-unreachable").checked = !wanted;
        dialogs.toast(
          t(wanted ? "comparison.unreachable_add_failed" : "comparison.unreachable_hide_failed"),
        );
      }
      return;
    }
    if (request !== filterRequest || state.comparison !== current) {
      return;
    }
    hideUpdating();
    current.changeSet = changeSet;
    // The tree and the patch notes don't show these units: only the changes are drawn again.
    if (current.view === "changes") {
      drawComparison();
    }
  }

  function drawComparison() {
    const current = state.comparison;
    if (current === null) {
      return;
    }
    const inTree = current.view === "tree";
    const inNotes = current.view === "notes";
    const alone = current.alone;
    drawUpdating();
    comparison.render({
      t,
      changeSet: current.changeSet,
      // The tree and the changes share one civ list (D-39): the tree shows the civ chosen last.
      civ: inTree ? current.treeCiv : current.civ,
      treeMode: inTree,
      alone,
      // The patch notes list their own civs, once they are written.
      notesCounts: inNotes && current.notes !== null ? notesCounts(current.notes) : null,
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
    show(byId("comparison-page"), !inTree && !inNotes);
    show(byId("tree-view"), inTree);
    show(byId("notes-view"), inNotes);
    show(byId("comparison-export"), !inTree);
    // The patch notes don't follow the filters (D-51): neither the filters nor their notices show.
    show(byId("comparison-filters"), !inNotes && !alone);
    // A version alone (D-52): its name in the header, a way to compare, and nothing else.
    byId("comparison-view").toggleAttribute("data-alone", alone);
    for (const id of ["picker-old", "comparison-swap", "comparison-tree", "comparison-notes"]) {
      show(byId(id), !alone);
    }
    show(byId("version-compare"), alone);
    drawHint();
    if (inNotes || alone) {
      show(byId("filters-panel"), false);
      byId("comparison-filters").setAttribute("aria-expanded", "false");
      show(byId("comparison-notice"), false);
    }
    treePanel.hide();
    const toggle = byId("comparison-tree");
    toggle.textContent = t(
      inTree ? (current.from === "notes" ? "tree.back_notes" : "tree.back") : "tree.open",
    );
    toggle.setAttribute("aria-pressed", String(inTree));
    const notesToggle = byId("comparison-notes");
    notesToggle.textContent = t(inNotes ? "notes.back" : "notes.open");
    notesToggle.setAttribute("aria-pressed", String(inNotes));
    if (inTree) {
      void drawTree();
    }
    if (inNotes) {
      void drawNotes();
    }
  }

  /** How to compare, under a version alone: with another version, or after getting one. */
  function drawHint() {
    const hint = byId("version-hint");
    show(hint, state.comparison?.alone === true);
    hint.textContent = t(state.versions.length > 1 ? "version.hint" : "version.hint_one");
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

  /**
   * How many bullets the patch notes hold for Overall (General) and for each civ.
   * @param {import("./notes.js").Notes} notes
   * @returns {Map<string | null, number>}
   */
  function notesCounts(notes) {
    /** @type {Map<string | null, number>} */
    const counts = new Map([[null, 0]]);
    for (const section of notes.sections ?? []) {
      for (const group of section.groups ?? []) {
        const key = group.civ ?? null;
        counts.set(key, (counts.get(key) ?? 0) + (group.items ?? []).length);
      }
    }
    return counts;
  }

  function toggleNotes() {
    const current = state.comparison;
    if (current === null) {
      return;
    }
    current.view = current.view === "notes" ? "changes" : "notes";
    current.from = current.view;
    state.listView = current.view;
    drawComparison();
  }

  let notesRequest = 0;
  /** @type {unknown} */
  let notesShown = null;

  /** Draw the patch notes, asking Python once per comparison, then show the civ chosen. */
  async function drawNotes() {
    const current = state.comparison;
    if (current === null) {
      return;
    }
    const container = byId("notes-view");
    if (current.notes === null) {
      const request = ++notesRequest;
      clear(container);
      container.append(el("p", { class: "help notes__loading", text: t("notes.loading") }));
      let answer = null;
      try {
        answer = await api.get_patch_notes(current.oldId, current.newId);
      } catch (error) {
        console.error("the patch notes failed", error);
      }
      if (request !== notesRequest || state.comparison !== current) {
        return; // another comparison was opened meanwhile
      }
      if (answer === null || typeof answer !== "object") {
        dialogs.toast(t("notes.failed"));
        // Back to the changes, unless the reader has moved on (to the tree) meanwhile.
        if (current.view === "notes") {
          current.view = "changes";
          current.from = "changes";
          drawComparison();
        }
        return;
      }
      current.notes = answer;
      drawComparison(); // the civ list now follows the notes; this draws them too
      return;
    }
    if (notesShown !== current.notes) {
      notesView.render(container, current.notes);
      notesShown = current.notes;
    }
    notesView.scrollTo(container, current.civ);
  }

  function toggleTree() {
    const current = state.comparison;
    if (current === null) {
      return;
    }
    if (current.view === "tree") {
      current.view = current.from;
    } else {
      current.from = current.view;
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
        if (current.alone) {
          // A version alone has no change list to go back to: say so in place.
          clear(container);
          container.append(el("p", { class: "help", text: t("tree.failed_alone") }));
          return;
        }
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
      marks: !current.alone,
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
      if (state.versions.length === 0) {
        showView("first-launch");
      } else {
        await openVersion(state.versions[0].capture_id);
      }
    },
    onCompare: (captureId) => picker.open(captureId),
    onDiagnostics: (captureId) => void diagnostics.open(captureId),
    onBack: () => {
      state.openId = null;
      showView("comparison-view");
      drawVersionList();
    },
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
        // In the patch notes mode, the export is the patch notes (D-51).
        notes: state.comparison.view === "notes",
        notesText: state.comparison.notes?.text ?? null,
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
  onClick("diagnostics-button", () => void diagnostics.open(state.openId ?? aloneId()));
  onClick("comparison-export", () => void exporter.open());
  onClick("comparison-tree", toggleTree);
  onClick("comparison-notes", toggleNotes);
  onClick("version-compare", () => {
    const captureId = aloneId();
    if (captureId !== null) {
      picker.open(captureId);
    }
  });
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
  input("filter-unreachable").addEventListener("change", (event) => {
    const target = event.target;
    if (target instanceof HTMLInputElement) {
      void updateUnreachable(target.checked);
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
