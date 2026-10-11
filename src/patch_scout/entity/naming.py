# SPDX-License-Identifier: GPL-3.0-or-later
"""Names across both versions, the newer one first, as the comparison names things."""

from patch_scout.diff.effects import script_titles
from patch_scout.diff.names import Names
from patch_scout.diff.reachability import UnitLookup
from patch_scout.diff.values import at_path, unknown_id
from patch_scout.snapshot import JsonObject, Snapshot


class Naming:
    """Unit, tech and script names from two snapshots; `#<id>` when neither names one."""

    def __init__(
        self,
        sides: tuple[tuple[Snapshot, Names, UnitLookup], ...],
    ) -> None:
        self._sides = sides
        self._scripts: dict[int, str] | None = None

    def unit(self, unit_id: int) -> str:
        """A unit or building's display name."""
        for _, names, units in self._sides:
            name = names.one_line(at_path(units.any_record(unit_id), "language_dll_name"))
            if name:
                return name
        return unknown_id(unit_id)

    def tech(self, tech_id: int) -> str:
        """A tech's display name, else its readable internal name (Names.tech_name)."""
        for snapshot, names, _ in self._sides:
            name = names.tech_name(tech_record(snapshot, tech_id), tech_id)
            if name:
                return name
        return unknown_id(tech_id)

    def shown_tech(self, tech_id: int) -> str | None:
        """A tech's name in the game's own text, or None for a tech players never see.

        Requirements name helper techs with internal names only, such as "Shadow Node+ for Age
        Two" (101.103.54800.0): those are left out.
        """
        for snapshot, names, _ in self._sides:
            record = tech_record(snapshot, tech_id)
            name = names.one_line(record.get("language_dll_name")) if record is not None else None
            if name:
                return name
        return None

    def script(self, number: int) -> str | None:
        """An Effects.xs function's title, or None when it has none."""
        if self._scripts is None:
            titles: dict[int, str] = {}
            for snapshot, _, _ in self._sides:
                text = snapshot.scripts.get("effects")
                for key, title in script_titles(text if isinstance(text, str) else "").items():
                    titles.setdefault(key, title)
            self._scripts = titles
        return self._scripts.get(number)


def tech_record(snapshot: Snapshot, tech_id: int) -> JsonObject | None:
    """One tech's record, or None when the snapshot has no stats or no such tech."""
    techs = (snapshot.stats or {}).get("techs")
    record = techs.get(str(tech_id)) if isinstance(techs, dict) else None
    return record if isinstance(record, dict) else None


def effect_record(snapshot: Snapshot, effect_id: object) -> JsonObject | None:
    """One effect's record, or None for no effect (-1) or a missing one."""
    if not isinstance(effect_id, int) or isinstance(effect_id, bool) or effect_id < 0:
        return None
    effects = (snapshot.stats or {}).get("effects")
    record = effects.get(str(effect_id)) if isinstance(effects, dict) else None
    return record if isinstance(record, dict) else None
