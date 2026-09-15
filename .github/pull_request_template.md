<!--
PR title: Conventional Commits format, e.g. "feat(capture): detect Steam libraries".
It becomes the commit on main when squash-merged.
Link an issue if there is one: "Closes #123".
-->

## What and why

## Design summary

<!-- For features and design changes: the agreed design in a few lines, and which docs were updated. Otherwise write "n/a". -->

## How it was tested

<!-- Commands run and their results. CI runs pre-commit, mypy and pytest; game tests only run locally. -->

- [ ] `uv run pre-commit run --all-files`, `uv run mypy` and `uv run pytest` pass locally
- [ ] Game tests (`uv run pytest -m game`) pass locally (required if capture code changed). Build tested: <!-- e.g. 101.103.48987.0 -->

## Risks

<!-- What could break, and what reviewers should look at closely. -->

## Definition of Done

- [ ] Tests written first; bug fixes include a regression test
- [ ] No game files and **no data from privately shared builds** (code, fixtures, screenshots, logs, descriptions); no hardcoded install paths; nothing writes inside a game folder
- [ ] Game-derived fixtures (public builds only) are in `tests/fixtures/game-derived/`
- [ ] User-visible text goes through the i18n catalog
- [ ] Docs updated if behaviour, formats or decisions changed (`docs/design/`, `docs/reference/`, `docs/decisions.md`)
- [ ] If the snapshot schema or diff rules changed: golden files updated and reviewed (and, from v1.0, schema version bumped with a migration)
- [ ] If a runtime dependency was added: licence checked and listed in `docs/legal.md`
- [ ] Whole diff self-reviewed
