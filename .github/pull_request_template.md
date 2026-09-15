## What and why

<!-- What does this change do, and why? Link the issue: "Closes #123". -->

## How it was tested

CI runs ruff, mypy and pytest. Game tests only run locally.

- [ ] `uv run ruff format .` / `uv run ruff check .` / `uv run mypy` / `uv run pytest` pass
- [ ] Game tests (`uv run pytest -m game`) pass locally (required if capture code changed). Build tested: <!-- e.g. 101.103.48987.0 -->

## Checklist

- [ ] No game files and **no data from privately shared builds** in this PR (code, fixtures, screenshots, logs, descriptions)
- [ ] Game-derived fixtures (public builds only) are in `tests/fixtures/game-derived/`
- [ ] Nothing writes inside a game install folder; no hardcoded install paths
- [ ] User-visible text goes through the i18n catalog
- [ ] Docs updated if behaviour, formats or decisions changed (`docs/design/`, `docs/reference/`, `docs/decisions.md`)
- [ ] If the snapshot schema or diff rules changed: golden files updated and reviewed (and, from v1.0, schema version bumped with a migration)
- [ ] If a runtime dependency was added: licence checked and listed in `docs/legal.md`
