from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from uuid import uuid4
import json
import os
import re
import html
import math
import secrets
import tempfile
from datetime import datetime

from character_API import IMPROVEMENT_CATALOG, STAT_NAMES


# ==============================================================
# Constants
# ==============================================================
VALID_DIE_SIZES = {4, 6, 8, 10, 12}
DEFAULT_DIE_SIZE = 4

STAT_POINT_COSTS = {
    4: 0,
    6: 1,
    8: 3,
    10: 6,
    12: 10  
}

STARTING_STAT_POINTS = 23
STARTING_IP = 6
STARTING_HEARTS = 2
STARTING_AT = 4

            
# ==============================================================
# Data Models: Stats
# ==============================================================

@dataclass
class Stat:
    die_size: int = DEFAULT_DIE_SIZE
    bonus: int = 0

    def validate(self) -> None:
        if self.die_size not in VALID_DIE_SIZES:
            self.die_size = DEFAULT_DIE_SIZE
        self.bonus = max(0, int(self.bonus))


@dataclass
class Stats:
    agility: Stat = field(default_factory=Stat)
    strength: Stat = field(default_factory=Stat)
    finesse: Stat = field(default_factory=Stat)
    instinct: Stat = field(default_factory=Stat)
    presence: Stat = field(default_factory=Stat)
    knowledge: Stat = field(default_factory=Stat)

    def validate(self) -> None:
        for stat in self.as_list():
            stat.validate()

    def as_list(self) -> List[Stat]:
        return [
            self.agility,
            self.strength,
            self.finesse,
            self.instinct,
            self.presence,
            self.knowledge,
        ]

    def as_dict(self) -> Dict[str, Stat]:
        return {
            "agility": self.agility,
            "strength": self.strength,
            "finesse": self.finesse,
            "instinct": self.instinct,
            "presence": self.presence,
            "knowledge": self.knowledge,
        }

    def get_stat(self, stat_name: str) -> Optional[Stat]:
        return self.as_dict().get(stat_name)

    def highest_stat_name(self) -> str:
        stats = self.as_dict()
        return max(
            stats,
            key=lambda name: (stats[name].die_size, stats[name].bonus)
        )

    def total_bonus_cost(self, free_bonus_stats: List[str]) -> int:
        total = 0

        for stat_name, stat in self.as_dict().items():
            bonus = max(0, stat.bonus)
            total += bonus * (bonus + 1) // 2
            if bonus and stat_name in free_bonus_stats:
                total -= min(bonus, free_bonus_stats.count(stat_name))

        return total
    
# ============================================================
# Data Models: Core Character Resources
# ============================================================

@dataclass
class HPData:
    current_HP: int = STARTING_HEARTS *  4
    max_hearts: int = STARTING_HEARTS
    max_HP: int = STARTING_HEARTS * 4
    temp_HP: int = 0

    def recalculate(self) -> None:
        self.max_hearts = max(0, int(self.max_hearts))
        self.max_HP = max(0, int(self.max_HP))
        self.current_HP = max(0, min(int(self.current_HP), self.max_HP))
        self.temp_HP = max(0, min(int(self.temp_HP), self.max_HP))

    def validate(self) -> None:
        self.recalculate()
        self.current_HP = max(0, min(self.current_HP, self.max_HP))
        self.temp_HP = max(0, min(self.temp_HP, self.max_HP))

@dataclass
class BonusDiceData:
    dice: Dict[str, int] = field(default_factory=dict)

    def validate(self) -> None:
        clean = {}

        for key, value in self.dice.items():
            die_size = int(value)
            if die_size in VALID_DIE_SIZES:
                clean[str(key)] = die_size

        self.dice = clean

@dataclass
class AdversityData:
    current_AT: int = 0
    max_AT: int = STARTING_AT

    def validate(self) -> None:
        self.max_AT = max(0, int(self.max_AT))
        self.current_AT = max(0, min(self.current_AT, self.max_AT))

        
@dataclass
class ProgressionData:
    current_IP: int = STARTING_IP
    used_IP: int = 0
    current_level: int = 1

    def validate(self) -> None:
        self.current_IP = max(0, int(self.current_IP))
        self.used_IP = max(0, int(self.used_IP))
        self.current_level = max(1, int(self.current_level))

    @property
    def available_IP(self) -> int:
        return self.current_IP - self.used_IP

    @property
    def level(self) -> int:
        return self.current_level

    def grant_IP(self, amount: int = 1) -> None:
        self.current_IP += int(amount)
        self.validate()

# ============================================================
# Data Models: Improvements / Inventory / Image
# ============================================================

@dataclass
class TakenEmpowerment:
    id: str
    group_id: str
    catalog_id: str
    name: str
    cost: int
    description: str
    source: str = "ip"
    choices: Dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        self.group_id = str(self.group_id)
        self.catalog_id = str(self.catalog_id)
        self.name = str(self.name)
        self.description = str(self.description)
        self.source = str(self.source)
        self.cost = max(0, int(self.cost))

        if self.choices is None:
            self.choices = {}


@dataclass
class Improvement:
    id: str
    catalog_id: str
    name: str
    cost: int
    description: str
    source: str = "ip"
    choices: Dict[str, Any] = field(default_factory=dict)
    empowerments: List[TakenEmpowerment] = field(default_factory=list)
    expanded: bool = False
    times_taken: int = 1
    sort_order: int = 0

    def validate(self) -> None:
        self.catalog_id = str(self.catalog_id)
        self.name = str(self.name)
        self.description = str(self.description)
        self.source = str(self.source)
        self.cost = max(0, int(self.cost))
        self.times_taken = max(1, int(self.times_taken))
        self.sort_order = int(self.sort_order)

        if self.choices is None:
            self.choices = {}

        for empowerment in self.empowerments:
            empowerment.validate()

    
    def total_cost(self) -> int:
        total = 0

        if self.source == "ip":
            total += self.cost

        for empowerment in self.empowerments:
            if empowerment.source == "ip":
                total += empowerment.cost
                
        return total


@dataclass
class ImprovementData:
    list_of_taken_improvements: List[Improvement] = field(default_factory=list)

    def validate(self) -> None:
        for improvement in self.list_of_taken_improvements:
            improvement.validate()

    def total_cost(self) -> int:
        return sum(
            improvement.total_cost()
            for improvement in self.list_of_taken_improvements
        )

    def get_by_catalog_id(self, catalog_id: str) -> List[Improvement]:
        return [
            improvement
            for improvement in self.list_of_taken_improvements
            if improvement.catalog_id == catalog_id
        ]

    def get_first_by_catalog_id(self, catalog_id: str) -> Optional[Improvement]:
        matches = self.get_by_catalog_id(catalog_id)
        if not matches:
            return None
        return matches[0]

    def count_by_catalog_id(self, catalog_id: str) -> int:
        total = 0

        for improvement in self.get_by_catalog_id(catalog_id):
            total += getattr(improvement, "times_taken", 1)

        return total

    def has_catalog_id(self, catalog_id: str) -> bool:
        return self.count_by_catalog_id(catalog_id) > 0

    def count_empowerments(self, parent_catalog_id: str, group_id: str) -> int:
        total = 0

        for improvement in self.get_by_catalog_id(parent_catalog_id):
            for empowerment in improvement.empowerments:
                if empowerment.group_id == group_id:
                    total += 1

        return total
    def has_empowerment(
        self,
        parent_catalog_id: str,
        group_id: str,
        empowerment_catalog_id: str,
    ) -> bool:
        for improvement in self.get_by_catalog_id(parent_catalog_id):
            for empowerment in improvement.empowerments:
                if (
                    empowerment.group_id == group_id
                    and empowerment.catalog_id == empowerment_catalog_id
                ):
                    return True

        return False
    
    def remove(self, improvement_id: str) -> None:
        self.list_of_taken_improvements = [
            improvement
            for improvement in self.list_of_taken_improvements
            if improvement.id != improvement_id
        ]

    def has_species_improvement(self) -> bool:
        return any(
            improvement.source == "species"
            for improvement in self.list_of_taken_improvements
        )


@dataclass
class InventoryItem:
    id: str
    name: str
    description: str
    quantity: int = 0
    expanded: bool = False

    def validate(self) -> None:
        self.name = str(self.name)
        self.description = str(self.description)
        self.quantity = max(0, int(self.quantity))

        
@dataclass 
class InventoryData:
    list_of_items: List[InventoryItem] = field(default_factory=list)

    def validate(self) -> None:
        for item in self.list_of_items:
            item.validate()

    def remove(self, item_id: str) -> None:
        self.list_of_items = [
            item for item in self.list_of_items
            if item.id != item_id
        ]
        
@dataclass
class CharacterNote:
    id: str
    title: str = ""
    text: str = ""
    color: str = "yellow"
    expanded: bool = True
    linked_improvement_id: str = ""
    pinned: bool = False

    def validate(self) -> None:
        self.id = str(self.id)
        self.title = str(self.title).strip()
        self.text = str(self.text)
        self.expanded = bool(self.expanded)
        self.pinned = bool(self.pinned)
        self.linked_improvement_id = str(
            self.linked_improvement_id
            or ""
        )

        if self.color not in {
            "red",
            "orange",
            "yellow",
            "green",
            "blue",
            "purple",
            "pink",
        } and not (
            isinstance(self.color, str)
            and len(self.color) == 7
            and self.color.startswith("#")
            and all(character in "0123456789abcdefABCDEF" for character in self.color[1:])
        ):
            self.color = "yellow"

@dataclass
class NoteData:
    list_of_notes: List[CharacterNote] = field(default_factory=list)

    def validate(self) -> None:
        clean_notes = []

        for note in self.list_of_notes:
            if isinstance(note, CharacterNote):
                note.validate()
                clean_notes.append(note)

        self.list_of_notes = clean_notes

    def remove(self, note_id: str) -> None:
        self.list_of_notes = [
            note
            for note in self.list_of_notes
            if note.id != note_id
        ]


@dataclass
class CharacterImageEntry:
    id: str
    image_data: Optional[str] = None
    
@dataclass
class CharacterImageData:
    images: List[CharacterImageEntry] = field(default_factory=list)

    current_index: int = 0
    
    offset_x: float = 0.0
    offset_y: float = 0.0
    scale: float = 1.0

    def validate(self) -> None:
        clean = []

        for image in self.images:
            if image.image_data:
                clean.append(image)
                
        self.images = clean

        if not self.images:
            self.current_index = 0
        else:
            self.current_index = max(
                0,
                min(self.current_index, len(self.images) - 1)
            )
            
        self.offset_x = float(self.offset_x)
        self.offset_y = float(self.offset_y)
        self.scale = max(0.1, float(self.scale))

    def current_image(self) -> Optional[str]:
        if not self.images:
            return None

        return self.images[self.current_index].image_data
    


# ============================================================
# Main Character Model
# ============================================================

@dataclass
class Character:
    id: str
    name: str = ""
    species_name: str = ""
    backstory: str = ""
    stats: Stats = field(default_factory=Stats)
    HP: HPData = field(default_factory=HPData)
    adversity: AdversityData = field(default_factory=AdversityData)
    progression: ProgressionData = field(default_factory=ProgressionData)
    improvements: ImprovementData = field(default_factory=ImprovementData)
    inventory: InventoryData = field(default_factory=InventoryData)
    notes: NoteData = field(default_factory=NoteData)
    image: CharacterImageData = field(default_factory=CharacterImageData)
    bonus_dice: BonusDiceData = field(default_factory=BonusDiceData)
    stat_point_budget: int = STARTING_STAT_POINTS
    free_heightened_ability_slots: int = 2
    free_heightened_ability_stats: List[str] = field(default_factory=list)
    selected_defense_stat_name: Optional[str] = None
    combat_mode_enabled: bool = False
    creation_rules_active: bool = False
    creation_template_name: str = ""
    creation_species_mode: str = "normal"
    creation_allow_custom_improvements: bool = True
    creation_allowed_ability_array_ids: List[str] = field(
        default_factory=list
    )
    creation_restrict_ability_dice_to_allowed_arrays: bool = False
    creation_improvement_mode: str = "all"
    creation_improvement_ids: List[str] = field(
        default_factory=list
    )
    creation_improvement_overrides: Dict[str, Dict[str, Any]] = field(
        default_factory=dict
    )
    creation_template_custom_improvements: List[Dict[str, Any]] = field(
        default_factory=list
    )

    roll_history: List[str] = field(default_factory=list)


    def validate(self) -> None:
        self.stats.validate()
        self.HP.validate()
        self.adversity.validate()
        self.progression.validate()
        self.improvements.validate()
        self.inventory.validate()
        self.notes.validate()
        self.image.validate()
        self.name = str(self.name)
        self.species_name = str(self.species_name)

        self.creation_rules_active = bool(
            self.creation_rules_active
        )

        self.creation_template_name = str(
            self.creation_template_name or ""
        ).strip()

        if self.creation_species_mode not in {
            "normal",
            "disabled",
            "required",
        }:
            self.creation_species_mode = "normal"


        self.creation_allow_custom_improvements = bool(
            self.creation_allow_custom_improvements
        )

        if not isinstance(
            self.creation_allowed_ability_array_ids,
            list,
        ):
            self.creation_allowed_ability_array_ids = []

        self.creation_allowed_ability_array_ids = [
            str(value)
            for value in self.creation_allowed_ability_array_ids
            if str(value).strip()
        ]

        self.creation_restrict_ability_dice_to_allowed_arrays = bool(
            self.creation_restrict_ability_dice_to_allowed_arrays
        )

        if self.creation_improvement_mode not in {
            "all",
            "allow_only",
            "ban",
        }:
            self.creation_improvement_mode = "all"

        if not isinstance(
            self.creation_improvement_ids,
            list,
        ):
            self.creation_improvement_ids = []

        self.creation_improvement_ids  = [
            str(value)
            for value in self.creation_improvement_ids
            if str(value).strip()
        ]

        if not isinstance(self.creation_improvement_overrides, dict):
            self.creation_improvement_overrides = {}

        if not isinstance(self.creation_template_custom_improvements, list):
            self.creation_template_custom_improvements = []

        self.stat_point_budget = max(
            0,
            int(self.stat_point_budget),
        )
        

        self.stat_point_budget = max(0, int(self.stat_point_budget))

        if self.selected_defense_stat_name not in STAT_NAMES:
            self.selected_defense_stat_name = None

        
        # Used IP is derived from improvements, not manually controlled.
        self.free_heightened_ability_slots = max(
            0, int(self.free_heightened_ability_slots)
        )

        self.free_heightened_ability_stats = [
            stat_name
            for stat_name in self.free_heightened_ability_stats
            if stat_name in STAT_NAMES
        ]

        # Older versions stored paid increases in the free-selection list.
        # Preserve them as paid purchases while retaining only genuine free slots.
        free = []
        for name in self.free_heightened_ability_stats:
            if len(free) < self.free_heightened_ability_slots:
                free.append(name)
            else:
                self.improvements.list_of_taken_improvements.append(Improvement(
                    id=str(uuid4()), catalog_id="heightened_ability",
                    name="Heightened Ability", cost=1, description="",
                    source="ip", choices={"stat_name": name},
                ))
        self.free_heightened_ability_stats = free

        ImprovementSystem.refresh_improvement_descriptions(self)
        CharacterDerivedStatsSystem.recalculate_heightened_ability_bonuses(self)
        CharacterDerivedStatsSystem.recalculate_hp(self)
        CharacterDerivedStatsSystem.recalculate_bonus_dice(self)
        
        # Heightened bonuses are charged once, at their actual bonus tiers.
        free_stats = self.free_heightened_ability_stats[
            :self.free_heightened_ability_slots
        ]
        tiers = {name: self.free_heightened_ability_stats.count(name)
                 for name in STAT_NAMES}
        catalog_paid = 0
        species_credit = 0
        for improvement in self.improvements.list_of_taken_improvements:
            name = improvement.choices.get("stat_name")
            if improvement.catalog_id != "heightened_ability" or name not in tiers:
                continue
            tiers[name] += 1
            improvement.cost = tiers[name]
            if improvement.source == "ip":
                catalog_paid += improvement.cost
            else:
                species_credit += improvement.cost
        self.progression.used_IP = (
            self.improvements.total_cost() - catalog_paid
            + self.stats.total_bonus_cost(free_stats) - species_credit
        )
        CharacterDerivedStatsSystem.recalculate_heightened_ability_bonuses(self)

        self.progression.validate()

    @staticmethod
    def create_new_character(name: str = "") -> "Character":
        character = Character(id=str(uuid4()), name=name)
        character.validate()
        return character

    @property
    def BDV(self) -> int:
        return self.adversity.max_AT // 2

    @property
    def defense_stat_name(self) -> str:
        if self.selected_defense_stat_name in STAT_NAMES:
            return self.selected_defense_stat_name
        return self.stats.highest_stat_name()

    @property
    def DR(self) -> int:
        stat = self.stats.get_stat(self.defense_stat_name)
        if stat is None:
            return 0
        return (stat.die_size // 2) + stat.bonus

    def grant_IP(self, amount: int = 1) -> None:
        self.progression.grant_IP(amount)
        self.validate()

    def set_level(self, target_level: int, heal_to_new_max: bool = True) -> None:
        target_level = max(1, int(target_level))

        old_level = self.progression.level
        level_change = target_level - old_level

        # Real Level Up grants 2 IP. Bonus IP is independent.
        if level_change:
            self.progression.current_IP += level_change * 2

        self.progression.current_level = target_level

        milestones_gained = target_level - 1
        self.adversity.max_AT = STARTING_AT + milestones_gained

        old_max_hp = self.HP.max_HP
        self.HP.max_hearts = STARTING_HEARTS + milestones_gained
        self.HP.recalculate()

        if heal_to_new_max:
            gained_hp = self.HP.max_HP - old_max_hp
            self.HP.current_HP += gained_hp

        self.validate()

    def grant_milestone(self, heal_new_heart: bool = True) -> None:
        self.set_level(
            self.progression.level + 1,
            heal_to_new_max=heal_new_heart
        )
        

# ============================================================
# Systems: HP
# ============================================================
class CharacterDerivedStatsSystem:

    @staticmethod
    def recalculate_all(character: Character) -> None:
        CharacterDerivedStatsSystem.recalculate_heightened_ability_bonuses(character)
        CharacterDerivedStatsSystem.recalculate_hp(character)
        CharacterDerivedStatsSystem.recalculate_bonus_dice(character)

    @staticmethod
    def recalculate_heightened_ability_bonuses(character: Character) -> None:
        # Stat bonuses are derived from Heightened Ability choices.
        # Rebuild them from scratch every validation so save/load cannot duplicate them.
        for stat_name in STAT_NAMES:
            stat = character.stats.get_stat(stat_name)

            if stat is not None:
                stat.bonus = 0

        # Free Heightened Ability choices, including duplicates.
        for stat_name in character.free_heightened_ability_stats:
            stat = character.stats.get_stat(stat_name)

            if stat is not None:
                stat.bonus += 1

        # Paid Heightened Ability improvements.
        for improvement in character.improvements.list_of_taken_improvements:
            if improvement.catalog_id != "heightened_ability":
                continue

            stat_name = improvement.choices.get("stat_name")

            if not stat_name:
                continue

            stat = character.stats.get_stat(stat_name)

            if stat is not None:
                stat.bonus += 1

    @staticmethod
    def recalculate_hp(character: Character) -> None:
        character.HP.max_hearts = max(0, int(character.HP.max_hearts))

        base_hp = character.HP.max_hearts * 4

        hearty_count = character.improvements.count_by_catalog_id("hearty")
        hearty_bonus_hp = hearty_count * character.HP.max_hearts

        character.HP.max_HP = base_hp + hearty_bonus_hp

        character.HP.current_HP = max(
            0,
            min(character.HP.current_HP, character.HP.max_HP)
        )

        character.HP.temp_HP = max(
            0,
            min(character.HP.temp_HP, character.HP.max_HP)
        )

    @staticmethod
    def recalculate_bonus_dice(character: Character) -> None:
        dice = {}

        for improvement in character.improvements.list_of_taken_improvements:
            option = ImprovementCatalogSystem.get_option(
                improvement.catalog_id,
                character,
            )

            if option is None:
                continue
            

            CharacterDerivedStatsSystem._apply_effects_to_bonus_dice(
                dice,
                option.get("effects", []),
            )

            groups = option.get("empowerment_groups", {})

            for empowerment in improvement.empowerments:
                group = groups.get(empowerment.group_id)

                if group is None:
                    continue

                matching_option = None

                if group.get("rule") in {
                    "single", "repeatable", "repeatable_scaling"
                }:
                    matching_option = group

                for possible_option in group.get("options", []):
                    possible_id = possible_option.get("id", "")

                    if empowerment.catalog_id == possible_id:
                        matching_option = possible_option
                        break

                    if (
                        possible_id
                        and empowerment.catalog_id.startswith(
                            possible_id + "_"
                        )
                    ):
                        matching_option = possible_option
                        break

                if matching_option is None:
                    continue

                CharacterDerivedStatsSystem._apply_effects_to_bonus_dice(
                    dice,
                    matching_option.get("effects", []),
                )

            scaling_groups = option.get(
                "scaling_empowerments",
                {},
            )

            for group_id, group in scaling_groups.items():
                taken = [
                    empowerment
                    for empowerment in improvement.empowerments
                    if empowerment.group_id == group_id
                ]

                if not taken:
                    continue

                rule = group.get("rule", "ordered")

                if rule == "ordered":
                    steps = group.get("steps", [])

                    step_index = len(taken) - 1

                    if 0 <= step_index < len(steps):
                        step = steps[step_index]

                        CharacterDerivedStatsSystem._apply_effects_to_bonus_dice(
                            dice,
                            step.get("effects", []),
                        )

                elif rule == "repeatable_scaling":
                    CharacterDerivedStatsSystem._apply_effects_to_bonus_dice(
                        dice,
                        group.get("effects", []),
                    )

        character.bonus_dice.dice = dice
        character.bonus_dice.validate()


    @staticmethod
    def _apply_effects_to_bonus_dice(dice: Dict[str, int], effects: List[dict]) -> None:
        for effect in effects:
            if effect.get("type") != "set_bonus_die":
                continue

            key = effect.get("key")
            die_size = effect.get("die_size")

            if key is None or die_size is None:
                continue

            die_size = int(die_size)

            previous = dice.get(key, 0)
            dice[key] = max(previous, die_size)


# ============================================================
# Systems: Dice Rolling
# ============================================================

class DiceRollSystem:
    @staticmethod
    def roll_die(die_size: int) -> int:
        die_size = int(die_size)

        if die_size < 2:
            raise ValueError("Die must have at least 2 sides.")

        return secrets.randbelow(die_size) + 1

    @staticmethod
    def roll_dice(
        die_size: int,
        count: int = 1,
        modifier: int = 0,
    ) -> dict:
        die_size = int(die_size)
        count = max(1, int(count))
        modifier = int(modifier)

        rolls = [
            DiceRollSystem.roll_die(die_size)
            for _ in range(count)
        ]

        subtotal = sum(rolls)
        total = subtotal + modifier

        return {
            "die_size": die_size,
            "count": count,
            "rolls": rolls,
            "modifier": modifier,
            "subtotal": subtotal,
            "total": total,
        }

    @staticmethod
    def roll_stat(character: Character, stat_name: str) -> dict:
        stat = character.stats.get_stat(stat_name)

        if stat is None:
            raise ValueError(f"Unknown stat: {stat_name}")

        result = DiceRollSystem.roll_dice(
            die_size=stat.die_size,
            count=1,
            modifier=stat.bonus,
        )

        result["stat_name"] = stat_name

        return result





class HPSystem:
    @staticmethod
    def add_HP(character: Character, amount: int = 1) -> bool:
        if amount <= 0:
            return False
        character.HP.current_HP += int(amount)
        character.validate()
        return True

    @staticmethod
    def remove_HP(character: Character, amount: int = 1) -> bool:
        if amount <= 0:
            return False
        character.HP.current_HP -= int(amount)
        character.validate()
        return True

    @staticmethod
    def set_HP(character: Character, amount: int) -> bool:
        character.HP.current_HP = int(amount)
        character.validate()
        return True

    @staticmethod
    def add_heart(
        character: Character,
        amount: int = 1,
        heal_add_HP: bool = False
    )-> bool:
        if amount <= 0:
            return False

        old_max = character.HP.max_HP
        character.HP.max_hearts += int(amount)
        character.HP.recalculate()

        if heal_add_HP:
            character.HP.current_HP += character.HP.max_HP - old_max

        character.HP.validate()
        return True

    @staticmethod
    def remove_heart(character: Character, amount: int = 1) -> bool:
        if amount <= 0:
            return False
        character.HP.max_hearts -= int(amount)
        character.validate()
        return True


# ============================================================
# Systems: AT / Stats
# ============================================================

class ATSystem:
    @staticmethod
    def click_at_slot(character: Character, slot_index: int) -> bool:
        if not 0 <= slot_index < character.adversity.max_AT:
            return False

        if slot_index < character.adversity.current_AT:
            character.adversity.current_AT = slot_index
        else:
            character.adversity.current_AT = slot_index + 1

        character.validate()
        return True

    @staticmethod
    def set_current_AT(character: Character, amount: int) -> bool:
        character.adversity.current_AT = int(amount)
        character.validate()
        return True

    @staticmethod
    def set_max_AT(character: Character, amount: int) -> bool:
        character.adversity.max_AT = int(amount)
        character.validate()
        return True


class StatSystem:
    @staticmethod
    def set_die_size(character: Character, stat_name: str, die_size: int) -> bool:
        stat = character.stats.get_stat(stat_name)

        if stat is None or die_size not in VALID_DIE_SIZES:
            return False

        if (
            getattr(character, "creation_rules_active", False)
            and getattr(
                character,
                "creation_restrict_ability_dice_to_allowed_arrays",
                False,
            )
        ):
            allowed_ids = set(
                getattr(
                    character,
                    "creation_allowed_ability_array_ids",
                    [],
                )
            )

            if allowed_ids:
                from character_API import ABILITY_ARRAYS

                allowed_dice = {
                    int(candidate)
                    for ability_array in ABILITY_ARRAYS
                    if ability_array.get("id") in allowed_ids
                    for candidate in ability_array.get("dice", [])
                }

                if die_size not in allowed_dice:
                    return False

        stat.die_size = die_size
        character.validate()
        return True

    @staticmethod
    def set_bonus(character: Character, stat_name: str, bonus: int) -> bool:
        stat = character.stats.get_stat(stat_name)

        if stat is None:
            return False

        stat.bonus = max(0, int(bonus))
        character.validate()
        return True

    @staticmethod
    def set_free_heightened_stats(
        character: Character,
        stat_names: List[str]
    ) -> bool:
        clean_stats = [name for name in stat_names if name in STAT_NAMES]
        if len(clean_stats) > character.free_heightened_ability_slots:
            return False
        old = character.free_heightened_ability_stats
        for name in STAT_NAMES:
            if clean_stats.count(name) != old.count(name):
                if character.stats.get_stat(name).bonus > old.count(name):
                    return False
        old_cost = sum(old.count(name) * (old.count(name) - 1) // 2 for name in STAT_NAMES)
        new_cost = sum(clean_stats.count(name) * (clean_stats.count(name) - 1) // 2 for name in STAT_NAMES)
        if new_cost - old_cost > character.progression.available_IP:
            return False

        character.free_heightened_ability_stats = clean_stats
        character.validate()
        return True

    @staticmethod
    def heightened_ability_cost(character: Character, stat_name: str,
                               use_free: bool = False) -> int:
        stat = character.stats.get_stat(stat_name)
        if stat is None:
            raise ValueError("Unknown ability")
        used = len(character.free_heightened_ability_stats)
        if use_free and used < character.free_heightened_ability_slots:
            return stat.bonus
        return stat.bonus + 1

    @staticmethod
    def add_free_heightened_ability(
        character: Character,
        stat_name: str,
    ) -> bool:
        if stat_name not in STAT_NAMES:
            return False

        selections = character.free_heightened_ability_stats
        if len(selections) >= character.free_heightened_ability_slots:
            return False
        count = selections.count(stat_name)
        if character.stats.get_stat(stat_name).bonus != count:
            return False
        if count > character.progression.available_IP:
            return False

        character.free_heightened_ability_stats.append(stat_name)

        character.validate()
        return True


    @staticmethod
    def remove_free_heightened_ability(
        character: Character,
        stat_name: str,
    ) -> bool:
        if stat_name not in character.free_heightened_ability_stats:
            return False

        stat = character.stats.get_stat(stat_name)

        if stat is None:
            return False

        if stat.bonus > character.free_heightened_ability_stats.count(stat_name):
            return False

        stat.bonus -= 1

        character.free_heightened_ability_stats.remove(stat_name)

        character.validate()
        return True

    
# ============================================================
# Systems: Improvements
# ============================================================

class ImprovementCatalogSystem:
    @staticmethod
    def get_all_options(character: Optional[Character] = None) -> List[dict]:
        options = []

        for catalog_id, original in IMPROVEMENT_CATALOG.items():
            option = dict(original)
            if character is not None:
                override = getattr(
                    character,
                    "creation_improvement_overrides",
                    {},
                ).get(catalog_id, {})
                for key in ("name", "cost", "description"):
                    if key in override:
                        option[key] = override[key]
            options.append(option)

        if character is not None:
            options.extend(
                dict(item)
                for item in getattr(
                    character,
                    "creation_template_custom_improvements",
                    [],
                )
            )

        return options

    @staticmethod
    def get_option(
        catalog_id: str,
        character: Optional[Character] = None,
    ) -> Optional[dict]:
        if character is not None:
            for custom in getattr(
                character,
                "creation_template_custom_improvements",
                [],
            ):
                if custom.get("id") == catalog_id:
                    return dict(custom)

        original = IMPROVEMENT_CATALOG.get(catalog_id)
        if original is None:
            return None

        option = dict(original)
        if character is not None:
            override = getattr(
                character,
                "creation_improvement_overrides",
                {},
            ).get(catalog_id, {})
            for key in ("name", "cost", "description"):
                if key in override:
                    option[key] = override[key]
        return option

    @staticmethod
    def get_empowerment_groups(catalog_id: str) -> dict:
        option = IMPROVEMENT_CATALOG.get(catalog_id)
        if option is None:
            return {}
        return option.get("empowerment_groups", {})

    @staticmethod
    def get_simple_empowerments(catalog_id: str) -> list[dict]:
        option = IMPROVEMENT_CATALOG.get(catalog_id)
        if option is None:
            return []
        return option.get("empowerments", [])

    @staticmethod
    def get_all_tags() -> List[str]:
        tags = set()

        for option in IMPROVEMENT_CATALOG.values():
            for tag in option.get("tags", []):
                tags.add(tag)

        return sorted(tags)
    
class ImprovementSystem:

    @staticmethod
    def build_improvement_display(character: Character, improvement: Improvement) -> dict:

        if improvement.catalog_id == "custom":
            description = improvement.description.strip()

            if description:
                description = (
                    ImprovementSystem.highlight_important_description_text(
                        description
                    )
                )

            return {
                "name": improvement.name,
                "summary": description,
                "choices": [],
                "upgrades": [],
                "details": description,
            }

        option = ImprovementCatalogSystem.get_option(improvement.catalog_id, character)

        if option is None:
            return {
                "name": improvement.name,
                "summary": improvement.description,
                "choices": [],
                "upgrades": [],
                "details": improvement.description,
            }

        summary_template = (
            option.get("owned_summary")
            or option.get("owned_description")
            or option.get("summary")
            or option.get("description", "")
        )

        rules_template = (
            option.get("rules_text")
            or option.get("description", "")
        )
        
        choices = ImprovementSystem.build_choice_lines(improvement)
        upgrades = ImprovementSystem.build_upgrade_lines(improvement)

        summary = ImprovementSystem.format_custom_description(
            option,
            summary_template,
            improvement=improvement,
            choices=improvement.choices,
            character=character,
        )

        details = ImprovementSystem.format_custom_description(
            option,
            rules_template,
            improvement=improvement,
            choices=improvement.choices,
            character=character,
        )

        return {
            "name": improvement.name,
            "summary": summary,
            "choices": choices,
            "upgrades": upgrades,
            "details": details,
        }

    @staticmethod
    def pretty_choice_value(value) -> str:
        if value is None or value == "":
            return "Missing"

        return str(value).replace("_", " ").title()


    @staticmethod
    def build_choice_lines(improvement: Improvement) -> List[str]:
        choices = improvement.choices or {}

        if improvement.catalog_id == "born_of_soil":
            return ImprovementSystem._choice_lines_born_of_soil(improvement)

        if improvement.catalog_id == "spellcasting":
            return ImprovementSystem._choice_lines_spellcasting(improvement)

        if improvement.catalog_id == "animal_buddy":
            return ImprovementSystem._choice_lines_animal_buddy(improvement)

        if improvement.catalog_id == "sneak_attack":
            return ImprovementSystem._choice_lines_sneak_attack(improvement)

        return ImprovementSystem._choice_lines_generic(improvement)

    @staticmethod
    def _choice_lines_generic(improvement: Improvement) -> List[str]:
        choices = improvement.choices or {}
        lines = []

        pretty_names = {
            "buddy_name": "Name",
            "buddy_stat_d6": "d6",
            "buddy_stat_d8_a": "d8",
            "buddy_stat_d8_b": "d8",
            "buddy_stat_d10": "d10",
            "buddy_perk": "Perk",
            "magic_school": "School",
            "magic_school_description": "School Description",
            "specific_magic_effect": "Effect",
            "stat_name": "Stat",
            "attuned_land": "Land",
            "tell": "Tell",
            "deity_name": "Deity",
            "deity_domain": "Domain",
            "skill_name": "Skill",
            "skill_description": "Description",
            "artificer_item_description": "Item",
        }

        for key, value in choices.items():
            label = pretty_names.get(key, key.replace("_", " ").title())
            pretty_value = ImprovementSystem.pretty_choice_value(value)
            lines.append(f"{label}: {pretty_value}")

        return lines

    @staticmethod
    def _choice_lines_born_of_soil(improvement: Improvement) -> List[str]:
        choices = improvement.choices or {}
        lines = []

        lands = []

        primary_land = choices.get("attuned_land")
        if primary_land and primary_land != "Missing":
            lands.append(ImprovementSystem.pretty_choice_value(primary_land))

        for empowerment in improvement.empowerments:
            if empowerment.catalog_id != "additional_attuned_land":
                continue

            extra_land = empowerment.choices.get("attuned_land")
            if extra_land and extra_land != "Missing":
                lands.append(ImprovementSystem.pretty_choice_value(extra_land))

        lands_text = ", ".join(lands) if lands else "Missing"
        lines.append(f"Lands: {lands_text}")

        tell = choices.get("tell")
        tell_text = (
            ImprovementSystem.pretty_choice_value(tell)
            if tell and tell != "Missing"
            else "Missing Tell"
        )
        lines.append(f"Tell: {tell_text}")

        return lines


    @staticmethod
    def _choice_lines_spellcasting(improvement: Improvement) -> List[str]:
        choices = improvement.choices or {}
        lines = []

        primary_school = choices.get("magic_school")
        primary_description = choices.get("magic_school_description")

        if primary_school and primary_school != "Missing":
            school_text = ImprovementSystem.pretty_choice_value(primary_school)

            if primary_description and primary_description != "Missing":
                school_text += f": {primary_description}"

            lines.append(f"School: {school_text}")

        for empowerment in improvement.empowerments:
            if empowerment.group_id != "school_savant":
                continue

            extra_school = empowerment.choices.get("magic_school")
            extra_description = empowerment.choices.get("magic_school_description")

            if not extra_school or extra_school == "Missing":
                extra_school = "Missing"

            school_text = ImprovementSystem.pretty_choice_value(extra_school)

            if extra_description and extra_description != "Missing":
                school_text += f": {extra_description}"

            lines.append(f"Additional School: {school_text}")

        if not lines:
            lines.append("School: Missing")

        return lines

    @staticmethod
    def _choice_lines_animal_buddy(improvement: Improvement) -> List[str]:
        choices = improvement.choices or {}
        lines = []

        name = choices.get("buddy_name")
        name_text = (
            ImprovementSystem.pretty_choice_value(name)
            if name and name != "Missing"
            else "Unnamed Buddy"
        )

        perks = []

        base_perk = choices.get("buddy_perk")
        if base_perk and base_perk != "Missing":
            perks.append(ImprovementSystem.pretty_choice_value(base_perk))

        buddy_bonuses = {
            stat_name: 0
            for stat_name in STAT_NAMES
        }

        for empowerment in improvement.empowerments:
            if empowerment.catalog_id == "gifted":
                extra_perk = empowerment.choices.get("buddy_perk")
                if extra_perk and extra_perk != "Missing":
                    perks.append(
                        ImprovementSystem.pretty_choice_value(extra_perk)
                    )

            elif empowerment.catalog_id == "well_trained":
                stat_name = empowerment.choices.get(
                    "buddy_training_stat"
                )

                if stat_name in buddy_bonuses:
                    buddy_bonuses[stat_name] += 1

        perk_text = ", ".join(perks) if perks else "Missing"
        lines.append(f"Name: {name_text} | Perks: {perk_text}")

        buddy_dice = {
            stat_name: 4
            for stat_name in STAT_NAMES
        }

        assigned_dice = [
            (choices.get("buddy_stat_d10"), 10),
            (choices.get("buddy_stat_d8_a"), 8),
            (choices.get("buddy_stat_d8_b"), 8),
            (choices.get("buddy_stat_d6"), 6),
        ]

        for stat_name, die_size in assigned_dice:
            if (
                stat_name
                and stat_name != "Missing"
                and stat_name in buddy_dice
            ):
                buddy_dice[stat_name] = die_size

        stat_parts = []

        for stat_name in STAT_NAMES:
            die_size = buddy_dice[stat_name]
            bonus = buddy_bonuses.get(stat_name, 0)

            bonus_text = f"+{bonus}" if bonus else ""

            stat_parts.append(
                f"{ImprovementSystem.pretty_choice_value(stat_name)} "
                f"d{die_size}{bonus_text}"
            )

        lines.append(
            "Stats: " + "  |  ".join(stat_parts)
        )

        return lines

    @staticmethod
    def _choice_lines_sneak_attack(improvement: Improvement) -> List[str]:
        effects = []

        for empowerment in improvement.empowerments:
            if empowerment.catalog_id == "hobbled":
                effects.append("Hobbled")
            elif empowerment.catalog_id == "drop_item":
                effects.append("Drop Item")
            elif empowerment.catalog_id == "drooling":
                effects.append("Stunned And Drooling")

        effects_text = ", ".join(effects) if effects else "Base Effects Only"

        return [f"Extra Effects: {effects_text}"]
    
    @staticmethod
    def build_upgrade_lines(improvement: Improvement) -> List[str]:
        hidden_in_choices = {
            "additional_attuned_land",
            "school_savant",
            "hobbled",
            "drop_item",
            "drooling",
            "gifted",
            "well_trained",
        }

        lines = []

        for empowerment in improvement.empowerments:
            if (
                empowerment.catalog_id in hidden_in_choices
                or empowerment.group_id in hidden_in_choices
            ):
                continue

            text = empowerment.name

            if empowerment.choices:
                choice_parts = []

                for key, value in empowerment.choices.items():
                    pretty_key = key.replace("_", " ").title()
                    pretty_value = ImprovementSystem.pretty_choice_value(value)
                    choice_parts.append(f"{pretty_key}: {pretty_value}")

                if choice_parts:
                    text += " — " + " | ".join(choice_parts)


            description = empowerment.description.strip()

            if description:
                if "<br>" not in description and "<span" not in description:
                    description = ImprovementSystem.highlight_important_description_text(
                        description
                )

                text += f"<br>{description}"

            lines.append(text)

        return lines
    
    @staticmethod
    def has_improvement(character: Character, catalog_id: str) -> bool:
        return character.improvements.has_catalog_id(catalog_id)

    @staticmethod
    def count_improvement(character: Character, catalog_id: str) -> int:
        return character.improvements.count_by_catalog_id(catalog_id)

    @staticmethod
    def get_taken_improvement(
        character: Character,
        catalog_id: str,
    ) -> Optional[Improvement]:
        return character.improvements.get_first_by_catalog_id(catalog_id)

    @staticmethod
    def get_base_purchase_count(character: Character, catalog_id: str) -> int:
        return character.improvements.count_by_catalog_id(catalog_id)

    @staticmethod
    def get_base_cost(character: Character, option: dict) -> int:
        purchase_rule = option.get("purchase_rule", "single")

        if purchase_rule == "stat_bonus_scaling":
            return min(stat.bonus + 1 for stat in character.stats.as_dict().values())

        if purchase_rule == "repeatable_scaling":
            catalog_id = option["id"]
            times_taken = ImprovementSystem.get_base_purchase_count(
                character,
                catalog_id,
            )
            return int(option["base_cost"]) + times_taken * int(option["cost_increase"])

        return int(option.get("cost", 0))

    @staticmethod
    def format_improvement_description(
        option: dict,
        improvement: Optional[Improvement] = None,
        times_taken: int = 1,
        choices: Optional[Dict[str, Any]] = None,
        use_owned_description: bool = False,
        character=None
    ) -> str:
        
        if use_owned_description:
            description = option.get("owned_description") or option.get("description", "")
        else:
            description = option.get("description", "")
            
        values = dict(option.get("scaling_values", {}))

        if option.get("id") == "animal_buddy" and character is not None:
            values["buddy_bdv"] = math.ceil(character.BDV / 2)

        if choices:
            values.update(choices)

        if improvement is not None:
            times_taken = getattr(improvement, "times_taken", times_taken)

            if improvement.choices:
                values.update(improvement.choices)

        if option.get("purchase_rule") == "repeatable_scaling":
            values["times_taken"] = times_taken

            value_key = option.get("value_key")
            base_value = int(option.get("base_value", 1))
            increase_by = int(option.get("increase_by", 1))

            if value_key:
                values[value_key] = base_value + ((times_taken - 1) * increase_by)

        if improvement is not None:
            scaling_empowerments = option.get("scaling_empowerments", {})

            for group_id, group in scaling_empowerments.items():
                taken = [
                    empowerment
                    for empowerment in improvement.empowerments
                    if empowerment.group_id == group_id
                ]

                if not taken:
                    continue

                rule = group.get("rule", "ordered")

                if rule == "ordered":
                    step_index = len(taken) - 1
                    steps = group.get("steps", [])

                    if step_index < 0 or step_index >= len(steps):
                        continue

                    step = steps[step_index]
                    step_value = step.get("value")

                    value_key = group.get("value_key", group_id)
                    values[value_key] = step_value

                    text_value_key = group.get("text_value_key")
                    if text_value_key:
                        values[text_value_key] = step.get("text_value", "")

                    updates = group.get("updates", {})

                    if step_value in updates:
                        values.update(updates[step_value])

                elif rule == "repeatable_scaling":
                    count = len(taken)

                    value_key = group.get("value_key", group_id)
                    increase_by = int(group.get("increase_by", 1))

                    base_value = values.get(value_key, 0)

                    try:
                        base_value = int(base_value)
                    except Exception:
                        base_value = 0

                    values[value_key] = base_value + (count * increase_by)

        try:
            formatted_description = description.format(**values)
        except Exception:
            formatted_description = description

        return ImprovementSystem.highlight_important_description_text(
            formatted_description
        )
    
    @staticmethod
    def format_improvement_name(
        option: dict,
        choices: Optional[Dict[str, Any]] = None,
    ) -> str:
        name = option.get("name", "").replace("...", "").strip()
        choices = choices or {}

        if option.get("id") == "skilled_at":
            skill_name = choices.get("skill_name")

            if skill_name and skill_name != "Missing":
                return f"{name}: {skill_name}"

        return name
    
    @staticmethod
    def format_empowerment_description(
        parent_option: dict,
        group_id: str,
        description: str,
        current_count: int = 1,
    ) -> str:
        values = dict(parent_option.get("scaling_values", {}))

        scaling_group = parent_option.get("scaling_empowerments", {}).get(group_id)

        if scaling_group is not None:
            value_key = scaling_group.get("value_key", group_id)

            if scaling_group.get("rule") == "repeatable_scaling":
                increase_by = int(scaling_group.get("increase_by", 1))
                base_value = values.get(value_key, 0)

                try:
                    base_value = int(base_value)
                except Exception:
                    base_value = 0

                values[value_key] = base_value + (current_count * increase_by)

        try:
            formatted = description.format(**values)
        except Exception:
            formatted = description

        return ImprovementSystem.highlight_important_description_text(formatted)

    @staticmethod
    def highlight_important_description_text(text: str) -> str:
        """Preserve authored HTML and emphasize relevant mechanics in plain text.

        The approved editor catalog contains plain owned-descriptions even when
        the corresponding buying descriptions have hand-authored <b> markup.
        Apply limited, readable mechanics emphasis to those summaries without
        modifying their saved source text or doubling existing markup.
        """
        text = str(text or "").replace("\n", "<br>")
        important = re.compile(
            r"(?<![\w{])(?:"
            r"\d+d(?:4|6|8|10|12|20|100)|"
            r"d(?:4|6|8|10|12|20|100)|"
            r"\+\d+\s+(?:HP|AT|IP)|"
            r"\d+\s+(?:HP|AT|IP)|"
            r"(?:very close|close|far|very far) range|"
            r"advantage|disadvantage|"
            r"(?:spend|gain|clear|mark)\s+AT|"
            r"(?:Agility|Strength|Finesse|Instinct|Presence|Knowledge)|"
            r"(?:Hearts?|Adversity Tokens|Improvement Points)"
            r")(?![\w}])",
            re.IGNORECASE,
        )
        pieces = re.split(
            r"(<(?:b|strong)\b[^>]*>.*?</(?:b|strong)>|<[^>]+>)",
            text,
            flags=re.IGNORECASE | re.DOTALL,
        )
        return "".join(
            piece if piece.startswith("<") else important.sub(
                lambda match: "<b>" + match.group(0) + "</b>", piece
            )
            for piece in pieces
        )

    @staticmethod
    def refresh_improvement_descriptions(character: Character) -> None:
        for improvement in character.improvements.list_of_taken_improvements:

            # Custom improvements keep their own name and description.
            if improvement.catalog_id == "custom":
                continue

            option = ImprovementCatalogSystem.get_option(improvement.catalog_id, character)

            if option is None:
                continue

            improvement.name = ImprovementSystem.format_improvement_name(
                option,
                improvement.choices,
            )

            # Legacy saved/display field. UI should use build_improvement_display().
            improvement.description = ImprovementSystem.format_improvement_description(
                option,
                improvement=improvement,
                times_taken=getattr(improvement, "times_taken", 1),
                choices=improvement.choices,
                use_owned_description=True,
                character=character,
            )

            scaling_groups = option.get("scaling_empowerments", {})

            for group_id, group in scaling_groups.items():
                count = 0

                for empowerment in improvement.empowerments:
                    if empowerment.group_id != group_id:
                        continue

                    count += 1

                    empowerment.description = (
                        ImprovementSystem.format_empowerment_description(
                            option,
                            group_id,
                            group.get("description", empowerment.description),
                            count,
                        )
                    )


    @staticmethod
    def can_buy_base(character: Character, option: dict) -> bool:
        catalog_id = option["id"]

        if getattr(
            character, "creation_rules_active",
            False,
        ):
            if catalog_id == "custom":
                if not getattr(
                    character,
                    "creation_allow_custom_improvements",
                    True,
                ):
                    return False
            else:
                mode = getattr(
                    character,
                    "creation_improvement_mode",
                    "all",
                )

                selected_ids = set(
                    getattr(
                        character,
                        "creation_improvement_ids",
                        [],
                    )
                )

                if (
                    mode == "allow_only"
                    and catalog_id not in selected_ids
                ):
                    return False

                if (
                    mode == "ban"
                    and catalog_id in selected_ids
                ):
                    return False

        
        purchase_rule = option.get("purchase_rule", "single")
        times_taken = ImprovementSystem.get_base_purchase_count(character, catalog_id)

        if purchase_rule == "single" and times_taken > 0:
            return False

        if purchase_rule == "repeatable_scaling":
            max_times = int(option.get("max_times", 999))
            if times_taken >= max_times:
                return False

        if purchase_rule == "repeatable":
            pass

        if purchase_rule == "stat_bonus_scaling":
            return min(stat.bonus + 1 for stat in character.stats.as_dict().values()) <= character.progression.available_IP

        cost = ImprovementSystem.get_base_cost(character, option)
        return cost <= character.progression.available_IP

    @staticmethod
    def add_from_catalog(
        character: Character,
        catalog_id: str,
        choices: Optional[Dict[str, Any]] = None,
        source: str = "ip",
    ) -> bool:
        option = ImprovementCatalogSystem.get_option(catalog_id, character)
        if option is None:
            return False

        if source == "ip" and not ImprovementSystem.can_buy_base(character, option):
            return False

        cost = ImprovementSystem.get_base_cost(character, option)
        if catalog_id == "heightened_ability":
            stat_name = (choices or {}).get("stat_name")
            if stat_name not in STAT_NAMES:
                return False
            cost = StatSystem.heightened_ability_cost(character, stat_name)
            if source == "ip" and cost > character.progression.available_IP:
                return False

        if source == "species":
            # Species is a *source*, not a free second copy of an Improvement.
            # The picker hides already-owned entries, but imports/mobile calls
            # must obey the same rule even if they bypass the picker.
            if cost not in (1, 2):
                return False
            if option.get("purchase_rule", "single") != "single":
                return False
            if character.improvements.has_species_improvement():
                return False
            if character.improvements.get_first_by_catalog_id(catalog_id) is not None:
                return False
            
        purchase_rule = option.get("purchase_rule", "single")

        if source == "ip" and purchase_rule == "repeatable_scaling":
            existing = character.improvements.get_first_by_catalog_id(option["id"])

            if existing is not None:
                existing.cost += cost
                existing.times_taken = getattr(existing, "times_taken", 1) + 1
                existing.description = ImprovementSystem.format_improvement_description(
                    option=option,
                    improvement=existing,
                    times_taken=existing.times_taken,
                    choices=existing.choices,
                )
                character.validate()
                return True

        character.improvements.list_of_taken_improvements.append(
            Improvement(
                id=str(uuid4()),
                catalog_id=option["id"],
                name=ImprovementSystem.format_improvement_name(
                    option,
                    choices or {},
                ),
                cost=cost,
                description=ImprovementSystem.format_improvement_description(
                    option,
                    times_taken=1,
                    choices=choices or {},
                ),
                source=source,
                choices=choices or {},
                expanded=False,
                times_taken=1,
                sort_order=len(character.improvements.list_of_taken_improvements),
            )
        )

        character.validate()
        return True

    @staticmethod
    def add_species_from_catalog(character: Character, catalog_id: str) -> bool:
        return ImprovementSystem.add_from_catalog(
            character=character,
            catalog_id=catalog_id,
            choices=None,
            source="species",
        )

    @staticmethod
    def can_remove_heightened(character: Character, improvement: Improvement) -> bool:
        if improvement.catalog_id != "heightened_ability":
            return True
        stat = character.stats.get_stat(improvement.choices.get("stat_name"))
        return stat is not None and improvement.cost == stat.bonus

    @staticmethod
    def remove_improvement(character: Character, improvement_id: str) -> bool:
        for improvement in character.improvements.list_of_taken_improvements:
            if improvement.id != improvement_id:
                continue

            if not ImprovementSystem.can_remove_heightened(character, improvement):
                return False

            option = ImprovementCatalogSystem.get_option(improvement.catalog_id, character)

            if (
                option is not None
                and option.get("purchase_rule") == "repeatable_scaling"
                and getattr(improvement, "times_taken", 1) > 1
            ):
                times_taken = getattr(improvement, "times_taken", 1)

                last_cost = (
                    int(option.get("base_cost", improvement.cost))
                    + (times_taken - 1) * int(option.get("cost_increase", 0))
                )

                improvement.times_taken = times_taken - 1
                improvement.cost = max(0, improvement.cost - last_cost)

                character.validate()
                return True

            character.improvements.remove(improvement_id)
            character.validate()
            return True

        return False

    @staticmethod
    def reorder_improvements(
        character: Character,
        ordered_ids: List[str],
    ) -> bool:
        current = list(character.improvements.list_of_taken_improvements)
        by_id = {improvement.id: improvement for improvement in current}
        clean_ids = []
        for improvement_id in ordered_ids:
            improvement_id = str(improvement_id)
            if improvement_id in by_id and improvement_id not in clean_ids:
                clean_ids.append(improvement_id)

        new_order = [by_id[improvement_id] for improvement_id in clean_ids]
        new_order.extend(
            improvement
            for improvement in current
            if improvement.id not in clean_ids
        )

        if new_order == current:
            return False

        for index, improvement in enumerate(new_order):
            improvement.sort_order = index

        character.improvements.list_of_taken_improvements = new_order
        character.validate()
        return True


    @staticmethod
    def toggle_expanded(character: Character, improvement_id: str) -> bool:
        for improvement in character.improvements.list_of_taken_improvements:
            if improvement.id == improvement_id:
                improvement.expanded = not improvement.expanded
                character.validate()
                return True

        return False

    @staticmethod
    def _get_taken_ids_by_group(improvement: Improvement) -> Dict[str, List[str]]:
        already_taken_ids_by_group: Dict[str, List[str]] = {}

        for empowerment in improvement.empowerments:
            already_taken_ids_by_group.setdefault(
                empowerment.group_id,
                [],
            ).append(empowerment.catalog_id)

        return already_taken_ids_by_group

    @staticmethod
    def _make_empowerment_purchase(
        taken_improvement: Improvement,
        parent_option: dict,
        group_id: str,
        empowerment_id: str,
        name: str,
        cost: int,
        description: str,
        requires_choices: Optional[List[str]] = None,
        effects: Optional[List[dict]] = None,
        include_parent_name: bool = True,
        tags: Optional[List[str]] = None,
    ) -> dict:
        display_name = (
            f"{parent_option['name']} -> {name}"
            if include_parent_name
            else name
        )

        # Empowerments always inherit their parent's tags.
        # They may also add their own more specific tags.
        combined_tags = list(
            dict.fromkeys(
                parent_option.get("tags", [])
                + (tags or [])
            )
        )
        
        return {
            "kind": "empowerment",
            "improvement_id": taken_improvement.id,
            "parent_catalog_id": taken_improvement.catalog_id,
            "group_id": group_id,
            "catalog_id": empowerment_id,
            "name": display_name,
            "cost": cost,
            "description": description,
            "requires_choices": requires_choices or [],
            "effects": effects or [],
            "tags": combined_tags,
        }
    
    @staticmethod
    def get_available_purchases(character: Character) -> List[dict]:
        purchases: List[dict] = []

        for option in ImprovementCatalogSystem.get_all_options(character):
            catalog_id = option.get("id")
            if not catalog_id:
                continue
            taken_improvements = character.improvements.get_by_catalog_id(catalog_id)
            taken_improvement = taken_improvements[0] if taken_improvements else None

            if catalog_id == "heightened_ability":
                free_used = len(character.free_heightened_ability_stats)
                free_total = character.free_heightened_ability_slots

                if free_used < free_total:
                    continue

            if ImprovementSystem.can_buy_base(character, option):
                cost = ImprovementSystem.get_base_cost(character, option)

                purchases.append(
                    {
                        "kind": "base",
                        "catalog_id": catalog_id,
                        "name": option["name"],
                        "cost": cost,
                        "description": ImprovementSystem.format_improvement_description(
                            option,
                            times_taken=ImprovementSystem.get_base_purchase_count(character, catalog_id) + 1,
                            choices={},
                        ),
                        "requires_choices": option.get("requires_choices", []),
                        "effects": option.get("effects", []),
                        "tags": option.get("tags", []),
                    }
                )

            if taken_improvement is None:
                continue
            
            simple_empowerments = option.get("empowerments", [])

            already_taken_simple_ids = {
                empowerment.catalog_id
                for empowerment in taken_improvement.empowerments
                if empowerment.group_id == "simple"
            }
            
            for empowerment_option in simple_empowerments:
                empowerment_id = empowerment_option["id"]

                if empowerment_id in already_taken_simple_ids:
                    continue

                cost = int(empowerment_option.get("cost", 0))

                if cost <= character.progression.available_IP:
                    purchases.append(
                        ImprovementSystem._make_empowerment_purchase(
                            taken_improvement=taken_improvement,
                            parent_option=option,
                            group_id="simple",
                            empowerment_id=empowerment_id,
                            name=empowerment_option["name"],
                            cost=cost,
                            description=empowerment_option.get("description", ""),
                            requires_choices=empowerment_option.get("requires_choices", []),
                            effects=empowerment_option.get("effects", []),
                            include_parent_name=True,
                            tags=empowerment_option.get("tags", []),
                        )
                    )
                    

            already_taken_ids_by_group = ImprovementSystem._get_taken_ids_by_group(
                taken_improvement
            )

            groups = option.get("empowerment_groups", {})

            for group_id, group in groups.items():
                rule = group.get("rule", "any")
                already_taken_ids = already_taken_ids_by_group.get(group_id, [])

                if rule == "ordered":
                    for empowerment_option in group.get("options", []):
                        if empowerment_option["id"] in already_taken_ids:
                            continue

                        cost = int(empowerment_option.get("cost", 0))

                        if cost <= character.progression.available_IP:
                            purchases.append(
                                ImprovementSystem._make_empowerment_purchase(
                                    taken_improvement=taken_improvement,
                                    parent_option=option,
                                    group_id=group_id,
                                    empowerment_id=empowerment_option["id"],
                                    name=empowerment_option["name"],
                                    cost=cost,
                                    description=ImprovementSystem.format_empowerment_description(
                                        option,
                                        group_id,
                                        group.get("description", ""),
                                        len(already_taken_ids) + 1,
                                    ),
                                    requires_choices=empowerment_option.get(
                                        "requires_choices",
                                        [],
                                    ),
                                    effects=empowerment_option.get("effects", []),
                                )
                            )

                        break


                elif rule == "any":
                    for empowerment_option in group.get("options", []):
                        # Well Trained is repeatable per buddy ability.
                        # Each ability has its own escalating cost:
                        # +1 costs 1 IP, +2 costs 2 IP, +3 costs 3 IP, etc.
                        if (
                            taken_improvement.catalog_id == "animal_buddy"
                            and empowerment_option.get("id") == "well_trained"
                        ):
                            owned_well_trained = [
                                empowerment
                                for empowerment in taken_improvement.empowerments
                                if empowerment.catalog_id == "well_trained"
                            ]

                            stat_counts = {
                                stat_name: 0
                                for stat_name in STAT_NAMES
                            }

                            for empowerment in owned_well_trained:
                                stat_name = empowerment.choices.get(
                                    "buddy_training_stat"
                                )

                                if stat_name in stat_counts:
                                    stat_counts[stat_name] += 1

                            # The exact cost depends on the ability chosen in
                            # the dialog. Show the cheapest currently possible
                            # cost in the picker; the frontend replaces it with
                            # the exact selected-ability cost before purchase.
                            next_cost = min(
                                count + 1
                                for count in stat_counts.values()
                            )

                            if next_cost <= character.progression.available_IP:
                                purchases.append(
                                    ImprovementSystem._make_empowerment_purchase(
                                        taken_improvement=taken_improvement,
                                        parent_option=option,
                                        group_id=group_id,
                                        empowerment_id="well_trained",
                                        name=empowerment_option.get(
                                            "name",
                                            "Well Trained",
                                        ),
                                        cost=next_cost,
                                        description=empowerment_option.get(
                                            "description",
                                            "",
                                        ),
                                        requires_choices=[
                                            "buddy_training_stat",
                                        ],
                                        effects=empowerment_option.get(
                                            "effects",
                                            [],
                                        ),
                                        include_parent_name=True,
                                        tags=empowerment_option.get(
                                            "tags",
                                            [],
                                        ),
                                    )
                                )

                            continue

                        if empowerment_option["id"] in already_taken_ids:
                            continue

                        cost = int(empowerment_option.get("cost", 0))

                        if cost <= character.progression.available_IP:
                            purchases.append(
                                ImprovementSystem._make_empowerment_purchase(
                                    taken_improvement=taken_improvement,
                                    parent_option=option,
                                    group_id=group_id,
                                    empowerment_id=empowerment_option["id"],
                                    name=empowerment_option["name"],
                                    cost=cost,
                                    description=empowerment_option.get("description", ""),
                                    requires_choices=empowerment_option.get(
                                        "requires_choices",
                                        [],
                                    ),
                                    effects=empowerment_option.get("effects", []),
                                    include_parent_name=True,
                                    tags=empowerment_option.get("tags", []),
                                )
                            )

                elif rule == "repeatable":
                    options = group.get("options", [])
                    next_number = len(already_taken_ids) + 1

                    if options:
                        empowerment_option = options[0]
                        
                        cost = int(empowerment_option.get("cost", 0))
                        empowerment_id = f"{empowerment_option['id']}_{next_number}"
                        name = f"{empowerment_option['name']} #{next_number}"
                        description = empowerment_option.get("description", "")
                        requires_choices = empowerment_option.get("requires_choices", [])
                        effects = empowerment_option.get("effects", [])

                    else:
                        cost = int(group.get("cost", 0))
                        empowerment_id = f"{group_id}_{next_number}"
                        name = f"{group['name']} #{next_number}"
                        description = group.get("description", "")
                        requires_choices = group.get("requires_choices", [])
                        effects = group.get("effects", [])

                    if cost <= character.progression.available_IP:
                        purchases.append(
                            ImprovementSystem._make_empowerment_purchase(
                                taken_improvement=taken_improvement,
                                parent_option=option,
                                group_id=group_id,
                                empowerment_id=empowerment_id,
                                name=name,
                                cost=cost,
                                description=description,
                                requires_choices=requires_choices,
                                effects=effects,
                                include_parent_name=True,
                            )
                        )

                elif rule == "repeatable_scaling":
                    times_taken = len(already_taken_ids)
                    max_times = int(group.get("max_times", 5))

                    if times_taken >= max_times:
                        continue

                    cost = (
                        int(group["base_cost"])
                        + times_taken * int(group["cost_increase"])
                    )

                    if cost <= character.progression.available_IP:
                        purchases.append(
                            ImprovementSystem._make_empowerment_purchase(
                                taken_improvement=taken_improvement,
                                parent_option=option,
                                group_id=group_id,
                                empowerment_id=f"{group_id}_{times_taken + 1}",
                                name=f"{group['name']} #{times_taken + 1}",
                                cost=cost,
                                description=ImprovementSystem.format_empowerment_description(
                                    option,
                                    group_id,
                                    group.get("description", ""),
                                    times_taken + 1,
                                ),
                                requires_choices=group.get("requires_choices", []),
                                effects=group.get("effects", []),
                            )
                        )

                elif rule == "single":
                    if already_taken_ids:
                        continue

                    cost = int(group.get("cost", 0))

                    if cost <= character.progression.available_IP:
                        purchases.append(
                            ImprovementSystem._make_empowerment_purchase(
                                taken_improvement=taken_improvement,
                                parent_option=option,
                                group_id=group_id,
                                empowerment_id=group_id,
                                name=group["name"],
                                cost=cost,
                                description=group.get("description", ""),
                                requires_choices=group.get("requires_choices", []),
                                effects=group.get("effects", []),
                                include_parent_name=True
                            )
                        )
            scaling_groups = option.get("scaling_empowerments", {})

            for group_id, group in scaling_groups.items():
                rule = group.get("rule", "ordered")

                already_taken = [
                    empowerment
                    for empowerment in taken_improvement.empowerments
                    if empowerment.group_id == group_id
                ]

                if rule == "ordered":
                    steps = group.get("steps", [])
                    next_index = len(already_taken)

                    if next_index >= len(steps):
                        continue

                    step = steps[next_index]
                    cost = int(step.get("cost", 0))

                    if cost <= character.progression.available_IP:
                        value = step.get("value")

                        display_value = value

                        if isinstance(value, int) and "die" in group_id:
                            display_value = f"d{value}"
                                
                        name = group.get(
                            "name",
                            group_id.replace("_", " ").title(),
                        )
                        if next_index > 0:
                            current_value = steps[next_index - 1].get("value")
                        else:
                            value_key = group.get("value_key", group_id)
                            current_value = option.get("scaling_values", {}).get(value_key)

                        new_value = step.get("value")

                        simple_description = (
                            f"Increase your {name} from {current_value} to {new_value}."
                        )

                        purchases.append(
                            ImprovementSystem._make_empowerment_purchase(
                                taken_improvement=taken_improvement,
                                parent_option=option,
                                group_id=group_id,
                                empowerment_id=f"{group_id}_{value}",
                                name=f"{name} -> {display_value}",
                                cost=cost,
                                description=ImprovementSystem.highlight_important_description_text(
                                    simple_description
                                ),
                                requires_choices=group.get("requires_choices", []),
                                effects=step.get("effects", []),
                                include_parent_name=True,
                            )
                        )

                elif rule == "repeatable_scaling":
                    times_taken = len(already_taken)
                    max_times = int(group.get("max_times", 999))

                    if times_taken >= max_times:
                        continue

                    cost = (
                        int(group.get("base_cost", 0))
                        + times_taken * int(group.get("cost_increase", 0))
                    )

                    if cost <= character.progression.available_IP:
                        name = group.get(
                            "name",
                            group_id.replace("_", " ").title(),
                        )

                        purchases.append(
                            ImprovementSystem._make_empowerment_purchase(
                                taken_improvement=taken_improvement,
                                parent_option=option,
                                group_id=group_id,
                                empowerment_id=f"{group_id}_{times_taken + 1}",
                                name=f"{name} #{times_taken + 1}",
                                cost=cost,
                                description=ImprovementSystem.format_empowerment_description(
                                    option,
                                    group_id,
                                    group.get("description", ""),
                                    times_taken + 1,
                                ),
                                requires_choices=group.get("requires_choices", []),
                                effects=group.get("effects", []),
                            )
                        )

        return purchases
    
    @staticmethod
    def get_species_options(character: Character) -> List[dict]:
        options = []

        if (
            getattr(
                character,
                "creation_rules_active",
                False,
            )
            and getattr(
                character,
                "creation_species_mode",
                "normal",
            ) == "disabled"
        ):
            return options

        if character.improvements.has_species_improvement():
            return options

        owned_catalog_ids = {
            improvement.catalog_id
            for improvement in character.improvements.list_of_taken_improvements
        }
        for option in ImprovementCatalogSystem.get_all_options(character):
            catalog_id = option.get("id")
            if not catalog_id or catalog_id in owned_catalog_ids:
                continue
            cost = int(option.get("cost", 0))

            if cost not in (1, 2):
                continue

            purchase_rule = option.get("purchase_rule", "single")

            if purchase_rule != "single":
                continue

            options.append(
                {
                    "kind": "species",
                    "catalog_id": catalog_id,
                    "name": option["name"],
                    "cost": cost,
                    "description": option.get("description", ""),
                    "requires_choices": option.get("requires_choices", []),
                    "tags": option.get("tags", [])
                }
            )

        return sorted(options, key=lambda item: item["name"])


    @staticmethod
    def buy_purchase(
        character: Character,
        purchase: dict,
        choices: Optional[Dict[str, Any]] = None,
    ) -> bool:
        if int(purchase["cost"]) > character.progression.available_IP:
            return False

        # Custom improvement
        if purchase["kind"] == "custom":
            character.improvements.list_of_taken_improvements.append(
                Improvement(
                    id=str(uuid4()),
                    catalog_id="custom",
                    name=purchase["name"],
                    cost=int(purchase["cost"]),
                    description=purchase.get("description", ""),
                    source="ip",
                    choices={},
                    expanded=False,
                    times_taken=1,
                )
            )
            character.validate()
            return True

        # Normal catalog improvement
        if purchase["kind"] == "base":
            return ImprovementSystem.add_from_catalog(
                character=character,
                catalog_id=purchase["catalog_id"],
                choices=choices,
                source="ip",
            )

        if purchase["kind"] == "empowerment":
            for improvement in character.improvements.list_of_taken_improvements:
                if improvement.id != purchase["improvement_id"]:
                    continue

                if purchase.get("catalog_id") == "upgrade_to_spellcasting":
                    return ImprovementSystem.upgrade_magic_novice_to_spellcasting(
                        character=character,
                        magic_novice=improvement,
                        purchase=purchase,
                        choices=choices or {},
                    )

                improvement.empowerments.append(
                    TakenEmpowerment(
                        id=str(uuid4()),
                        group_id=purchase["group_id"],
                        catalog_id=purchase["catalog_id"],
                        name=purchase["name"],
                        cost=int(purchase["cost"]),
                        description=purchase.get("description", ""),
                        source="ip",
                        choices=choices or {},
                    )
                )

                character.validate()
                return True

        return False

    @staticmethod
    def upgrade_magic_novice_to_spellcasting(
        character: Character,
        magic_novice: Improvement,
        purchase: dict,
        choices: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Replace Magic Novice with Spellcasting.

        Preserves the IP already spent on Magic Novice and converts any
        owned Magic Novice die upgrades into their Spellcasting versions.
        """

        if magic_novice.catalog_id != "magic_novice":
            return False

        spellcasting_option = ImprovementCatalogSystem.get_option(
            "spellcasting",
            character,
        )

        if spellcasting_option is None:
            return False

        choices = dict(choices or {})

        # ------------------------------------------------------------
        # Build the new Spellcasting choices
        # ------------------------------------------------------------

        spellcasting_choices = {
            "magic_school": choices.get(
                "magic_school",
                "Missing",
            ),
            "magic_school_description": choices.get(
                "magic_school_description",
                "Missing",
            ),
        }

        # Preserve the casting stat if older character files contain it.
        old_stat = (
            magic_novice.choices.get("spellcasting_stat")
            or magic_novice.choices.get("spellcasing_stat")
        )

        if old_stat:
            spellcasting_choices["spellcasting_stat"] = old_stat

        # ------------------------------------------------------------
        # Create Spellcasting with the combined base cost:
        #
        # Magic Novice base cost + Upgrade empowerment cost
        # ------------------------------------------------------------

        new_spellcasting = Improvement(
            id=str(uuid4()),
            catalog_id="spellcasting",
            name=spellcasting_option.get(
                "name",
                "Spellcasting",
            ),
            cost=(
                int(magic_novice.cost)
                + int(purchase.get("cost", 0))
            ),
            description=spellcasting_option.get(
                "description",
                "",
            ),
            source=magic_novice.source,
            choices=spellcasting_choices,
            expanded=magic_novice.expanded,
            times_taken=1,
        )

        # ------------------------------------------------------------
        # Convert Magic Novice Magic Die empowerments
        #
        # Magic Die scaling is ordered. Convert by owned rank rather
        # than relying on historical catalog-id formats.
        #
        # This supports both current files and older files whose
        # empowerment IDs used a different naming convention.
        # The ORIGINAL cost is preserved so upgrading never refunds
        # or re-charges IP already spent on Magic Dice.
        # ------------------------------------------------------------

        spellcasting_magic_group = (
            spellcasting_option
            .get("scaling_empowerments", {})
            .get("magic_die", {})
        )

        spellcasting_steps = (
            spellcasting_magic_group.get(
                "steps",
                []
            )
        )

        old_magic_die_empowerments = [
            empowerment
            for empowerment in magic_novice.empowerments
            if empowerment.group_id == "magic_die"
        ]

        for index, old_empowerment in enumerate(
            old_magic_die_empowerments
        ):
            if index >= len(
                spellcasting_steps
            ):
                break

            step = spellcasting_steps[
                index
            ]

            die_size = step.get(
                "value"
            )

            new_catalog_id = (
                f"magic_die_{die_size}"
                if die_size is not None
                else old_empowerment.catalog_id
            )

            new_spellcasting.empowerments.append(
                TakenEmpowerment(
                    id=str(uuid4()),
                    group_id="magic_die",
                    catalog_id=new_catalog_id,
                    name=(
                        f"Magic Die -> d{die_size}"
                        if die_size is not None
                        else old_empowerment.name
                    ),
                    cost=int(
                        old_empowerment.cost
                    ),
                    description=step.get(
                        "text_value",
                        old_empowerment.description,
                    ),
                    source=old_empowerment.source,
                    choices=dict(
                        old_empowerment.choices
                    ),
                )
            )
        # ------------------------------------------------------------
        # Replace Magic Novice in the same list position
        # ------------------------------------------------------------

        improvements = (
            character.improvements
            .list_of_taken_improvements
        )

        try:
            index = improvements.index(
                magic_novice
            )
        except ValueError:
            return False

        improvements[index] = new_spellcasting

        character.validate()
        return True

    @staticmethod
    def format_custom_description(
        option: dict,
        description: str,
        improvement=None,
        choices=None,
        character=None,
    ) -> str:
        original_description = option.get("description", "")

        option = dict(option)
        option["description"] = description

        result = ImprovementSystem.format_improvement_description(
            option,
            improvement=improvement,
            choices=choices,
            use_owned_description=False,
            character=character,
        )

        option["description"] = original_description
        return result

    @staticmethod
    def get_empowerment_group_rule(parent_option: dict, group_id: str) -> str:
        if group_id in parent_option.get("scaling_empowerments", {}):
            return parent_option["scaling_empowerments"][group_id].get("rule", "ordered")

        if group_id in parent_option.get("empowerment_groups", {}):
            return parent_option["empowerment_groups"][group_id].get("rule", "any")

        return "any"

    @staticmethod
    def remove_empowerment(
        character: Character,
        improvement_id: str,
        empowerment_id: str,
    ) -> bool:
        for improvement in character.improvements.list_of_taken_improvements:
            if improvement.id != improvement_id:
                continue

            target = None

            for empowerment in improvement.empowerments:
                if empowerment.id == empowerment_id:
                    target = empowerment
                    break

            if target is None:
                return False

            # Well Trained behaves like Heightened Ability for the buddy.
            # For a given buddy ability, only the most recently purchased
            # (highest-cost) bonus may be removed.
            if (
                improvement.catalog_id == "animal_buddy"
                and target.catalog_id == "well_trained"
            ):
                target_stat = target.choices.get("buddy_training_stat")

                same_stat_training = [
                    empowerment
                    for empowerment in improvement.empowerments
                    if (
                        empowerment.catalog_id == "well_trained"
                        and empowerment.choices.get("buddy_training_stat")
                        == target_stat
                    )
                ]

                if (
                    same_stat_training
                    and same_stat_training[-1].id != target.id
                ):
                    return False

            parent_option = ImprovementCatalogSystem.get_option(improvement.catalog_id, character)

            if parent_option is not None:
                rule = ImprovementSystem.get_empowerment_group_rule(
                    parent_option,
                    target.group_id,
                )

                if rule in {"ordered", "repeatable", "repeatable_scaling"}:
                    same_branch = [
                        empowerment
                        for empowerment in improvement.empowerments
                        if empowerment.group_id == target.group_id
                    ]

                    if same_branch and same_branch[-1].id != target.id:
                        return False

            improvement.empowerments = [
                empowerment
                for empowerment in improvement.empowerments
                if empowerment.id != empowerment_id
            ]

            character.validate()
            return True

        return False
# ============================================================
# Systems: Inventory / Image
# ============================================================

class InventorySystem:
    @staticmethod
    def add_item(
        character: Character,
        name: str,
        description: str,
        quantity: int = 1
    ) -> bool:
        character.inventory.list_of_items.append(
            InventoryItem(
                id=str(uuid4()),
                name=name,
                description=description,
                quantity=max(0, int(quantity)),
                expanded=True,
            )
        )
        character.validate()
        return True

    @staticmethod
    def remove_item(character: Character, item_id: str) -> bool:
        original_count = len(character.inventory.list_of_items)
        character.inventory.remove(item_id)
        changed = len(character.inventory.list_of_items) != original_count
        character.validate()
        return changed

    @staticmethod
    def set_quantity(
        character: Character,
        item_id: str,
        quantity: int
    ) -> bool:
        for item in character.inventory.list_of_items:
            if item.id == item_id:
                item.quantity = max(0, int(quantity))
                character.validate()
                return True
        return False

    @staticmethod
    def adjust_quantity(
        character: Character,
        item_id: str,
        delta: int,
    ) -> bool:
        for item in character.inventory.list_of_items:
            if item.id == item_id:
                item.quantity += int(delta)
                character.validate()
                return True
        return False

    @staticmethod
    def reorder_items(
        character: Character,
        ordered_ids: List[str],
    ) -> bool:
        current = list(character.inventory.list_of_items)
        by_id = {item.id: item for item in current}
        clean_ids = []
        for item_id in ordered_ids:
            item_id = str(item_id)
            if item_id in by_id and item_id not in clean_ids:
                clean_ids.append(item_id)

        new_order = [by_id[item_id] for item_id in clean_ids]
        new_order.extend(
            item
            for item in current
            if item.id not in clean_ids
        )

        if new_order == current:
            return False

        character.inventory.list_of_items = new_order
        character.validate()
        return True


    @staticmethod
    def toggle_expanded(character: Character, item_id: str) -> bool:
        for item in character.inventory.list_of_items:
            if item.id == item_id:
                item.expanded = not item.expanded
                return True
        return False


class ImageSystem:
    @staticmethod
    def add_image(character: Character, image_data: Optional[str]) -> bool:
        if not image_data:
            return False

        character.image.images.append(
            CharacterImageEntry(
                id=str(uuid4()),
                image_data=image_data,
            )
        )

        character.image.current_index = len(character.image.images) - 1
        character.validate()
        return True

    @staticmethod
    def remove_current_image(character: Character) -> bool:
        if not character.image.images:
            return False

        character.image.images.pop(character.image.current_index)
        character.validate()
        return True

    @staticmethod
    def next_image(character: Character) -> bool:
        if not character.image.images:
            return False

        character.image.current_index = (
            character.image.current_index + 1
        ) % len(character.image.images)

        character.validate()
        return True

    @staticmethod
    def previous_image(character: Character) -> bool:
        if not character.image.images:
            return False

        character.image.current_index = (
            character.image.current_index - 1
        ) % len(character.image.images)

        character.validate()
        return True

    @staticmethod
    def clear_images(character: Character) -> bool:
        character.image = CharacterImageData()
        character.validate()
        return True

    
    
# ============================================================
# Systems: Save / Load Characters
# ============================================================

class CharacterStorageSystem:
    SAVE_DIR = os.path.join(
        os.path.expanduser("~"),
        "Documents",
        "DID Character Sheet",
        "Saved_characters"
    )

    RECOVERY_DIR = os.path.join(
        os.path.expanduser("~"),
        "Documents",
        "DID Character Sheet",
        "Recovery",
    )
        

    @staticmethod
    def ensure_save_dir() -> None:
        os.makedirs(CharacterStorageSystem.SAVE_DIR, exist_ok=True)

    @staticmethod
    def save_filename(name:str) -> str:
        safe = name.strip() or "character"

        safe = re.sub(r'[<>:"/\\|?*]', "_", safe)
        safe = re.sub(r"\s+", "_", safe)

        return safe

    @staticmethod
    def ensure_recovery_dir() -> None:
        os.makedirs(
            CharacterStorageSystem.RECOVERY_DIR,
            exist_ok=True,
        )

    @staticmethod
    def character_to_dict(character: Character) -> dict:
        character.validate()

        return {
            "id": character.id,
            "name": character.name,
            "species_name": character.species_name,
            "backstory": character.backstory,


            "stats": {
                stat_name: {
                    "die_size": stat.die_size,
                    "bonus": stat.bonus,
                }
                for stat_name, stat in character.stats.as_dict().items()
            },
            "HP": {
                "current_HP": character.HP.current_HP,
                "max_hearts": character.HP.max_hearts,
                "max_HP": character.HP.max_HP,
            },

            "Adversity": {
                "current_AT": character.adversity.current_AT,
                "max_AT": character.adversity.max_AT,
            },

            "progression": {
                "current_IP": character.progression.current_IP,
                "used_IP": character.progression.used_IP,
                "level": character.progression.level,
            },

            "improvements": {
                "list_of_taken_improvements": [
                    {
                        "id": improvement.id,
                        "catalog_id": improvement.catalog_id,
                        "name": improvement.name,
                        "cost": improvement.cost,
                        "description": improvement.description,
                        "source": improvement.source,
                        "choices": improvement.choices,
                        "expanded": improvement.expanded,
                        "times_taken": improvement.times_taken,
                        "sort_order": improvement.sort_order,
                        "empowerments": [
                            {
                                "id": empowerment.id,
                                "group_id": empowerment.group_id,
                                "catalog_id": empowerment.catalog_id,
                                "name": empowerment.name,
                                "cost": empowerment.cost,
                                "description": empowerment.description,
                                "source": empowerment.source,
                                "choices": empowerment.choices,
                            }
                            for empowerment in improvement.empowerments
                        ],
                    }
                    for improvement in character.improvements.list_of_taken_improvements
                ]
            },

            "inventory": {
                "list_of_items": [
                    {
                        "id": item.id,
                        "name": item.name,
                        "description": item.description,
                        "quantity": item.quantity,
                        "expanded": item.expanded,
                    }
                    for item in character.inventory.list_of_items
                ]
            },
            
            "notes": {
                "list_of_notes": [
                    {
                        "id": note.id,
                        "title": note.title,
                        "text": note.text,
                        "color": note.color,
                        "expanded": note.expanded,
                        "pinned": bool(getattr(note, "pinned", False)),
                        "linked_improvement_id": (
                            note.linked_improvement_id
                        ),
                    }
                    for note in character.notes.list_of_notes
                ]
            },
            "image": {
                "images": [
                    {
                        "id": image.id,
                        "display": image.image_data,
                    }
                    for image in character.image.images
                ],
                "current_index": character.image.current_index,
                "offset_x": character.image.offset_x,
                "offset_y": character.image.offset_y,
                "scale": character.image.scale,
            },

            "bonus_dice": {
                "dice": character.bonus_dice.dice,
            },

            "stat_point_budget": character.stat_point_budget,
            "free_heightened_ability_slots": character.free_heightened_ability_slots,
            "free_heightened_ability_stats": character.free_heightened_ability_stats,
            "selected_defense_stat_name": character.selected_defense_stat_name,
            "combat_mode_enabled": character.combat_mode_enabled,

            "creation_rules": {
                "active": (
                    character.creation_rules_active
                ),
                "template_name": (
                    character.creation_template_name
                ),
                "species_mode": (
                    character.creation_species_mode
                ),
                "allow_custom_improvements": (
                    character.creation_allow_custom_improvements
                ),
                "allowed_ability_array_ids": (
                    character.creation_allowed_ability_array_ids
                ),
                "restrict_ability_dice_to_allowed_arrays": (
                    character.creation_restrict_ability_dice_to_allowed_arrays
                ),
                "improvement_mode": (
                    character.creation_improvement_mode
                ),
                "improvement_ids": (
                    character.creation_improvement_ids
                ),
                "improvement_overrides": (
                    character.creation_improvement_overrides
                ),
                "template_custom_improvements": (
                    character.creation_template_custom_improvements
                ),
            }
        }
    
    
    @staticmethod
    def character_from_dict(data: dict) -> Character:
        character = Character(
            id=data.get("id", str(uuid4())),
            name=data.get("name", ""),
            species_name=data.get("species_name", ""),
            backstory=data.get("backstory", ""),

        )

        # Stats
        stats_data = data.get("stats", {})
        for stat_name in STAT_NAMES:
            stat_data = stats_data.get(stat_name, {})
            stat = character.stats.get_stat(stat_name)
            if stat is not None:
                stat.die_size = stat_data.get("die_size", DEFAULT_DIE_SIZE)
                stat.bonus = stat_data.get("bonus", 0)

        # HP
        hp_data = data.get("HP", {})
        character.HP.current_HP = hp_data.get("current_HP", STARTING_HEARTS * 4)
        character.HP.max_hearts = hp_data.get("max_hearts", STARTING_HEARTS)
        character.HP.max_HP = hp_data.get("max_HP", STARTING_HEARTS * 4)
        

        # AT
        adversity_data = data.get("Adversity", data.get("adversity", {}))
        character.adversity.current_AT = adversity_data.get("current_AT", 0)
        character.adversity.max_AT = adversity_data.get("max_AT", STARTING_AT)

        # Roll history is intentionally session-only and is never restored
        # from a saved character. Older files may still contain roll_history;
        # ignore it so reopening the app starts with a clean history.
        character.roll_history = []

        # Progression
        progression_data = data.get("progression", {})
        character.progression.current_IP = progression_data.get(
            "current_IP",
            STARTING_IP,
        )
        character.progression.used_IP = progression_data.get(
            "used_IP",
            0,
        )

        saved_level = progression_data.get("level")

        if saved_level is None:
            # Legacy files did not store level and incorrectly derived it
            # from total IP. max_AT tracks actual Level Up actions instead.
            saved_level = 1 + max(
                0,
                int(character.adversity.max_AT) - STARTING_AT,
            )

        character.progression.current_level = max(
            1,
            int(saved_level),
        )

        # Improvements
        character.improvements.list_of_taken_improvements = []

        improvements_data = data.get("improvements", {})
        for improvement_index, improvement_data in enumerate(
            improvements_data.get("list_of_taken_improvements", [])
        ):
            improvement = Improvement(
                id=improvement_data.get("id", str(uuid4())),
                catalog_id=improvement_data.get("catalog_id", ""),
                name=improvement_data.get("name", ""),
                cost=improvement_data.get("cost", 0),
                description=improvement_data.get("description", ""),
                source=improvement_data.get("source", "ip"),
                choices=improvement_data.get("choices", {}),
                expanded=improvement_data.get("expanded", False),
                times_taken=improvement_data.get("times_taken", 1),
                sort_order=improvement_data.get(
                    "sort_order",
                    improvement_index,
                ),
            )

            for empowerment_data in improvement_data.get("empowerments", []):
                improvement.empowerments.append(
                    TakenEmpowerment(
                        id=empowerment_data.get("id", str(uuid4())),
                        group_id=empowerment_data.get("group_id", ""),
                        catalog_id=empowerment_data.get("catalog_id", ""),
                        name=empowerment_data.get("name", ""),
                        cost=empowerment_data.get("cost", 0),
                        description=empowerment_data.get("description", ""),
                        source=empowerment_data.get("source", "ip"),
                        choices=empowerment_data.get("choices", {}),
                    )
                )
            character.improvements.list_of_taken_improvements.append(improvement)

        # Preserve explicit sort_order values exactly, including ties. A tie
        # is legal for a character created by the editor/fuzzer, and silently
        # renumbering it corrupts otherwise lossless save/load round trips.
        # Older files lacking the field already receive their list index in
        # the Improvement constructor above, preserving their original order.

        # Inventory
        character.inventory.list_of_items = []

        inventory_data = data.get("inventory", {})
        for item_data in inventory_data.get("list_of_items", []):
            character.inventory.list_of_items.append(
                InventoryItem(
                    id=item_data.get("id", str(uuid4())),
                    name=item_data.get("name", ""),
                    description=item_data.get("description", ""),
                    quantity=item_data.get("quantity", 0),
                    expanded=item_data.get("expanded", False),
                )
            )
            
        # Notes
        character.notes.list_of_notes = []

        notes_data = data.get("notes", {})

        for note_data in notes_data.get("list_of_notes", []):
            character.notes.list_of_notes.append(
                CharacterNote(
                    id=note_data.get("id", str(uuid4())),
                    title=note_data.get("title", "Note"),
                    text=note_data.get("text", ""),
                    color=note_data.get("color", "yellow"),
                    expanded=note_data.get("expanded", True),
                    pinned=note_data.get("pinned", False),
                    linked_improvement_id=note_data.get(
                        "linked_improvement_id",
                        "",
                    ),
                )
            )
        # Image
        image_data = data.get("image", {})

        character.image.images = []

        for image_entry in image_data.get("images", []):
            character.image.images.append(
                CharacterImageEntry(
                    id=image_entry.get("id", str(uuid4())),
                    image_data=image_entry.get("display"),
                )
            )

        character.image.current_index = image_data.get("current_index", 0)
        character.image.offset_x = image_data.get("offset_x", 0.0)
        character.image.offset_y = image_data.get("offset_y", 0.0)
        character.image.scale = image_data.get("scale", 1.0)


        # Bonus dice
        if hasattr(character, "bonus_dice"):
            bonus_dice_data = data.get("bonus_dice", {})
            character.bonus_dice.dice = bonus_dice_data.get("dice", {})

        # Other fields
        character.stat_point_budget = data.get("stat_point_budget", STARTING_STAT_POINTS)
        character.free_heightened_ability_slots = data.get("free_heightened_ability_slots", 2)
        character.free_heightened_ability_stats = data.get("free_heightened_ability_stats", [])
        character.selected_defense_stat_name = data.get("selected_defense_stat_name")
        character.combat_mode_enabled = data.get("combat_mode_enabled", False)

        creation_rules = data.get(
            "creation_rules",
            {},
        )

        if not isinstance(
            creation_rules,
            dict,
        ):
            creation_rules = {}

        character.creation_rules_active = (
            creation_rules.get(
                "active",
                False,
            )
        )

        character.creation_template_name = (
            creation_rules.get(
                "template_name",
                "",
            )
        )


        character.creation_species_mode = (
            creation_rules.get(
                "species_mode",
                "normal",
            )
        )

        character.creation_allow_custom_improvements = (
            creation_rules.get(
                "allow_custom_improvements",
                True,
            )
        )

        character.creation_allowed_ability_array_ids = (
            creation_rules.get(
                "allowed_ability_array_ids",
                [],
            )
        )

        character.creation_restrict_ability_dice_to_allowed_arrays = (
            creation_rules.get(
                "restrict_ability_dice_to_allowed_arrays",
                False,
            )
        )

        character.creation_improvement_mode = (
            creation_rules.get(
                "improvement_mode",
                "all",
            )
        )

        character.creation_improvement_ids = (
            creation_rules.get(
                "improvement_ids",
                [],
            )
        )
        character.creation_improvement_overrides = (
            creation_rules.get(
                "improvement_overrides",
                {},
            )
        )
        character.creation_template_custom_improvements = (
            creation_rules.get(
                "template_custom_improvements",
                [],
            )
        )
        character.validate()
        return character

    @staticmethod
    def save_character(character: Character) -> str:
        CharacterStorageSystem.ensure_save_dir()

        base_name = character.name.strip() or "character"
        filename = CharacterStorageSystem.save_filename(base_name)
        filepath = os.path.join(CharacterStorageSystem.SAVE_DIR, f"{filename}.json")

        data = CharacterStorageSystem.character_to_dict(character)

        with open(filepath, "w", encoding="utf-8") as file:
            json.dump(data, file, indent=2, ensure_ascii=False)

        return filepath

    @staticmethod
    def list_saved_characters() -> List[str]:
        CharacterStorageSystem.ensure_save_dir()

        files = []

        for filename in os.listdir(CharacterStorageSystem.SAVE_DIR):
            if filename.endswith(".json"):
                files.append(filename)

        return sorted(files)

    @staticmethod
    def load_character(filename:str) -> Character:
        CharacterStorageSystem.ensure_save_dir()

        filepath = os.path.join(CharacterStorageSystem.SAVE_DIR, filename)

        with open(filepath, "r", encoding="utf-8") as file:
            data = json.load(file)

        return CharacterStorageSystem.character_from_dict(data)

    @staticmethod
    def export_character_file(character: Character, filepath: str) -> str:
        data = {
            "file_type": "did_character",
            "file_version": 1,
            "character": CharacterStorageSystem.character_to_dict(
                character
            ),
        }

        save_folder = os.path.dirname(
            os.path.abspath(filepath)
        )

        os.makedirs(
            save_folder,
            exist_ok=True,
        )

        file_descriptor, temp_filepath = tempfile.mkstemp(
            prefix=".did_save_",
            suffix=".saving",
            dir=save_folder,
        )

        try:
            with os.fdopen(
                file_descriptor,
                "w",
                encoding="utf-8",
            ) as file:
                json.dump(
                    data,
                    file,
                    indent=2,
                    ensure_ascii=False,
                )

                file.flush()
                os.fsync(file.fileno())

            os.replace(
                temp_filepath,
                filepath,
            )

            temp_filepath = None

        finally:
            if (
                temp_filepath
                and os.path.exists(temp_filepath)
            ):
                try:
                    os.remove(temp_filepath)
                except OSError:
                    pass

        return filepath

    @staticmethod
    def looks_like_character_file(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as file:
                data = json.load(file)

            if not isinstance(data, dict):
                return False

            # New DID character file
            if data.get("file_type") == "did_character":
                return isinstance(data.get("character"), dict)

            # Old raw JSON character file
            required_keys = {
                "id",
                "name",
                "stats",
                "HP",
                "Adversity",
                "progression",
                "improvements",
                "inventory",
                "stat_point_budget",
                "free_heightened_ability_slots",
            }

            if not required_keys.issubset(data.keys()):
                return False

            # Must contain the six DID stats
            stats = data.get("stats")

            if not isinstance(stats, dict):
                return False

            if not all(stat_name in stats for stat_name in STAT_NAMES):
                return False

            for stat_name in STAT_NAMES:
                stat = stats[stat_name]

                if not isinstance(stat, dict):
                    return False

                if "die_size" not in stat:
                    return False

            # Check distinctive DID nested structures
            hp = data.get("HP")
            progression = data.get("progression")
            improvements = data.get("improvements")
            inventory = data.get("inventory")

            if not isinstance(hp, dict):
                return False

            if not {"current_HP", "max_hearts"}.issubset(hp):
                return False

            if not isinstance(progression, dict):
                return False

            if "current_IP" not in progression:
                return False

            if not isinstance(improvements, dict):
                return False

            if "list_of_taken_improvements" not in improvements:
                return False

            if not isinstance(inventory, dict):
                return False

            if "list_of_items" not in inventory:
                return False

            return True

        except Exception:
            return False

    @staticmethod
    def import_character_file(filepath: str) -> Character:
        with open(filepath, "r", encoding="utf-8") as file:
            data = json.load(file)

        # New shareable format
        if data.get("file_type") == "did_character":
            character_data = data.get("character", {})
            return CharacterStorageSystem.character_from_dict(character_data)

        # Backward compatibility with older raw JSON character saves
        return CharacterStorageSystem.character_from_dict(data)

    @staticmethod
    def find_character_files():
        from pathlib import Path

        home = Path.home()

        search_roots = [
            home / "Desktop",
            home / "Documents",
            home / "Downloads",
        ]

        onedrive = os.environ.get("OneDrive")

        if onedrive:
            search_roots.append(Path(onedrive))

        # ------------------------------------------------------------
        # Find possible character files
        # ------------------------------------------------------------

        found = set()

        for root in search_roots:
            if not root.exists():
                continue

            try:
                for pattern in ("*.didchar", "*.json"):
                    for filepath in root.rglob(pattern):

                        if not filepath.is_file():
                            continue

                        if "_history" in filepath.parts:
                            continue

                        filepath = str(filepath)

                        # .didchar is always a candidate.
                        if filepath.lower().endswith(".didchar"):
                            found.add(filepath)
                            continue

                        # Old .json files must match the old character structure.
                        if CharacterStorageSystem.looks_like_character_file(
                            filepath
                        ):
                            found.add(filepath)

            except (PermissionError, OSError):
                continue

        # ------------------------------------------------------------
        # Load valid characters and remove duplicate copies
        # ------------------------------------------------------------

        unique_characters = {}

        for filepath in found:
            try:
                character = CharacterStorageSystem.import_character_file(
                    filepath
                )

                character_id = str(character.id)

                if not character_id:
                    continue

                modified_time = os.path.getmtime(filepath)

            except Exception:
                continue

            existing = unique_characters.get(character_id)

            if (
                existing is None
                or modified_time > existing["modified"]
            ):
                unique_characters[character_id] = {
                    "filepath": filepath,
                    "modified": modified_time,
                }

        # ------------------------------------------------------------
        # Return one file per character
        # ------------------------------------------------------------

        result = [
            data["filepath"]
            for data in unique_characters.values()
        ]

        return sorted(
            result,
            key=lambda path: os.path.basename(path).lower(),
        )

    @staticmethod
    def _history_clean_choices(value):
        """
        Remove internal UI bookkeeping from improvement choices while
        preserving the player-facing/gameplay choices themselves.
        """
        if isinstance(
            value,
            dict,
        ):
            return {
                str(key): CharacterStorageSystem._history_clean_choices(
                    child_value
                )
                for key, child_value in value.items()
                if not str(key).startswith("_")
            }

        if isinstance(
            value,
            list,
        ):
            return [
                CharacterStorageSystem._history_clean_choices(
                    child_value
                )
                for child_value in value
            ]

        return value

    @staticmethod
    def _history_sort_key(value) -> str:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )

    @staticmethod
    def meaningful_history_state(
        character: Character,
    ) -> dict:
        """
        Build the state used by Earlier Versions.

        Runtime-only data is deliberately excluded:
        - UUIDs;
        - expanded/collapsed arrows;
        - current carousel selection;
        - derived used-IP / bonus-dice values;
        - improvement catalog display text which can change when the app
          itself is updated.

        Lists whose visual order is not player-controlled are normalized,
        so removing and then recreating the exact same item/improvement/note
        does not create a fake historical change just because it got a new
        UUID or was appended at a different list position.
        """
        data = (
            CharacterStorageSystem
            .character_to_dict(
                character
            )
        )

        improvements = []

        for improvement in (
            data.get(
                "improvements",
                {},
            )
            .get(
                "list_of_taken_improvements",
                [],
            )
        ):
            catalog_id = str(
                improvement.get(
                    "catalog_id",
                    "",
                )
            )

            normalized_improvement = {
                "catalog_id": catalog_id,
                "cost": int(
                    improvement.get(
                        "cost",
                        0,
                    )
                ),
                "source": str(
                    improvement.get(
                        "source",
                        "ip",
                    )
                ),
                "choices": (
                    CharacterStorageSystem
                    ._history_clean_choices(
                        improvement.get(
                            "choices",
                            {},
                        )
                    )
                ),
                "times_taken": int(
                    improvement.get(
                        "times_taken",
                        1,
                    )
                ),
                "sort_order": int(
                    improvement.get(
                        "sort_order",
                        0,
                    )
                ),
                "empowerments": [],
            }

            # Custom improvements are authored by the player, so their
            # name/description are meaningful. Catalog improvements derive
            # those strings from character_API and should not generate a
            # history entry merely because the app was updated.
            if catalog_id == "custom":
                normalized_improvement[
                    "name"
                ] = str(
                    improvement.get(
                        "name",
                        "",
                    )
                )

                normalized_improvement[
                    "description"
                ] = str(
                    improvement.get(
                        "description",
                        "",
                    )
                )

            for empowerment in improvement.get(
                "empowerments",
                [],
            ):
                normalized_improvement[
                    "empowerments"
                ].append(
                    {
                        "group_id": str(
                            empowerment.get(
                                "group_id",
                                "",
                            )
                        ),
                        "catalog_id": str(
                            empowerment.get(
                                "catalog_id",
                                "",
                            )
                        ),
                        "cost": int(
                            empowerment.get(
                                "cost",
                                0,
                            )
                        ),
                        "source": str(
                            empowerment.get(
                                "source",
                                "ip",
                            )
                        ),
                        "choices": (
                            CharacterStorageSystem
                            ._history_clean_choices(
                                empowerment.get(
                                    "choices",
                                    {},
                                )
                            )
                        ),
                    }
                )

            normalized_improvement[
                "empowerments"
            ].sort(
                key=(
                    CharacterStorageSystem
                    ._history_sort_key
                )
            )

            improvements.append(
                normalized_improvement
            )

        inventory = [
            {
                "name": str(
                    item.get(
                        "name",
                        "",
                    )
                ),
                "description": str(
                    item.get(
                        "description",
                        "",
                    )
                ),
                "quantity": int(
                    item.get(
                        "quantity",
                        0,
                    )
                ),
            }
            for item in (
                data.get(
                    "inventory",
                    {},
                )
                .get(
                    "list_of_items",
                    [],
                )
            )
        ]

        notes = [
            {
                "title": str(
                    note.get(
                        "title",
                        "",
                    )
                ),
                "text": str(
                    note.get(
                        "text",
                        "",
                    )
                ),
                "color": str(
                    note.get(
                        "color",
                        "yellow",
                    )
                ),
            }
            for note in (
                data.get(
                    "notes",
                    {},
                )
                .get(
                    "list_of_notes",
                    [],
                )
            )
        ]

        notes.sort(
            key=(
                CharacterStorageSystem
                ._history_sort_key
            )
        )

        image_data = data.get(
            "image",
            {},
        )

        images = [
            str(
                image.get(
                    "display",
                    "",
                )
                or ""
            )
            for image in image_data.get(
                "images",
                [],
            )
        ]

        progression = data.get(
            "progression",
            {},
        )

        state = {
            "name": str(
                data.get(
                    "name",
                    "",
                )
            ),
            "species_name": str(
                data.get(
                    "species_name",
                    "",
                )
            ),
            "backstory": str(
                data.get(
                    "backstory",
                    "",
                )
            ),
            "stats": data.get(
                "stats",
                {},
            ),
            "HP": {
                "current_HP": int(
                    data.get(
                        "HP",
                        {},
                    ).get(
                        "current_HP",
                        0,
                    )
                ),
                "max_hearts": int(
                    data.get(
                        "HP",
                        {},
                    ).get(
                        "max_hearts",
                        0,
                    )
                ),
            },
            "Adversity": {
                "current_AT": int(
                    data.get(
                        "Adversity",
                        {},
                    ).get(
                        "current_AT",
                        0,
                    )
                ),
                "max_AT": int(
                    data.get(
                        "Adversity",
                        {},
                    ).get(
                        "max_AT",
                        0,
                    )
                ),
            },
            "progression": {
                "current_IP": int(
                    progression.get(
                        "current_IP",
                        0,
                    )
                ),
                "level": int(
                    progression.get(
                        "level",
                        1,
                    )
                ),
            },
            "improvements": improvements,
            "inventory": inventory,
            "notes": notes,
            "image": {
                "images": images,
                "offset_x": float(
                    image_data.get(
                        "offset_x",
                        0.0,
                    )
                ),
                "offset_y": float(
                    image_data.get(
                        "offset_y",
                        0.0,
                    )
                ),
                "scale": float(
                    image_data.get(
                        "scale",
                        1.0,
                    )
                ),
            },
            "stat_point_budget": int(
                data.get(
                    "stat_point_budget",
                    STARTING_STAT_POINTS,
                )
            ),
            "free_heightened_ability_slots": int(
                data.get(
                    "free_heightened_ability_slots",
                    2,
                )
            ),
            "free_heightened_ability_stats": sorted(
                str(value)
                for value in data.get(
                    "free_heightened_ability_stats",
                    [],
                )
            ),
            "selected_defense_stat_name": (
                data.get(
                    "selected_defense_stat_name"
                )
            ),
            "creation_rules": data.get(
                "creation_rules",
                {},
            ),
        }

        return state

    @staticmethod
    def meaningful_history_equal(
        first_character: Character,
        second_character: Character,
    ) -> bool:
        return (
            CharacterStorageSystem
            .meaningful_history_state(
                first_character
            )
            ==
            CharacterStorageSystem
            .meaningful_history_state(
                second_character
            )
        )

    @staticmethod
    def describe_meaningful_changes(
        older_character: Character,
        newer_character: Character,
    ) -> List[str]:
        """
        Return concise player-facing categories that changed between two
        historical snapshots.
        """
        older = (
            CharacterStorageSystem
            .meaningful_history_state(
                older_character
            )
        )

        newer = (
            CharacterStorageSystem
            .meaningful_history_state(
                newer_character
            )
        )

        changes = []

        if older["name"] != newer["name"]:
            changes.append("Name")

        if older["species_name"] != newer["species_name"]:
            changes.append("Species")

        if older["backstory"] != newer["backstory"]:
            changes.append("Backstory")

        if older["stats"] != newer["stats"]:
            changes.append("Abilities")

        if older["HP"] != newer["HP"]:
            changes.append("Hearts / HP")

        if (
            older["Adversity"]
            != newer["Adversity"]
        ):
            changes.append("AT")

        if (
            older["progression"].get(
                "level"
            )
            != newer["progression"].get(
                "level"
            )
        ):
            changes.append("Level")

        if (
            older["progression"].get(
                "current_IP"
            )
            != newer["progression"].get(
                "current_IP"
            )
        ):
            changes.append("IP")

        if (
            older["improvements"]
            != newer["improvements"]
        ):
            changes.append("Improvements")

        if older["inventory"] != newer["inventory"]:
            changes.append("Inventory")

        if older["notes"] != newer["notes"]:
            changes.append("Notes")

        if older["image"] != newer["image"]:
            changes.append("Portraits")

        if (
            older["stat_point_budget"]
            != newer["stat_point_budget"]
        ):
            changes.append("Ability point budget")

        if (
            older["free_heightened_ability_slots"]
            != newer["free_heightened_ability_slots"]
            or older["free_heightened_ability_stats"]
            != newer["free_heightened_ability_stats"]
        ):
            changes.append("Heightened Ability")

        if (
            older["selected_defense_stat_name"]
            != newer["selected_defense_stat_name"]
        ):
            changes.append("Defense ability")

        if (
            older["creation_rules"]
            != newer["creation_rules"]
        ):
            changes.append("Creation rules")

        return changes

    @staticmethod
    def backup_character_file(
        character: Character,
        filepath: str,
        preserve_reversion: bool = False,
    ):
        if not filepath:
            return False

        save_folder = os.path.dirname(
            os.path.abspath(filepath)
        )

        character_filename = os.path.basename(
            filepath
        )

        character_name = os.path.splitext(
            character_filename
        )[0]

        history_folder = os.path.join(
            save_folder,
            "_history",
            character_name,
        )

        os.makedirs(
            history_folder,
            exist_ok=True,
        )

        history_files = (
            CharacterStorageSystem
            .get_character_history(
                filepath
            )
        )

        current_state = (
            CharacterStorageSystem
            .meaningful_history_state(
                character
            )
        )

        matching_history_index = None

        for index, history_filepath in enumerate(
            history_files
        ):
            try:
                history_character = (
                    CharacterStorageSystem
                    .import_character_file(
                        history_filepath
                    )
                )

                history_state = (
                    CharacterStorageSystem
                    .meaningful_history_state(
                        history_character
                    )
                )

            except Exception:
                continue

            if history_state == current_state:
                matching_history_index = index
                break

        # Exact same meaningful sheet as the latest snapshot: saving again
        # is not a new Earlier Version.
        if matching_history_index == 0:
            return False

        # If the user performs a temporary change which autosaves and then
        # returns the sheet to a state which already existed, collapse those
        # transient versions. UUID differences and list insertion order have
        # already been normalized above.
        #
        # Explicitly restoring from Earlier Versions opts out of this collapse
        # so the promise "restoring does not erase newer versions" remains true.
        if (
            matching_history_index is not None
            and matching_history_index > 0
            and not preserve_reversion
        ):
            for transient_filepath in history_files[
                :matching_history_index
            ]:
                try:
                    os.remove(
                        transient_filepath
                    )
                except OSError:
                    pass

            return False

        timestamp = datetime.now().strftime(
            "%Y-%m-%d_%H-%M-%S_%f"
        )

        backup_filepath = os.path.join(
            history_folder,
            f"{timestamp}.didchar",
        )

        CharacterStorageSystem.export_character_file(
            character,
            backup_filepath,
        )

        CharacterStorageSystem.prune_character_history(
            history_folder
        )

        return True

    @staticmethod
    def prune_character_history(
        history_folder: str,
        keep: str = 20,
    ):
        if not os.path.isdir(history_folder):
            return

        backups = [
            os.path.join(
                history_folder,
                filename,
            )
            for filename in os.listdir(history_folder)
            if filename.lower().endswith(".didchar")
        ]

        backups.sort(
            key=os.path.getmtime,
            reverse=True,
        )

        for old_backup in backups[keep:]:
            try:
                os.remove(old_backup)
            except OSError:
                pass

    @staticmethod
    def get_character_history(filepath: str):
        if not filepath:
            return []

        save_folder = os.path.dirname(
            os.path.abspath(filepath)
        )

        character_filename = os.path.basename(
            filepath
        )

        character_name = os.path.splitext(
            character_filename
        )[0]

        history_folder = os.path.join(
            save_folder,
            "_history",
            character_name,
        )

        if not os.path.isdir(history_folder):
            return []

        backups = []

        for filename in os.listdir(history_folder):
            if not filename.lower().endswith(".didchar"):
                continue

            backup_filepath = os.path.join(
                history_folder,
                filename,
            )

            try:
                if not CharacterStorageSystem.looks_like_character_file(
                    backup_filepath
                ):
                    continue
            except Exception:
                continue

            backups.append(
                backup_filepath
            )

        backups.sort(
            key=os.path.getmtime,
            reverse=True,
        )

        return backups

    @staticmethod
    def get_meaningful_character_history(
        filepath: str,
    ):
        """
        Return history snapshots with consecutive no-op saves hidden.

        Older app versions created a history file for every save operation,
        so existing users may already have duplicate snapshots. Keeping the
        files on disk is safest, but the Earlier Versions UI should not show
        those duplicates.
        """
        history_files = (
            CharacterStorageSystem
            .get_character_history(
                filepath
            )
        )

        meaningful_files = []
        previous_state = None

        for history_filepath in history_files:
            try:
                character = (
                    CharacterStorageSystem
                    .import_character_file(
                        history_filepath
                    )
                )

                state = (
                    CharacterStorageSystem
                    .meaningful_history_state(
                        character
                    )
                )

            except Exception:
                # Keep unreadable/legacy entries visible rather than deleting
                # or silently discarding user history.
                meaningful_files.append(
                    history_filepath
                )
                previous_state = None
                continue

            if (
                previous_state is not None
                and state == previous_state
            ):
                continue

            meaningful_files.append(
                history_filepath
            )
            previous_state = state

        return meaningful_files

    @staticmethod
    def migrate_character_history(
        old_filepath: str,
        new_filepath: str,
    ):
        if not old_filepath or not new_filepath:
            return

        old_filepath = os.path.abspath(
            old_filepath
        )

        new_filepath = os.path.abspath(
            new_filepath
        )

        old_name = os.path.splitext(
            os.path.basename(old_filepath)
        )[0]

        new_name = os.path.splitext(
            os.path.basename(new_filepath)
        )[0]

        if old_name == new_name:
            return

        old_history_folder = os.path.join(
            os.path.dirname(old_filepath),
            "_history",
            old_name,
        )

        new_history_folder = os.path.join(
            os.path.dirname(new_filepath),
            "_history",
            new_name,
        )

        if not os.path.isdir(
            old_history_folder
        ):
            return

        os.makedirs(
            new_history_folder,
            exist_ok=True,
        )

        for filename in os.listdir(
            old_history_folder
        ):
            source = os.path.join(
                old_history_folder,
                filename,
            )

            if not os.path.isfile(source):
                continue

            destination = os.path.join(
                new_history_folder,
                filename,
            )

            if os.path.exists(destination):
                base, extension = os.path.splitext(
                    filename
                )

                number = 2

                while True:
                    candidate = os.path.join(
                        new_history_folder,
                        f"{base}_{number}{extension}",
                    )

                    if not os.path.exists(candidate):
                        destination = candidate
                        break

                    number += 1

            os.replace(
                source,
                destination,
            )

        try:
            os.rmdir(
                old_history_folder
            )
        except OSError:
            pass

    @staticmethod
    def recovery_filepath(character: Character) -> str:
        CharacterStorageSystem.ensure_recovery_dir()

        character_id = str(
            character.id
        ).strip()

        if not character_id:
            character_id = "unknown_character"

        safe_id = re.sub(
            r'[^A-Za-z0-9_-]',
            "_",
            character_id,
        )

        return os.path.join(
            CharacterStorageSystem.RECOVERY_DIR,
            f"{safe_id}.didrecover",
        )


    @staticmethod
    def write_recovery_file(
        character: Character,
    ) -> str:
        filepath = (
            CharacterStorageSystem.recovery_filepath(
                character
            )
        )

        CharacterStorageSystem.export_character_file(
            character,
            filepath,
        )

        return filepath


    @staticmethod
    def delete_recovery_file(
        character: Character,
    ) -> None:
        filepath = (
            CharacterStorageSystem.recovery_filepath(
                character
            )
        )

        if not os.path.exists(filepath):
            return

        try:
            os.remove(filepath)
        except OSError:
            pass




    @staticmethod
    def list_recovery_files() -> List[str]:
        CharacterStorageSystem.ensure_recovery_dir()

        recovery_files = []

        for filename in os.listdir(
            CharacterStorageSystem.RECOVERY_DIR
        ):
            if not filename.lower().endswith(
                ".didrecover"
            ):
                continue

            filepath = os.path.join(
                CharacterStorageSystem.RECOVERY_DIR,
                filename,
            )

            if not os.path.isfile(filepath):
                continue

            try:
                if not CharacterStorageSystem.looks_like_character_file(
                    filepath
                ):
                    continue
            except Exception:
                continue

            recovery_files.append(
                filepath
            )

        recovery_files.sort(
            key=os.path.getmtime,
            reverse=True,
        )

        return recovery_files


    @staticmethod
    def find_saved_character_filepath(
        character_id: str,
    ):
        CharacterStorageSystem.ensure_save_dir()

        matches = []

        for root, dirs, files in os.walk(
            CharacterStorageSystem.SAVE_DIR
        ):
            # History snapshots must never count as
            # the character's normal save.
            dirs[:] = [
                folder
                for folder in dirs
                if folder != "_history"
            ]

            for filename in files:
                if not filename.lower().endswith(
                    ".didchar"
                ):
                    continue

                filepath = os.path.join(
                    root,
                    filename,
                )

                try:
                    character = (
                        CharacterStorageSystem
                        .import_character_file(
                            filepath
                        )
                    )
                except Exception:
                    continue

                if str(character.id) != str(
                    character_id
                ):
                    continue

                matches.append(
                    filepath
                )

        if not matches:
            return None

        return max(
            matches,
            key=os.path.getmtime,
        )


    @staticmethod
    def get_recovery_candidates():
        candidates = []

        for recovery_filepath in (
            CharacterStorageSystem
            .list_recovery_files()
        ):
            try:
                recovery_character = (
                    CharacterStorageSystem
                    .import_character_file(
                        recovery_filepath
                    )
                )
            except Exception:
                continue

            normal_filepath = (
                CharacterStorageSystem
                .find_saved_character_filepath(
                    recovery_character.id
                )
            )

            # --------------------------------------------------------
            # A recovery that is not newer than the real save is stale.
            # Delete it automatically.
            # --------------------------------------------------------

            if (
                normal_filepath
                and os.path.exists(
                    normal_filepath
                )
            ):
                try:
                    recovery_time = os.path.getmtime(
                        recovery_filepath
                    )

                    normal_time = os.path.getmtime(
                        normal_filepath
                    )

                    if recovery_time <= normal_time:
                        try:
                            os.remove(
                                recovery_filepath
                            )
                        except OSError:
                            pass

                        continue

                except OSError:
                    pass

            candidates.append(
                {
                    "recovery_filepath": (
                        recovery_filepath
                    ),
                    "character": (
                        recovery_character
                    ),
                    "normal_filepath": (
                        normal_filepath
                    ),
                }
            )

        candidates.sort(
            key=lambda item: os.path.getmtime(
                item["recovery_filepath"]
            ),
            reverse=True,
        )

        return candidates
# ============================================================
# Smoke Test
# ============================================================

if __name__ == "__main__":
    char = Character.create_new_character("Test Character")
    print(f"Created character: {char.id}")
    print(f"Level: {char.progression.level}")
    print(f"HP: {char.HP.current_HP}/{char.HP.max_HP}")
    print(f"AT: {char.adversity.current_AT}/{char.adversity.max_AT}")
    print(f"BDV: {char.BDV}")
    print(f"DR: {char.DR}")
