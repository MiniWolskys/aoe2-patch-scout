# Diff rules

**Status: draft v2, 2026-09-15.** This page defines what counts as a change, how changes are grouped and how they're presented. Any change to these rules is a behaviour change: it needs a golden-test update and a note in the PR.

## Inputs and preconditions

**Signature:** `diff(old: Snapshot, new: Snapshot, rules: RuleSet) -> ChangeSet`. It is pure: no I/O, and the output is deterministic.

**Preconditions:**
1. Both snapshots are migrated in memory to the current schema (P-15).
2. **Stats sections** (`stats.*`) are compared only if **both** snapshots have `flags.stats_available = true`. Otherwise the change set carries a `stats_not_compared` notice naming the snapshot(s) and reasons.
3. If either snapshot has `flags.format_verified = false`, the change set carries a mild `layout_substituted` notice. Example: *"The new build's data format is labelled VER 9.0, which this version of the tool doesn't know yet. It was read with the VER 8.9 layout and passed all checks."*
4. If `sources` fingerprints are equal on both sides, the result is "identical" and no change is computed. It still lists every civ with a tech tree and the stat icons, which the tech tree needs: a version on its own is the version compared with itself (D-52).

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
   - The game's tech trees and offer lists also list what a civ **can't** get (`NotAvailable`). A node that appears or disappears as `NotAvailable` is not gained or lost, and an offered item whose node is `NotAvailable` for that civ is left out of the offer comparison. *Seen on build 101.103.54800.0: Cranequins is in 15 civs' trees but available to 6, and in the Italians' Archery Range offers.*
   - Offered items are matched by ID and shown by name: the civ's tech tree label, else the offer list's own name.
   - **Who gained or lost a node** is measured against every civ in the comparison, not against the civs whose tree lists it: those include civs that list it as `NotAvailable`. A unit ten civs gained reads with those ten civs named, and shows on their pages. *Before 2026-10-10 it read "(all 15 civilizations that have it, except Vikings, …)" for Mounted Crossbowman.*
   - **Statuses read in words:** `ResearchedCompleted` is "Available", `ResearchRequired` "Needs a prerequisite", `NotAvailable` "Not available" (catalog `status.*`). The change set keeps the game's values; every renderer, the app included, shows the words.
3. **Civ and team bonuses:**
   - The civ's bonus **text** diff (the game's own words).
   - Changed bonus **effects** as sentences (see Effects).
   - `civ_dat.resources` changes, such as starting resources.
4. **Unit stats:** allowlisted fields of the raw unit records, collapsed per civ.
5. **Techs:** cost, research time, required techs, research location, effect ID; the effect's commands as sentences. An effect ID change is reported once, with the effect's commands. A tech that gains an effect it didn't have lists every command as new, and one that loses its effect lists every command as gone (Cranequins on 101.103.54800.0 went from no effect to +1 range and +2 vs Infantry, and only the ID said so).
6. **Other effects:** effect command changes not covered by 3 or 5, and **scripted effects**: each numbered function of `Effects.xs` whose code changed, appeared or disappeared is one line named by its title ("Effect of Atheism for Huns · Script changed"). The game's code is never copied into the report. Snapshots captured before scripts were kept compare nothing here.
7. **Text** *(low)*: name and help text changes for entities not already reported above. Help text changes are attached to the entity's entry when it has one. **A tech tree node's new name** is not low priority: it is a `renamed` change in Civ availability, with the old and new names ("Longship · Name · Longboat → Longship"; missed on 101.103.54800.0).
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
| Train time | A building's time at its builder reads **Build time** (a unit record of type 80; "Fortified Church train time at Builder" on 101.103.54800.0) |
| Garrison capacity / garrison type | |
| Work rate | Villagers, monks, trade |
| Unit class, trainable location, button | Report changes; usually signals a redesign |
| Charge / special ability fields (DE) | e.g. charge attack, charge regen |

Every allowlist change goes through a PR that adds a fixture case showing the field.

## Attack and armour classes (D-50)

A unit's attacks and armours are lists of classes with an amount. They are worded the way players say them:

| Class | Armour | Attack |
|---|---|---|
| Melee or Pierce | `Melee armour: -2` | `Pierce attack: 6` |
| Any other | `Archers armour class: 0` | `Bonus vs Shock Infantry: 3` |

- **Basic classes** are recognised by their `Constants.xs` names (`Melee`, `Pierce`), not by number. A class the constants don't name keeps its number: `#31 armour class`.
- **Unit stats, effect sentences and the details drawer** all use this wording, including projectiles (`Projectile: Pierce attack`).
- **Every armour class is shown,** even one that looks unused. Class 31, unnamed and on most units, has no unit attacking it on 101.103.54800.0, but the Achaemenids' Sagaris (Chronicles) gives cavalry +2 against it. Hiding classes risks losing information.
- **The details drawer shows each value once.** The game also stores a displayed attack and displayed melee and pierce armour, the numbers its interface shows. The drawer lists the Melee and Pierce classes first, with the stat icons, and lists a displayed value only when it differs from its class in either version, as "Displayed melee armour" and the like. The comparison already ranks a displayed value that moved like its class as a detail ([Levels](#levels-d-46)).

## Reachability (D-37)

For each civ, the diff reports only the units that civ can actually get. Reachability is computed at diff time from both snapshots; captures always keep every unit (P-03).

1. **Seeds:** the unit and building IDs of the civ's tech tree nodes and building offers, in either snapshot, **except what the civ's tree marks `NotAvailable`**: trees and offers also list what a civ can't get. *Before 2026-10-10 those counted, so the new Heavy Mounted Crossbowman read "all 15 civilizations that have it" on 101.103.54800.0, though only 10 can get it, and a ram's change read "all civilizations" for civs without rams.*
2. **Linked forms.** From every reachable unit, follow these links, and repeat until no unit is added:
   - `Building.transform_unit`: the other form of a transforming unit, e.g. Trebuchet ↔ Trebuchet (Packed);
   - `Unit.blood_unit_id`, only when the target's `language_dll_name` resolves to a string, e.g. Konnik → Konnik (Dismounted).
   - `Bird.task_swap_group`: every unit in the same group (other than 0), the forms the game swaps a unit into by its task, e.g. Villager → Gold Miner, Forager, Builder; Fishing Ship → Oystering Ship (maintainer, 2026-10-12). *Before, a change to the Gold Miner was hidden, and the Malians' bonus "no longer affects Gold Miner" was too.*
3. **Projectiles aren't units in the report.** They are linked through `Type50.projectile_unit_id`, `Creatable.secondary_projectile_unit` and `Creatable.charge_projectile_unit`. A change to a projectile's allowlisted fields is shown on the entry of each reachable unit that fires it, labelled `Projectile: <field>` (e.g. `Arbalester · Projectile: Pierce attack · 6 → 7`), with the civs where that unit fires it.
4. **Not followed:**
   - `Unit.dead_unit_id` (corpses, rubble);
   - `DeadFish.tracking_unit`;
   - `Bird.drop_sites`;
   - `Building.annexes` and `Building.head_unit`;
   - `Building.stack_unit_id`;
   - the reverse of `Creatable.train_locations`, i.e. the units trained at a reachable building;
   - object swaps from `objreplacement.json`. The replacements that matter (Port, Mule Cart, Settlement) are already tech tree nodes of their civs. The female Villager and the Town Center replacement (444) are variants present in every civ, and aren't reported on their own;
   - unit tasks (`Bird.tasks`). Their links to other units (task type 155) point to the units an ability affects, e.g. Centurion → infantry or Monaspa → Knights, not to unit forms (inferred from the targets).
5. **Open:** how the Spartan Polemarch variants become reachable. They should count for the Spartans (D-37), but none of the followed links leads to them. Until their source is found (M3), they count as unreachable.

**Field names** are those of genieutils-py 0.1.2 ([genieutils-py.md](../reference/genieutils-py.md#where-things-are-verified-012)). Snapshot field names start out as these ([snapshot-format.md](snapshot-format.md)).

**Unreachable units** are shown only when "show unreachable" is on.

## Per-civ collapsing (D-07)

Collapsing is applied to **every per-civ change**, not only unit stats: a tech tree node's availability, its name and help text, and its icon all go through it. A help text that changed for every civ then reads as one line instead of fifty-nine.

For each unit ID and allowlisted field of the raw unit records:

1. **Scope.** Consider the civs where the unit exists in either snapshot and is **reachable** (see [Reachability](#reachability-d-37)). Unreachable civ copies are ignored unless "show unreachable" is on.
   - **Civs only one build has** (a civ added or removed) are left out when the entity exists in both builds: they have no value to compare on one side. Otherwise every shared unit would read "added" for a new civ, and split each real change into two groups. A brand-new entity keeps them. The same rule applies to tech tree nodes.
2. **Values.** Compute each civ's old and new value.
3. **Changed civs.** Collect every civ where old ≠ new.
4. **Grouping.** Group the changed civs by the (old, new) value pair.
5. **Wording** (English catalog shown; the GUI may render groups as badges):

"All civilizations" is measured against **every civ in the comparison** (the civs with a tech tree in either build), never against the in-scope civs alone. Otherwise an entity only the Franks have would read "(all civilizations)".

| Situation | Output |
|---|---|
| One value pair, every civ in the comparison is in scope and changed | `Knight — HP 100 → 110 (all civilizations)` |
| One value pair, every civ in scope, most changed | `Knight — HP 100 → 110 (all civilizations except Franks, Persians)` |
| One value pair, at most 8 civs in scope, all changed | `Throwing Axeman — LOS 5 → 7 (Franks)` |
| One value pair, more than 8 civs in scope (not all), all changed | `Onager — attack 50 → 55 (all 45 civilizations that have it)` |
| One value pair, more than 8 civs in scope (not all), most changed | `(all 45 civilizations that have it, except Goths)` |
| One value pair, few civs changed | `Knight — HP 120 → 130 (Franks)` |
| Several value pairs | One line per group, largest group first. The largest group, when no other is as large, may use the "except" forms; the civs of the other groups are among its exceptions and are named on their own lines: `Champion — Bonus vs Shock Infantry 8 → 9 (all civilizations except Achaemenids, …)` and `6 → 9 (Achaemenids, …)` |

**Thresholds:**
- The app names at most 8 civs in a list ("… and 3 more"), with the full list on hover. **Exports name every civ**: they are read out or pasted, so nothing may be cut.
- Use the "except" forms when listing the exceptions is shorter than listing the changed civs.

**Where it shows (D-44):** a change that names its civs is on each of those civs' pages; every other form, including "all N civilizations that have it", is on Overall. When the civs named are every civ that has the entity, the scope also carries their count, as "having" does; the patch notes use it (see Patch notes).

**Civ-specific changes go first.** A change limited to some civs usually means a civ bonus changed, so within a category those lines come before "all civs" lines.

## One entry per entity

The change set is field-level: one change per field and value group. The app and the exports draw **entries** instead: all the changes of one entity that share a category, a page and a scope. A unit whose HP changed for every civ and whose attack changed for the Franks gives two entries, so the civ information stays exact.

```
• Knight · (all civilizations)
    - Hit points · 100 → 110
    - Movement speed · 1.35 → 1.4
```

- **One change:** the entry reads as one line, as before.
- **A new unit** (in Unit stats, every field goes from nothing to a value, hit points among them): the entry is marked Added and lists only its **main stats**, without empty or default values (`0`, `-1`). The main stats are hit points, line of sight, speed, attacks, armours, displayed attack and armours, maximum range, reload time, cost and train time. The entry ends with the number of values it leaves out. Every unit has hit points, so a unit that only gains a value in a new slot isn't new: the Missionary only gained a food cost (Spanish, 101.103.54800.0) and stays Modified.
- **A removed unit:** one line, with the number of values left out.
- **A new tech** is compared with nothing, like a new unit, so its entry lists its cost, research location and time, required techs and its effect's commands. The entry is marked Added when every change is a new value and one of them is a research location: a tech players could research always has one. That also covers a placeholder record the patch fills in. Bookkeeping fields (effect ID, required count, flags) and default values don't count either way. *Ordonnance Companies and Cranequins on 101.103.54800.0 were such placeholders in 101.103.48987.0 and read as lists of "added" values before 2026-10-12.* A removed tech stays one line.
- **Other categories** keep every change they have, e.g. a building that only gained offered items.
- **Any entry:** a line that reads exactly like one already listed is listed once. The game has several records for some buildings, one per look, all named alike (four Docks on 101.103.54800.0); the change set keeps every change.
- **Any entry:** a field that only appears or disappears with a default value (`added 0`) is counted, not listed. A placeholder unit that the patch fills in otherwise shows dozens of them. A sentence with no value, such as "New: Enables Champi Runner", is never a default: its label says it all. *Before 2026-10-10 such sentences were counted, which hid the Chronicles civs' full tech tree fix on 101.103.54800.0.*
- **Counts:** the civ list counts entries.
- **In the change set JSON,** an entry lists its changes by position in `changes`, so no change is written twice.

## New civilizations

A civ added in the new build has no old values, so comparing it field by field would report everything as "added". Instead its page shows a summary:
- **Added** (the civ itself) and its **bonus text**, all shown as new text;
- what sets it apart, as its tech tree marks it: its **unique units**, **unique techs**, **regional units** and **regional techs** (node types `UniqueUnit`, `UniqueTech`, `RegionalUnit`, `RegionalTech`), one line each, in tree order;
- its **tech tree** as one entry: one line per building with what is available there (every node that isn't `NotAvailable`), plus one line for its buildings. Building offers are not compared;
- entities that are new everywhere (its unique units and techs) as usual, since they are brand new for every civ.

Shared units and nodes aren't compared for it (see Per-civ collapsing, Scope). A civ removed in the new build reads as one "Removed" line.

## Effects (O-5)

Every changed effect command is shown in up to three layers, most readable first:

1. **The game's own text.** If the civ's bonus text, or the tech's help text, changed: a word-level diff of it. Texts read as players see them: the game's line-break marker is a line break and its bold markers are dropped. A text with several lines (a civ bonus list) is compared line by line: an added or removed bonus is a whole line, and a line that only changed a little marks the words that changed. The exports keep the lines: plain text marks each removed or added line on its own line.
2. **A generated sentence.** For command types that have a template: a sentence built from the command, with unit, class, resource, tech and attribute names resolved.
   - Examples (illustrative): `Cavalry — hit points ×1.20 → ×1.15`, `Enables unit: Elite Konnik`, `Loom — food cost −50`.
   - Templates live in the i18n catalog.
3. **The raw command.** Always available in an expanded view, and the only form for command types without a template, e.g. (illustrative) `effect 527 "C-Bonus, Cavalry +20% HP" · command 3 · type 5 · a=-1 b=12 c=0 · d=1.2 → 1.15`.

**Names come from the game's own `Constants.xs`** ([game-files.md §11](../reference/game-files.md#11-xs-scripts-resources_commonxs)), stored in each snapshot's `scripts` section, never from memory. The new build's table is used first, then the old one's. Labels are derived from the identifiers (`cDamageClassShockInfantry` → "Shock Infantry"). An ID the file doesn't name shows as `#<id>`.

**Templates (layer 2)** are keyed by the command type's **name** in `Constants.xs`, not by its number. A snapshot whose constants don't name a type gets no sentence for it.

| Type (XS name) | Label | Value |
|---|---|---|
| `SetAttribute` | `{target}: {attribute}` | `=5` |
| `AddAttribute` | `{target}: {attribute}` | `+1` |
| `MulAttribute` | `{target}: {attribute}` | `×1.2` |
| `ModResource` (mode set / add) | `{resource}` | `=100` / `-50` |
| `MulResource` | `{resource}` | `×1.1` |
| `EnableObject` (mode enable / disable) | `Enables {unit}` / `Disables {unit}` | none |
| `UpgradeUnit` | `Upgrades {unit} to {unit}` | none |
| `DisableTech` | `Disables {tech}` | none |
| `AddTechCost` (mode set / multiply) | `{tech}: Cost`, or `{tech}: {resource} cost` for one resource | `=0` / `×0.85` |
| `ModTechTime` (mode set / multiply, every resource) | `{tech}: Research time` | `=0` / `×0.75` |
| `ModResource` setting `EffectFunctionNumber` | `Runs the scripted effect: {title}` | none |

- **Target:** the unit in `a`, else the class in `b` ("Cavalry class"). A command with neither stays raw.
- **Scripted effects:** setting the resource `EffectFunctionNumber` runs that numbered function of `Effects.xs`; the sentence uses the function's title comment, e.g. "Effect of Kasbah for Berbers" (game-files.md §11; the Kasbah tech sets it to 52 on 101.103.54800.0).
- **Attack and armour** (attributes 9 and 8) unpack `d` as class × 256 + amount, e.g. "Archer: Pierce attack · +1". A negative `d`, or a multiplied attack or armour, stays raw: its packing isn't verified.
- **An attribute the constants don't name** stays raw, and so do attributes whose value probably packs data in a way not yet verified: `ResourceCost`, `AddArmorType`, `AddAttackType`, `RemoveArmorType` and `RemoveAttackType`. Attack and armour are recognised by their XS names (`Attack`, `Armor`), not by number.
- **Two commands that differ only in a slot the sentence doesn't show** stay raw, so a change never reads "×1.5 → ×1.5".
- **Tech cost and time** (`AddTechCost`, `ModTechTime`): `a` is the tech, `b` the resource (`-1` every one; food, wood, stone or gold for a cost), `c` the mode. Verified on 101.103.54800.0 from bonuses named after what they do: mode 0 sets ("free Careening, Dry Dock" sets their food and gold to 0), mode 2 multiplies (the Italians' "Age up 15% cheaper" is ×0.85). Modes 1 and -1, other `b` values, and a time with a resource stay raw.
- **Other types** (`SpawnUnit`, `ModifyTech`, `SetPlayerData`, the unit-attribute variants 10–12, `SetTechCost`) have no template yet: their slot meanings aren't verified from game files. Types the constants don't name, such as 15 (120 commands on 101.103.54800.0), stay raw.

**How a changed command reads:**
- **Same target and attribute on both sides:** one line with both values, e.g. "Archer: Pierce attack · +1 → +2".
- **Otherwise:** the old sentence with only an old value, and the new one with only a new value.
- **A sentence without a value** says it in words: "New: Enables Crossbowman", "No longer: Enables Crossbowman".
- **The raw command** stays in the change's detail: "Bodkin Arrow, command 7: type 4 a=4 b=-1 c=9 d=769".

A command without a sentence is not an error; it falls back to layer 3. The effect's own name from the `.dat` is shown when present (how descriptive those names are is checked in M0).

**Commands are compared as a sequence.** The two lists are aligned first (Python's `difflib`), so a command inserted or removed is one change, not a shift of every command after it. Within a replaced stretch, commands are paired by position. Each added, removed or changed command gets its own entry, with its position in the new effect (or the old one, when removed). *Before 2026-09-27 they were compared position by position; one inserted command in Butalmapu gave over 100 changes.*

## Levels (D-46)

Every change has a **level**: `headline` (shown by default), `detail` or `technical`. The filters "Show minor changes" and "Show technical changes" bring the others back, in the app and the exports. An entry shows only its changes at the chosen levels; an entry with none left is not shown. A notice counts the hidden changes of named objects. Levels never remove a change from the change set.

The rules come from measuring 101.103.48987.0 → 101.103.54800.0 against its official notes.

| Change | Level | Why |
|---|---|---|
| Unit search radius, resource capacity and decay, button icon, accuracy dispersion, base armour, charge event/type/target, projectile IDs, special ability, invulnerability level, friendly fire damage | detail | Behaviour tuning and plumbing, not what players compare |
| Displayed melee/pierce armour, attack, range or reload time that moved exactly like the stat it shows (class 4/3 armour, an attack, maximum range, reload time) | detail | The same change twice (Hulk: armour 4 → 3 and displayed armour 4 → 3) |
| Blast attack or defence level of a unit with no blast width in either build, and no effect giving it one | technical | It does nothing without a width |
| Blast attack or defence level of a unit whose blast width only an effect gives (a tech or bonus) | detail | The effect's own line says what changes; the level alone read as if every civ gained trample (Knight line and Vendel Legacy on 101.103.54800.0) |
| An attack or armour class row appearing or disappearing with 0 | technical | No effect |
| Techs and units offered by a building | detail | The availability lines already say it |
| A building switching between `ResearchRequired` and `ResearchedCompleted` | detail | Available either way |
| Tech repeatable flag, required tech count, tech type; an effect ID change | detail | Bookkeeping; an effect's commands are reported on their own lines |
| A raw command in a civ's tech tree effect | technical | The availability lines already say it |
| A sentence in a civ's tech tree effect that enables or disables a unit or tech | detail | The availability lines already say it (Treadmill Crane on 101.103.54800.0: "Not available (Bengalis, …)" and "Bengalis · New: Disables Treadmill Crane") |
| A value that only changed by rounding (less than 0.1 %, e.g. 0.99999 → 1) | technical | No effect |
| A text change in spacing only | technical | No effect |

**Never lowered:** a raw command outside tech tree effects. A command without a sentence can be a real change (the Huns' Atheism uses unnamed command types).

**A unit no civ could get in the old build**, that some civ can get now, reads as **Added**, even when the old `.dat` held a placeholder record for it (Mounted Crossbowman on 101.103.54800.0 went "Hit points 1 → 45"). Only units new to every civ: a civ gaining an existing unit keeps its availability line.

**Starting resources** are compared across civs: a change every civ shares, Gaia included, is one Overall line named after the resource, instead of one per civ page. Only the four stockpiles (food, wood, stone, gold: resources 0 to 3) read **Starting amount**. The others are values the game's mechanics read, which no civ starts with, so they read **Game value** (e.g. "Varangian Gold · Game value · 0 → 50").

## Civ bonuses are not applied to units (P-17)

Snapshots store raw data only (D-20), and v1 **never applies civ bonus effects to unit stats**. Bonuses can depend on age, researched techs and unit class, so a single "effective" number would be misleading and would add a lot of complexity.

Instead, as in the game itself, the app shows:
- **civ bonuses** as their own list: the bonus text and the effect sentences (see Effects);
- **units** with their raw stats.

The details drawer (D-49) shows how a civ's bonuses affect a unit as a **list** next to its raw values; computing applied values stays under "Later" ([roadmap.md](../roadmap.md)).

## What affects an entity (D-49)

The details drawer lists the effect commands that touch one unit, building or tech. A command matches by what its type says its slots mean, looked up by name in the snapshot's `Constants.xs`, never by "slot `a` equals the ID": unit and tech IDs overlap. On 101.103.54800.0 the Bulgarians' tech tree effect halves the cost of tech 74, Scale Mail Armor, which is not the Militia, unit 74.

- **A unit or building** (with its class from the record shown):
  - `SetAttribute`, `AddAttribute`, `MulAttribute` with `a` the unit, or `a = -1` and `b` its class;
  - `EnableObject` with `a` the unit;
  - `UpgradeUnit` with `a` or `b` the unit, but not both: an age-up "upgrades" the Town Center to itself, which only changes its look.
- **A tech:** `AddTechCost` and `ModTechTime` with `a` the tech.
- **Left out:**
  - `DisableTech`: availability, which the tech tree already shows;
  - every other type.
- **A unit upgrade** (a `UnitUpgrade` node) also matches the commands on its research (`trigger_tech_id`), so the Bulgarians' free Militia-line upgrades appear under the Man-at-Arms.
- **A scripted effect** (`ModResource` setting `EffectFunctionNumber`) can't be matched to anything. The drawer names the civ's scripted bonuses by their `Effects.xs` title instead.
- **Sentences and raw commands** follow the Effects rules above.

## Change-volume check

**Trigger:** more than **20 %** of the compared allowlisted unit field values changed between the two snapshots. The threshold is to be tuned against real patches.

**Effect:** the change set carries an `unusually_many_changes` warning, pointing to the Diagnostics window.

**Why:** a misread `.dat` that still passed the gates would most likely show up as mass changes. A genuinely large patch can trigger the warning too; it prompts a double-check and never blocks anything.

## Values and formatting

- **Comparison** is exact on stored values. Floats come from the file's float32 values, so the same bits always give the same Python float.
- **Display:**
  - Show the shortest decimal form that tells old and new apart: `2.0 → 1.9`, not `2 → 2`.
  - Resources are shown by name: type 0 is food, 1 wood, 2 stone and 3 gold, checked against costs the game shows in its own interface (game-files.md §4).
  - Armour and attack classes are named from the snapshots' `Constants.xs` and worded as players say them (D-50; see [Attack and armour classes](#attack-and-armour-classes-d-50)). Train and research locations show the building's name.
  - **Required techs** show tech names separated by semicolons (names can hold commas, e.g. "C-Bonus, Free Chemistry"), without the empty `-1` slots. A tech whose required count is 0 lists none: its slots then hold placeholders such as tech 0, "New Research". A change that only touches such slots is not reported.
  - Unknown IDs are shown as `#<id>`.
- **Names:**
  - A unit, tech tree node or building is named from the game's strings, the new build first.
  - A **tech with no display name** uses its internal `.dat` name. Civ bonuses are such techs, e.g. `C-Bonus, Military cost -20%`. The developers' prefix is spelled out from the catalog, for techs and effects alike: `C-Bonus, X` reads "Civ bonus: X" and `T-Bonus, X` reads "Team bonus: X" (345 and 1 such names on build 101.103.54800.0). The rest of the name is kept as written; it is never reworded or guessed, except the developers' age numbers: "Age1" to "Age4" read as the ages' names ("Inf Cav +1 armor Age3" reads "… Castle Age"; maintainer, 2026-10-12). "Age 3" with a space is left as written. The scenario editor's placeholder, `New Research`, doesn't count as a name (seen on build 101.103.54800.0).
  - A **tech the `.dat` ties to a civ** (its `civ` slot, on either side; Gaia doesn't count) is that civ's bonus. Its changes go on that civ's page.
  - A **tech known only by its internal name** in every build that has it, whose name isn't a civ or team bonus's, is marked `internal: true`, and so is an effect whose name isn't a bonus's. Such techs are plumbing players never see ("Disable Regionals", "Genitour (make avail)" on 101.103.54800.0). The comparison shows them as any other; the patch notes leave them out (see Patch notes).
  - An entity still left with **no name** is marked `named: false` and shown as `#<id>`. Its changes are **hidden by default**: a notice gives their count, and "Show objects with no name" shows them, in the app and in the exports. They stay in the change set, so nothing is lost.
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
| **HTML** | Sharing, archiving, showing on stream | One self-contained file: inline CSS, and icons as data URIs, each embedded once and shrunk to 80 px (twice the displayed size). |
| **Patch notes** | Video descriptions, Reddit, Discord | The comparison written as the official notes are (D-51; see Patch notes below). Light Markdown, copied or saved as `.txt`. It doesn't follow the filters. |
| **Image (PNG)** | Putting a page on screen in a video | The page on screen, with the filters on, drawn on a canvas by the frontend (`gui/web/js/image.js`): 1920 px wide, at most 1080 px tall, a long page in numbered parts that break between entries. Each part has the page title, both versions and the Microsoft notice; civ lists name every civ. No screenshot library. |

There is no Markdown export of the comparison; the patch notes are light Markdown (P-13, amended for them).

**Sections of the text and HTML exports:** Overall, then **Several civilizations**, then each civ. The app shows a change shared by a few civs on each of their pages (D-44). An export prints it once, in Several civilizations, so a patch that gives three civs the same change doesn't print it three times. An export limited to some civs keeps each shared change in each civ's section instead.

Every export starts with a header (snapshot labels, game builds unless the label already holds them, capture dates as YYYY-MM-DD, pre-release marks, tool version) and any notices: stats not compared, layout substituted, unusually many changes. Notices about filters are written for the export's readers, who can't change them: they count what **this export leaves out** (minor or technical changes, objects with no name), and are left out when it includes everything. The HTML export ends with the Microsoft notice ([legal.md](../legal.md)).

## Patch notes (D-51)

The comparison written the way the official patch notes are, for players who aren't developers: in the app (a mode of the comparison) and as text to paste (`report/notes/`). The examples are from 101.103.48987.0 → 101.103.54800.0.

**What they hold.** A summary with a fixed meaning: the **headline** changes of **named** objects outside the low-priority categories (text, icons), whatever the comparison's filters say. They only reword the change set, never interpret it (rule 4). A change that can't be written cleanly is left out and counted in the closing line ("2597 more changes aren't in these notes … The detailed changes list them all"), never guessed:
- a raw effect command (no sentence template);
- a line that would show an unknown ID (`#123`), or bare building IDs ("Made at");
- detail and technical levels, objects with no name, text and icon changes;
- the details of a new civ (see below).

**Structure:**
- A title with both versions (label, build unless the label holds it, "(pre-release)"), the line "Written by Patch Scout from the game's data. These are not the official patch notes.", then the comparison's notices for readers (stats not compared, layout substituted, unusually many changes). The filter notices are replaced by the closing line.
- **General:** the Overall entries, one group per category in the change set's order. Techs marked `internal` are left out everywhere (maintainer, 2026-10-12).
- **Civilizations:** one group per civ with notes, alphabetical, headed by the civ's name and crest; then **Chronicles** with the `antiquity` civs (D-38). A change shared by several civs is repeated in each of their blocks, as the official notes do. **Except** a unit or tech change whose civs are every civ that has the object, two or more: it is said once, in General, as the official notes do (Lou Chuan, Armored Elephant, Fortified Church, Eagle Scout, Varangian Guard on 101.103.54800.0). Gaining or losing access stays with each civ ("Gain access to (Elite) Varangian Guard"), and a change only some of its holders share stays with them (Champion for the three Chronicles civs). **A new civ** reads in a few lines, as a player first wants it (maintainer, 2026-10-12): "New civilization: Infantry and Siege civilization." (the first line of its description), then "Unique units: Jomsviking.", "Unique techs: …", "Regional units: …", "Regional techs: …" from the engine's summary. A unit's upgrades are named once: a name that is another of the list with one word before it ("Elite Jomsviking", "E. Varangian Guard") is left out. Its bonuses' exact effects, its units' stats and its whole tech tree are in the detailed changes and the tech tree, and counted in the closing line. Inside any other civ's block: whether it is removed, its description, its bonuses, unit stats, techs, what it gains, what it loses, other effects, then its internal techs.

**Sentences** (every word from the catalog's `notes.*` keys):

| Change | Sentence |
|---|---|
| Fields of a unit, tech or resource | "Onager pierce armour increased from 7 → 8, melee attack increased from 50 → 55." A value that appears: "bonus vs Camels added: 3"; disappears: "… removed (was 2)". |
| A change every civ but some shares | "… (except Athenians, Spartans and Thracians)", whatever the kind of sentence: a field, gaining or losing access, NEW, removed, what an effect gives. |
| Something added or removed with no value | "Stable building offer added.", "Effect of Kasbah removed." Never a bare label. |
| A new unit (entry Added) | One line with where it is trained: "NEW: (Elite) Varangian Guard (Barracks)." Its stats are in the detailed changes and the tech tree; the line says the unit is new, so its values count as said. |
| A new upgrade (entry Added) | A tech whose only sentence upgrades a unit into the one it is named after: "NEW: Heavy Mounted Crossbowman upgrade." |
| A new tech (entry Added) | One line with what it does: "NEW: Ordonnance Companies: (Heavy) Mounted Crossbowman -40% gold cost." (maintainer, 2026-10-12). Its cost, research time and requirements are in the detailed changes and the tech tree; the line says the tech is new, so they count as said. An effect sentence the line doesn't write, such as one the tech lost, is counted in the closing line. |
| A unit or tech removed | "Bearded Axe removed." |
| A node gained, or its status leaving Not available | "Gain access to Treadmill Crane." Left out where a NEW item about the same unit or tech says it. |
| A node lost, or its status becoming Not available | "Lose access to (Heavy) Cavalry Archer." |
| A renamed node | "Longboat renamed to Longship." |
| A new civ | A few lines: see above. |
| The civ's description (bonus text) | One bullet per line that changed, in the game's words, with the heading it sits under: "Unique Techs: Bearded Axe (…) → Ordonnance Companies (…)", "New in Team Bonus: …", "Removed: Docks +5 garrison capacity". When most of a line stays, only what changed: "Wagenburg Tactics (Gunpowder Units move +15% → +10% faster)"; a line that only gains or loses words reads whole both ways. A text that only wraps differently says nothing (Byzantines). |
| What an effect now gives units or classes | Whom, not what: "Gambesons now affects (Elite) Varangian Guard, Eastern Swordsman and Norse Warrior." Players know what the tech does; the detailed changes have the values. "… no longer affects …" for what it gives no longer. |
| What an effect does to a tech's cost or research time | Always with its numbers, as a clause: "Incas: Team bonus: Start w/ Llama food cost removed (was 0)." Without them, "no longer affects Team bonus: …" read as if the civ lost the bonus. |
| An effect value that changed | "Wagenburg Tactics: Hand Cannoneer, Bombard Cannon, … movement speed decreased from +15% → +10%." |
| An effect sentence with no value | "Disable Regionals: new effect: Disables Cranequins"; several under one tech as bullets. |
| A script an effect runs, or no longer runs | Left out, with the tech's other effect sentences: a function of Effects.xs says nothing a player can read. On 101.103.54800.0 five only showed a message (Kasbah, Cuman Mercenaries, First Crusade, Flemish Revolution, Atheism), and the others took over a bonus whose old effects read as removed ("Gold Bonus removed", Malians). The tech's other fields stay; the closing line counts the rest. |

- **Left to the detailed changes:** required techs. On 101.103.54800.0 every change to them was plumbing ("Dupl. Imperial Age", "Civ bonus: Free Chemistry"); players read requirements as ages and availability, which the notes say from the tech tree. They are counted in the closing line.
- **A tech's cost** reads "research cost in food", so an upgrade named after its unit isn't read as the unit's cost ("Elite Rattan Archer research cost in food decreased from 1000 → 800").
- **Field labels** are the comparison's, with the first letter lowered mid-sentence (`notes.field_case`; a label whose second letter is a capital is left alone). Attribute names from `Constants.xs`, in title case, are lowered whole ("line of sight").
- **Values:** a leading `=` is dropped; a multiplier reads as a percentage, computed in decimal ("×0.6" → "-40%", "×1.0835" → "+8.35%"); `+N`/`-N` keep their sign.
- **Direction:** "increased" or "decreased" only when both values are numbers of the same form (plain, set, added, or multiplied); otherwise "changed". It states the number's direction only, never a buff or nerf (D-34).
- **Pairs:** "Throwing Axeman" and "Elite Throwing Axeman" with the same fields read "(Elite) Throwing Axeman"; when their values differ, "… from 3 → 5, Elite 4 → 6". The prefix is one word and the pairing is textual: it is a contraction of the two names, true whatever the upgrade line, and never guesses one. So "Archer" and "Cavalry Archer" given the same thing read "(Cavalry) Archer". Two subjects that moved in opposite directions read "changed". Each field must have changed the same way for both (a value added to one and removed from the other can't share a clause); otherwise they stay apart.
- **Unit lines:** one field that changed differently for several units of a line of the game's `unitlines.json` is one sentence, each unit with its own values and scope, in the line's order: "Militia line bonus vs Shock Infantry increased: Man-at-Arms 2 → 3, Long Swordsman 6 → 8, Two-Handed Swordsman 8 → 9 and Champion 8 → 9 (except Athenians, Spartans and Thracians)." (maintainer, 2026-10-12; four sentences on 101.103.54800.0). The line is named after its first unit, as the players read it. The units' other fields stay in their own sentences. Not when the field changed alike for all of them (merging says it) or when the units are just a unit and its upgrade (pairing says "(War) Hulk … War 115 → 110"). It reads where its name puts it among the group's sentences. The comparison carries the lines (`ChangeSet.unit_lines`) for this.
- **Unit names:** the tech tree's labels shorten some names ("H. Mounted Crossbowman"); when the comparison's Unit stats have the same unit ID, its own name is used, so the pair reads "(Heavy) Mounted Crossbowman".
- **Merging:** within a group, sentences that say the same about different subjects become one ("Battering Ram, Capped Ram and Siege Ram line of sight increased from 3 → 5"; "Bodkin Arrow, Bracer and Fletching now affect …"). Gaining and losing access are one line per item, as in the official notes.
- **No repeats:** in a civ's block whose description changed, the effect lines of the civ's own bonuses (its own entity, techs named "Civ bonus: …" or "Team bonus: …") and of techs a changed line names ("Wagenburg Tactics (…)") are left out: the description says it in the game's words (Teutons on 101.103.54800.0 said one bonus three times). They are counted in the closing line.
- **Punctuation:** a description line whose letters and digits didn't change says nothing (Mapuche: "Slingers and" → "Slingers, and" read as if a unit lost its bonus).
- **Free techs made redundant:** an effect that set a tech's cost in some resource to 0, removed while that tech loses its own cost in that resource, changes nothing for the civ: it still gets the tech for nothing (Incas' "Team bonus: Start w/ Llama", Berbers' Genitour and Italians' Condottiero on 101.103.54800.0, each 1 food made free). Matched by tech name and resource, whatever the tech. The effect counts as said; the tech's own cost change is left to the detailed changes and counted, since no other civ is known not to have paid it.
- **Moved commands:** the same sentence removed and added for one target (a command that only moved in the effect's list; Fabric Shields, Incas) cancels out and counts as said.

**Text form:** light Markdown, so it reads as plain text in a video description and as lists on Reddit and Discord: section titles in capitals, group titles as plain lines, `- ` bullets, nested bullets indented four spaces (CommonMark and old Reddit both read that as a nested list). Names are not escaped. Copied, or saved as `patch-notes.txt`.
