// SPDX-License-Identifier: GPL-3.0-or-later
/** The page's only link to Python: pywebview's `window.pywebview.api` (architecture.md). */

/**
 * @typedef {object} Version
 * @property {string} capture_id
 * @property {string} label
 * @property {boolean} prerelease
 * @property {string} notes
 * @property {string} origin
 * @property {string | null} game_build
 * @property {string} captured_at
 * @property {boolean} stats_available
 * @property {string | null} stats_reason
 */

/**
 * @typedef {object} Settings
 * @property {boolean} raw_backups
 * @property {string} language
 * @property {string} data_folder
 * @property {string[]} recent_game_folders
 */

/**
 * @typedef {object} Startup
 * @property {string} language
 * @property {Record<string, string>} messages
 * @property {string} app_version
 * @property {Version[]} versions
 * @property {Settings} settings
 * @property {string[]} last_comparison
 * @property {CaptureStatus | null} capture
 */

/**
 * @typedef {object} CaptureStatus
 * @property {boolean} running
 * @property {string} label
 * @property {string} phase
 * @property {number} fraction
 * @property {string} detail
 * @property {Record<string, unknown>} result
 */

/**
 * @typedef {object} Candidate
 * @property {string} path
 * @property {string} source
 * @property {string | null} steam_build_id
 * @property {boolean} prerelease_hint
 * @property {string | null} game_build
 */

/**
 * @typedef {object} Api
 * @property {() => Promise<Startup>} get_startup
 * @property {() => Promise<Version[]>} get_versions
 * @property {(captureId: string) => Promise<Record<string, unknown>>} get_version
 * @property {(captureId: string, label?: string | null, prerelease?: boolean | null,
 *   notes?: string | null) => Promise<Version>} update_version
 * @property {(captureId: string) => Promise<{versions: Version[]}>} delete_version
 * @property {() => Promise<Candidate[]>} detect_game_folders
 * @property {() => Promise<string | null>} browse_for_folder
 * @property {(path: string) => Promise<Record<string, unknown>>} validate_game_folder
 * @property {(path: string, label: string, prerelease?: boolean,
 *   captureAnyway?: boolean) => Promise<{started: boolean, reason?: string}>} start_capture
 * @property {() => Promise<CaptureStatus | null>} get_capture_status
 * @property {() => Promise<unknown>} cancel_capture
 * @property {() => Promise<unknown>} clear_capture
 * @property {(oldId: string, newId: string,
 *   showUnreachable?: boolean) => Promise<Record<string, any>>} compare_versions
 * @property {(hashes: string[]) => Promise<Record<string, string>>} get_icons
 * @property {(oldId: string, newId: string, lowPriority?: boolean,
 *   civs?: string[] | null) => Promise<{text: string}>} export_text
 * @property {(oldId: string, newId: string, kind?: string, lowPriority?: boolean,
 *   civs?: string[] | null) => Promise<{saved: boolean, path?: string}>} save_export
 * @property {() => Promise<Settings>} get_settings
 * @property {(rawBackups?: boolean | null) => Promise<Settings>} update_settings
 * @property {() => Promise<{removed: number}>} purge_backups
 * @property {(captureId?: string | null) => Promise<Record<string, any>>} get_diagnostics
 * @property {(captureId: string, section: string, key?: string) => Promise<unknown>}
 *   get_snapshot_section
 */

/**
 * Wait until pywebview has injected the Python API.
 * @returns {Promise<Api>}
 */
export function connect() {
  if (typeof window.pywebview?.api?.get_startup === "function") {
    return Promise.resolve(window.pywebview.api);
  }
  return new Promise((resolve) => {
    window.addEventListener("pywebviewready", () => resolve(window.pywebview.api), {
      once: true,
    });
  });
}
