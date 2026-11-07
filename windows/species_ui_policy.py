"""Centralize the UI visibility policy for campaign Species rules.

No Qt dependency: rules can be tested without launching the application.
Existing Species selections remain visible even if rules later become optional.
"""


def is_species_required(character):
    return bool(getattr(character, "creation_rules_active", False)) and (
        getattr(character, "creation_species_mode", "normal") == "required"
    )


def species_tool_visible(character):
    """Offer Add Species for standalone characters or required campaign species."""
    if character.improvements.has_species_improvement():
        return False
    if not getattr(character, "creation_rules_active", False):
        return True
    return is_species_required(character)


def species_field_visible(character):
    """Always show required campaign Species field, even before one is chosen."""
    return character.improvements.has_species_improvement() or is_species_required(character)
