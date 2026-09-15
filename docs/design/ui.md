# User interface

**Status: draft v1, 2026-09-15.** Follows D-32 to D-35 in [decisions.md](../decisions.md). The theme tokens are in the app's stylesheet, [theme.css](../../src/patch_scout/gui/web/styles/theme.css).

The screens were designed in three rounds of mockups with sample data. The mockups aren't in the repository.

## Principles

- **One window.** The comparison is the main output and must be good enough to show on stream (P-13).
- **The game icons bring the colour.** The interface is a quiet dark theme so painted icons don't clash with it.
- **Red means old, green means new**, and nothing else uses them (D-34).
- **Colour is never the only signal.** Every control can be reached with the keyboard ([CONTRIBUTING.md](../../CONTRIBUTING.md#frontend-html-css-javascript)).
- **No text in CSS or images.** Every label comes from the i18n catalog (P-20), and layouts leave room for longer translations.

## Window layout

```
┌──────────────────────┬───────────────────────────────────────────────┐
│ Patch Scout      [◧] │  Main area, depending on the selection:       │
│ [Capture new version]│   • no versions      → first launch           │
│ [Import]             │   • a version open   → version details        │
│──────────────────────│   • a capture open   → capture progress       │
│ VERSIONS           4 │   • two versions     → comparison             │
│ ◌ PUP October   64%  │                                               │
│ ● PUP September  NEW │                                               │
│ ● Live           OLD │                                               │
│   Baseline August    │                                               │
│──────────────────────│                                               │
│ Diagnostics Settings │                                               │
└──────────────────────┴───────────────────────────────────────────────┘
```

- **Version list:** 280px wide; it collapses to a 64px strip holding Capture, Import, Diagnostics and Settings.
- **The main area** fills the rest of the window.
- **Window size** (D-42): 1440×900, centred on the primary screen when it's at least 1440×980; maximized otherwise; minimum 1120×640.

## Behaviour

### Version list

- **Order:** newest game build first.
- **Row:** label, then `build · capture date`. On the right:
  - a flag for pre-release versions;
  - a warning icon for versions without stats;
  - the OLD or NEW tag when the version is in the comparison.

  Both icons have a tooltip.
- **Row states:**

  | State | Look |
  |---|---|
  | Default | Panel background |
  | Hover | Hover background. The **Compare** button replaces the icons and tags, so the name and build keep their room |
  | Open (details) | Selected background with a strong border |
  | In the comparison | Selected background, OLD or NEW tag |
  | Capturing | Label, "Capturing · 64%", a progress ring and a thin progress bar along the bottom |

### Opening and comparing (D-32)

| Action | Result |
|---|---|
| Click a version | Its details open. If a comparison was open, the details show a link back to it. |
| Hover another version, click **Compare** | That version is compared with the open one. |
| Ctrl+click another version | Same as Compare. |
| **Compare with…** in the details | Pick a version, then compare. This is the keyboard route. |
| A picker in the comparison header | Changes that side. |
| Swap | Exchanges old and new. |

- **Old and new are assigned automatically:** the lower game build is old; for the same build, the earlier capture is old.
- **On launch:** the last comparison reopens.

### Capture

1. **Capture new version** opens the capture dialog:
   - the game folder, detected and validated ([architecture.md](architecture.md#finding-the-game-d-19));
   - the label;
   - the pre-release tickbox, prefilled from Steam when possible (P-23);
   - the reminder to capture the live build before switching Steam to PUP.
2. **Start capture** closes the dialog. The capture appears as a row at the top of the list. **Capture new version** is disabled until it finishes; the rest of the app stays usable.
3. **Opening that row** shows the progress view: a progress bar and the steps.

   | Step | Detail shown |
   |---|---|
   | Game folder | Build number |
   | Fingerprints | |
   | Civs, tech trees and texts | |
   | Unit and tech stats | Current gate, e.g. "VER 9.0 read as VER 8.9 · round trip passed" |
   | Icons | |
   | Backup | |
   | Save | |

   Done steps show a neutral check, the running step an accent ring, and pending steps a hollow circle. **Cancel** stops the capture.
4. **When it finishes,** the new version opens compared with the previous newest version.
5. **If every input matches an existing snapshot** (P-05), the capture stops early. The message names that snapshot and offers to capture anyway.

### Import

**Import** takes the baseline pack (P-21) and snapshot archives. An imported version is added to the list and opened.

### First launch

- **With no versions,** the main area explains that a comparison needs two versions and offers two cards: **Capture your game** and **Import a version** (a baseline pack or an exported version).
- **A warning line** reminds users to capture the live build before switching Steam to a preview build.
- **With one version,** its details show, with a hint that comparing needs a second version.

### Version details

- **Title:** the label (click to rename, P-14), then build and capture date.
- **Actions:** **Compare with…**, **Export version** (snapshot archive), **Delete** (asks for confirmation).
- **Fields:**
  - source (captured from a folder, imported, or baseline pack);
  - game data status, with a link to Diagnostics;
  - the pre-release tickbox and its help text;
  - notes.

### Comparison

- **Header:** the old and new pickers (legend dot, OLD/NEW label, version name, build, pre-release badge), swap, and **Export report** (P-13).
- **Notice bar:** it shows when stats weren't compared, a layout was substituted, or there are unusually many changes. The text is truncated on one line, and a link opens Diagnostics.
- **Civ list** (236px, D-33):
  - **Overall** comes first, with its change count;
  - then each civ with changes, with its emblem and count;
  - a civ added in the new build shows a **NEW** tag instead of a count;
  - the Chronicles civs are kept apart from the base civs (D-38); how is open question 9.
- **Page title:** the civ, or "Overall". "Overall" has the subtitle "Changes to every civilization, with exceptions noted". A legend on the right names the old and new versions.
- **Change row:**

  | Column | Content |
  |---|---|
  | Icon | Game icon, 40px, framed |
  | Entity | Name, plus kind and where it's made, e.g. "Unit · Stable" |
  | Field | Stat icon and label |
  | Values | Old value, arrow, new value. The arrows line up down the list. |
  | Note | Exceptions as civ chips, e.g. "Except Franks, Persians" |

  A text change replaces the values and note columns with a word diff: removed words struck through in red, added words in green.

### Diagnostics and Settings

- **Diagnostics** opens its own window ([architecture.md](architecture.md#gui-v1-d-15)).
- **Settings** covers the data folder, raw backups and recent game folders (P-10, P-19).

## Open questions

1. **Civ bonuses and unit stats (D-20) in the civ-navigated comparison.** Where do a civ's bonus text, effect sentences and the unit stats view go?
2. **Categories inside a civ's page.** Are entries grouped by category (diff-rules.md) or listed as one list?
3. **Changes shared by a few civs** (not "all except"): do they appear under each of those civs, in Overall, or both?
4. **Civ list order:** alphabetical (easier to scan) or `civilizations.json` order (the change set's order)?
5. **Filters and search:** low-priority categories, unreachable units, all fields. Where do they go?
6. **PNG export of a selected section:** how is a section selected?
7. **Collapsed list during a capture:** show progress on the Capture button.
8. ~~Minimum window size~~ **Decided in D-42:** 1440×900 when the screen has room, maximized otherwise; minimum 1120×640.
9. **Chronicles civs (D-38):**
   - Do they get their own group at the end of the civ list, or sit behind a filter?
   - Does "all civs" in Overall count them, or would every base-civ change read "all civs except" the six Chronicles civs?

## Theme: Forge (D-35)

### Colours

| Token | Hex | Use |
|---|---|---|
| `bg-app` | `#0e0c0a` | Collapsed strip, icon frame gap |
| `bg-inset` | `#0c0a08` | Inputs, progress tracks |
| `bg-base` | `#15120f` | Main content |
| `bg-panel` | `#1a1612` | Version list, civ list |
| `bg-hover` | `#1e1a15` | Row hover |
| `bg-raised` | `#221d18` | Pickers, dialogs, cards, chips |
| `bg-selected` | `#2b241c` | Open or selected item |
| `line-subtle` | `#241f19` | Row dividers, panel borders |
| `line` | `#342c23` | Control borders |
| `line-strong` | `#51432f` | Emphasis borders, icon frames |
| `text` | `#ece3d3` | Primary text |
| `text-2` | `#aa9e8a` | Secondary text, metadata, success checks |
| `text-3` | `#8a7f6d` | Hints, placeholders, pending steps, checkbox outline |
| `text-on-accent` | `#1a140c` | Text on accent buttons |
| `accent` | `#c9a45c` | Primary buttons, ticked checkboxes, progress |
| `accent-hover` | `#dcb974` | Accent and link hover |
| `accent-soft` | `#2d2518` | Tint behind selected items |
| `accent-text` | `#d8b36b` | Links, active labels |
| `old` | `#e35b50` | Old value, removed, OLD tag |
| `old-soft` | `#2c1a16` | Behind removed words and the OLD tag |
| `new` | `#92dcaa` | New value, added, NEW tag and badge |
| `new-soft` | `#1b2a20` | Behind added words and the NEW tag |
| `info` | `#8fb0c9` | Notices |
| `warn` | `#f0a03e` | Warnings, pre-release |
| `warn-soft` | `#35291a` | Behind warning and pre-release badges |
| `focus` | `#f1d493` | Keyboard focus ring |

**Overlays:**

| Use | Value |
|---|---|
| Dialog scrim | `rgb(6 5 4 / 64%)` |
| Dialog shadow | `0 24px 60px rgb(0 0 0 / 60%)` |
| Floating bar shadow | `0 16px 36px rgb(0 0 0 / 50%)` |

### Colour rules

- **`old` and `new` are reserved** for:
  - old and new values;
  - removed and added text;
  - the OLD/NEW tags and legend dots;
  - the NEW civ badge.
- **Success is a neutral check** (`text-2`), never green.
- **Warnings and pre-release are orange** (`warn`), with an icon. **Notices are steel blue** (`info`).
- **The brass accent** is for primary actions, selection and progress. It isn't a status colour.
- **Game art gets a quiet frame:**
  - square, 2px radius;
  - a 1px `bg-app` gap, then a 1px `line-strong` ring;
  - no rounded corners, shadows or glows.
- **Interface icons** come from Lucide (D-43), drawn in the text colour of their control.

### Contrast

WCAG 2 contrast ratios. Body text needs 4.5:1; large text and UI components need 3:1.

| Text token | On `bg-base` | On `bg-panel` | On `bg-raised` |
|---|---|---|---|
| `text` | 14.7 | 14.1 | 13.1 |
| `text-2` | 7.1 | 6.8 | 6.3 |
| `text-3` | 4.7 | 4.6 | 4.2 |
| `accent-text` | 9.4 | 9.1 | 8.4 |
| `old` | 5.2 | 5.0 | 4.7 |
| `new` | 11.6 | 11.2 | 10.4 |
| `info` | 8.2 | 7.9 | 7.3 |
| `warn` | 8.7 | 8.4 | 7.8 |
| `focus` | 13.0 | 12.5 | 11.6 |

- **Pairs:**
  - `text-on-accent` on `accent`: 7.8;
  - `old` on `old-soft`: 4.6;
  - `new` on `new-soft`: 9.3;
  - `warn` on `warn-soft`: 6.6.
- **Small text on `bg-raised`** (dialogs, pickers) uses `text-2`, not `text-3`, because `text-3` is only 4.2 there.
- **`line-strong` is decorative** (1.9:1). Control outlines that must be seen, such as an unticked checkbox, use `text-3` (4.7:1).

### Colour blindness

**Old is darker than new,** so the two still differ in lightness when red and green can't be told apart.

| Vision | Contrast between `old` and `new` |
|---|---|
| Typical | 2.2:1 |
| Deuteranopia | 1.9:1 |
| Protanopia | 3.0:1 |

- Simulated with Machado et al. (2009) at full severity.
- Position (old first, then an arrow) and strikethrough carry the same information without colour.

### Typography

| Role | Font | Notes |
|---|---|---|
| Interface | **Barlow Semi Condensed** 400, 500, 600, 700 | Condensed, so dense rows stay readable |
| Section labels | **Marcellus SC** | Small caps with 0.07em letter spacing; labels only, never body text |
| Raw commands, paths | Cascadia Mono, then Consolas | System fonts, not bundled |

- **Licence:** both fonts are under the SIL Open Font License 1.1 (checked 2026-09-15). They're bundled in `gui/web/vendor/fonts/` with their `OFL.txt`, because the app has no network access (D-02), and listed in `THIRD_PARTY_NOTICES`.
- **Numbers** use tabular figures (`.num`) wherever they line up.

| Token | Size | Use |
|---|---|---|
| `fs-display` | 38px | First-launch headline |
| `fs-title` | 34px | Version details, capture progress |
| `fs-section` | 28px | Comparison page title |
| `fs-dialog` | 24px | Dialog title |
| `fs-lg` | 17px | Old and new values, version names in the header |
| `fs-md` | 16px | Body, list rows |
| `fs-sm` | 15px | Secondary text, buttons |
| `fs-xs` | 13.5px | Metadata, help text |
| `fs-label` | 12px | Small-caps labels |
| `fs-tag` | 11.5px | OLD/NEW tags |

### Shape and sizes

| Token | Value | Use |
|---|---|---|
| `radius-icon` | 2px | Game icons |
| `radius-tag` | 3px | Tags, badges, chips, checkboxes |
| `radius-control` | 4px | Buttons, inputs, rows |
| `radius-card` | 6px | Cards |
| `radius-dialog` | 8px | Dialogs |
| `control-height` / `control-height-sm` | 38px / 28px | Buttons |
| `input-height` | 40px | Text inputs |
| `game-icon-size` | 40px | Icons in change rows (88px in a unit header) |
| `sidebar-width` / `sidebar-collapsed-width` | 280px / 64px | Version list |
| `civ-list-width` | 236px | Civ list |
| `header-height` | 74px | Comparison header |
| `notice-height` | 40px | Notice bar |
| `dialog-width` | 600px | Capture dialog |

### Components in theme.css

| Class | Component |
|---|---|
| `.button`, `--accent`, `--ghost`, `--small`, `:disabled` | Buttons |
| `.input`, `.checkbox` | Form controls |
| `.tag--old`, `.tag--new`, `.badge-prerelease` | Tags and badges |
| `.value-old`, `.value-new`, `del`, `ins` | Values and text diffs |
| `.game-icon` | Framed game icon |
| `.version-list` (`[data-collapsed]`), `.version-row` (`:hover`, `[data-side]`, `[aria-current="true"]`) | Version list |
| `.comparison-header`, `.version-picker`, `.legend-dot`, `.notice` | Comparison header |
| `.civ-list`, `.civ-row` | Civ list |
| `.change-row`, `.change-values` | Change list |
| `.progress`, `.step` (`[data-state]`) | Capture progress |
| `.scrim`, `.dialog` | Dialogs |
