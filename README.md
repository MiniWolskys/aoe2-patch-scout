# Patch Scout

Find out what changed in *Age of Empires II: Definitive Edition* between two game builds, without waiting for patch notes.

> **Status: early development.** No release yet. This README describes the planned v1; progress is tracked in the [roadmap](docs/roadmap.md).

## Why

Content creators often get early builds (pre-release, PUP) before any patch notes exist. Today they check tech trees and unit stats by hand to find what changed. This tool reads the game data of each build, keeps a snapshot, and lists every difference in one click.

## Planned features (v1)

- **Capture** a snapshot of any AoE2:DE install. The app looks for the game and shows you the folder it found; you can always pick another one, e.g. a pre-release build.
- **Compare** two snapshots and get a categorised list of changes, with game icons:
  - new or removed civilizations;
  - units, techs and buildings gained or lost, per civ;
  - civ bonus and team bonus changes, in plain sentences;
  - unit stat changes (HP, attack, armour, range, speed, cost, train time…), marked *all civs* or *specific civs*;
  - tech cost, research time and effect changes;
  - text and icon changes.
- **Export** as plain text (for video descriptions), a single HTML page, or an image you can put straight into a video.
- **Organise your snapshots:** rename them, and mark the ones from pre-release builds.
- **A snapshot of the current live build is published with every release,** so you can compare even if you installed after the patch dropped.
- **Windows app,** no Python installation needed.

## How it works

The tool reads two kinds of data:

- **Files:** civilizations, tech trees, texts and icons are ordinary game files, and they are always read.
- **Stats:** unit and tech numbers live in the binary `empires2_x2_p1.dat`, read with [genieutils-py](https://github.com/SiegeEngineers/genieutils-py).
  - Every read is double-checked: the file must re-encode byte-for-byte and agree with the game's other files.
  - If a new build only changes the data format's version number, the tool still reads it, checks it, and tells you.
  - If the format really changed, the report says **"stats not compared"** and why, instead of showing numbers that might be wrong.

More detail in [docs/design/architecture.md](docs/design/architecture.md).

## Privacy and pre-release builds

- Works fully offline: no telemetry, no uploads.
- Never modifies your game folder.
- Steam's Public Update Preview (PUP) is a beta branch of your normal install: **switching to it overwrites the live game**, so capture the live build first.
- Snapshots stay on your computer. If you share an export from a pre-release build, follow the terms under which you got access.

## Requirements (planned)

- Windows 10 or 11.
- [Microsoft Edge WebView2 Runtime](https://developer.microsoft.com/microsoft-edge/webview2/). Windows 11 and most Windows 10 installs already have it; the app tells you if it's missing.
- An AoE2:DE installation to capture from.

## Documentation

| Document | Content |
|---|---|
| [Roadmap](docs/roadmap.md) | Milestones and what's next |
| [Decisions](docs/decisions.md) | What was decided and why; open questions |
| [Architecture](docs/design/architecture.md) | Components, data flow, screens |
| [Snapshot format](docs/design/snapshot-format.md) | What a snapshot contains |
| [Diff rules](docs/design/diff-rules.md) | What counts as a change and how it's shown |
| [Game files reference](docs/reference/game-files.md) | How the game data is laid out |
| [genieutils-py reference](docs/reference/genieutils-py.md) | The `.dat` reader and its version handling |
| [Packaging reference](docs/reference/packaging.md) | How the Windows build is made and checked |
| [Legal](docs/legal.md) | Licences, Microsoft's content rules, embargo |
| [Contributing](CONTRIBUTING.md) | Dev setup, workflow, testing |

## Contributing

Contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md), and read the rules about game files and pre-release data first.

## Acknowledgements

- [genieutils-py](https://github.com/SiegeEngineers/genieutils-py) (SiegeEngineers): reads the `.dat` file.
- [genieutils](https://github.com/Tapsa/genieutils) and [Advanced Genie Editor](https://github.com/Tapsa/AGE) (Tapsa): format reference.
- [aoe2techtree](https://github.com/SiegeEngineers/aoe2techtree) (SiegeEngineers): prior art for building on AoE2 game data.

## License

Copyright (C) 2026 the Patch Scout contributors.

This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version. See [LICENSE](LICENSE). Third-party components keep their own licences. Game content shown or exported by the tool (icons, texts, data) belongs to Microsoft and is not covered by the GPL; see [docs/legal.md](docs/legal.md).

Age of Empires II © Microsoft Corporation. Patch Scout was created under Microsoft's "[Game Content Usage Rules](https://www.xbox.com/en-US/developers/rules)" using assets from Age of Empires II, and it is not endorsed by or affiliated with Microsoft.
