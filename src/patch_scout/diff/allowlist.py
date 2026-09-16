# SPDX-License-Identifier: GPL-3.0-or-later
"""Which unit fields the comparison reports, and how (D-08, diff-rules.md).

The allowlist names stat concepts; each entry gives the snapshot path the value lives at. The
paths use genieutils-py 0.1.2's field names, read from the installed source, never from memory
(AGENTS.md rule 7). Adding an entry is a behaviour change: it needs a fixture case and a note in
the pull request.

`stat_icon` names a key of the snapshot's `stat_icons` section, or None where the game has no
icon for that stat (line of sight and train time, game-files.md §10).
"""

from dataclasses import dataclass
from typing import Final, Literal

type FieldKind = Literal["value", "by_class", "resource_costs", "train_locations"]


@dataclass(frozen=True, slots=True)
class Field:
    """One allowlisted stat concept."""

    key: str
    path: str
    kind: FieldKind = "value"
    stat_icon: str | None = None

    @property
    def label(self) -> str:
        """The catalog key for this field's label."""
        return f"field.{self.key}"


UNIT_FIELDS: Final = (
    Field("hit_points", "hit_points", stat_icon="hp"),
    Field("line_of_sight", "line_of_sight"),
    Field("speed", "speed", stat_icon="movement_speed"),
    Field("garrison_capacity", "garrison_capacity", stat_icon="garrison"),
    Field("unit_class", "class_"),
    Field("attacks", "type_50.attacks", kind="by_class", stat_icon="melee_attack"),
    Field("armours", "type_50.armours", kind="by_class", stat_icon="melee_armor"),
    Field("displayed_attack", "type_50.displayed_attack", stat_icon="melee_attack"),
    Field("displayed_melee_armour", "type_50.displayed_melee_armour", stat_icon="melee_armor"),
    Field("displayed_pierce_armour", "creatable.displayed_pierce_armour", stat_icon="pierce_armor"),
    Field("base_armor", "type_50.base_armor", stat_icon="melee_armor"),
    Field("max_range", "type_50.max_range", stat_icon="range"),
    Field("min_range", "type_50.min_range", stat_icon="range"),
    Field("displayed_range", "type_50.displayed_range", stat_icon="range"),
    Field("reload_time", "type_50.reload_time", stat_icon="reload_time"),
    Field("displayed_reload_time", "type_50.displayed_reload_time", stat_icon="reload_time"),
    Field("accuracy_percent", "type_50.accuracy_percent"),
    Field("accuracy_dispersion", "type_50.accuracy_dispersion"),
    Field("blast_width", "type_50.blast_width", stat_icon="blast_radius"),
    Field("blast_attack_level", "type_50.blast_attack_level", stat_icon="blast_radius"),
    Field("blast_damage", "type_50.blast_damage", stat_icon="blast_radius"),
    Field("blast_defense_level", "blast_defense_level", stat_icon="blast_radius"),
    Field("frame_delay", "type_50.frame_delay"),
    Field("projectile_unit_id", "type_50.projectile_unit_id"),
    Field("garrison_firepower", "type_50.garrison_firepower"),
    Field("bonus_damage_resistance", "type_50.bonus_damage_resistance"),
    Field("damage_reflection", "type_50.damage_reflection"),
    Field("friendly_fire_damage", "type_50.friendly_fire_damage"),
    Field("resource_costs", "creatable.resource_costs", kind="resource_costs"),
    Field("train_locations", "creatable.train_locations", kind="train_locations"),
    Field("rear_attack_modifier", "creatable.rear_attack_modifier"),
    Field("flank_attack_modifier", "creatable.flank_attack_modifier"),
    Field("max_charge", "creatable.max_charge"),
    Field("recharge_rate", "creatable.recharge_rate"),
    Field("charge_event", "creatable.charge_event"),
    Field("charge_type", "creatable.charge_type"),
    Field("charge_target", "creatable.charge_target"),
    Field("charge_projectile_unit", "creatable.charge_projectile_unit"),
    Field("secondary_projectile_unit", "creatable.secondary_projectile_unit"),
    Field("total_projectiles", "creatable.total_projectiles"),
    Field("max_total_projectiles", "creatable.max_total_projectiles"),
    Field("min_conversion_time_mod", "creatable.min_conversion_time_mod", stat_icon="convert"),
    Field("max_conversion_time_mod", "creatable.max_conversion_time_mod", stat_icon="convert"),
    Field("conversion_chance_mod", "creatable.conversion_chance_mod", stat_icon="convert"),
    Field("invulnerability_level", "creatable.invulnerability_level"),
    Field("special_ability", "creatable.special_ability"),
    Field("button_icon_id", "creatable.button_icon_id"),
    Field("work_rate", "bird.work_rate", stat_icon="work_rate"),
    Field("search_radius", "bird.search_radius"),
    Field("resource_capacity", "resource_capacity"),
    Field("resource_decay", "resource_decay"),
    Field("garrison_type", "building.garrison_type", stat_icon="garrison"),
    Field("garrison_heal_rate", "building.garrison_heal_rate", stat_icon="hp_regen"),
    Field("garrison_repair_rate", "building.garrison_repair_rate"),
    Field("transform_unit", "building.transform_unit"),
)

# Tech fields the comparison reports (diff-rules.md, category 5).
TECH_FIELDS: Final = (
    Field("resource_costs", "resource_costs", kind="resource_costs"),
    Field("research_locations", "research_locations", kind="train_locations"),
    Field("required_techs", "required_techs"),
    Field("required_tech_count", "required_tech_count"),
    Field("effect_id", "effect_id"),
    Field("repeatable", "repeatable"),
    Field("tech_type", "type"),
)

# Resource types, checked against costs the game shows in its own interface on build
# 101.103.48987.0 (game-files.md §4): Militia 50 food, Barracks 175 wood, Watch Tower 125 stone
# and 35 wood, Archer 25 wood and 45 gold. Any other type is shown as `#<id>`, never guessed.
RESOURCE_KEYS: Final = {0: "food", 1: "wood", 2: "stone", 3: "gold"}
