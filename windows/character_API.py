# ==============================================================
# Character API / Game Catalog
# ==============================================================

STAT_NAMES = [
    "agility",
    "strength",
    "finesse",
    "instinct",
    "presence",
    "knowledge",
]

ABILITY_ARRAYS = [
    {
        "id": "adventurer",
        "name": "Adventurer Array",
        "description": "A balanced adventurer spread",
        "dice": [12, 10, 8, 8, 6, 4],
    },
    {
        "id": "hybrid",
        "name": "Hybrid Build",
        "description": "Strong in half of the stats, weaker in the other half.",
        "dice": [12, 10, 10, 6, 4, 4],
    },
    {
        "id": "specialist",
        "name": "Specialist Array",
        "description": "Excel in two stats.",
        "dice": [12, 12, 6, 6, 6, 4],
    },
    {
        "id": "prodigy",
        "name": "Prodigy Build",
        "description": "Excellent in some stats, very weak in the others.",
        "dice": [12, 12, 8, 4, 4, 4],
    },
    {
        "id": "backbone",
        "name": "Backbone Build",
        "description": "One strong stat and the rest reliable.",
        "dice": [12, 8, 8, 8, 8, 6],
    },
    {
        "id": "jack_of_all_trades",
        "name": "Jack of All Trades",
        "description": "Good at everything, but excels at none.",
        "dice": [10, 10, 10, 8, 6, 6],
    },
]


ANIMAL_BUDDY_PERKS = {
    "mobile": {
        "id": "mobile",
        "name": "Mobile",
        "description": (
            "Your companion has another method of movement, "
            "such as flying or swimming."
        ),
    },

    "sturdy": {
        "id": "sturdy",
        "name": "Sturdy",
        "description": (
            "Your companion has a base of <b>2 Hearts (8 HP)</b>."
        ),
        "effects": [
            {
                "type": "companion_base_hearts",
                "amount": 2,
            }
        ],
    },

    "large": {
        "id": "large",
        "name": "Large",
        "description": (
            "Your companion can carry an impressive amount of weight "
            "and occupies <b>double the space</b> of a normal character. "
            "<b>Cannot be combined with Small.</b>"
        ),
        "incompatible_with": ["small"],
    },

    "small": {
        "id": "small",
        "name": "Small",
        "description": (
            "Your companion has <b>permanent advantage</b> on checks "
            "to avoid being noticed and occupies <b>half the space</b> "
            "of a normal character. "
            "<b>Cannot be combined with Large.</b>"
        ),
        "incompatible_with": ["large"],
    },

    "fluid": {
        "id": "fluid",
        "name": "Fluid",
        "description": (
            "Your companion can fit through holes as small as "
            "<b>1 inch</b>."
        ),
    },

    "speedy": {
        "id": "speedy",
        "name": "Speedy",
        "description": (
            "Your companion moves at <b>twice the speed</b> "
            "of a normal character."
        ),
    },

    "custom": {
        "id": "custom",
        "name": "Custom",
        "description": (
            "Create a custom Natural Perk with your GM."
        ),
        "custom": True,
    },
}


ANIMAL_BUDDY_PERK_ORDER = tuple(ANIMAL_BUDDY_PERKS)


def normalize_animal_buddy_perk_id(value):
    """Return the API perk id for saved values; unknown legacy text is custom."""
    raw = str(value or "").strip()
    if not raw or raw.lower() == "missing":
        return ""

    lowered = raw.lower().replace("_", " ").strip()
    for perk_id, perk in ANIMAL_BUDDY_PERKS.items():
        if lowered in {perk_id.replace("_", " "), str(perk.get("name", "")).lower()}:
            return perk_id

    # Older characters stored arbitrary free-text perks directly in buddy_perk.
    return "custom"


def animal_buddy_perk_id_from_choices(choices):
    return normalize_animal_buddy_perk_id((choices or {}).get("buddy_perk"))


def animal_buddy_perk_name(choices):
    choices = choices or {}
    raw = str(choices.get("buddy_perk") or "").strip()
    perk_id = animal_buddy_perk_id_from_choices(choices)

    if perk_id == "custom":
        custom_name = str(choices.get("buddy_perk_custom_name") or "").strip()
        if custom_name:
            return custom_name
        # Preserve legacy free-text perks instead of replacing them with "Custom".
        if raw and raw.lower() not in {"custom", "missing"}:
            return raw
        return "Custom"

    perk = ANIMAL_BUDDY_PERKS.get(perk_id)
    return str((perk or {}).get("name") or raw or "None selected")


def animal_buddy_perk_description(choices):
    choices = choices or {}
    perk_id = animal_buddy_perk_id_from_choices(choices)
    if perk_id == "custom":
        return str(choices.get("buddy_perk_custom_description") or "").strip()
    return str(ANIMAL_BUDDY_PERKS.get(perk_id, {}).get("description") or "")


def animal_buddy_perk_is(choices, perk_id):
    return animal_buddy_perk_id_from_choices(choices) == str(perk_id or "").strip().lower()

IMPROVEMENT_CATALOG = {
    "sharpshooter": {
        "id": "sharpshooter",
        "name": "Sharpshooter",
        "cost": 2,
        "purchase_rule": "single",
        "tags": ["range"],
        "description": 'When using a ranged or throwable weapon, your <b>basic reach becomes Close range</b>. For each range level beyond your reach, the attack roll suffers <b>one stack of disadvantage</b>. Empowerments can extend your reach.',

        "owned_description": 'Ranged and throwable weapon reach: <b>{reach}</b>. One disadvantage per range level beyond it.',

        "scaling_values": {"reach": "close range"},
        
        "effects": [
            {
                "type": "set_basic_reach",
                "weapon_types": ["ranged", "throwable"],
                "range": "close",
            }
        ],
        
        "scaling_empowerments": {
            "reach": {
                "name": "Reach",
                'description': '<b>Increase your basic ranged or throwable weapon reach.</b> Purchase upgrades in order: Far (3 IP), then Very Far (4 IP).',
                              "owned_description": '',
                "rule": "ordered",
                "value_key": "reach",
                "steps": [
                    {
                        "value": "far range",
                        "cost": 3,
                               "owned_description": '',
                               "description": 'Increase the basic reach of ranged and throwable weapons to far range. One disadvantage applies for each further range level.',
                        "effects": [
                            {
                                "type": "set_basic_reach",
                                "weapon_types": ["ranged", "throwable"],
                                "range": "far",
                            }
                        ],
                    },
                    {
                        "value": "very far range",
                        "cost": 4,
                               "owned_description": '',
                               "description": 'Increase the basic reach of ranged and throwable weapons to very far range. One disadvantage applies for each further range level.',
                        "effects": [
                            {
                                "type": "set_basic_reach",
                                "weapon_types": ["ranged", "throwable"],
                                "range": "very_far",
                            }
                        ],
                    },
                ],
            }
        },
    },

    "born_of_soil": {
        "id": "born_of_soil",
        "name": "Born of Soil",
        "cost": 4,
        "purchase_rule": "single",
        "requires_choices": ["attuned_land", "attuned_land_description", "tell"],
        "tags": ["nature", "magic"],
        "description": 'You learned your magic in a place whose spirits are strong and ancient. They have marked you as one of their own. <b>Choose an attuned land.</b> Shapeshift into any animal that could naturally live there. <b>You retain your stats in every form.</b> Choose a tell—a physical attribute reflecting your land. It remains visible in every form. <b>Spend 1 AT</b> to suppress your tell for one hour.{wild_die_text}',

        "owned_description": 'Shapeshift into animals from your attuned lands; retain your stats. <b>Spend 1 AT</b> to hide your tell for an hour. {wild_die_text}',
        "scaling_values": {
            "attuned_lands": "your chosen attuned land",
            "wild_die": None,
            "wild_die_text": "",
            },
        "empowerments": [
            {
                "id": "additional_attuned_land",
                "name": "Additional Attuned Land",
                "cost": 2,
                "purchase_rule": "repeatable",
                "requires_choices": ["attuned_land", "attuned_land_description"],
                "description": 'After a period of adventuring, <b>choose one additional attuned land</b> in the land-selection interface. You can shapeshift into animals that naturally live there. No permanent land-list note is created.',
                              "owned_description": 'You can also transform into animals from your newly selected land.',
            }
        ],
        "scaling_empowerments": {
            "wild_die": {
                "name": "Wild Dice",
                'description': 'While in an appropriate animal form, add the current Wild Die to suitable <b>Agility, Strength, Instinct, or Finesse checks</b>, with GM approval. <b>Wild Dice do not explode.</b> Buy in order: d4 (2 IP), d6 (3 IP), d8 (4 IP), d10 (5 IP).',
                              "owned_description": '',
                "rule": "ordered",
                "applies_to_stats": ["agility", "strength", "instinct", "finesse"],
                "text_value_key": "wild_die_text",
                "steps":[
                    {
                        "value": 4,
                        "cost": 2,
                        "text_value": 'When using the corresponding ability, add your <b>d4 Wild Die</b> to the appropriate rolls. <b>Wild Dice do not explode.</b>',
                                     "owned_description": '',
                                     "description": 'Upgrade the Wild Die to d4. Add it on suitable physical animal-form checks with GM approval. <b>Wild Dice do not explode.</b>',
                        "effects": [
                            {"type": "set_bonus_die",
                             "key": "wild_die",
                             "die_size": 4
                            }
                        ]
                    },
                    {
                        "value": 6,
                        "cost": 3,
                        "text_value": 'When using the corresponding ability, add your <b>d6 Wild Die</b> to the appropriate rolls. <b>Wild Dice do not explode.</b>',
                                     "owned_description": '',
                                     "description": 'Upgrade the Wild Die to d6. Add it on suitable physical animal-form checks with GM approval. <b>Wild Dice do not explode.</b>',
                        "effects": [
                            {
                                "type": "set_bonus_die",
                                "key": "wild_die",
                                "die_size": 6
                            }
                        ]
                    },
                    {
                        "value": 8,
                        "cost": 4,
                        "text_value": 'When using the corresponding ability, add your <b>d8 Wild Die</b> to the appropriate rolls. <b>Wild Dice do not explode.</b>',
                                     "owned_description": '',
                                     "description": 'Upgrade the Wild Die to d8. Add it on suitable physical animal-form checks with GM approval. <b>Wild Dice do not explode.</b>',
                        "effects": [
                            {
                                "type": "set_bonus_die",
                                "key": "wild_die",
                                "die_size": 8
                            }
                        ]
                    },
                    {
                        "value": 10,
                        "cost": 5,
                        "text_value": 'When using the corresponding ability, add your <b>d10 Wild Die</b> to the appropriate rolls. <b>Wild Dice do not explode.</b>',
                                     "owned_description": '',
                                     "description": 'Upgrade the Wild Die to d10. Add it on suitable physical animal-form checks with GM approval. <b>Wild Dice do not explode.</b>',
                        "effects": [
                            {"type": "set_bonus_die",
                             "key": "wild_die",
                             "die_size": 10
                            }
                        ]
                    },
                ],
            }
        },
    },

    "wild_eyes": {
        "id": "wild_eyes",
        "name": "Wild Eyes",
        "cost": 1,
        "purchase_rule": "single",
        "tags": ["nature", "magic", "resource"],
        "description": 'Mark an animal with mud, dirt, or blood to <b>see through its eyes</b>, regardless of distance. You may have <b>only one marked animal</b> at a time; marking another ends the previous mark.',
        'owned_description': 'Mark an animal with mud, dirt, or blood to see through its eyes at any distance. <b>One marked animal at a time.</b>',
    },

    "wild_empathy": {
        "id": "wild_empathy",
        "name": "Wild Empathy",
        "cost": 1,
        "purchase_rule": "single",
        "tags": ["nature", "resource"],
        "description": 'You can <b>speak with and understand animals</b>. Ask what they have seen, heard, smelled, feared, wanted, or learned. Their answers are limited by their animal perspective.',
        'owned_description': 'Speak with and understand animals; their knowledge is limited by their perspective.',
        "empowerments": [
            {

                "id": "thing_talker",
                "name": "Thing Talker",
                "cost": 2,
                "description": 'You can also <b>speak with the spirits of objects and plants</b>. Ancient objects and plants may have deep insights, but their knowledge is limited by their surroundings and experiences.',
                              "owned_description": 'Speak with object and plant spirits; they know only what they have experienced.',
            }
        ],
    },

    "communion_of_whispers": {
        "id": "communion_of_whispers",
        "name": "Communion of Whispers",
        "cost": 1,
        "purchase_rule": "single",
        "tags": ["nature", "resource"],
        "description": 'Spend time in a place, observe its residents, and call on its ancient spirits to receive a vision significant to you, your allies, or the spirits. The vision is unclear unless you <b>spend 1 AT</b> to make it clear and helpful.',
        'owned_description': 'Receive an unclear vision from local spirits. <b>Spend 1 AT</b> for a clear, helpful vision.',

        "empowerments": [
            {
                "id": "animist",
                "name": "Animist",
                "cost": 2,
                "description": '<b>Once per location</b>, receive a clear vision about a specific interest, with GM approval. <b>Spend 1 AT</b> for an additional vision in the same location.',
                              "owned_description": 'Once per location, obtain a clear vision about a specific interest; <b>1 AT</b> for another vision.',
            }
        ],
    },
            

    "camouflage": {
        "id": "camouflage",
        "name": "Camouflage",
        "cost": 2,
        "purchase_rule": "single",
        "tags": ["stealth"],
        "description": 'When you remain still in natural surroundings, <b>enemies cannot spot you until you move</b>, with GM approval. Even while moving, you have <b>advantage on checks to avoid being noticed</b> in natural surroundings.',
        'owned_description': 'In nature, staying still prevents detection (GM discretion). <b>Advantage on stealth checks</b> even when moving.',
    },

    "animal_buddy": {
        "id": "animal_buddy",
        "name": "Animal Buddy",
        "cost": 3,
        "purchase_rule": "single",
        "requires_choices": [
            "buddy_name",
            "buddy_stat_d6",
            "buddy_stat_d8_a",
            "buddy_stat_d8_b",
            "buddy_stat_d10",
            "buddy_perk",
        ],
        "tags": ["nature", "support", "rolls"],
        "description": 'You gain an animal companion. It acts as a second character you control when acting independently, but <b>cannot gain Improvements or GM-granted progression</b>. When present and able to help, add its <b>d{buddy_die} Buddy Die</b> to your check. Assign d10, d8, d8, and d6 to four stats; the remaining two are d4. Your buddy starts with 1 Heart (4 HP), has BDV equal to half yours rounded up, and gains one Natural Perk. <b>It cannot die permanently:</b> at 0 HP it is taken out of commission or scared off. <b>It recovers Hearts like any other character.</b> See its permanent note for the buddy you chose.',

        "owned_description": 'When your buddy helps, add <b>d{buddy_die}</b> to the check. It can also act independently. See its note for stats, perks, and recovery.',

        "scaling_values": {"buddy_die": 4, "buddy_hearts": 1},

        "creates": {
            "type": "companion",
            "key": "animal_buddy",
            "default_hearts": 1,
            "buddy_die": 4,
            "bdv_rule": "half_owner_bdv_rounded_up",
            "stat_array": [10, 8, 8, 6, 4, 4],
        },
        "effects": [
            {"type": "set_bonus_die", "key": "buddy_die", "die_size": 4}
        ],
        "empowerment_groups": {
            "training": {
                "id": "training",
                "name": "Training",
                "rule": "any",
                "options": [
                    {
                        "id": "well_trained",
                        "name": "Well Trained",
                        "cost": 1,
                        "description": 'Give your buddy a permanent stat bonus following Heightened Ability: <b>+1 costs 1 IP, increasing to +2 costs 2 additional IP</b>, and so on. You may improve the same stat repeatedly.',
                                      "owned_description": 'Your buddy gains its chosen permanent stat bonus (shown in its stats).',
                    },
                    {
                        "id": "gifted",
                        "name": "Gifted",
                        "cost": 2,
                        "requires_choices": ["buddy_perk"],
                        "description": 'Choose <b>one additional Natural Perk</b> for your buddy from the perk list, or choose <b>Custom</b> to create an appropriate perk with the GM.',
                                      "owned_description": 'Your buddy gains its newly selected perk.',
                    },
                ],
            },
        },
        "scaling_empowerments": {
            "buddy_hearts": {
                "name": "Extra Heart",
                "rule": "repeatable_scaling",
                "max_times": 3,
                "base_cost": 2,
                "cost_increase": 1,
                "value_key": "buddy_hearts",
                "increase_by": 1,
                "description": 'Your buddy gains <b>1 additional Heart (4 HP)</b>. May be purchased up to three times at <b>2, then 3, then 4 IP</b>. If Sturdy is selected, it establishes a base of 2 Hearts; each Extra Heart adds 1 more.',
                              "owned_description": '',
                "effects": [
                    {
                        "type": "companion_add_heart",
                        "companion_key": "animal_buddy",
                        "amount": 1,
                    }
                ],
            }
        }
    },

    "martial_feats": {
        "id": "martial_feats",
        "name": "Martial Feats",
        "cost": 3,
        "purchase_rule": "single",
        "tags": ["might", "rolls"],
        "description": "When rolling with a weapon, declare a martial deed and add your <b>d{martial_die} Martial Die</b>. If that die rolls <b>3 or higher</b>, perform a reasonable feat or inflict a narrative consequence or condition, with GM approval. Examples: pole-vault with a spear, knock an enemy dizzy, or injure a leg with an arrow. A condition lasts until the start of your side's next turn. <b>Martial Dice do not explode.</b>",

        "owned_description": 'Add <b>d{martial_die}</b> to a weapon roll when declaring a deed. On <b>3+</b>, perform a reasonable deed or impose a condition until your side’s next turn. <b>No exploding.</b>',

        "scaling_values": {
            "martial_die": 4
        },
        
        "effects": [
            {
                "type": "set_bonus_die",
                "key": "martial_die",
                "die_size": 4,
            }
        ],
        "scaling_empowerments": {
            "martial_die": {
                "name": "Martial Die",
                'description': 'Increase your Martial Die in order: <b>d6 (3 IP), d8 (4 IP), d10 (5 IP)</b>. This replaces the previous die. <b>Martial Dice do not explode.</b>',
                              "owned_description": '',
                "rule": "ordered",
                "value_key": "martial_die",
                "steps": [
                    {
                        "value": 6,
                        "cost": 3,
                               "owned_description": '',
                               "description": 'Upgrade your Martial Die to d6. Add it to weapon rolls for deeds; on 3+, a reasonable deed succeeds (GM discretion). <b>Martial Dice do not explode.</b>',
                        "effects": [
                            {
                                "type": "set_bonus_die",
                                "key": "martial_die",
                                "die_size": 6
                            }
                        ],
                    },
                    {
                        "value": 8,
                        "cost": 4,
                               "owned_description": '',
                               "description": 'Upgrade your Martial Die to d8. Add it to weapon rolls for deeds; on 3+, a reasonable deed succeeds (GM discretion). <b>Martial Dice do not explode.</b>',
                        "effects": [
                            {
                                "type": "set_bonus_die",
                                "key": "martial_die",
                                "die_size": 8
                            }
                        ],
                    },
                    {
                        "value": 10,
                        "cost": 5,
                               "owned_description": '',
                               "description": 'Upgrade your Martial Die to d10. Add it to weapon rolls for deeds; on 3+, a reasonable deed succeeds (GM discretion). <b>Martial Dice do not explode.</b>',
                        "effects": [
                            {
                                "type": "set_bonus_die",
                                "key": "martial_die",
                                "die_size": 10
                            }
                        ],
                    },
                ],
            }
        },
    },

    "shoot_first": {
        "id": "shoot_first",
        "name": "Shoot First",
        "cost": 3,
        "purchase_rule": "single",
        "tags": ["stealth"],
        "description": 'You are <b>never caught by surprise</b>. When an enemy would get the drop on you, <b>you act first instead</b>.',
        'owned_description': 'Never surprised: <b>act first</b> when an enemy gets the drop on you.',
    },

    "trap_expert": {
        "id": "trap_expert",
        "name": "Trap Expert",
        "cost": 1,
        "purchase_rule": "single",
        "tags": ["resource"],
        "description": 'Survey a dangerous area to ask the GM <b>one question about environmental dangers</b>; the GM must answer honestly. <b>Spend 1 AT per additional question.</b> Examples: Is there a trap and what activates it? What does it do? What else is hidden? Multiple characters with Trap Expert may survey the same area.',
        'owned_description': 'Survey danger: ask the GM <b>one question</b>; <b>1 AT</b> for each extra question. Answers are honest.',
    },

    "sneak_attack": {
        "id": "sneak_attack",
        "name": "Sneak Attack",
        "cost": 3,
        "purchase_rule": "single",
        "tags": ["stealth"],
        "description": '<b>When you hit a surprised or distracted enemy</b>, choose one Sneak Attack effect; <b>spend 1 AT per additional effect</b>. Your base options let you avoid entering Melee, impose disadvantage, create an advantage, hide, or deal <b>+{sneak_attack_damage} HP</b>. Purchased Empowerments add effects or increase the damage. See your Sneak Attack note for the complete list.',
        'owned_description': 'Hit a surprised or distracted enemy: choose one Sneak Attack effect; <b>1 AT</b> per additional effect. Extra-damage option: <b>+{sneak_attack_damage} HP</b>. See the note for effects.',
        "scaling_values": {
            "sneak_attack_damage": 1,
        },
        
        "empowerment_groups": {
            "extra_effects": {
                "id": "extra_effects",
                "name": "Additional Sneak Attack Effects",
                "rule": "any",
                "options": [
                    {
                        "id": "hobbled",
                        "name": "Hobbled",
                        "cost": 1,
                        "description": 'Add a Sneak Attack option: the target becomes hobbled and slow-moving. <b>Reduce its movement range by one range level.</b>',
                                      "owned_description": 'Reduce the target’s movement by one range level.',
                    },
                    {
                        "id": "drop_item",
                        "name": "Drop Item",
                        "cost": 1,
                        "description":'Add a Sneak Attack option: <b>the target drops anything it is holding.</b>',
                                     "owned_description": 'The target drops what it is holding.',
                    },
                    {
                        "id": "drooling",
                        "name": "Stunned and Drooling",
                        "cost": 1,
                        "description": "Add a Sneak Attack option: the target stands stunned and drooling for a few moments and <b>cannot act on its side's next turn.</b>",
                                      "owned_description": 'The target cannot act on its side’s next turn.',
                    },
                ],
            },
        },
        "scaling_empowerments": {
            "sneak_attack_damage": {
                "name": "Sneak Attack Damage",
                "rule": "repeatable_scaling",
                "max_times": 3,
                "base_cost": 2,
                "cost_increase": 1,
                "value_key": "sneak_attack_damage",
                "increase_by": 1,
                "description": 'Increase your extra-damage Sneak Attack option by <b>+1 HP</b> per purchase. You may purchase this three times at <b>2, then 3, then 4 IP</b>. The bonus applies only when you choose the extra-damage effect.',
                              "owned_description": '',
                "effects": [
                    {
                        "type": "increase_sneak_attack_damage",
                        "amount": 1,
                    },
                ],
            },
        },
    },

    "spin_attack": {
        "id": "spin_attack",
        "name": "Spin Attack",
        "cost": 1,
        "purchase_rule": "single",
        "tags": ["multi_target"],
        "description": '<b>Spend 1 AT</b> to make one combat roll against every enemy within Melee range. For each enemy you hit, deal damage or inflict a status effect.',
        'owned_description': '<b>Spend 1 AT:</b> Roll once against all enemies in Melee; damage or inflict a status effect on each hit.',
    },

    "trick_shot": {
        "id": "trick_shot",
        "name": "Trick Shot",
        "cost": 2,
        "purchase_rule": "single",
        "tags": ["range"],
        "description": '<b>Spend 1 AT</b> to target a location with a ranged weapon without direct line of sight, provided you can see a point from which the shot can bounce to its target. <b>Spend 1 additional AT per additional bounce.</b>',
        'owned_description': '<b>Spend 1 AT</b> to attack via a visible bounce point without direct line of sight; <b>1 AT</b> per extra bounce.',
    },

    "blow_out_the_sun": {
        "id": "blow_out_the_sun",
        "name": "Blow Out the Sun",
        "cost": 2,
        "purchase_rule": "single",
        "tags": ["range", "multi_target"],
        "description": 'When volleying with a ranged weapon, spend AT before rolling. Choose <b>one additional target per AT spent</b>. Roll once and apply damage to each target you hit.',
        'owned_description': 'Before a ranged volley, spend <b>1 AT per extra target</b>. Roll once; damage targets you hit.',
    },

    "healer": {
        "id": "healer",
        "name": "Healer",
        "cost": 4,
        "purchase_rule": "single",
        "tags": ["healing", "magic", "support"],
        "description": 'Touch someone skin to skin and channel magic. Choose: clear <b>{healing_dice} HP</b>, use the fixed halved value of <b>{halved_hp} HP</b>, or heal one narrative injury. Heal each person <b>once per dawn</b>; to heal the same person again before dawn, spend <b>{repeat_healing_cost} AT</b>. You have <b>advantage</b> on rolls to stabilize dying creatures.',

        "owned_description": 'Touch to heal <b>{healing_dice} HP</b> (or fixed {halved_hp} HP) or one injury. Once per person per dawn; repeat: <b>{repeat_healing_cost} AT</b>. Advantage stabilizing.',
        
        "scaling_values": {
            "healing_dice": "1d6",
            "halved_hp": 3,
            "repeat_healing_cost": 3
        },
        
        "scaling_empowerments": {
            "repeat_healing_cost": {
                "name": "Repeat Healing Cost",
                'description': 'Reduce the AT cost of healing the same person again before dawn. Buy in order: <b>2 AT for 2 IP</b>, then <b>1 AT for 3 IP</b>.',
                              "owned_description": '',
                "rule": "ordered",
                "steps": [
                    {
                        "value": 2,
                        "cost": 2,
                               "owned_description": '',
                               "description": 'Reduce the AT cost for repeat healing on the same person before dawn to 2 AT.',
                        "effects": [
                            {"type": "set_action_cost",
                             "action_id": "repeat_healing",
                             "cost": 2
                             }
                        ]
                    },
                    {
                        "value": 1,
                        "cost": 3,
                               "owned_description": '',
                               "description": 'Reduce the AT cost for repeat healing on the same person before dawn to 1 AT.',
                        "effects": [
                            {
                                "type": "set_action_cost",
                                "action_id": "repeat_healing",
                                "cost": 1
                            }
                        ]
                    },
                ],
            },
            "healing_dice": {
                "name": "Healing Amount",
                'description': 'Increase the healing per use. Buy in order: <b>2d6 HP (or fixed 6 HP) for 3 IP</b>, then <b>3d6 HP (or fixed 9 HP) for 4 IP</b>.',
                              "owned_description": '',
                "rule": "ordered",
                "updates": {
                    2: {
                        "healing_dice": "2d6",
                        "halved_hp": 6
                        },
                    3: {
                        "healing_dice": "3d6",
                        "halved_hp": 9
                        }
                    },
                "steps": [
                    {
                        "value": 2,
                        "cost": 3,
                               "owned_description": '',
                               "description": 'Upgrade each healing burst to 2d6 HP, or the fixed halved value instead.',
                        "effects": [
                            {"type": "set_healing_die_count",
                             "amount": 2
                            }
                        ]
                    },
                    {
                        "value": 3,
                        "cost": 4,
                               "owned_description": '',
                               "description": 'Upgrade each healing burst to 3d6 HP, or the fixed halved value instead.',
                        "effects": [
                            {"type": "set_healing_die_count",
                             "amount": 3
                            }
                        ]
                    },
                ],
            },
        },
    },
        
    "physician": {
        "id": "physician",
        "name": "Physician",
        "cost": 2,
        "purchase_rule": "single",
        "tags": ["healing", "support"],
        "description": 'Given enough time and supplies, and with GM approval, medically treat a creature you understand. During a rest, clear an <b>additional 2 HP</b> from it, <b>once per person each day cycle</b>. You have advantage on rolls to stabilize dying creatures.',
        "owned_description": 'During a rest, treat a creature you understand with time and supplies: <b>+2 HP</b> once per person per day. Advantage stabilizing.',
        
        "effects": [
            {"type": "rest_healing_bonus", "amount": 2}
        ],
    },

    "hearty": {
        "id": "hearty",
        "name": "Hearty",
        "cost": 2,
        "purchase_rule": "repeatable_scaling",
        "max_times": 3,
        "base_cost": 2,
        "cost_increase": 1,
        "base_value": 1,
        "increase_by": 1,
        "value_key": "hp_per_heart",
        "tags": ["might"],
        "description": 'Gain <b>+{hp_per_heart} HP per Heart</b> you have or gain. Purchase Hearty up to three times: <b>2, then 3, then 4 IP</b>.',
        'owned_description': 'Gain <b>+{hp_per_heart} HP per Heart</b>, including future Hearts.',
        "effects": [
            {
                "type": "max_hp_per_heart",
                "amount": 1,
            }
        ],
    },

    "deity": {
        "id": "deity",
        "name": "Deity",
        "cost": 2,
        "purchase_rule": "single",
        "requires_choices": ["deity_name", "deity_domain"],
        "tags": ["magic", "resource"],
        "description": "Spend about an hour in quiet, uninterrupted communion with your deity to gain useful knowledge, with GM approval. Petition according to your religion's teachings and spend AT to receive a boon related to your deity's domain. <b>More AT means a greater boon.</b> Explain your intentions to the GM. Have faith.",
        'owned_description': 'About an hour of communion grants knowledge (GM discretion). Petition your deity for a boon by spending AT; <b>more AT = greater boon.</b>',
    },

    "minstrel": {
        "id": "minstrel",
        "name": "Minstrel",
        "cost": 1,
        "purchase_rule": "single",
        "tags": ["resource"],
        "description": 'You are a traveling scholar or performer sharing tales and knowledge. On first entering a civilized settlement, someone honoring hospitality to minstrels welcomes you as a guest. At an important location of your choosing, ask the GM for <b>one historical fact</b> you heard in a tale or read in a book.',
        'owned_description': 'Receive hospitality in settlements that honor minstrels. At an important location, ask for <b>one historical fact</b>.',
    },

    "prestidigitation": {
        "id": "prestidigitation",
        "name": "Prestidigitation",
        "cost": 1,
        "purchase_rule": "single",
        "tags": ["magic"],
        "description": 'Perform minor tricks of true magic. Touch an item to clean, soil, cool, warm, flavor, or recolor it. Without touching an item, create a minor illusion no larger than yourself. <b>Illusions are crude and obvious; they cannot fool anyone.</b>',
        'owned_description': 'Touch an item for cosmetic magic, or create an illusion no larger than yourself. <b>Illusions cannot fool anyone.</b>',
    },

    "spellcasting": {
        "id": "spellcasting",
        "name": "Spellcasting",
        "cost": 4,
        "purchase_rule": "single",
        "requires_choices": ["magic_school", "magic_school_description"],
        "tags": ["magic", "rolls"],
        "description": 'You can <b>cast spells</b> that fit your chosen school of magic; agree on any custom school with the GM. Use the <b>magic verb chart</b> to choose the stat for each effect. Simple harmless magic may need no roll (GM discretion); complex magic follows the spell rules. <b>Magical attacks:</b> Melee range by default unless another ability extends it. <b>Harmful or beneficial spells:</b> Close range, no larger than a Melee-radius area, and <b>only one creature</b>. <b>Harmless effects:</b> Far range; the area influences the DC. You cannot cast effects outside your chosen school or these limits unless an ability explicitly permits it. The permanent Spellcasting note contains <b>only the six-stat verb chart</b>; write personal spell information in your own notes.',
        'owned_description': 'Cast spells within your chosen schools. Use the <b>magic verb chart</b> to choose a stat.{magic_die_text}',

        "scaling_values": {
            "magic_die": None,
            "magic_die_text": ""
        },
        "scaling_empowerments": {
            "magic_die": {
                "name": "Magic Die",
                'description': 'Gain a Magic Die for spell rolls and other rolls benefiting from your magic. Buy in order: <b>d4 (3 IP), d6 (4 IP), d8 (5 IP), d10 (6 IP)</b>. <b>Magic Dice do not explode.</b>',
                              "owned_description": '',
                "rule": "ordered",
                "text_value_key": "magic_die_text",
                "steps": [
                    {
                        "value": 4,
                        "cost": 3,
                        "text_value": '<br><b>Magic Die: d4</b><br>Magic Dice do not explode.',
                                     "owned_description": '',
                                     "description": 'Gain a d4 Magic Die for spells and rolls that benefit from your magic. <b>Magic Dice do not explode.</b>',
                        "effects": [
                            {"type": "set_bonus_die",
                             "key": "magic_die",
                             "die_size": 4
                            }
                        ]
                    },
                    {
                        "value": 6,
                        "cost": 4,
                        "text_value": '<br><b>Magic Die: d6</b><br>Magic Dice do not explode.',
                                     "owned_description": '',
                                     "description": 'Gain a d6 Magic Die for spells and rolls that benefit from your magic. <b>Magic Dice do not explode.</b>',
                        "effects": [
                            {
                                "type": "set_bonus_die",
                                "key": "magic_die",
                                "die_size": 6
                            }
                        ]
                    },
                    {
                        "value": 8,
                        "cost": 5,
                        "text_value": '<br><b>Magic Die: d8</b><br>Magic Dice do not explode.',
                                     "owned_description": '',
                                     "description": 'Gain a d8 Magic Die for spells and rolls that benefit from your magic. <b>Magic Dice do not explode.</b>',
                        "effects": [
                            {"type": "set_bonus_die",
                             "key": "magic_die",
                             "die_size": 8
                            }
                        ]
                    },
                    {
                        "value": 10,
                        "cost": 6,
                        "text_value": '<br><b>Magic Die: d10</b><br>Magic Dice do not explode.',
                                     "owned_description": '',
                                     "description": 'Gain a d10 Magic Die for spells and rolls that benefit from your magic. <b>Magic Dice do not explode.</b>',
                        "effects": [
                            {
                                "type": "set_bonus_die",
                                "key": "magic_die",
                                "die_size": 10
                            }
                        ]
                    },
                ],
            },
        },
        "empowerment_groups": {
            "school_savant": {
                "id": "school_savant",
                "name": "School Savant",
                "rule": "repeatable_scaling",
                "base_cost": 2,
                "cost_increase": 1,
                "requires_choices": ["magic_school", "magic_school_description"],
                "description": '<b>Choose an additional school of magic.</b> You can cast spells from it under your Spellcasting rules. You may purchase additional schools for <b>2 IP, then 3 IP, then 4 IP</b>, and so on; this branch has its own progression.',
                              "owned_description": ''
            },
        },
        "empowerments": [
            {
                "id": "harm_slinger",
                "name": "Harm Slinger",
                "cost": 2,
                "tags": ["magic", "multi_target", "range"],
                "description": 'When casting a <b>harmful non-attack spell on an unwilling target</b>, spend an <b>AT</b> to choose one of the new abilities in your Spellcasting note. Choose additional abilities for each extra <b>AT</b> spent.',
                "owned_description": 'When casting a <b>harmful non-attack spell on an unwilling target</b>, spend an <b>AT</b> to choose one of the new abilities in your Spellcasting note. Choose additional abilities for each extra <b>AT</b> spent.'
            },
            {
                "id": "expert_enchanter",
                "name": "Expert Enchanter",
                "cost": 2,
                "tags": ["magic", "multi_target", "range", "support"],
                "description": 'When casting a spell that affects a <b>willing living being or an object</b>, spend an <b>AT</b> to choose one of the new abilities in your Spellcasting note. Choose additional abilities for each extra <b>AT</b> spent.',
                "owned_description": 'When casting a spell that affects a <b>willing living being or an object</b>, spend an <b>AT</b> to choose one of the new abilities in your Spellcasting note. Choose additional abilities for each extra <b>AT</b> spent.'
            },
        ],
    },

        
    "magic_novice": {
        "id": "magic_novice",
        "name": "Magic Novice",
        "cost": 2,
        "purchase_rule": "single",
        "requires_choices": ["specific_magic_effect"],
        "tags": ["magic", "rolls"],
        "description": 'Master one specific magical ability, agreed with the GM (such as manipulating water, vines, flames, or a spirit). <b>Choose a spellcasting stat</b> for attacks with it. Your effect follows normal Spellcasting limits; agree with the GM whether it requires a skill check or works on command. At GM discretion, spend AT to stretch its limits. <b>Magical attacks: Melee reach by default</b> unless another ability changes it. {magic_die_text}',
        'owned_description': 'Use your one agreed magical effect under Spellcasting limits. The GM determines when to roll and may allow AT to stretch it.{magic_die_text}',
        "scaling_values": {
            "magic_die": None,
            "magic_die_text": ""
        },
        "empowerments": [
            {"id": "upgrade_to_spellcasting", "name": "Upgrade to Spellcasting", "cost": 2, "requires_choices": ["magic_school"], "description": '<b>Replace Magic Novice with Spellcasting</b> for 2 IP. Keep your spellcasting stat where possible; choose a school. Convert matching Magic Die upgrades without repurchasing them.',
                                                                                                                                                "owned_description": '', "effects": [{"type": "replace_improvement", "remove": "magic_novice", "add": "spellcasting", "preserve_choices": ["spellcasting_stat"], "requires_new_choices": ["magic_school"], "convert_improvements": [{"from_group": "magic_die", "from_key": "magic_novice_die", "to_group": "magic_die", "to_key": "magic_die", "id_map": {"magic_novice_die_d4": "magic_die_d4", "magic_novice_die_d6": "magic_die_d6", "magic_novice_die_d8": "magic_die_d8", "magic_novice_die_d10": "magic_die_d10"}}]}]},
        ],
        "scaling_empowerments": {
            "magic_die": {
                "name": "Magic Die",
                'description': 'Gain a Magic Die for rolls benefiting from your chosen magical ability. Buy in order: <b>d4 (3 IP), d6 (4 IP), d8 (5 IP), d10 (6 IP)</b>. <b>Magic Dice do not explode.</b>',
                              "owned_description": '',
                "rule": "ordered",
                "text_value_key": "magic_die_text",
                "steps": [
                    {
                        "value": 4,
                        "cost": 3,
                        "text_value": '<br><b>Magic Die: d4</b><br>Magic Dice do not explode.',
                                     "owned_description": '',
                                     "description": 'Gain a d4 Magic Die for spells and rolls that benefit from your magic. <b>Magic Dice do not explode.</b>', "effects": [{"type": "set_bonus_die", "key": "magic_novice_die", "die_size": 4}]},
                    {
                        "value": 6, "cost": 4, "text_value": '<br><b>Magic Die: d6</b><br>Magic Dice do not explode.',
                                                            "owned_description": '',
                                                            "description": 'Gain a d6 Magic Die for spells and rolls that benefit from your magic. <b>Magic Dice do not explode.</b>', "effects": [{"type": "set_bonus_die", "key": "magic_novice_die", "die_size": 6}]},
                    {"value": 8, "cost": 5, "text_value": '<br><b>Magic Die: d8</b><br>Magic Dice do not explode.',
                                                         "owned_description": '',
                                                         "description": 'Gain a d8 Magic Die for spells and rolls that benefit from your magic. <b>Magic Dice do not explode.</b>', "effects": [{"type": "set_bonus_die", "key": "magic_novice_die", "die_size": 8}]},
                    {"value": 10, "cost": 6, "text_value": '<br><b>Magic Die: d10</b><br>Magic Dice do not explode.',
                                                          "owned_description": '',
                                                          "description": 'Gain a d10 Magic Die for spells and rolls that benefit from your magic. <b>Magic Dice do not explode.</b>', "effects": [{"type": "set_bonus_die", "key": "magic_novice_die", "die_size": 10}]},
                ],
            }
        },
    },
        
    "eye_for_weakness": {
        "id": "eye_for_weakness",
        "name": "Eye for Weakness",
        "cost": 2,
        "purchase_rule": "single",
        "tags": ["resource"],
        "description": "<b>Spend 1 AT</b> to ask the GM, 'What here is weak or vulnerable?' The GM answers honestly, to the best of their ability. Attacking the identified weak area grants <b>advantage and +1 HP damage</b>. <b>You cannot forgo this advantage for additional damage.</b>",
        'owned_description': '<b>Spend 1 AT</b> to learn a weakness. Attack it with <b>advantage and +1 HP</b>; you cannot trade that advantage for damage.',
    },

    "wide_wanderer": {
        "id": "wide_wanderer",
        "name": "Wide-Wanderer",
        "cost": 1,
        "purchase_rule": "single",
        "tags": ["resource"],
        "description": 'You have traveled widely. When you arrive somewhere, ask the GM about important traditions, rituals, customs, or similar local knowledge; they tell you what you need to know.',
        'owned_description': 'When arriving somewhere, ask the GM about important local customs and traditions.',
    },

    "mighty": {
        "id": "mighty",
        "name": "Mighty",
        "cost": 3,
        "purchase_rule": "single",
        "tags": ["might", "rolls"],
        "description": 'Regardless of your size, you are a physical wonder. Add your <b>d{mighty_die} Mighty Die</b> to stat checks requiring physical effort. For an athletic challenge, choose <b>one Mighty benefit</b> (DC -5, reduced effective size, farther movement, weakened material, or reduced vertical distance). <b>Spend 1 AT</b> to activate one additional benefit for the same challenge. <b>Mighty Dice do not explode.</b> See your Mighty note for the full list.',
        'owned_description': 'Add <b>d{mighty_die}</b> to physical-effort checks. Choose one athletic benefit; <b>1 AT</b> for one extra. See Mighty note. Dice do not explode.',
        "scaling_values": {"mighty_die": 4},
        "effects": [
            {
                "type": "set_bonus_die",
                "key": "mighty_die",
                "die_size": 4}
        ],
        
        "scaling_empowerments": {
            "mighty_die": {
                "id": "mighty_die",
                'description': 'Increase your Mighty Die in order: <b>d6 (2 IP), d8 (3 IP), d10 (4 IP)</b>. Each upgrade replaces the previous die. <b>Mighty Dice do not explode.</b>',
                              "owned_description": '',
                "name": "Mighty Die",
                "rule": "ordered",
                "value_key": "mighty_die",
                "steps": [
                    {
                        "value": 6,
                        "cost": 2,
                               "owned_description": '',
                               "description": 'Upgrade your Mighty Die to d6. Add it to physical-effort stat checks. <b>Mighty Dice do not explode.</b>',
                        "effects": [
                            {
                                "type": "set_bonus_die",
                                "key": "mighty_die",
                                "die_size": 6
                            }
                        ]
                    },
                    {
                        "value": 8,
                        "cost": 3,
                               "owned_description": '',
                               "description": 'Upgrade your Mighty Die to d8. Add it to physical-effort stat checks. <b>Mighty Dice do not explode.</b>',
                        "effects": [
                            {
                                "type": "set_bonus_die",
                                "key": "mighty_die",
                                "die_size": 8
                            }
                        ]
                    },
                    {
                        "value": 10,
                        "cost": 4,
                               "owned_description": '',
                               "description": 'Upgrade your Mighty Die to d10. Add it to physical-effort stat checks. <b>Mighty Dice do not explode.</b>',
                        "effects": [
                            {
                                "type": "set_bonus_die",
                                "key": "mighty_die",
                                "die_size": 10
                            }
                        ]
                    },
                ]
            }
        }
    },

    "torturer": {
        "id": "torturer",
        "name": "Torturer",
        "cost": 2,
        "purchase_rule": "single",
        "tags": ["rolls", "might"],
        "description": 'When you parley using threats of impending violence as leverage, you have <b>advantage on the roll</b>.',
        'owned_description': '<b>Advantage</b> when parleying with threats of impending violence.',
    },

    "berserker": {
        "id": "berserker",
        "name": "Berserker",
        "cost": 2,
        "purchase_rule": "repeatable_scaling",
        "max_times": 3,
        "base_cost": 2,
        "cost_increase": 1,
        "base_value": 1,
        "increase_by": 1,
        "value_key": "extra_at_from_damage",
        "tags": ["might"],
        "description": 'Whenever you gain AT from taking damage, gain <b>+{extra_at_from_damage} additional AT</b>. Purchase up to three times: <b>2, then 3, then 4 IP</b>.',
        'owned_description': 'Whenever damage grants AT, gain <b>+{extra_at_from_damage} additional AT</b>.',
    },

    "reckless_attack": {
        "id": "reckless_attack",
        "name": "Reckless Attack",
        "cost": 2,
        "purchase_rule": "single",
        "tags": ["might", "rolls"],
        "description": 'When making your attack on your turn, you may attack recklessly. Gain <b>advantage on melee attacks during this turn</b>, but <b>attacks against you have advantage until your next turn</b>.',
        'owned_description': 'On your attack on your turn, if you attack recklessly: gain advantage on melee attacks this turn; enemies have advantage against you until your next turn.',
    },

    "shared_pain": {
        "id": "shared_pain",
        "name": "Shared Pain",
        "cost": 2,
        "purchase_rule": "single",
        "tags": ["healing", "support"],
        "description": 'Clear any amount of marked HP from an ally by marking the same amount on yourself. <b>You gain AT from this damage normally.</b>',
        'owned_description': 'Clear an ally’s HP damage by taking equal damage yourself. <b>Gain AT normally.</b>',
    },

    "piercer": {
        "id": "piercer",
        "name": "Piercer",
        "cost": 1,
        "purchase_rule": "single",
        "tags": ["range", "multi_target"],
        "description": '<b>Spend 1 AT</b> to make a combat roll against every enemy in a <b>Very Close line</b> originating from you. On each hit, deal damage or inflict disadvantage.',
        'owned_description': '<b>Spend 1 AT:</b> Roll against all enemies in a <b>Very Close line</b>; damage or impose disadvantage on each hit.',
    },

    "baller": {
        "id": "baller",
        "name": "Baller",
        "cost": 2,
        "purchase_rule": "single",
        "tags": ["range", "multi_target"],
        "description": '<b>Spend 1 AT</b> to create a <b>Very Close-radius sphere</b> within Close range. Make one combat roll against every creature inside, <b>including allies</b>. On each hit, deal damage or inflict disadvantage.',
        'owned_description': '<b>Spend 1 AT:</b> Roll against all creatures in a <b>Very Close sphere</b> within Close range, <b>including allies</b>; damage or impose disadvantage on each hit.',
    },

    "martyr": {
        "id": "martyr",
        "name": "Martyr",
        "cost": 1,
        "purchase_rule": "single",
        "tags": ["support", "range"],
        "description": 'When using Protect, you may protect an ally within <b>Close</b> rather than only Very Close range.',
        'owned_description': 'Protect allies within <b>Close range</b>.',
    },

    "defender": {
        "id": "defender",
        "name": "Defender",
        "cost": 1,
        "purchase_rule": "single",
        "tags": ["support", "range"],
        "description": 'When using Parry, you may protect an ally within <b>{parry_range}</b>. Empowerments increase this range.',
        'owned_description': 'Parry for allies within <b>{parry_range}</b>.',
        "scaling_values": {"parry_range": "very close range"},
        "scaling_empowerments": {
            "parry_range": {
                "name": "Parry Range",
                'description': 'Increase the range at which you can Parry for an ally. Buy in order: <b>Close (2 IP), Far (3 IP), Very Far (4 IP)</b>.',
                              "owned_description": '',
                "rule": "ordered",
                "value_key": "parry_range",
                "steps": [
                    {
                        "value": "close range",
                        "cost": 2,
                               "owned_description": '',
                               "description": 'Increase the range at which you can Parry for an ally to close range.'
                    },
                    {
                        "value": "far range",
                        "cost": 3,
                               "owned_description": '',
                               "description": 'Increase the range at which you can Parry for an ally to far range.'
                    },
                    {
                        "value": "very far range",
                        "cost": 4,
                               "owned_description": '',
                               "description": 'Increase the range at which you can Parry for an ally to very far range.'
                    }
                ],
            },
        },
    },

##    "artificer": {
##        "id": "artificer",
##        "name": "Artificer",
##        "cost": 3,
##        "purchase_rule": "single",
##        "tags": ["magic"],
##        "description": "You get 20 points to build your items. Choose an effect, then range, strength, and uses per day.",
##        "requires_choices": ["artificer_item_description"],
##        "effects": [
##            {
##                "type": "grant_artificer_points",
##                "amount": 20,
##            }
##        ],
##    },

    "heightened_ability": {
        "id": "heightened_ability",
        "name": "Heightened Ability",
        "cost": 1,
        "purchase_rule": "stat_bonus_scaling",
        "requires_choices": ["stat_name"],
        "tags": ["rolls"],
        "description": 'Choose one stat and gain a <b>permanent +1 bonus</b> to its checks. Each further +1 costs IP equal to the new bonus: +1 costs 1, +2 costs 2 more, +3 costs 3 more, and so on. A +4 bonus costs 10 IP in total.',
        'owned_description': 'Your selected stat has a permanent bonus (shown with the stat).',
        "effects": [
            {
                "type": "increase_stat_bonus",
                "amount": 1,
            }
        ],
    },

    "high_flier": {
        "id": "high_flier",
        "name": "High Flier",
        "cost": 2,
        "purchase_rule": "single",
        "tags": ["range"],
        "description": 'You can <b>fly</b> using biological or magical means, appropriate to the campaign’s setting.',
        'owned_description': 'You can fly using your chosen biological or magical means.',
    },

    "intuitive": {
        "id": "intuitive",
        "name": "Intuitive",
        "cost": 1,
        "purchase_rule": "single",
        "tags": ["resource"],
        "description": '<b>Spend 1 AT</b> to ask the GM about your surroundings, an NPC, or something similar. <b>The GM must answer honestly.</b>',
        'owned_description': '<b>Spend 1 AT:</b> Ask the GM about something nearby or an NPC; the answer must be honest.',
    },

    "lucky": {
        "id": "lucky",
        "name": "Lucky",
        "cost": 2,
        "purchase_rule": "single",
        "tags": ["rolls"],
        "description": '<b>Spend 2 AT</b> to reroll a stat check.',
        'owned_description': '<b>Spend 2 AT:</b> Reroll a stat check.',
    },

    "nerves_of_steel": {
        "id": "nerves_of_steel",
        "name": "Nerves of Steel",
        "cost": 2,
        "purchase_rule": "single",
        "tags": ["rolls", "might"],
        "description": "<b>Spend 1 AT</b> to take half your die's value instead of rolling on a Snap Decision.",
        'owned_description': '<b>Spend 1 AT:</b> Take half your die value instead of rolling a Snap Decision.',
    },

    "skilled_at": {
        "id": "skilled_at",
        "name": "Skilled At...",
        "cost": 1,
        "purchase_rule": "repeatable",
        "requires_choices": ["skill_name", "skill_description"],
        "tags": ["rolls"],
        "description": 'Choose a non-combat skill with the GM. <b>Automatically succeed on DC 9 or lower</b> checks with it. For harder checks, the GM may require a roll; add up to <b>+3</b>. <b>This bonus does not stack with other Improvement bonuses.</b>',
        'owned_description': 'Your chosen non-combat skill: automatically pass DC <b>9 or lower</b>; on harder rolls, up to <b>+3</b> (no stacking with other Improvement bonuses).',
    },

    "treasure_hunter": {
        "id": "treasure_hunter",
        "name": "Treasure Hunter",
        "cost": 1,
        "purchase_rule": "single",
        "tags": ["resource"],
        "description": '<b>Spend 1 AT</b> to find a useful item in your surroundings.',
        'owned_description': '<b>Spend 1 AT:</b> Find a useful item nearby.',
    },

    "stealthy": {
        "id": "stealthy",
        "name": "Stealthy",
        "cost": 2,
        "purchase_rule": "single",
        "tags": ["stealth"],
        "description": '<b>Spend 1 AT</b> to avoid being seen, within reason and with GM approval.',
        'owned_description': '<b>Spend 1 AT:</b> Avoid being seen, with GM approval.',
    },

    "utility_belt": {
        "id": "utility_belt",
        "name": "Utility Belt",
        "cost": 2,
        "purchase_rule": "single",
        "tags": ["resource"],
        "description": '<b>Spend 1 AT</b> to reveal that you happen to have one commonplace item with you, with GM approval.',
        'owned_description': '<b>Spend 1 AT:</b> Reveal that you have one commonplace item, with GM approval.',
    },

    "spirited_motivator": {
        "id": "spirited_motivator",
        "name": "Spirited Motivator",
        "cost": 1,
        "purchase_rule": "single",
        "tags": ["support", "rolls"],
        "description": 'When helping a crewmate, each AT you spend grants <b>+2 instead of +1</b>. You may help even when absent if they describe a pep talk you gave them earlier that prepared them.',
        'owned_description': 'Helping grants <b>+2 per AT</b>, not +1. You may help while absent if the ally recalls an earlier pep talk.',
    },
    
    "custom": {
        "id": "custom",
        "name": "Custom Improvement...",
        "cost": 0,
        "purchase_rule": "repeatable",
        "description": "Create an improvement with a custom name, description, and IP cost.",
    },
}


# API-authored reference text. The note interface must only render these definitions;
# player-written ordinary notes remain independent and must never be replaced.
# All companion note prose lives in the API. Notes UI supplies only character values.
ANIMAL_BUDDY_NOTE_TEMPLATE = (
    "Name: {buddy_name}\n"
    "Hearts: {buddy_hearts} ({buddy_hp} HP)    BDV: {buddy_bdv}\n"
    "Buddy Die: d{buddy_die}\n"
    "\nStats\n{buddy_stats}\n"
    "\nYour perks\n{buddy_perks}\n"
    "\nWhen your buddy is present and can help, add its d{buddy_die} Buddy Die "
    "to your check. It can also act independently as a second character you control. "
    "It cannot gain Improvements or GM-granted progression. "
    "At 0 HP, it is out of action or scared off, not permanently dead; "
    "it recovers HP normally."
)

# Compatibility view for older UI code. The canonical perk content above is the
# source of truth; do not duplicate wording here.
ANIMAL_BUDDY_PERK_DESCRIPTIONS = {
    perk_id: perk.get("description", "")
    for perk_id, perk in ANIMAL_BUDDY_PERKS.items()
}


# The detailed options are written once, in the existing Spellcasting note.
SPELLCASTING_EMPOWERMENT_NOTE_HTML = {
    "harm_slinger": (
        '<li><b>Area harm:</b> Affect all targets within a <b>Very Close-radius sphere</b> of the point you cast the spell. '
        'Spend another <b>AT</b> to increase it to a <b>Close-radius sphere</b>. '
        'If the spell does damage, roll once and apply damage to all targets.</li>'
        '<li><b>Extended range:</b> Your target can be within <b>Far range</b>, or <b>Very Far</b> for another <b>AT</b>.</li>'
        '<li><b>Damage and effect:</b> The spell both does damage and creates an effect.</li>'
    ),
    "expert_enchanter": (
        '<li><b>Area enchantment:</b> Affect all targets within a <b>Very Close-radius sphere</b> of the point you cast the spell. '
        'Spend another <b>AT</b> to increase it to a <b>Close-radius sphere</b>. '
        'Roll once and apply the effect to all targets.</li>'
        '<li><b>Very far range:</b> Your target can be within <b>Very Far range</b>.</li>'
        '<li><b>Extended duration:</b> The effect lasts an hour and another hour for every extra <b>AT</b> spent. '
        'It still ends if you cast another spell.</li>'
    ),
}

IMPROVEMENT_REFERENCE_NOTES = {'animal_buddy': ANIMAL_BUDDY_NOTE_TEMPLATE, 'sneak_attack': "<b>Sneak Attack</b>\nWhen you hit a surprised or distracted enemy, choose one effect. Spend 1 AT for each extra effect.\n<b>Effects:</b> Avoid entering Melee; impose disadvantage on the target's next turn; create an advantage for you or an ally; hide immediately (GM discretion); deal +{sneak_attack_damage} HP.\n<b>Additional effects:</b> Show only purchased effects and keep extra damage current.", 'spellcasting': '<b>Agility:</b> teleport, speed up, fly (moving yourself).\n<b>Strength:</b> lift, constrict, hold, break, launch (moving others and objects).\n<b>Finesse:</b> conceal, dispel, abjure.\n<b>Instinct:</b> shape, detect, connect, bless.\n<b>Presence:</b> charm, direct, buff, channel.\n<b>Knowledge:</b> identify, clairvoyance, reveal, modify.', 'mighty': '<b>Reduce difficulty:</b> DC -5.\n<b>Move heavy objects:</b> Treat the object or creature as half its size.\n<b>Move farther:</b> Move Far instead of Close as part of your combat turn.\n<b>Break materials:</b> Treat the material as having a substantial tear.\n<b>Vertical distances:</b> Treat the distance as half as long.'}


# --------------------------------------------------------------
# CATALOG AUTHORITY CONTRACT
# --------------------------------------------------------------
# SOURCE MODE: IMPROVEMENT_CATALOG above is the ONLY approved catalog.
# Editing this Python file changes the game on the next launch. The editor's
# approval tool updates the source with a backup; old live_catalog.json files
# are NEVER imported over your Python changes.
#
# FROZEN MODE: the bundled source is read-only. An approved catalog snapshot
# beside the EXE is loaded only through THIS module. The backend and UI must
# never open that snapshot independently.

def _validate_approved_catalog(options):
    if not isinstance(options, dict) or not all(
        isinstance(key, str) and isinstance(item, dict) and item.get("id") == key
        for key, item in options.items()
    ):
        raise ValueError("Approved Improvements catalog contains invalid entries")


def apply_approved_catalog(options):
    """Update this module's shared catalog in place after validated approval."""
    import copy as _copy
    _validate_approved_catalog(options)
    normalized = _copy.deepcopy(options)
    # JSON object keys are always strings. Restore numeric rule-level keys
    # before the backend looks them up with integer step values.
    for improvement in normalized.values():
        for group in improvement.get("scaling_empowerments", {}).values():
            updates = group.get("updates")
            if isinstance(updates, dict):
                group["updates"] = {
                    int(key) if isinstance(key, str) and key.isdecimal() else key: value
                    for key, value in updates.items()
                }
    IMPROVEMENT_CATALOG.clear()
    IMPROVEMENT_CATALOG.update(normalized)


import hashlib as _catalog_hashlib
import json as _catalog_json
_PACKAGED_API_SHA256 = _catalog_hashlib.sha256(
    _catalog_json.dumps(IMPROVEMENT_CATALOG, sort_keys=True,
                        ensure_ascii=False).encode("utf-8")
).hexdigest()


def _load_frozen_approved_catalog():
    import sys as _sys
    if not getattr(_sys, "frozen", False):
        return  # Never overwrite hand-edited character_API.py in source mode.
    import json as _json
    import hashlib as _hashlib
    import warnings as _warnings
    from pathlib import Path as _Path
    live = (_Path(_sys.executable).resolve().parent /
            "catalog_editor_data" / "live_catalog.json")
    if live.is_file():
        try:
            approved = _json.loads(live.read_text(encoding="utf-8"))
            packaged_fingerprint = _PACKAGED_API_SHA256
            if approved.get("api_base_sha256") != packaged_fingerprint:
                _warnings.warn(
                    "Old approved catalog was NOT applied: it belongs to a different "
                    "character_API.py. It is preserved for manual migration."
                )
                return
            apply_approved_catalog(approved["improvements"])
        except (OSError, ValueError, TypeError, KeyError) as error:
            _warnings.warn(f"Could not load frozen approved catalog: {error}")


_load_frozen_approved_catalog()
