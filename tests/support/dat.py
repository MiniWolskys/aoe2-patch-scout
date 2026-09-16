# SPDX-License-Identifier: GPL-3.0-or-later
"""Build a tiny synthetic `.dat` with genieutils-py, for the stats-tier tests.

No game file is involved: every record is built from the library's own dataclasses with zeroed
fields, then written with `to_bytes`. That gives a stream the real reader can parse, so the round
trip and the gates are exercised for real without shipping a `.dat` (CONTRIBUTING.md).
"""

import dataclasses
import types
import typing
import zlib
from typing import Any, Final

from genieutils.civ import Civ
from genieutils.common import UnitType
from genieutils.datfile import DatFile
from genieutils.effect import Effect, EffectCommand
from genieutils.randommaps import RandomMaps
from genieutils.tech import ResearchLocation, ResearchResourceCost, Tech
from genieutils.techtree import TechTree
from genieutils.terrainblock import TerrainBlock
from genieutils.unit import Bird, Creatable, DeadFish, Type50, Unit

# Counts the reader expects for arrays whose length is not stored in the file.
FIXED_LENGTHS: Final = {
    ("Terrain", "frame_data"): 19,
    ("Terrain", "terrain_unit_masked_density"): 30,
    ("Terrain", "terrain_unit_id"): 30,
    ("Terrain", "terrain_unit_density"): 30,
    ("Terrain", "terrain_unit_centering"): 30,
    ("TerrainBlock", "tile_sizes"): 19,
    ("TerrainBlock", "terrains"): 200,
    ("Bird", "drop_sites"): 3,
}


def zero(annotation: Any, owner: str = "", name: str = "") -> Any:
    """A neutral value for one annotated field."""
    origin = typing.get_origin(annotation)
    if origin is None:
        if annotation is int:
            return 0
        if annotation is float:
            return 0.0
        if annotation is str:
            return ""
        if dataclasses.is_dataclass(annotation) and isinstance(annotation, type):
            return build(annotation)
        raise TypeError(f"no neutral value for {annotation!r}")
    args = typing.get_args(annotation)
    if origin is list:
        length = FIXED_LENGTHS.get((owner, name), 0)
        return [zero(args[0], owner, name) for _ in range(length)]
    if origin is tuple:
        return tuple(zero(arg, owner, name) for arg in args)
    if origin in (typing.Union, types.UnionType):
        return None if type(None) in args else zero(args[0], owner, name)
    raise TypeError(f"no neutral value for {annotation!r}")


def build[T](cls: type[T], **overrides: Any) -> T:
    """Build one genieutils record with every field zeroed, apart from the overrides."""
    hints = typing.get_type_hints(cls)
    values = {
        f.name: overrides[f.name]
        if f.name in overrides
        else zero(hints[f.name], cls.__name__, f.name)
        for f in dataclasses.fields(cls)  # type: ignore[arg-type]  # genieutils records are dataclasses
    }
    return cls(**values)


def make_unit(unit_id: int, name: str, **overrides: Any) -> Unit:
    """A creatable unit, the shape most tech tree units have."""
    fields: dict[str, Any] = {
        "id": unit_id,
        "name": name,
        "type": int(UnitType.Creatable),
        "speed": 0.96,
        "hit_points": 40,
        "line_of_sight": 6.0,
        "language_dll_name": 5000 + unit_id,
        "dead_fish": build(DeadFish),
        "bird": build(Bird),
        "type_50": build(Type50),
        "creatable": build(Creatable),
    }
    fields.update(overrides)
    return build(Unit, **fields)


def make_tech(
    name: str,
    *,
    effect_id: int = -1,
    food: int = 0,
    gold: int = 0,
    time: int = 0,
    name_id: int = 0,
) -> Tech:
    """A tech with one research location and up to two resource costs."""
    costs = (
        build(ResearchResourceCost, type=0, amount=food, flag=1),
        build(ResearchResourceCost, type=3, amount=gold, flag=1),
        build(ResearchResourceCost, type=-1, amount=0, flag=0),
    )
    return build(
        Tech,
        name=name,
        civ=-1,
        effect_id=effect_id,
        resource_costs=costs,
        research_locations=[build(ResearchLocation, location_id=12, research_time=time)],
        language_dll_name=name_id,
    )


def make_civ(name: str, units: list[Unit | None], **overrides: Any) -> Civ:
    """One civ holding its own copy of every unit slot."""
    fields: dict[str, Any] = {
        "name": name,
        "units": units,
        "resources": [0.0, 200.0, 200.0, 100.0],
        "tech_tree_id": -1,
        "team_bonus_id": -1,
    }
    fields.update(overrides)
    return build(Civ, **fields)


def make_dat(
    civs: list[Civ],
    techs: list[Tech] | None = None,
    effects: list[Effect] | None = None,
    version: str = "VER 8.9",
) -> DatFile:
    """A complete, writable `DatFile` holding just the sections the app reads."""
    return DatFile(
        version=version,
        float_ptr_terrain_tables=[],
        terrain_pass_graphic_pointers=[],
        terrain_restrictions=[],
        player_colours=[],
        sounds=[],
        graphics=[],
        terrain_block=build(TerrainBlock),
        random_maps=build(RandomMaps),
        effects=effects if effects is not None else [],
        unit_headers=[],
        civs=civs,
        techs=techs if techs is not None else [],
        time_slice=0,
        unit_kill_rate=0,
        unit_kill_total=0,
        unit_hit_point_rate=0,
        unit_hit_point_total=0,
        razing_kill_rate=0,
        razing_kill_total=0,
        tech_tree=build(TechTree),
    )


def make_effect(name: str, commands: list[tuple[int, int, int, int, float]]) -> Effect:
    """An effect and its commands, each given as (type, a, b, c, d)."""
    return build(
        Effect,
        name=name,
        effect_commands=[
            build(EffectCommand, type=kind, a=a, b=b, c=c, d=d) for kind, a, b, c, d in commands
        ],
    )


def sample(
    *,
    archer_hp: int = 30,
    blue_archer_hp: int = 35,
    range_hp: int = 1000,
    fletching_food: int = 100,
    bonus_multiplier: float = 1.2,
) -> DatFile:
    """The `.dat` that matches the synthetic game folder in `game_tree`.

    The keyword arguments let a test build a second, slightly different build.
    """
    archer = make_unit(4, "Archer", hit_points=archer_hp)
    range_building = make_unit(87, "ArcheryRange", hit_points=range_hp)
    slots: list[Unit | None] = [None] * 200
    for unit in (archer, range_building):
        slots[unit.id] = unit
    gaia = make_civ("Gaia", [None] * 200, player_type=2)
    red = make_civ("RedCiv", list(slots), tech_tree_id=0, team_bonus_id=2)
    blue_slots = list(slots)
    blue_archer = dataclasses.replace(archer, hit_points=blue_archer_hp)
    blue_slots[4] = blue_archer
    blue = make_civ("BlueCiv", blue_slots, tech_tree_id=0, team_bonus_id=1)
    ancient = make_civ("AncientCiv", list(slots), tech_tree_id=0, team_bonus_id=1)
    techs = [make_tech("filler") for _ in range(199)]
    techs.append(
        make_tech("Fletching", effect_id=1, food=fletching_food, gold=50, time=30, name_id=14199)
    )
    effects = [
        make_effect("Red Tech Tree", [(102, 200, 0, 0, 0.0)]),
        make_effect("Fletching", [(4, -1, 0, 0, 1.0)]),
        make_effect("C-Bonus, Archers", [(5, -1, 12, 0, bonus_multiplier)]),
    ]
    return make_dat([gaia, red, blue, ancient], techs, effects)


def compressed(dat: DatFile) -> bytes:
    """The bytes a `.dat` file holds: raw DEFLATE, no zlib header (game-files.md §4)."""
    return zlib.compress(dat.to_bytes(), level=-1, wbits=-15)


def sample_bytes(**overrides: object) -> bytes:
    """The synthetic `.dat` as it would sit on disk."""
    return compressed(sample(**overrides))  # type: ignore[arg-type]  # keywords match sample
