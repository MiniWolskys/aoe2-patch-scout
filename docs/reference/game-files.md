# Game files reference (AoE2:DE)

This page describes how to read the game data the tool uses.

**Markers**

- **[verified]:** checked read-only on 2026-09-15 against Steam build `101.103.48987.0` (Steam build ID `24094652`, `.dat` SHA-256 `ce3530df…22b4cf`).
- **[to verify]:** not yet checked; tracked under M0 in [roadmap.md](../roadmap.md).

**Conventions**

- Paths are relative to the install root, e.g. `C:\Program Files (x86)\Steam\steamapps\common\AoE2DE`. Never hardcode the root.
- Layout facts hold for one build. Re-check them when a game update changes a format, and update this file.

---

## 1. Locating an install

**The install location is never assumed** (D-19).
- Detection proposes candidates; the user confirms one or browses to any folder.
- Folders used before are offered again.
- When detection finds nothing, that's a normal outcome.

**Validating a folder:** it must contain `resources\_common\dat\empires2_x2_p1.dat` and `resources\_common\dat\civilizations.json`.

### Steam
- **App ID** is `813780`. [verified]
- **Detection:**
  1. Registry `HKCU\Software\Valve\Steam` → `SteamPath`, e.g. `c:/program files (x86)/steam`. [verified]
  2. `<SteamPath>\steamapps\libraryfolders.vdf` lists every library's `path`. [verified]
  3. The library holding `steamapps\appmanifest_813780.acf` is the right one; the game is in `<library>\steamapps\common\<installdir>`, where `installdir` is `AoE2DE`. [verified]
  4. **Fallback:** `HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Steam App 813780` → `InstallLocation`. [to verify]
- **App manifest fields:**
  - `buildid` [verified];
  - `UserConfig` / `MountedConfig` → `language`, e.g. `english`: the game language, useful for O-3 [verified];
  - on the live branch there is no beta-branch field [verified]. What the manifest records when a beta branch is selected is [to verify] (P-23).
- **Pre-release (PUP) builds.** Per the official "Public Update Preview" support article (updated 2026-03-06), the PUP is a **Steam beta branch of app 813780**, not a separate app.
  - Users select it under Properties → Game Versions & Betas.
  - **Switching branches overwrites the live install in place**, so capture the live build first.
  - Builds shared privately with content creators aren't publicly documented. They may also be branches, or folders installed anywhere; manual folder choice covers them.

### Microsoft Store / Xbox app (Game Pass)
**[to verify]:** no test install yet. The sources are community tools and forums.
- **Newer installs:** a library folder, by default `<drive>:\XboxGames\<game name>\Content`. Game files there are readable by normal programs.
  - **Finding library folders:** each drive root may hold a hidden **binary** `.GamingRoot` file: 4-byte magic, uint32 version = 1, then UTF-16LE library path(s) relative to the drive.
  - **Identifying the game:** `Content\MicrosoftGame.Config` → `Identity/@Name`.
- **Older installs:** `C:\Program Files\WindowsApps\…`, which is permission-locked and likely unreadable.
- **Package name** reported by community sources: `Microsoft.MSPhoenix` (`Get-AppxPackage` → `InstallLocation`).
- **Unconfirmed:** the exact folder name, whether the exe is also `AoE2DE_s.exe`, and whether the `resources\` layout is identical. Indirect evidence says the layout is the same.

## 2. Version identifiers

Store all of these in the snapshot metadata.

| Identifier | Source | Example | Notes |
|---|---|---|---|
| Game build | `AoE2DE_s.exe` PE FileVersion | `101.103.48987.0` | [verified] If the exe is missing or named differently (pre-release, Store version) [to verify], record "unknown" and carry on. |
| Steam build ID | `appmanifest_813780.acf` → `buildid` | `24094652` | [verified] Steam installs only. |
| Steam branch | App manifest beta-branch field | e.g. a `pup…` branch | [to verify] Used only to prefill the pre-release tickbox (P-23). |
| `.dat` format version | First 8 bytes of the **decompressed** `.dat` | `VER 8.9` | [verified] The raw bytes are `VER 8.9\0`; strip trailing NULs. This is the file layout version, not the patch. |
| Input fingerprints | SHA-256 + size of **every** input file | — | Not only the `.dat`: a hotfix can change strings or JSON alone. |

## 3. Inputs

### In scope

| Data | Path | Format | Section |
|---|---|---|---|
| Core game data: units, techs, effects, civs | `resources\_common\dat\empires2_x2_p1.dat` | Raw DEFLATE binary | §4 |
| Per-civ tech tree (UI) | `resources\_common\dat\CivTechTrees\<CIV>.json` | JSON, 59 files | §5 |
| Civ list and metadata | `resources\_common\dat\civilizations.json` | JSON | §6 |
| What each building offers (base civs) | `resources\_common\dat\futuravailableunits.json` | JSON | §7 |
| Same, for Chronicles (`antiquity`) civs | `resources\_common\dat\paphosfutureavailableunits.json` | JSON | §7 |
| Unit upgrade lines | `resources\_common\dat\unitlines.json` | JSON | §8 |
| Linked / exclusive techs | `resources\_common\dat\linkedTechs.json` | JSON | §8 |
| Other helpers | `linkedUnits.json`, `unitcategories.json`, `eras.json` (same folder) | JSON | §8 |
| Strings, English | `resources\en\strings\key-value\key-value-strings-utf8.txt` | Text | §9 |
| Strings, Chronicles content | `resources\en\strings\key-value\key-value-paphos-strings-utf8.txt` | Text | §9 |
| Non-localized strings | `resources\_common\strings\key-value\non-localized-key-value-strings-utf8.txt` | Text | §9 |
| Icons | `widgetui\textures\ingame\{units,tech,buildings}\` and more | DDS / PNG | §10 |

**Not inspected yet** [to verify]: `sharedbuildings.json`, `dropsites.json`, `objreplacement.json`.

**Other languages:** `resources\<lang>\strings\key-value\…` for `br de en es fr hi it jp ko ms mx pl ru tr tw vi zh`. See decision O-3.

**JSON facts** [verified]:
- All 80 JSON files in `dat\` (21) and `dat\CivTechTrees\` (59) load with Python's strict `json` module.
- They are UTF-8 without a BOM.
- Always open them with `encoding="utf-8"`. PowerShell's default reading garbles non-ASCII text such as "Lü Bu".

### Out of scope / ignore

- **Unneeded JSONs in `dat\`:** `adapterblacklist`, `AIConsts`, `airesourcetypes`, `buttons`, `chronicles_selection_group_def`, `hotkeys`, `maps`, `peru_campaign`, `selection_group_def`, `sounds`.
- **Other string files:**
  - Campaign strings (`*-campaign-key-value-strings-utf8.txt`).
  - `tournament-key-value-strings-utf8.txt`.
  - `key-value-modded-strings-utf8.txt`: its role is [to verify].
- **Also ignored:**
  - `resources\<lang>\strings\history\` (flavour text).
  - `widgetui\*.json` (screen layouts).
  - `Docs\*.pdf` (obsolete manuals).
- **`modes\Pompeii\` is Return of Rome, not Chronicles** [verified]. It is a separate mode with its own `.dat` (**`VER 8.8`**, 2.5 MB), `civilizations.json`, `CivTechTrees\` and strings, and 17 civs: Egyptian, Greek, Babylonian, Assyrian, Minoan, Hittite, Phoenician, Sumerian, Persian, Shang, Yamato, Choson, Roman, Carthaginian, Palmyran, Macedonian, LacViet. Out of scope for v1 (D-14); the same reader could support it later.
- **`Tools_Builds\`** holds `AdvancedGenieEditor3.exe` and `docs\` with the genieutils and AGE licences plus `Source.7z`. `Source.7z` is LZMA-compressed: Windows `tar` can't open it, 7-Zip can. Useful for cross-checking by hand; not an input.

## 4. The `.dat` file

### Container [verified]
- Raw DEFLATE with **no zlib header**: `zlib.decompress(data, wbits=-15)`.
- 11,076,546 bytes on disk, **86,745,747** bytes decompressed. Decompression takes about 0.12 s.
- Starts with `VER 8.9\0`.

### Contents
Read it with genieutils-py; see [genieutils-py.md](genieutils-py.md) for exact class and field names. Never use names from memory.

- **Civs.** Each civ holds its **own copy of every unit slot**: `civ.units: list[Unit | None]`. Many slots are empty or used only by scenarios.
  - Every civ has **2,701 unit slots** (IDs 0–2700). Of the 162,060 slots across the 60 civs, 33,335 are empty. [verified 101.103.48987.0]
  - The file also holds 1,510 techs and 1,409 effects. [verified 101.103.48987.0]
- **Techs.** One global table: cost, research time, required techs, research location, effect ID.
- **Effects.** Lists of commands: modify attribute, enable/disable unit, upgrade unit, disable tech, resource modifiers…
  - Civ bonuses, team bonuses, Blacksmith-style upgrades and each civ's disabled units and techs are all effects.
  - Each civ points to its tech tree effect (what it can't have) and its team bonus effect.
- **Where civ bonuses live** [to verify]. Expected: mostly effects (bonus techs applied at game start), not values baked into per-civ unit copies. Check with the Franks mounted-unit HP bonus. The answer decides how bonus changes show up in the diff (decision O-5).
- **Irrelevant for the diff:** graphics, sounds, terrain and random map data.

### To verify (M0)
- [x] genieutils-py 0.1.2 parses this `VER 8.9` file and consumes all of it, and the round trip on the decompressed stream is byte-exact. [verified 101.103.48987.0]
- [ ] Extracted values match Advanced Genie Editor or in-game values: Knight HP, a Blacksmith tech cost, the Franks bonus effect.
- [x] Civ order in the `.dat` matches `civilizations.json` order (Gaia = 0); see §6. [verified 101.103.48987.0]
- [x] Parse time and peak memory for the 87 MB stream: about 18 s and 1.1 GB; see [genieutils-py.md](genieutils-py.md#measured-on-the-live-build).

## 5. `CivTechTrees\<CIV>.json`

**Scale** [verified]
- 59 files, one per playable civ; Gaia has none.
- Each filename equals `tech_tree_name` in `civilizations.json`, e.g. `FRANKS.json`.
- 10,167 nodes in total, about 172 per civ.

**Top-level keys:**
- `civ_id` (string, e.g. `"FRANKS"`)
- `civ_techs_buildings` (array)
- `civ_techs_units` (array)

**Node keys** [verified]
- **Always present:** `Name`, `Use Type`, `Node Status`, `Name String ID`, `Age ID`, `Building ID`, `Help String ID`, `Node ID`, `Picture Index`.
- **Optional:** `Node Type` (absent in 52 nodes), `Link Node Type` (absent in 1), `Draw Node Type` (absent in 2), `Link ID`, `Trigger Tech ID`, `Building upgraded from ID`, `Building in new column`, `Prerequisite IDs`, `Prerequisite Types`.
- **Unknown keys:** future builds may add keys. Keep them (see the snapshot format) instead of dropping them.

| Field | Meaning |
|---|---|
| `Use Type` | `Unit` (3,468), `Tech` (4,974), `Building` (1,725). **Chooses the ID namespace of `Node ID` and the icon folder.** [verified] |
| `Node ID` | Unit, tech or building ID in the `.dat`; the namespace follows `Use Type`. |
| `Node Type` | `Research` 4,974 · `UnitUpgrade` 1,575 · `Unit` 1,526 · `BuildingNonTech` 931 · `BuildingTech` 777 · `UniqueUnit` 173 · `RegionalUnit` 142 · `RegionalBuilding` 11 · `UniqueBuilding` 6 · **key absent** 52. All 52 key-absent nodes are Elite Cannon Galleon (Node ID 691). [verified] |
| `Node Status` | `ResearchedCompleted` 8,153 (available) · `ResearchRequired` 593 (needs a prerequisite) · `NotAvailable` 1,421. **This is the per-civ availability to diff.** [verified] |
| `Age ID` | 1 = Dark, 2 = Feudal, 3 = Castle, 4 = Imperial; only 1–4 occur. Chronicles civs use other age names (§8, `eras.json`). [verified] |
| `Building ID` | Building where the node is trained or researched. |
| `Link ID` / `Link Node Type` | Parent node in the tree, e.g. Crossbowman → Archer. |
| `Trigger Tech ID` | Tech that performs the upgrade, e.g. Crossbowman ← tech 100. |
| `Prerequisite IDs` / `Prerequisite Types` | Fixed arrays of 5. Only `"Tech"` and `"None"` occur in this build. [verified] |
| `Name String ID` | Resolves **directly**, e.g. 14128 → `"Archery\nRange"`. The tech tree label may contain `\n`. 10,167/10,167 resolve. [verified] |
| `Help String ID` | Resolves as **`ID − 79000`**, e.g. 105128 → 26128 "Build Archery Range…"; 10,167/10,167 resolve. A direct lookup matches 21 IDs **by coincidence** and returns the wrong strings; never use it. [verified] |
| `Picture Index` | Icon file number; ambiguous without `Use Type` (§10). |

## 6. `civilizations.json`

**Shape** [verified]
- `{ "civilization_list": [ ... ] }` with **60 entries**: Gaia first, Tupi last.
- `era` is `"base"` (54 entries, Gaia included) or `"antiquity"` (6).

**Order** [verified]
- Follows `name_string_id`, running in order from 10102 (Gaia) to 10329 (Tupi).
- **It matches the `.dat` civ indices** [verified 101.103.48987.0]: 60 civs in both, each at the same position.
- **Match civs by index, never by name.** The `.dat` civ `name` is an old internal name, not `internal_name`: e.g. `British`, `French`, `Byzantine`, `Mayan`, `Hindustanis` for Britons, Franks, Byzantines, Mayans, Indians.

**Keys:**

| Key | Notes |
|---|---|
| `internal_name` | e.g. `Franks`. Also the key used in `futuravailableunits.json`. |
| `tech_tree_name` | CivTechTrees filename, e.g. `FRANKS`. Gaia has no file. |
| `data_name` | e.g. `BRITON-CIV`. |
| `hud_style` | |
| `name_string_id` | |
| `computer_name_string_table_offset` | |
| `era` | `"base"` or `"antiquity"`. |
| `unique_tech_id_1`, `unique_tech_id_2` | |
| `unique_unit_id`, `elite_unique_unit_id` | |
| `unique_unit_line` | Negative line ID; always present in `unitlines.json`. [verified] |
| `unique_unit_upgrade_id` | |
| `unique_unit_string_ids` | `[{name, description}]`; both resolve directly. |
| `tech_tree_image_path`, `emblem_image_path`, `unique_unit_image_paths` | |

**Chronicles (`antiquity`) civs:** Achaemenids, Athenians, Spartans, Macedonians, Thracians, Puru. [verified]

**Civ bonus text** [verified]
- String ID = `120150 + (position in the list − 1)`, for the 59 non-Gaia civs (120150–120208).
- Checked for all 59: each text contains the civ's unique unit name.
- The IDs aren't contiguous in the file, so look them up by ID.
- 120149 and 120209 don't exist.
- Format: `"<Type> civilization\n\n• bonus\n• bonus…\n\n<b>Unique Unit:<b>…<b>Unique Techs:<b>…<b>Team Bonus:<b>…"`.
- **Adding a civ may shift this mapping.** Re-verify on every build with the unique-unit-name check, and flag a mismatch instead of guessing.

## 7. `futuravailableunits.json` / `paphosfutureavailableunits.json`

**Shape:**
- `{ "<internal_name>": { "Buildings": [ { ID, Name, Techs: [...], Units: [...], RequiredAge?, PrereqTech?, ... } ] } }`.
- **Entry keys:** `ID`, `Name`, `RequiredAge`, `PrereqTech`, `RequiredTechID`, `RequiredUnitID`, `PrereqIconSet`, `PrereqIconIndex`, `PrereqStyle`, `PrereqStringID`.

**Civ keys** [verified]
- Keys equal `civilizations.json` → `internal_name`.
- The base file has 55 keys: Gaia, the 53 base civs, and `FullTechCiv`.
- The paphos file has 12 keys: Gaia, the 6 Chronicles civs, the placeholders `Paphos6`–`Paphos9`, and `FullTechCiv`.
- **Skip** `FullTechCiv` and `Paphos6`–`Paphos9`.

**Use:**
- "What does building X offer this civ."
- Together with CivTechTrees, the source of the **reachable unit** set used at diff time.
- Units created by other units, such as dismount or transform forms, may not appear here [to verify].

## 8. Helper JSONs

- **`unitlines.json`:** `{ Hint, UnitLines: [ { Name, Identifier, Building?, LineID, IDChain: [unitIDs] } ] }`. [verified]
  - 112 lines, `LineID` from −399 to −200.
  - Archer line −299 = `[4, 24, 492]`.
- **`linkedTechs.json`:** `{ LinkedTechs: [ { NameId, Comment, Type, Techs: [...], StartingTech?, Instant?, Local? } ] }`. [verified]
  - `Type` is `MutuallyExclusive` (14), `Cycle` (4) or `Toggleable` (2).
  - Mostly Chronicles civ choices and doctrines.
- **`linkedUnits.json`:** `{ Data: [ { Name, Units: [...] } ] }`, groups of equivalent units (heroes, villager variants).
- **`unitcategories.json`:** category → `[ {Name, ID} ]` overrides (SiegeWeapons, Monks…).
- **`eras.json`:** `[ { Name: "base" | "antiquity", Ages: [ { NameId, TechTreeIconMaterialName?, ShieldMaterialName?, PrerequisiteStringId? } ] } ]`. [verified]
  - Each era has **5** age entries.
  - The fifth has only a `NameId` (4205 base, 407088 antiquity); its meaning is [to verify].

## 9. String files (key-value)

**Encoding:** UTF-8, no BOM. [verified]

**Line format:**
- Lines starting with `//` are comments; blank lines occur.
- Entry: `<key> "<text>"`, optionally followed by a trailing comment: `3106 "[W]" //Wonder abbreviation…`.
- Keys are usually numeric, but **non-numeric keys exist**: 3,215 in the main file, e.g. `IDS_OPT_ESC_MENU`. [verified]
- Regex: `^(\S+)\s+"((?:[^"\\]|\\.)*)"`. Ignore everything after the closing quote. Every non-comment, non-blank line of the main and paphos files matches it. [verified]

**Text content:**
- Escapes: `\n`; handle `\"` defensively.
- Rich-text tags: `<b>…<b>`, `<i>…<i>`, `<GREY>`, `<DEFAULT>`.
- Placeholders: `<cost>`, `<hp>`, `<attack>`, `<armor>`, `<piercearmor>`, `<range>`, `<garrison>`.
- Store text raw; render tags only in the report.

**Duplicates** [verified]
- Main file: 19,391 numeric entries but 19,380 unique IDs, e.g. 13170, 13171, 15556, 5323.
- Non-numeric keys also repeat.
- Rule: **last one wins**, and the duplicates are logged. Which entry the game uses is [to verify].

**Main vs paphos file** [verified]
- The paphos file has 1,708 numeric and 46 non-numeric keys.
- The two files share no keys, so load order doesn't matter today. Detect overlaps anyway and log them.

## 10. Icons

### Tech tree icons [verified]
- **Folders:** `widgetui\textures\ingame\units\` (755 files), `tech\` (304), `buildings\` (107).
- **Size:** 242 MB in total, about 200 KB per file.
- **Names:** `NNN_<suffix>.<ext>`, e.g. `000_crop_rotation`, `023_stable_1`, `017_50730`.
  - The extension is `.DDS` or `.dds` (mixed case): **match case-insensitively**.
- **Lookup:** `NNN` is the node's `Picture Index` and **`Use Type` picks the folder**.
  - `Unit` → `units\`, `Tech` → `tech\`, `Building` → `buildings\`.
  - All 10,167 nodes resolve to exactly one file.
  - Every index number exists in several folders, so `Picture Index` alone is ambiguous.
- **DDS compression:** no DX10 header (so no BC7). Files are either not block-compressed (no FourCC) or `DXT1` / `DXT5`.
  - Checked: all tech and building icons, 400 of 755 unit icons.
  - Pillow should decode these [to verify].

### Other icon sets
- Unique unit PNGs: `resources\_common\wpfg\resources\uniticons\NNN_50730.png` (95 files). [verified]
- Civ emblems: `resources\_common\wpfg\resources\civ_emblems\` (62) and `widgetui\textures\ingame\emblems\` (59). [verified]
- Stat icons: `widgetui\textures\ingame\staticons\` (29 files). **Not used**: the app draws its own stat icons (D-09).
- Age and legend icons: `widgetui\textures\menu\techtree\`.

### Handling
See [snapshot-format.md](../design/snapshot-format.md) (icon store) and [diff-rules.md](../design/diff-rules.md) (redraw vs remap).
- Convert only icons referenced by a snapshot.
- A missing or unreadable icon is recorded with `hash: null` and a reason. It never fails a capture.
