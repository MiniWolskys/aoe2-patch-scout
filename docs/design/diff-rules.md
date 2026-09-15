# Diff rules

**Status: draft v2, 2026-09-15.** This page defines what counts as a change, how changes are grouped and how they're presented. Any change to these rules is a behaviour change: it needs a golden-test update and a note in the PR.

## Inputs and preconditions

**Signature:** `diff(old: Snapshot, new: Snapshot, rules: RuleSet) -> ChangeSet`. It is pure: no I/O, and the output is deterministic.

**Preconditions:**
1. Both snapshots are migrated in memory to the current schema (P-15).
2. **Stats sections** (`stats.*`) are compared only if **both** snapshots have `flags.stats_available = true`. Otherwise the change set carries a `stats_not_compared` notice naming the snapshot(s) and reasons.
3. If either snapshot has `flags.format_verified = false`, the change set carries a mild `layout_substituted` notice. Example: *"The new build's data format is labelled VER 9.0, which this version of the tool doesn't know yet. It was read with the VER 8.9 layout and passed all checks."*
4. If `sources` fingerprints are equal on both sides, the result is "identical" and nothing else is computed.

## Identity (P-07)

| Entity | Matched by |
|---|---|
| Civ | `internal_name` |
| Tech tree node | (civ `internal_name`, `use_type`, `node_id`) |
| Building offer | (civ `internal_name`, building `ID`) |
| Unit, tech, effect (stats) | numeric ID |
| String | key |
| Icon | the entity that references it |

An entity present only in the new snapshot is **Added**, one present only in the old is **Removed**. The same ID with a different internal name is **Renamed**, and its other changes are still reported.

## Change kinds

| Kind | Example |
|---|---|
| `added` / `removed` | New civ; unit removed from the game |
| `availability` | Tech tree node status `NotAvailable` → `ResearchedCompleted` for a civ |
| `modified` | Field value changed |
| `renamed` | Internal name or display name changed under the same ID |
| `text_changed` | String text changed |
| `icon_redrawn` | Same entity, same `picture_index`, different hash |
| `icon_remapped` | Same entity, different `picture_index` |

## Categories and default priority

Shown in this order. Categories marked *low* are collapsed by default.

1. **Civilizations:** civs added or removed; era changes.
2. **Civ availability:** per-civ tech tree changes (units, techs, buildings gained or lost, node status changes); building offer changes.
3. **Civ and team bonuses:**
   - The civ's bonus **text** diff (the game's own words).
   - Changed bonus **effects** as sentences (see Effects).
   - `civ_dat.resources` changes, such as starting resources.
4. **Unit stats:** allowlisted fields of the raw unit records, collapsed per civ.
5. **Techs:** cost, research time, required techs, research location, effect ID; the effect's commands as sentences.
6. **Other effects:** effect command changes not covered by 3 or 5.
7. **Text** *(low)*: name and help text changes for entities not already reported above. Help text changes are attached to the entity's entry when it has one.
8. **Icons** *(low)*: `icon_redrawn`, `icon_remapped`.
9. **Other fields** *(hidden by default)*: differences in non-allowlisted fields. Available through "show all fields", mainly to find missing allowlist entries.

## Unit fields allowlist (D-08)

The allowlist names **stat concepts**. The mapping to snapshot field paths is filled in during M2 from the pinned genieutils-py source, not from memory.

| Concept | Notes |
|---|---|
| Hit points | |
| Line of sight | |
| Movement speed | |
| Attack values | Per armour class; report as class → amount, with class names |
| Armour values | Per armour class, including displayed melee/pierce |
| Range (min / max), displayed range | |
| Reload time | Attack speed |
| Accuracy percent | |
| Blast radius / blast attack level | |
| Frame delay | Attack delay |
| Projectile unit / count / charging fields | |
| Cost | Per resource |
| Train time | |
| Garrison capacity / garrison type | |
| Work rate | Villagers, monks, trade |
| Unit class, trainable location, button | Report changes; usually signals a redesign |
| Charge / special ability fields (DE) | e.g. charge attack, charge regen |

Every allowlist change goes through a PR that adds a fixture case showing the field.

## Reachability (D-37)

For each civ, the diff reports only the units that civ can actually get. Reachability is computed at diff time from both snapshots; captures always keep every unit (P-03).

1. **Seeds:** the unit and building IDs of the civ's tech tree nodes and building offers, in either snapshot.
2. **Linked forms.** From every reachable unit, follow these links, and repeat until no unit is added:
   - `Building.transform_unit`: the other form of a transforming unit, e.g. Trebuchet ↔ Trebuchet (Packed);
   - `Unit.blood_unit_id`, only when the target's `language_dll_name` resolves to a string, e.g. Konnik → Konnik (Dismounted).
3. **Projectiles aren't units in the report.** They are linked through `Type50.projectile_unit_id`, `Creatable.secondary_projectile_unit` and `Creatable.charge_projectile_unit`. A change to a projectile's allowlisted fields is shown on the entry of each reachable unit that fires it.
4. **Not followed:**
   - `Unit.dead_unit_id` (corpses, rubble);
   - `DeadFish.tracking_unit`;
   - `Bird.drop_sites`;
   - `Building.annexes` and `Building.head_unit`;
   - `Building.stack_unit_id`;
   - the reverse of `Creatable.train_locations`, i.e. the units trained at a reachable building.
5. **Open:** links through unit tasks (`Bird.tasks`), such as the Spartan Polemarch variants reached from the Hippeus. Until this is decided, those units count as unreachable.

**Field names** are those of genieutils-py 0.1.2 ([genieutils-py.md](../reference/genieutils-py.md#where-things-are-verified-012)). Snapshot field names start out as these ([snapshot-format.md](snapshot-format.md)).

**Unreachable units** are shown only when "show unreachable" is on.

## Per-civ collapsing (D-07)

For each unit ID and allowlisted field of the raw unit records:

1. **Scope.** Consider the civs where the unit exists in either snapshot and is **reachable** (see [Reachability](#reachability-d-37)). Unreachable civ copies are ignored unless "show unreachable" is on.
2. **Values.** Compute each civ's old and new value.
3. **Changed civs.** Collect every civ where old ≠ new.
4. **Grouping.** Group the changed civs by the (old, new) value pair.
5. **Wording** (English catalog shown; the GUI may render groups as badges):

| Situation | Output |
|---|---|
| Changed in every in-scope civ, one value pair | `Knight — HP 100 → 110 (all civs)` |
| One value pair, most civs but not all | `Knight — HP 100 → 110 (all civs except Franks, Persians)` |
| One value pair, few civs | `Knight — HP 120 → 130 (Franks)` |
| Several value pairs | One line per group, largest group first |

**Thresholds:**
- Name at most 8 civs in a list.
- Use the "all civs except" form when listing the exceptions is shorter than listing the changed civs.

**Civ-specific changes go first.** A change limited to some civs usually means a civ bonus changed, so within a category those lines come before "all civs" lines.

## Effects (O-5)

Every changed effect command is shown in up to three layers, most readable first:

1. **The game's own text.** If the civ's bonus text, or the tech's help text, changed: a word-level diff of it.
2. **A generated sentence.** For command types that have a template: a sentence built from the command, with unit, class, resource, tech and attribute names resolved.
   - Examples (illustrative): `Cavalry — hit points ×1.20 → ×1.15`, `Enables unit: Elite Konnik`, `Loom — food cost −50`.
   - Templates live in the i18n catalog.
3. **The raw command.** Always available in an expanded view, and the only form for command types without a template, e.g. (illustrative) `effect 527 "C-Bonus, Cavalry +20% HP" · command 3 · type 5 · a=-1 b=12 c=0 · d=1.2 → 1.15`.

**Mapping tables** (command type numbers, attribute IDs, unit class IDs → names) are built in M3 from genieutils-py and Advanced Genie Editor, never from memory. A command type without a template is not an error; it falls back to layer 3. The effect's own name from the `.dat` is shown when present (how descriptive those names are is checked in M0).

**Commands are compared as ordered lists.** Each added, removed or changed command gets its own entry.

## Civ bonuses are not applied to units (P-17)

Snapshots store raw data only (D-20), and v1 **never applies civ bonus effects to unit stats**. Bonuses can depend on age, researched techs and unit class, so a single "effective" number would be misleading and would add a lot of complexity.

Instead, as in the game itself, the app shows:
- **civ bonuses** as their own list: the bonus text and the effect sentences (see Effects);
- **units** with their raw stats.

Showing how a civ's bonuses affect a unit may come later as a separate feature ([roadmap.md](../roadmap.md), "Later").

## Change-volume check

**Trigger:** more than **20 %** of the compared allowlisted unit field values changed between the two snapshots. The threshold is to be tuned against real patches.

**Effect:** the change set carries an `unusually_many_changes` warning, pointing to the Diagnostics window.

**Why:** a misread `.dat` that still passed the gates would most likely show up as mass changes. A genuinely large patch can trigger the warning too; it prompts a double-check and never blocks anything.

## Values and formatting

- **Comparison** is exact on stored values. Floats come from the file's float32 values, so the same bits always give the same Python float.
- **Display:**
  - Show the shortest decimal form that tells old and new apart: `2.0 → 1.9`, not `2 → 2`.
  - Resources and armour classes are shown by name.
  - Unknown IDs are shown as `#<id>`.
- **Lists** (e.g. attack entries):
  - Keyed by class when the entries have one: added, removed and changed classes are reported separately.
  - Otherwise compared by position.
- **Language:** every label, sentence and civ-list phrase comes from the i18n catalog. Game names come from `strings.tables[<lang>]`, falling back to `en` (O-3).

## Strings

- The full tables are compared (P-04).
- When a changed string is referenced by a reported entity (its name, help text or bonus text), the change is attached to that entity.
- Other changed strings go to the low-priority **Text** category. Pure whitespace changes are still reported, but marked as such.
- Rich-text tags are shown literally in raw views and rendered in the formatted view.

## Determinism and ordering

- Within a category, entries are sorted by: civ-specific before global (where applicable), then display name, then ID.
- Civ lists are sorted in `civilizations.json` order.
- The same pair of snapshots always gives a byte-identical change set (JSON) and plain-text export; golden tests depend on it.

## Presentation and exports (P-13)

The **comparison** in the app is the main output: icons, navigation by civilization (D-33), filters, expandable raw details. Red marks old values and green new ones (D-34); see [ui.md](ui.md). Exports render the same `ChangeSet`, filtered as currently shown on screen:

| Export | Use | Notes |
|---|---|---|
| **Plain text** | Video descriptions, chat, forums | Unicode bullets and indentation, no markup. Copy to clipboard or save as `.txt`. Filters let users fit length limits. |
| **HTML** | Sharing, archiving, showing on stream | One self-contained file: icons as data URIs, inline CSS. |
| **Image (PNG)** | Putting a section on screen in a video | The current view or a selected section, rendered by the frontend. |

There is no Markdown export.

Every export starts with a header (snapshot labels, game builds, capture dates, pre-release marks, tool version) and any notices: stats not compared, layout substituted, unusually many changes. The HTML export ends with the Microsoft notice ([legal.md](../legal.md)).
