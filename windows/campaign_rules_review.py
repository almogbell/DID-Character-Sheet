"""Conservative, testable rule-difference/shortfall planner for DID characters.

NOT wired into the UI or Supabase. Never automatically adjusts a character.
Only minimum resource shortfalls can be applied on explicit user action.
"""
from __future__ import annotations
from dataclasses import dataclass

STARTING_IP = 6  # backend_2_1.py STARTING_IP; verify against current source before integration


@dataclass(frozen=True)
class Shortfall:
    label: str
    current: int
    required: int
    message: str


@dataclass(frozen=True)
class Review:
    shortfalls: tuple[Shortfall, ...]
    manual_issues: tuple[str, ...]

    @property
    def can_auto_adjust(self):
        return bool(self.shortfalls)


def _value(value, default):
    try:
        return int(value)
    except (ValueError, TypeError):
        return int(default)


def inspect_character(character, rules, known_mismatches=()):
    """Classify only positive minimum shortfalls; cannot repair rule bans/choices."""
    progression = getattr(character, 'progression', None)
    actual_level = max(1, _value(getattr(progression, 'level', 1), 1))
    required_level = max(1, _value(getattr(rules, 'level', 1), 1))
    actual_total = max(0, _value(getattr(progression, 'current_IP', 0), 0))
    # Level-up grants two IP per level; compare against actual level, never
    # decrease a high-level character to the campaign's starting level.
    required_total = STARTING_IP + (max(actual_level, required_level) - 1) * 2 + max(0, _value(getattr(rules, 'extra_ip', 0), 0))
    hp = getattr(character, 'HP', None)
    actual_hearts = max(0, _value(getattr(hp, 'max_hearts', 0), 0))
    need_hearts = getattr(rules, 'starting_hearts', None)
    adversity = getattr(character, 'adversity', None)
    actual_at = max(0, _value(getattr(adversity, 'max_AT', 0), 0))
    need_at = getattr(rules, 'starting_at', None)
    out = []
    if actual_level < required_level:
        out.append(Shortfall('level', actual_level, required_level, f'Level {actual_level} → {required_level}'))
    if actual_total < required_total:
        out.append(Shortfall('total_ip', actual_total, required_total,
                             f'IP total {actual_total} → {required_total} (+{required_total-actual_total} unspent IP)'))
    if need_hearts is not None and actual_hearts < int(need_hearts):
        out.append(Shortfall('max_hearts', actual_hearts, int(need_hearts),
                             f'Maximum Hearts {actual_hearts} → {int(need_hearts)}'))
    if need_at is not None and actual_at < int(need_at):
        out.append(Shortfall('max_at', actual_at, int(need_at),
                             f'Maximum AT {actual_at} → {int(need_at)}'))
    # Differences unrelated to minimums require manual player choice or DM approval.
    manual = []
    for mismatch in known_mismatches or ():
        t = str(mismatch)
        if not any(t.lower().startswith(prefix) for prefix in (
            'character level ', 'character has ', 'character maximum at', 'free heightened abilities:'
        )):
            manual.append(t)
    free = getattr(rules, 'free_heightened_ability_slots', None)
    if free is not None:
        actual_free = _value(getattr(character, 'free_heightened_ability_slots', 2), 2)
        if actual_free != int(free):
            manual.append(f'Free Heightened Abilities: {actual_free}, campaign requires {int(free)}; choose manually.')
    return Review(tuple(out), tuple(dict.fromkeys(manual)))


def apply_minimums(character, review):
    """Mutate only approved minimum shortfalls; call after explicit confirmation.

    Does not save the character, grant/choose improvements, edit rules metadata,
    or mark the campaign accepted. Run a new server review after normal Save.
    """
    if not isinstance(review, Review):
        raise TypeError('Expected a Review from inspect_character')
    changes = []
    for item in review.shortfalls:
        if item.label == 'level':
            current = _value(getattr(character.progression, 'level', 1), 1)
            if current < item.required:
                character.set_level(item.required)
                changes.append(item.label)
        elif item.label == 'total_ip':
            current = _value(getattr(character.progression, 'current_IP', 0), 0)
            if current < item.required:
                character.progression.current_IP = item.required
                changes.append(item.label)
        elif item.label == 'max_at':
            current = _value(getattr(character.adversity, 'max_AT', 0), 0)
            if current < item.required:
                character.adversity.max_AT = item.required
                changes.append(item.label)
        elif item.label == 'max_hearts':
            current = _value(getattr(character.HP, 'max_hearts', 0), 0)
            if current < item.required:
                character.HP.max_hearts = item.required
                character.HP.recalculate()
                changes.append(item.label)
    return tuple(changes)
