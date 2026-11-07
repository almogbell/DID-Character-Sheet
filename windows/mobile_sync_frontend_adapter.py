"""Adapter between the finished DID desktop window and the mobile companion.

Windows and Android can both own local character files. When they meet on the
same network, this adapter imports phone-created characters and applies queued
phone changes to the desktop character model. Desktop validation still decides
whether received DID state is structurally legal before it is saved.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import shutil
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Optional
from uuid import uuid4


class MobileSyncValidationError(ValueError):
    """User-facing validation failure returned to the Android companion."""


@dataclass
class FrontendHooks:
    """Optional explicit hooks for desktop operations with dedicated UI paths."""

    save_after_change: Optional[Callable[[], None]] = None
    refresh_after_change: Optional[Callable[[], None]] = None
    hp_change: Optional[Callable[[int], None]] = None
    adversity_change: Optional[Callable[[int], None]] = None
    ip_change: Optional[Callable[[int], None]] = None


class DesktopSyncAdapter:
    MAX_NAME_CHARS = 240
    MAX_ITEM_DESCRIPTION_CHARS = 25_000

    _NOTE_COLORS = {
        "red": "#f3a6a6",
        "orange": "#ffc078",
        "yellow": "#ffe98a",
        "green": "#a8e6b0",
        "blue": "#9fcfe3",
        "purple": "#c8b6ff",
        "pink": "#f4b6cf",
    }

    def __init__(self, window: Any, storage_system: Any, hooks: Optional[FrontendHooks] = None) -> None:
        self.window = window
        self.storage_system = storage_system
        self.hooks = hooks or FrontendHooks()
        self.cloud_sync = None
        try:
            try:
                from .mobile_cloud_sync import MobileCloudSync
            except ImportError:
                from mobile_cloud_sync import MobileCloudSync
            self.cloud_sync = MobileCloudSync()
        except Exception:
            self.cloud_sync = None

    # ------------------------------------------------------------------
    # MobileSyncServer callbacks
    # ------------------------------------------------------------------
    def state_provider(self) -> Optional[dict]:
        character = getattr(self.window, "character", None)
        if character is None:
            # Still publish the saved-character library. This lets Android see
            # PC-side creations/deletions even when the desktop currently has no
            # active sheet open. Android recognizes this as metadata-only state.
            return {
                "_mobile_library_only": True,
                "_mobile_library": self._mobile_character_library(),
                "_mobile_deleted_characters": self._mobile_tombstones(),
            }

        state = self.storage_system.character_to_dict(character)
        if isinstance(state, dict):
            canonical_hash = self._character_content_hash(state)
            canonical_base = json.loads(json.dumps(state))
            assets = self._load_mobile_assets()
            self._enrich_improvements(state, character)
            self._enrich_notes(state)
            state["free_heightened_ability_slots"] = int(
                getattr(character, "free_heightened_ability_slots", 0) or 0
            )
            state["free_heightened_ability_stats"] = [
                str(value) for value in
                (getattr(character, "free_heightened_ability_stats", []) or [])
            ]
            purchase_options, browse_only = self._mobile_purchase_options()
            state["_mobile_ui"] = {
                "icons": assets,
                "ability_options": self._mobile_ability_options(),
                "available_purchases": purchase_options,
                "purchase_browse_only": browse_only,
                "species_options": self._mobile_species_options(),
                "animal_buddy": self._mobile_animal_buddy_state(),
                "ability_editor": self._mobile_ability_editor_config(),
                "species_editor": self._mobile_species_editor(),
                "earlier_versions": self._mobile_earlier_versions(),
                "dice_roller_enabled": self._mobile_dice_roller_enabled(),
            }
            state["_mobile_sync"] = {
                "content_hash": canonical_hash,
                "base_character": canonical_base,
                "conflict_policy": "merge_v2",
            }
            state["_mobile_library"] = self._mobile_character_library()
            state["_mobile_deleted_characters"] = self._mobile_tombstones()
            if self.cloud_sync is not None:
                try:
                    state["_mobile_cloud"] = self.cloud_sync.public_config()
                    self.cloud_sync.upload_async(state)
                except Exception:
                    pass
        return state

    @staticmethod
    def _asset_key(value: str) -> str:
        value = re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().lower())
        return value.strip("_")

    @staticmethod
    def _icon_match_key(value: str) -> str:
        return "".join(ch for ch in str(value or "").lower() if ch.isalnum())

    @staticmethod
    def _read_svg_base64(path: str | None) -> str | None:
        if not path or not os.path.isfile(path):
            return None
        try:
            with open(path, "rb") as handle:
                raw = handle.read()
            return base64.b64encode(raw).decode("ascii") if raw else None
        except (OSError, ValueError):
            return None

    def _frontend_presentation_globals(self) -> dict:
        """Read the exact constants used by the live desktop frontend."""
        for name in ("open_dice_options_for_stat", "show_character_page", "refresh_ui"):
            method = getattr(self.window, name, None)
            function = getattr(method, "__func__", method)
            namespace = getattr(function, "__globals__", None)
            if isinstance(namespace, dict):
                return namespace
        return {}

    def _desktop_app_dir(self) -> str:
        """Return the actual desktop app folder that owns icons/."""
        namespace = self._frontend_presentation_globals()
        candidate = namespace.get("APP_DIR") if isinstance(namespace, dict) else None
        if isinstance(candidate, str) and candidate.strip() and os.path.isdir(candidate):
            return os.path.abspath(candidate)

        module_name = getattr(self.window.__class__, "__module__", "")
        try:
            module = __import__(module_name)
            module_file = getattr(module, "__file__", None)
            if module_file:
                return os.path.dirname(os.path.abspath(module_file))
        except Exception:
            pass

        return os.path.dirname(os.path.abspath(__file__))

    def _find_improvement_icon_path(self, improvement: Any, display_name: str = "") -> str | None:
        """Mirror the desktop improvement-icon matching rules on Windows."""
        icon_dir = os.path.join(self._desktop_app_dir(), "icons", "improvements")
        if not os.path.isdir(icon_dir):
            return None

        candidates: list[str] = []
        choices = getattr(improvement, "choices", {}) or {}
        if str(getattr(improvement, "catalog_id", "")) == "custom":
            chosen = str(choices.get("_custom_icon", "") or "").strip()
            if chosen and os.path.basename(chosen) == chosen:
                candidates.append(chosen.removesuffix(".svg"))

        candidates.extend([
            str(getattr(improvement, "catalog_id", "") or ""),
            str(getattr(improvement, "name", "") or ""),
            str(display_name or ""),
        ])
        candidates = [value.strip() for value in candidates if value and value.strip()]

        for candidate in candidates:
            for filename in (
                f"{candidate}.svg",
                f"{candidate.lower()}.svg",
                f"{self._asset_key(candidate)}.svg",
            ):
                path = os.path.join(icon_dir, filename)
                if os.path.isfile(path):
                    return path

        wanted = {self._icon_match_key(candidate) for candidate in candidates}
        try:
            for filename in os.listdir(icon_dir):
                if filename.lower().endswith(".svg"):
                    stem = os.path.splitext(filename)[0]
                    if self._icon_match_key(stem) in wanted:
                        return os.path.join(icon_dir, filename)
        except OSError:
            return None
        return None

    @staticmethod
    def _required_choice_keys(option: dict | None) -> list[str]:
        if not isinstance(option, dict):
            return []
        required = option.get("required_choices")
        if isinstance(required, dict):
            return [str(key) for key in required.keys() if str(key) and not str(key).startswith("_")]
        if isinstance(required, (list, tuple)):
            keys = []
            for item in required:
                if isinstance(item, str):
                    key = item
                elif isinstance(item, dict):
                    key = str(item.get("key") or item.get("id") or item.get("name") or "")
                else:
                    key = ""
                if key and not key.startswith("_"):
                    keys.append(key)
            return keys
        return []

    def _enrich_improvements(self, state: dict, character: Any) -> None:
        state_items = (
            state.get("improvements", {}).get("list_of_taken_improvements", [])
            if isinstance(state.get("improvements"), dict) else []
        )
        character_system = getattr(character, "improvements", None)
        live_items = list(getattr(character_system, "list_of_taken_improvements", []) or [])
        if not isinstance(state_items, list) or not live_items:
            return

        try:
            from backend_2_1 import ImprovementSystem, ImprovementCatalogSystem  # type: ignore
        except ImportError:
            return

        live_by_id = {
            str(getattr(item, "id", "")): item
            for item in live_items
            if getattr(item, "id", None)
        }
        notes = list(getattr(getattr(character, "notes", None), "list_of_notes", []) or [])

        for index, serialized in enumerate(state_items):
            if not isinstance(serialized, dict):
                continue

            live = live_by_id.get(str(serialized.get("id", "")))
            if live is None and index < len(live_items):
                live = live_items[index]
            if live is None:
                continue

            try:
                display = ImprovementSystem.build_improvement_display(character, live) or {}
            except Exception:
                display = {}

            serialized["_mobile_display_summary"] = str(display.get("summary") or "")
            serialized["_mobile_display_details"] = str(display.get("details") or "")
            serialized["_mobile_display_choices"] = [
                str(line) for line in (display.get("choices") or []) if str(line).strip()
            ]
            serialized["_mobile_display_upgrades"] = [
                str(line) for line in (display.get("upgrades") or []) if str(line).strip()
            ]

            catalog_id = str(getattr(live, "catalog_id", "") or "")
            try:
                option = ImprovementCatalogSystem.get_option(catalog_id, character)
            except TypeError:
                option = ImprovementCatalogSystem.get_option(catalog_id)
            except Exception:
                option = None

            editable_keys = self._required_choice_keys(option)
            custom = (
                catalog_id == "custom"
                or str(getattr(live, "source", "") or "") == "custom"
            )
            serialized["_mobile_editable_choice_keys"] = editable_keys
            serialized["_mobile_editable"] = bool(custom or editable_keys)

            icon_svg = self._read_svg_base64(
                self._find_improvement_icon_path(live, str(display.get("name") or ""))
            )
            if icon_svg:
                serialized["_mobile_icon_svg"] = icon_svg

            improvement_id = str(getattr(live, "id", "") or "")
            linked_notes = [
                note for note in notes
                if str(getattr(note, "linked_improvement_id", "") or "") == improvement_id
            ]

            target_title = None
            if catalog_id in {"spellcasting", "magic_novice"}:
                target_title = "spellcasting verbs"
            elif catalog_id == "sneak_attack":
                target_title = "sneak attack"
            elif catalog_id == "mighty":
                target_title = "mighty"
            elif catalog_id == "animal_buddy":
                target_title = "animal buddy"

            if target_title:
                system_note = next(
                    (
                        note for note in notes
                        if str(getattr(note, "title", "") or "").strip().lower() == target_title
                    ),
                    None,
                )
                if system_note is not None and system_note not in linked_notes:
                    linked_notes.insert(0, system_note)

            linked_ids = [
                str(getattr(note, "id"))
                for note in linked_notes
                if getattr(note, "id", None)
            ]
            if linked_ids:
                serialized["_mobile_linked_note_id"] = linked_ids[0]
                serialized["_mobile_linked_note_ids"] = linked_ids

    def _enrich_notes(self, state: dict) -> None:
        notes = (
            state.get("notes", {}).get("list_of_notes", [])
            if isinstance(state.get("notes"), dict) else []
        )
        if not isinstance(notes, list):
            return

        note_paper_color = None
        try:
            import notes_ui  # type: ignore
            note_paper_color = getattr(notes_ui, "note_paper_color", None)
        except Exception:
            note_paper_color = None

        for note in notes:
            if not isinstance(note, dict):
                continue

            raw = str(note.get("color") or "").strip()
            display_color = None

            if callable(note_paper_color):
                try:
                    candidate = str(note_paper_color(raw) or "").strip()
                    if re.fullmatch(r"#[0-9a-fA-F]{6}", candidate):
                        display_color = candidate
                except Exception:
                    display_color = None

            if display_color is None:
                if re.fullmatch(r"#[0-9a-fA-F]{6}", raw):
                    display_color = raw
                else:
                    display_color = self._NOTE_COLORS.get(
                        raw.lower(),
                        self._NOTE_COLORS["yellow"],
                    )

            note["_mobile_display_color"] = display_color

            title = str(note.get("title") or "").strip().lower()
            linked = bool(str(note.get("linked_improvement_id") or "").strip())
            system = (
                title in {"spellcasting verbs", "sneak attack", "mighty"}
                or (title == "animal buddy" and linked)
            )
            # Personal notes remain editable even while linked, matching desktop.
            note["_mobile_editable"] = not system

    def _mobile_purchase_options(self, character=None) -> tuple[list[dict], bool]:
        """Mirror the desktop picker list without moving rules to Android."""
        character = character if character is not None else self._character()
        try:
            from backend_2_1 import ImprovementSystem  # type: ignore
        except Exception:
            return [], False

        progression = getattr(character, "progression", None)
        available_ip = int(getattr(progression, "available_IP", 0) or 0)
        browse_only = available_ip <= 0

        original_current_ip = getattr(progression, "current_IP", None)
        try:
            if browse_only and progression is not None:
                progression.current_IP = int(getattr(progression, "used_IP", 0) or 0) + 999999
            options = list(ImprovementSystem.get_available_purchases(character) or [])
        except Exception:
            options = []
        finally:
            if browse_only and progression is not None and original_current_ip is not None:
                progression.current_IP = original_current_ip

        result: list[dict] = []
        for option in options:
            if not isinstance(option, dict):
                continue
            tags = [str(tag) for tag in (option.get("tags") or [])]
            catalog_id = str(option.get("catalog_id") or "")
            if option.get("source") == "species" or "species" in tags or catalog_id == "custom":
                continue
            required_choices = option.get("requires_choices") or []
            if catalog_id == "upgrade_to_spellcasting":
                required_choices = ["magic_school", "magic_school_description"]
            result.append({
                "kind": str(option.get("kind") or "base"),
                "improvement_id": str(option.get("improvement_id") or ""),
                "parent_catalog_id": str(option.get("parent_catalog_id") or ""),
                "group_id": str(option.get("group_id") or ""),
                "catalog_id": catalog_id,
                "name": str(option.get("name") or "Improvement"),
                "cost": int(option.get("cost", 0) or 0),
                "description": str(option.get("description") or ""),
                "requires_choices": [
                    str(item.get("key") or item.get("id") or item.get("name") or "")
                    if isinstance(item, dict) else str(item)
                    for item in required_choices
                    if (str(item.get("key") or item.get("id") or item.get("name") or "").strip() if isinstance(item, dict) else str(item).strip())
                ],
                "tags": tags,
            })

        return result, browse_only

    def _mobile_animal_buddy_state(self, character=None) -> dict | None:
        """Return desktop-calculated Animal Buddy state for the phone."""
        character = character if character is not None else self._character()
        buddy = next(
            (
                improvement
                for improvement in character.improvements.list_of_taken_improvements
                if str(getattr(improvement, "catalog_id", "")) == "animal_buddy"
            ),
            None,
        )
        if buddy is None:
            return None

        try:
            from notes_ui import buddy_state  # type: ignore
            from character_API import (  # type: ignore
                animal_buddy_perk_name,
                animal_buddy_perk_description,
            )
            data = buddy_state(buddy, character.BDV)
        except Exception:
            return None

        accents = {
            "Agility": "#6F8F2C",
            "Strength": "#A8453C",
            "Finesse": "#356FA8",
            "Instinct": "#6B55A6",
            "Presence": "#2F8792",
            "Knowledge": "#B17828",
        }

        stats = [
            {
                "key": stat_name.lower(),
                "name": stat_name,
                "die_size": int(data["dice"].get(stat_name, 4)),
                "bonus": int(data["training"].get(stat_name, 0)),
                "accent": accents[stat_name],
            }
            for stat_name in (
                "Agility", "Strength", "Finesse",
                "Instinct", "Presence", "Knowledge",
            )
        ]

        perks = []
        for _saved_name, destination, _key in data.get("perks", []):
            name = str(animal_buddy_perk_name(destination) or "").strip()
            description = str(animal_buddy_perk_description(destination) or "").strip()
            if name:
                perks.append({"name": name, "description": description})

        upgrades = []
        extra_hearts = sum(
            1 for upgrade in buddy.empowerments
            if str(getattr(upgrade, "group_id", "")) == "buddy_hearts"
        )
        if extra_hearts:
            upgrades.append(f"Extra Heart ×{extra_hearts}")

        trained = [
            f"{stat_name} +{value}"
            for stat_name, value in data.get("training", {}).items()
            if int(value or 0) > 0
        ]
        if trained:
            upgrades.append("Well Trained · " + ", ".join(trained))

        gifted = sum(
            1 for upgrade in buddy.empowerments
            if str(getattr(upgrade, "catalog_id", "")) == "gifted"
        )
        if gifted:
            upgrades.append(f"Gifted ×{gifted}")

        for upgrade in buddy.empowerments:
            if (
                str(getattr(upgrade, "group_id", "")) == "buddy_hearts"
                or str(getattr(upgrade, "catalog_id", "")) in {"well_trained", "gifted"}
            ):
                continue
            label = str(getattr(upgrade, "name", "") or "").strip()
            if label:
                upgrades.append(label)

        note_id = ""
        for note in character.notes.list_of_notes:
            if (
                str(getattr(note, "linked_improvement_id", "") or "") == str(buddy.id)
                and str(getattr(note, "title", "") or "").strip().lower() == "animal buddy"
            ):
                note_id = str(getattr(note, "id", "") or "")
                break

        return {
            "improvement_id": str(buddy.id),
            "note_id": note_id,
            "name": str((buddy.choices or {}).get("buddy_name") or "Unnamed Buddy"),
            "hearts": int(data["hearts"]),
            "max_hp": int(data["max_hp"]),
            "current_hp": int(data["current_hp"]),
            "bdv": int(data["bdv"]),
            "stats": stats,
            "perks": perks,
            "upgrades": upgrades,
        }

    def _mobile_dice_roller_enabled(self) -> bool:
        checker = getattr(self.window, "dice_roller_is_enabled", None)
        if callable(checker):
            try:
                return bool(checker())
            except Exception:
                pass
        return bool(getattr(self.window, "_dice_roller_enabled", True))

    def _mobile_earlier_versions(self) -> list[dict]:
        filepath = str(getattr(self.window, "current_character_filepath", "") or "")
        if not filepath:
            return []
        try:
            history_files = self.storage_system.get_character_history(filepath)
        except Exception:
            return []
        if len(history_files) <= 1:
            return []
        versions = []
        for history_index, history_path in enumerate(history_files[1:], start=1):
            filename = os.path.basename(history_path)
            timestamp_text = os.path.splitext(filename)[0]
            try:
                timestamp = datetime.strptime(timestamp_text, "%Y-%m-%d_%H-%M-%S_%f")
                date_text = timestamp.strftime("%d %B %Y  ·  %H:%M")
            except ValueError:
                date_text = timestamp_text.replace("_", " ")
            details, changes = [], []
            try:
                version_character = self.storage_system.import_character_file(history_path)
                previous_index = history_index + 1
                if previous_index < len(history_files):
                    previous_character = self.storage_system.import_character_file(history_files[previous_index])
                    describe = getattr(self.storage_system, "describe_meaningful_changes", None)
                    if callable(describe):
                        cats = list(describe(previous_character, version_character) or [])
                        if not cats:
                            continue
                        details.append("Changed: " + " · ".join(str(x) for x in cats))
                else:
                    details.append("First saved version")
                restore_describe = getattr(self.window, "describe_restore_differences", None)
                if callable(restore_describe):
                    changes = [str(v) for v in (restore_describe(self._character(), version_character) or [])]
            except Exception:
                details.append("Earlier saved version")
            display = date_text + (("\n" + "   •   ".join(details)) if details else "")
            versions.append({"token": filename, "display": display, "changes": changes})
        return versions

    def _mobile_species_editor(self, character=None) -> dict | None:
        """Return metadata needed to edit the already-owned Species."""
        character = character if character is not None else self._character()
        species = next(
            (
                improvement
                for improvement in character.improvements.list_of_taken_improvements
                if str(getattr(improvement, "source", "") or "") == "species"
            ),
            None,
        )
        if species is None:
            return None

        try:
            from backend_2_1 import ImprovementCatalogSystem  # type: ignore
            option = ImprovementCatalogSystem.get_option(species.catalog_id)
        except Exception:
            option = None

        option = option if isinstance(option, dict) else {}
        required = []
        for item in option.get("requires_choices", []) or []:
            key = (
                str(item.get("key") or item.get("id") or item.get("name") or "")
                if isinstance(item, dict)
                else str(item)
            ).strip()
            if key:
                required.append(key)

        choices = dict(getattr(species, "choices", {}) or {})
        species_name = str(
            choices.get("_species_name")
            or getattr(character, "species_name", "")
            or ""
        ).strip()

        return {
            "improvement_id": str(getattr(species, "id", "") or ""),
            "catalog_id": str(getattr(species, "catalog_id", "") or ""),
            "species_type_name": str(
                option.get("name")
                or getattr(species, "name", "")
                or "Species"
            ),
            "species_name": species_name,
            "required_choices": required,
            "choices": {
                str(key): str(value or "")
                for key, value in choices.items()
                if str(key) in required
            },
        }

    def _mobile_species_options(self, character=None) -> list[dict]:
        """Desktop-authoritative Species picker options for Android Settings."""
        character = character if character is not None else self._character()
        try:
            from backend_2_1 import ImprovementSystem  # type: ignore
            options = list(ImprovementSystem.get_species_options(character) or [])
        except Exception:
            return []

        result = []
        for option in options:
            if not isinstance(option, dict):
                continue
            required = option.get("requires_choices") or []
            result.append({
                "kind": "species",
                "improvement_id": "",
                "parent_catalog_id": "",
                "group_id": "",
                "catalog_id": str(option.get("catalog_id") or option.get("id") or ""),
                "name": str(option.get("name") or "Species"),
                "cost": int(option.get("cost", 0) or 0),
                "description": str(option.get("description") or ""),
                "requires_choices": [
                    str(item.get("key") or item.get("id") or item.get("name") or "")
                    if isinstance(item, dict) else str(item)
                    for item in required
                    if (str(item.get("key") or item.get("id") or item.get("name") or "").strip()
                        if isinstance(item, dict) else str(item).strip())
                ],
                "tags": ["species"],
            })
        return result

    def _mobile_ability_editor_config(self, character=None) -> dict:
        """Expose the exact desktop ability arrays/costs for the phone editor."""
        character = character if character is not None else self._character()

        namespace = self._frontend_presentation_globals()
        stat_costs = namespace.get("STAT_POINT_COSTS") if isinstance(namespace, dict) else None
        ability_arrays = namespace.get("ABILITY_ARRAYS") if isinstance(namespace, dict) else None

        if not isinstance(stat_costs, dict):
            try:
                from backend_2_1 import STAT_POINT_COSTS as stat_costs  # type: ignore
            except Exception:
                stat_costs = {4: 0, 6: 1, 8: 3, 10: 6, 12: 10}

        if not isinstance(ability_arrays, list):
            try:
                from character_API import ABILITY_ARRAYS as ability_arrays  # type: ignore
            except Exception:
                ability_arrays = [
                    {"id": "adventurer", "name": "Adventurer Array", "dice": [12, 10, 8, 8, 6, 4]},
                    {"id": "hybrid", "name": "Hybrid Build", "dice": [12, 10, 10, 6, 4, 4]},
                    {"id": "specialist", "name": "Specialist Array", "dice": [12, 12, 6, 6, 6, 4]},
                    {"id": "prodigy", "name": "Prodigy Build", "dice": [12, 12, 8, 4, 4, 4]},
                    {"id": "backbone", "name": "Backbone Build", "dice": [12, 8, 8, 8, 8, 6]},
                    {"id": "jack_of_all_trades", "name": "Jack of All Trades", "dice": [10, 10, 10, 8, 6, 6]},
                ]

        allowed_ids = None
        if bool(getattr(character, "creation_rules_active", False)):
            raw_allowed = list(
                getattr(character, "creation_allowed_ability_array_ids", []) or []
            )
            if raw_allowed:
                allowed_ids = {str(value) for value in raw_allowed}

        legal_arrays = []
        for ability_array in ability_arrays:
            if not isinstance(ability_array, dict):
                continue
            array_id = str(ability_array.get("id") or "")
            if allowed_ids and array_id not in allowed_ids:
                continue
            legal_arrays.append({
                "id": array_id,
                "name": str(ability_array.get("name") or "Ability Array"),
                "dice": [int(value) for value in (ability_array.get("dice") or [])],
            })

        die_options = [
            {
                "die_size": int(die_size),
                "cost": int(cost),
            }
            for die_size, cost in sorted(
                stat_costs.items(),
                key=lambda item: int(item[0]),
            )
        ]

        return {
            "point_budget": int(getattr(character, "stat_point_budget", 0) or 0),
            "die_options": die_options,
            "legal_arrays": legal_arrays,
        }

    def _mobile_ability_options(self) -> dict[str, list[dict]]:
        result: dict[str, list[dict]] = {}
        provider = getattr(self.window, "_available_roll_modifier_options", None)
        if not callable(provider):
            return result

        for stat_key in (
            "agility",
            "finesse",
            "instinct",
            "knowledge",
            "presence",
            "strength",
        ):
            try:
                try:
                    options = provider(stat_key) or []
                except TypeError:
                    options = provider() or []
                result[stat_key] = [
                    {
                        "kind": str(item.get("kind") or "bonus_die"),
                        "label": str(item.get("label") or item.get("short_label") or "Die"),
                        "short_label": str(item.get("short_label") or "die"),
                        "sides": int(item.get("sides", 6)),
                        "sign": -1 if int(item.get("sign", 1)) < 0 else 1,
                        "explode": bool(item.get("explode", False)),
                    }
                    for item in options
                    if isinstance(item, dict)
                ]
            except Exception:
                result[stat_key] = []

        return result

    def _load_mobile_assets(self) -> dict[str, str]:
        """Return desktop-owned artwork/help used by the Android presentation."""
        app_dir = self._desktop_app_dir()

        paths = {
            "agility": os.path.join(app_dir, "icons", "agility.svg"),
            "finesse": os.path.join(app_dir, "icons", "finesse.svg"),
            "instinct": os.path.join(app_dir, "icons", "instinct.svg"),
            "knowledge": os.path.join(app_dir, "icons", "knowledge.svg"),
            "presence": os.path.join(app_dir, "icons", "presence.svg"),
            "strength": os.path.join(app_dir, "icons", "strength.svg"),
            "bdv": os.path.join(app_dir, "icons", "defenses", "bdv.svg"),
            "dr": os.path.join(app_dir, "icons", "defenses", "dr.svg"),
            "inventory": os.path.join(app_dir, "icons", "headers", "inventory.svg"),
        }

        for candidate in (
            os.path.join(app_dir, "icons", "notes", "custom.svg"),
            os.path.join(app_dir, "icons", "headers", "notes.svg"),
            os.path.join(app_dir, "icons", "notes.svg"),
        ):
            if os.path.isfile(candidate):
                paths["notes"] = candidate
                break

        note_dir = os.path.join(app_dir, "icons", "notes")
        if os.path.isdir(note_dir):
            try:
                for filename in os.listdir(note_dir):
                    if filename.lower().endswith(".svg"):
                        stem = os.path.splitext(filename)[0]
                        key = self._asset_key(stem)
                        if key:
                            paths.setdefault(f"note:{key}", os.path.join(note_dir, filename))
            except OSError:
                pass

        improvement_dir = os.path.join(app_dir, "icons", "improvements")
        if os.path.isdir(improvement_dir):
            for root, _dirs, files in os.walk(improvement_dir):
                for filename in files:
                    if not filename.lower().endswith(".svg"):
                        continue
                    path = os.path.join(root, filename)
                    stem = os.path.splitext(filename)[0]
                    key = self._asset_key(stem)
                    if key:
                        paths.setdefault(f"improvement:{key}", path)
                        paths.setdefault(f"improvement-name:{key}", path)

        result: dict[str, str] = {}
        for key, path in paths.items():
            encoded = self._read_svg_base64(path)
            if encoded:
                result[key] = encoded

        namespace = self._frontend_presentation_globals()
        ability_accents = namespace.get("ABILITY_ACCENTS", {})
        ability_descriptions = namespace.get("ABILITY_DESCRIPTIONS", {})
        rows = getattr(self.window, "stat_rows", {}) or {}
        stats = getattr(self._character(), "stats", None)

        for stat_key in (
            "agility",
            "finesse",
            "instinct",
            "knowledge",
            "presence",
            "strength",
        ):
            row = rows.get(stat_key) if isinstance(rows, dict) else None
            help_text = (
                getattr(row, "_ability_tooltip_text", None)
                if row is not None else None
            )
            accent = (
                getattr(row, "_ability_tooltip_accent", None)
                if row is not None else None
            )

            if not isinstance(help_text, str) or not help_text.strip():
                help_text = (
                    ability_descriptions.get(stat_key)
                    if isinstance(ability_descriptions, dict) else None
                )
            if not accent:
                accent = (
                    ability_accents.get(stat_key)
                    if isinstance(ability_accents, dict) else None
                )

            if isinstance(help_text, str) and help_text.strip():
                result[f"ability-help:{stat_key}"] = help_text.strip()
            if isinstance(accent, str) and re.fullmatch(
                r"#[0-9a-fA-F]{6}",
                accent.strip(),
            ):
                result[f"ability-color:{stat_key}"] = accent.strip()

            if f"ability-help:{stat_key}" not in result:
                stat = (
                    stats.get_stat(stat_key)
                    if stats is not None and hasattr(stats, "get_stat")
                    else None
                )
                if stat is not None:
                    for attr in (
                        "tooltip",
                        "tool_tip",
                        "help_text",
                        "description",
                        "info",
                        "explanation",
                    ):
                        value = getattr(stat, attr, None)
                        if isinstance(value, str) and value.strip():
                            result[f"ability-help:{stat_key}"] = value.strip()
                            break

        return result

    def _note_link(self, payload: dict) -> None:
        note_id = self._required_id(payload)
        target_id = str(payload.get("target_id") or "").strip()

        notes_system = getattr(self._character(), "notes", None)
        if notes_system is None or not hasattr(notes_system, "list_of_notes"):
            raise MobileSyncValidationError("This character has no notes")

        note = next(
            (
                item for item in notes_system.list_of_notes
                if str(getattr(item, "id", "") or "") == note_id
            ),
            None,
        )
        if note is None:
            raise MobileSyncValidationError("Note no longer exists")

        title = str(getattr(note, "title", "") or "").strip().lower()
        linked_now = str(getattr(note, "linked_improvement_id", "") or "").strip()
        system = (
            title in {"spellcasting verbs", "sneak attack", "mighty"}
            or (title == "animal buddy" and bool(linked_now))
        )
        if system:
            raise MobileSyncValidationError(
                "System notes must stay linked to their owning Improvement"
            )

        valid_ids = {
            str(getattr(item, "id"))
            for item in getattr(
                getattr(self._character(), "improvements", None),
                "list_of_taken_improvements",
                [],
            )
            if getattr(item, "id", None)
        }
        if target_id and target_id not in valid_ids:
            raise MobileSyncValidationError("That Improvement no longer exists")

        try:
            import notes_ui  # type: ignore
            can_link = getattr(notes_ui, "can_link_note", None)
            if callable(can_link) and not can_link(self._character(), note, target_id):
                raise MobileSyncValidationError(
                    "That Improvement already has the maximum number of linked notes"
                )
        except MobileSyncValidationError:
            raise
        except Exception:
            pass

        note.linked_improvement_id = target_id
        validate = getattr(notes_system, "validate", None)
        if callable(validate):
            validate()

    # ------------------------------------------------------------------
    # Character lifecycle / active-character sync
    # ------------------------------------------------------------------
    def _character_id(self, character: Any | None = None) -> str:
        character = character if character is not None else getattr(self.window, "character", None)
        return str(getattr(character, "id", "") or "").strip()

    def _mobile_character_library(self) -> list[dict]:
        """Return a lightweight index of every saved Windows character."""
        save_dir = os.path.abspath(str(getattr(self.storage_system, "SAVE_DIR", "") or ""))
        importer = getattr(self.storage_system, "import_character_file", None)
        looks_like = getattr(self.storage_system, "looks_like_character_file", None)
        if not save_dir or not os.path.isdir(save_dir) or not callable(importer):
            return []

        rows = []
        for root, dirs, files in os.walk(save_dir):
            dirs[:] = [folder for folder in dirs if folder != "_history"]
            for filename in files:
                if not filename.lower().endswith(".didchar"):
                    continue
                path = os.path.join(root, filename)
                try:
                    if callable(looks_like) and not looks_like(path):
                        continue
                    character = importer(path)
                    character_id = self._character_id(character)
                    if not character_id:
                        continue
                    data = self.storage_system.character_to_dict(character)
                    rows.append({
                        "id": character_id,
                        "name": str(getattr(character, "name", "") or "").strip() or "Unnamed Character",
                        "content_hash": self._character_content_hash(data),
                        "modified_at": int(os.path.getmtime(path) * 1000),
                    })
                except Exception:
                    continue
        rows.sort(key=lambda item: (str(item.get("name", "")).lower(), str(item.get("id", ""))))
        return rows

    def _mobile_saved_character_snapshot(self, character_id: str) -> dict:
        """Return a saved character without changing the active Windows sheet."""
        _path, character = self._saved_character_by_id(character_id)
        data = self.storage_system.character_to_dict(character)
        canonical_hash = self._character_content_hash(data)
        canonical_base = json.loads(json.dumps(data))
        self._enrich_improvements(data, character)
        self._enrich_notes(data)
        data["free_heightened_ability_slots"] = int(
            getattr(character, "free_heightened_ability_slots", 0) or 0
        )
        data["free_heightened_ability_stats"] = [
            str(value) for value in
            (getattr(character, "free_heightened_ability_stats", []) or [])
        ]
        purchases, browse_only = self._mobile_purchase_options(character)
        data["_mobile_ui"] = {
            "icons": self._load_mobile_assets(),
            "ability_options": {},
            "available_purchases": purchases,
            "purchase_browse_only": browse_only,
            "species_options": self._mobile_species_options(character),
            "animal_buddy": self._mobile_animal_buddy_state(character),
            "ability_editor": self._mobile_ability_editor_config(character),
            "species_editor": self._mobile_species_editor(character),
            "earlier_versions": [],
            "dice_roller_enabled": self._mobile_dice_roller_enabled(),
        }
        data["_mobile_sync"] = {
            "content_hash": canonical_hash,
            "base_character": canonical_base,
            "conflict_policy": "merge_v2",
        }
        return data

    def _saved_character_by_id(self, character_id: str) -> tuple[str, Any]:
        character_id = str(character_id or "").strip()
        if not character_id:
            raise MobileSyncValidationError("Invalid character id")

        save_dir = os.path.abspath(str(getattr(self.storage_system, "SAVE_DIR", "") or ""))
        if not save_dir or not os.path.isdir(save_dir):
            raise MobileSyncValidationError("The Windows character folder is unavailable")

        importer = getattr(self.storage_system, "import_character_file", None)
        looks_like = getattr(self.storage_system, "looks_like_character_file", None)
        if not callable(importer):
            raise MobileSyncValidationError("This Windows build cannot open saved characters from mobile")

        for root, dirs, files in os.walk(save_dir):
            dirs[:] = [folder for folder in dirs if folder != "_history"]
            for filename in files:
                if not filename.lower().endswith(".didchar"):
                    continue
                path = os.path.join(root, filename)
                try:
                    if callable(looks_like) and not looks_like(path):
                        continue
                    character = importer(path)
                except Exception:
                    continue
                if self._character_id(character) == character_id:
                    return path, character

        raise MobileSyncValidationError("That character is not saved on this computer")

    def _open_character_from_mobile(self, payload: dict) -> dict:
        target_id = self._required_id(payload)
        if self._character_id() == target_id:
            return {"opened_character_id": target_id}

        # Never silently discard unsaved desktop work merely because a phone
        # selected another character.
        if bool(getattr(self.window, "unsaved_changes", False)):
            filepath = getattr(self.window, "current_character_filepath", None)
            if filepath:
                saver = getattr(self.window, "save_current_character", None)
                if callable(saver):
                    saver()
                if bool(getattr(self.window, "unsaved_changes", False)):
                    raise MobileSyncValidationError(
                        "Windows has unsaved changes. Save them before switching characters from the phone."
                    )
            else:
                raise MobileSyncValidationError(
                    "Windows has an unsaved new character. Save or discard it before switching characters from the phone."
                )

        filepath, character = self._saved_character_by_id(target_id)
        self.window.character = character
        open_notes = getattr(self.window, "open_notes_for_session", None)
        if callable(open_notes):
            open_notes()
        self.window.current_character_filepath = filepath
        remember = getattr(self.window, "remember_last_opened_character", None)
        if callable(remember):
            remember(filepath)
        self.window.saved_character_name = getattr(character, "name", None)
        self.window.character_access_mode = "editable"
        self.window.active_character_template = None
        self.window._silently_recovered = False
        self.window._recovered_state_edited = False
        self.window._history_restore_pending = False

        old_suppress = bool(getattr(self.window, "supress_dirty", False))
        self.window.supress_dirty = True
        try:
            reconnect = getattr(self.window, "reconnect_character_references", None)
            if callable(reconnect):
                reconnect()
            refresh = getattr(self.window, "refresh_all", None) or getattr(self.window, "refresh_ui", None)
            if callable(refresh):
                refresh()
        finally:
            self.window.supress_dirty = old_suppress

        self.window.unsaved_changes = False
        set_modified = getattr(self.window, "setWindowModified", None)
        if callable(set_modified):
            set_modified(False)
        reset_undo = getattr(self.window, "reset_undo_history", None)
        if callable(reset_undo):
            try:
                reset_undo(saved_character=character)
            except TypeError:
                reset_undo()
        label = getattr(self.window, "save_status_label", None)
        if label is not None and hasattr(label, "setText"):
            label.setText("Saved")

        return {"opened_character_id": target_id}

    def _new_character_from_mobile(self) -> dict:
        creator = getattr(self.window, "new_character_from_ui", None)
        if not callable(creator):
            raise MobileSyncValidationError("This Windows build cannot create a character from mobile")
        before_character = self._character()
        before_id = self._character_id()
        creator()
        after_character = self._character()
        after_id = self._character_id()
        if after_character is before_character and after_id == before_id:
            raise MobileSyncValidationError("New character creation was cancelled on Windows")
        refresh = getattr(self.window, "refresh_all", None)
        if callable(refresh):
            refresh()
        return {"opened_character_id": after_id, "created": True}

    @classmethod
    def _character_content_hash(cls, value: Any) -> str:
        core = cls._strip_mobile_transport_fields(value)
        raw = json.dumps(
            core,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    @staticmethod
    def _strip_mobile_transport_fields(value: Any) -> Any:
        if isinstance(value, dict):
            return {
                key: DesktopSyncAdapter._strip_mobile_transport_fields(item)
                for key, item in value.items()
                if not str(key).startswith("_mobile_")
            }
        if isinstance(value, list):
            return [DesktopSyncAdapter._strip_mobile_transport_fields(item) for item in value]
        return value

    def _mobile_tombstone_path(self) -> str:
        save_dir = os.path.abspath(str(getattr(self.storage_system, "SAVE_DIR", "") or ""))
        if not save_dir or save_dir == os.path.abspath(""):
            raise MobileSyncValidationError("The Windows character folder is unavailable.")
        return os.path.join(save_dir, "_mobile_deleted_characters.json")

    def _mobile_tombstones(self) -> dict:
        path = self._mobile_tombstone_path()
        if not os.path.exists(path):
            return {}
        try:
            with open(path, "r", encoding="utf-8") as stream:
                result = json.load(stream)
            if not isinstance(result, dict):
                raise ValueError("Expected a JSON object")
            return result
        except (OSError, ValueError) as exc:
            raise MobileSyncValidationError(f"Cannot read mobile deletion records: {exc}") from exc

    @classmethod
    def record_desktop_deletion(cls, storage_system: Any, character_id: str) -> None:
        """Persist a desktop deletion even if Mobile Companion was never started."""
        if not str(character_id or "").strip():
            raise MobileSyncValidationError("Cannot record deletion without character ID.")
        # This method deliberately requires no live server, controller or Qt window.
        adapter = cls.__new__(cls)
        adapter.storage_system = storage_system
        adapter._record_mobile_tombstone(str(character_id).strip())

    def _record_mobile_tombstone(self, character_id: str) -> None:
        path = self._mobile_tombstone_path()
        records = self._mobile_tombstones()
        records[character_id] = datetime.utcnow().isoformat() + "Z"
        os.makedirs(os.path.dirname(path), exist_ok=True)
        temporary = path + ".tmp"
        try:
            with open(temporary, "w", encoding="utf-8") as stream:
                json.dump(records, stream, ensure_ascii=False, indent=2, sort_keys=True)
            os.replace(temporary, path)
        except OSError as exc:
            raise MobileSyncValidationError(f"Cannot persist mobile deletion record: {exc}") from exc

    def _save_phone_snapshot(self, payload: dict) -> dict:
        raw = payload.get("character")
        if not isinstance(raw, dict):
            raise MobileSyncValidationError("Phone character snapshot is missing.")

        data = self._strip_mobile_transport_fields(raw)
        character_id = str(data.get("id") or "").strip()
        if not character_id:
            raise MobileSyncValidationError("Phone character snapshot has no id.")
        # Never resurrect an offline-deleted character through a stale snapshot.
        # Explicit Keep Phone resolution is the only permitted override.
        if character_id in self._mobile_tombstones() and not bool(payload.get("force", False)):
            raise MobileSyncValidationError(
                "SYNC_CONFLICT: This character was deleted on Windows. "
                "Choose Keep Phone to restore it, or Use PC to keep it deleted."
            )

        converter = getattr(self.storage_system, "character_from_dict", None)
        exporter = getattr(self.storage_system, "export_character_file", None)
        if not callable(converter) or not callable(exporter):
            raise MobileSyncValidationError(
                "This Windows build cannot import characters created on the phone."
            )

        try:
            existing_path, existing_character = self._saved_character_by_id(character_id)
        except MobileSyncValidationError:
            existing_path = None
            existing_character = None

        # Compare with the current open PC sheet if it has unsaved edits.
        # An incoming phone snapshot must merge these edits, not overwrite them.
        if existing_character is not None:
            pc_character = existing_character
            if self._character_id() == character_id and bool(getattr(self.window, "unsaved_changes", False)):
                pc_character = self.window.character
            current_dict = self.storage_system.character_to_dict(pc_character)
            current_hash = self._character_content_hash(current_dict)
            phone_hash = self._character_content_hash(data)
            base_hash = str(payload.get("base_hash") or "").strip()
            if phone_hash != current_hash and base_hash != current_hash:
                base_character = payload.get("base_character")
                if not isinstance(base_character, dict):
                    raise MobileSyncValidationError(
                        "SYNC_MERGE_NEEDS_BASE: This phone has older unsynchronized edits "
                        "without a common snapshot. Both copies are preserved; update the apps and export a backup."
                    )
                if not base_hash or self._character_content_hash(base_character) != base_hash:
                    raise MobileSyncValidationError(
                        "SYNC_MERGE_NEEDS_BASE: The common snapshot does not match its hash. Both copies are preserved."
                    )
                try:
                    try:
                        from .mobile_sync_merge import merge_characters
                    except ImportError:
                        from mobile_sync_merge import merge_characters
                    outcome = merge_characters(
                        self._strip_mobile_transport_fields(base_character),
                        self._strip_mobile_transport_fields(current_dict),
                        data,
                        hp_at_choice=payload.get("hp_at_choice"),
                    )
                except ValueError as exc:
                    raise MobileSyncValidationError(f"SYNC_MERGE_NEEDS_BASE: {exc}") from exc
                if outcome.merged is None:
                    raise MobileSyncValidationError(
                        "HP_AT_CONFLICT:" + ",".join(outcome.conflicting_resources)
                    )
                data = outcome.merged

        alternatives = data.pop("sync_alternatives", [])
        try:
            character = converter(data)
            character.validate()
        except Exception as exc:
            raise MobileSyncValidationError(
                f"The merged phone character could not be validated: {exc}"
            ) from exc

        if existing_path is None:
            ensure_dir = getattr(self.storage_system, "ensure_save_dir", None)
            if callable(ensure_dir):
                ensure_dir()
            save_dir = os.path.abspath(str(getattr(self.storage_system, "SAVE_DIR", "") or ""))
            if not save_dir:
                raise MobileSyncValidationError("The Windows character folder is unavailable.")
            safe_name_fn = getattr(self.storage_system, "save_filename", None)
            base_name = str(getattr(character, "name", "") or "").strip() or "character"
            safe_name = safe_name_fn(base_name) if callable(safe_name_fn) else re.sub(r"[^A-Za-z0-9_-]+", "_", base_name)
            candidate = os.path.join(save_dir, f"{safe_name}.didchar")
            number = 2
            while os.path.exists(candidate):
                candidate = os.path.join(save_dir, f"{safe_name}_{number}.didchar")
                number += 1
            existing_path = candidate

        # Save both competing scalar values in a durable sidecar before
        # updating the character. A backup failure blocks the merge.
        if alternatives:
            sidecar_path = existing_path + ".sync-alternatives.json"
            try:
                old_values = []
                if os.path.isfile(sidecar_path):
                    with open(sidecar_path, encoding="utf-8") as fh:
                        old_values = json.load(fh)
                if not isinstance(old_values, list):
                    raise ValueError("Invalid existing recovery file")
                seen = {json.dumps(value, sort_keys=True) for value in old_values}
                for alternative in alternatives:
                    key = json.dumps(alternative, sort_keys=True)
                    if key not in seen:
                        old_values.append(alternative)
                        seen.add(key)
                temporary = sidecar_path + ".tmp"
                with open(temporary, "w", encoding="utf-8") as fh:
                    json.dump(old_values, fh, ensure_ascii=False, indent=2)
                os.replace(temporary, sidecar_path)
            except (OSError, ValueError, TypeError) as exc:
                raise MobileSyncValidationError(
                    f"Could not preserve conflicting field edits: {exc}"
                ) from exc

        # Clear a prior deletion record only after an explicit restore has
        # successfully saved the character (handled below).
        try:
            exporter(character, existing_path)
        except Exception as exc:
            raise MobileSyncValidationError(
                f"Windows could not save the phone-created character: {exc}"
            ) from exc

        if character_id in self._mobile_tombstones():
            records = self._mobile_tombstones()
            records.pop(character_id, None)
            path = self._mobile_tombstone_path()
            temporary = path + ".tmp"
            with open(temporary, "w", encoding="utf-8") as stream:
                json.dump(records, stream, ensure_ascii=False, indent=2, sort_keys=True)
            os.replace(temporary, path)

        # Saving a phone character must not hijack the PC player's currently
        # open sheet. Refresh the desktop only when this same character is
        # already active; otherwise it simply appears in Windows Load Character.
        if self._character_id() == character_id:
            self.window.character = character
            self.window.current_character_filepath = existing_path
            self.window.saved_character_name = getattr(character, "name", None)
            self.window.character_access_mode = "editable"
            self.window.active_character_template = None
            self.window.unsaved_changes = False
            self.window._silently_recovered = False
            self.window._recovered_state_edited = False
            self.window._history_restore_pending = False
            open_notes = getattr(self.window, "open_notes_for_session", None)
            if callable(open_notes):
                open_notes()
            reconnect = getattr(self.window, "reconnect_character_references", None)
            if callable(reconnect):
                reconnect()
            refresh = getattr(self.window, "refresh_all", None) or getattr(self.window, "refresh_ui", None)
            if callable(refresh):
                refresh()

        if self.cloud_sync is not None:
            try:
                canonical = self.storage_system.character_to_dict(character)
                self.cloud_sync.upload_async(canonical)
            except Exception:
                pass

        return {
            "character_id": character_id,
            "created_on_windows": True,
            "filepath": existing_path,
            "content_hash": self._character_content_hash(
                self.storage_system.character_to_dict(character)
            ),
            "character": self.storage_system.character_to_dict(character),
        }

    def _confirm_delete_from_mobile(self, payload: dict) -> dict:
        target_id = self._required_id(payload)
        try:
            filepath, saved_character = self._saved_character_by_id(target_id)
        except MobileSyncValidationError:
            self._record_mobile_tombstone(target_id)
            return {"deleted_character_id": target_id, "already_missing": True}

        current_hash = self._character_content_hash(
            self.storage_system.character_to_dict(saved_character)
        )
        base_hash = str(payload.get("base_hash") or "").strip()
        force = bool(payload.get("force", False))
        if not force and (not base_hash or base_hash != current_hash):
            raise MobileSyncValidationError(
                "SYNC_CONFLICT: The PC copy changed after the phone last synced it. "
                "Choose Keep Phone to delete it anyway, or Use PC to restore the PC copy."
            )

        try:
            if os.path.exists(filepath):
                os.remove(filepath)
        except OSError as exc:
            raise MobileSyncValidationError(f"Could not delete the Windows character file: {exc}") from exc

        self._record_mobile_tombstone(target_id)

        history_folder = os.path.join(
            os.path.dirname(os.path.abspath(filepath)),
            "_history",
            os.path.splitext(os.path.basename(filepath))[0],
        )
        if os.path.isdir(history_folder):
            shutil.rmtree(history_folder, ignore_errors=True)

        if self._character_id() == target_id:
            self.window.character = None
            self.window.current_character_filepath = None
            self.window.saved_character_name = None
            refresh = getattr(self.window, "refresh_all", None) or getattr(self.window, "refresh_ui", None)
            if callable(refresh):
                try:
                    refresh()
                except Exception:
                    pass

        return {"deleted_character_id": target_id}

    def command_handler(
        self,
        action: str,
        payload: dict,
        base_revision: int,
        request_id: str,
    ) -> Optional[dict]:
        del base_revision, request_id

        if not isinstance(payload, dict):
            raise MobileSyncValidationError("Command payload must be an object")

        if action == "character.fetch_snapshot":
            character_id = self._required_id(payload)
            return {"character": self._mobile_saved_character_snapshot(character_id)}
        if action == "character.open":
            return self._open_character_from_mobile(payload)
        if action == "character.new":
            return self._new_character_from_mobile()
        if action == "character.upsert_snapshot":
            return self._save_phone_snapshot(payload)
        if action == "character.delete":
            return self._confirm_delete_from_mobile(payload)
        if action == "dice.set_enabled":
            enabled = bool(payload.get("enabled", True))
            current = self._mobile_dice_roller_enabled()

            if current != enabled:
                toggle = getattr(self.window, "toggle_dice_roller_from_ui", None)
                if callable(toggle):
                    toggle()
                else:
                    self.window._dice_roller_enabled = enabled
                    try:
                        from PySide6.QtCore import QSettings  # type: ignore
                        settings = QSettings("DID", "CharacterSheet")
                        settings.setValue("dice_roller_enabled", enabled)
                        settings.sync()
                    except Exception:
                        pass

            refresh = getattr(self.window, "refresh_all", None)
            if callable(refresh):
                refresh()
            return {"enabled": self._mobile_dice_roller_enabled()}

        if action == "character.restore_history":
            token = str(payload.get("token") or "").strip()
            if not token:
                raise MobileSyncValidationError("Earlier-version token is missing.")
            current_filepath = str(getattr(self.window, "current_character_filepath", "") or "")
            if not current_filepath:
                raise MobileSyncValidationError("Earlier versions are available only after the character has been saved.")
            history_files = self.storage_system.get_character_history(current_filepath)
            target_path = next((path for path in history_files[1:] if os.path.basename(path) == token), None)
            if not target_path:
                raise MobileSyncValidationError("That earlier version is no longer available.")
            restored_character = self.storage_system.import_character_file(target_path)
            self.window.character = restored_character
            self.window.current_character_filepath = current_filepath
            self.window.saved_character_name = restored_character.name
            self.window.character_access_mode = "editable"
            open_notes = getattr(self.window, "open_notes_for_session", None)
            if callable(open_notes): open_notes()
            reconnect = getattr(self.window, "reconnect_character_references", None)
            refresh = getattr(self.window, "refresh_all", None)
            self.window.supress_dirty = True
            try:
                if callable(reconnect): reconnect()
                if callable(refresh): refresh()
            finally:
                self.window.supress_dirty = False
            self.window._history_restore_pending = True
            mark_dirty = getattr(self.window, "mark_dirty", None)
            if callable(mark_dirty): mark_dirty()
            return {"restored": True, "token": token}


        self._ensure_editable()

        if action == "improvement.reorder":
            character = self._character()
            improvement_id = self._required_id(payload)
            direction = -1 if int(payload.get("direction", 1) or 1) < 0 else 1
            improvements = character.improvements.list_of_taken_improvements
            index = next(
                (i for i, improvement in enumerate(improvements)
                 if str(getattr(improvement, "id", "")) == improvement_id),
                None,
            )
            if index is None:
                raise MobileSyncValidationError("That Improvement could not be found.")
            target = max(0, min(len(improvements) - 1, index + direction))
            if target != index:
                improvements[index], improvements[target] = improvements[target], improvements[index]
            for order, improvement in enumerate(improvements):
                try:
                    improvement.sort_order = order
                except Exception:
                    pass
            self._validate_character()
            self._persist_and_refresh()
            return None

        if action == "abilities.set":
            character = self._character()

            try:
                from backend_2_1 import (  # type: ignore
                    STAT_NAMES,
                    STAT_POINT_COSTS,
                    StatSystem,
                )
                from character_API import ABILITY_ARRAYS  # type: ignore
            except ImportError as exc:
                raise MobileSyncValidationError(
                    f"Desktop build cannot edit abilities: {exc}"
                ) from exc

            raw_dice = payload.get("dice")
            if not isinstance(raw_dice, dict):
                raise MobileSyncValidationError(
                    "Ability dice must be sent as an object."
                )

            expected_stats = {str(name) for name in STAT_NAMES}
            if set(raw_dice) != expected_stats:
                raise MobileSyncValidationError(
                    "Choose exactly one die for every ability."
                )

            selected = {}
            for stat_name in STAT_NAMES:
                value = raw_dice.get(stat_name)
                if isinstance(value, bool):
                    raise MobileSyncValidationError("Invalid ability die.")
                try:
                    die_size = int(value)
                except (TypeError, ValueError) as exc:
                    raise MobileSyncValidationError("Invalid ability die.") from exc

                if die_size not in STAT_POINT_COSTS:
                    raise MobileSyncValidationError(
                        f"d{die_size} is not a legal ability die."
                    )
                selected[str(stat_name)] = die_size

            point_budget = int(getattr(character, "stat_point_budget", 0) or 0)
            used_points = sum(
                int(STAT_POINT_COSTS[selected[str(stat_name)]])
                for stat_name in STAT_NAMES
            )
            if used_points != point_budget:
                raise MobileSyncValidationError(
                    f"You must use exactly all {point_budget} ability points."
                )

            allowed_ids = None
            if bool(getattr(character, "creation_rules_active", False)):
                raw_allowed = list(
                    getattr(
                        character,
                        "creation_allowed_ability_array_ids",
                        [],
                    ) or []
                )
                if raw_allowed:
                    allowed_ids = {str(value) for value in raw_allowed}

            legal_arrays = [
                ability_array
                for ability_array in ABILITY_ARRAYS
                if isinstance(ability_array, dict)
                and (
                    not allowed_ids
                    or str(ability_array.get("id") or "") in allowed_ids
                )
            ]

            current_dice = sorted(selected.values(), reverse=True)
            legal_dice_sets = [
                sorted(
                    [int(value) for value in (ability_array.get("dice") or [])],
                    reverse=True,
                )
                for ability_array in legal_arrays
            ]

            if current_dice not in legal_dice_sets:
                raise MobileSyncValidationError(
                    "Your dice must match one of the legal ability arrays."
                )

            for stat_name in STAT_NAMES:
                StatSystem.set_die_size(
                    character,
                    stat_name,
                    selected[str(stat_name)],
                )

            self._validate_character()
            self._persist_and_refresh()
            return {"dice": selected}

        if action in {"buddy.set_name", "buddy.set_hp"}:
            character = self._character()
            buddy = next(
                (
                    improvement
                    for improvement in character.improvements.list_of_taken_improvements
                    if str(getattr(improvement, "catalog_id", "")) == "animal_buddy"
                    and str(getattr(improvement, "id", "")) == str(payload.get("improvement_id") or "")
                ),
                None,
            )
            if buddy is None:
                raise MobileSyncValidationError("The Animal Buddy could not be found.")

            if action == "buddy.set_name":
                buddy.choices["buddy_name"] = str(payload.get("name") or "").strip()[:100]
            else:
                try:
                    from notes_ui import buddy_state  # type: ignore
                    data = buddy_state(buddy, character.BDV)
                except Exception as exc:
                    raise MobileSyncValidationError(
                        f"Could not read the Animal Buddy state: {exc}"
                    ) from exc
                hp = int(payload.get("hp", data["current_hp"]))
                hp = max(0, min(int(data["max_hp"]), hp))
                buddy.choices["_buddy_marked_damage"] = int(data["max_hp"]) - hp

            self._validate_character()
            self._persist_and_refresh()
            return None

        if action == "character.level_up":
            character = self._character()
            character.grant_milestone(heal_new_heart=True)
            self._validate_character()
            self._persist_and_refresh()
            return {"level": int(getattr(character.progression, "level", 1))}

        if action in {"heightened.add", "heightened.remove"}:
            try:
                from backend_2_1 import StatSystem  # type: ignore
            except ImportError as exc:
                raise MobileSyncValidationError(f"Desktop build cannot edit Heightened Abilities: {exc}") from exc
            stat = str(payload.get("stat") or "").strip().lower()
            ok = (
                StatSystem.add_free_heightened_ability(self._character(), stat)
                if action == "heightened.add"
                else StatSystem.remove_free_heightened_ability(self._character(), stat)
            )
            if not ok:
                raise MobileSyncValidationError("That Heightened Ability change is not allowed.")
            self._validate_character()
            self._persist_and_refresh()
            return None

        if action == "improvement.remove":
            improvement_id = self._required_id(payload)
            try:
                from backend_2_1 import ImprovementSystem  # type: ignore
            except ImportError as exc:
                raise MobileSyncValidationError(f"Desktop build cannot remove Improvements: {exc}") from exc
            if not ImprovementSystem.remove_improvement(self._character(), improvement_id):
                raise MobileSyncValidationError("That Improvement could not be removed.")
            self._validate_character()
            self._persist_and_refresh()
            return None

        if action in {"empowerment.edit", "empowerment.remove"}:
            improvement_id = self._required_id(payload, "improvement_id")
            empowerment_id = self._required_id(payload, "empowerment_id")
            parent = next(
                (item for item in self._character().improvements.list_of_taken_improvements
                 if str(getattr(item, "id", "")) == improvement_id),
                None,
            )
            if parent is None:
                raise MobileSyncValidationError("The parent Improvement no longer exists.")
            empowerment = next(
                (item for item in list(getattr(parent, "empowerments", []) or [])
                 if str(getattr(item, "id", "")) == empowerment_id),
                None,
            )
            if empowerment is None:
                raise MobileSyncValidationError("That empowerment no longer exists.")

            if action == "empowerment.remove":
                try:
                    from backend_2_1 import ImprovementSystem  # type: ignore
                except ImportError as exc:
                    raise MobileSyncValidationError(f"Desktop build cannot remove empowerments: {exc}") from exc
                if not ImprovementSystem.remove_empowerment(self._character(), improvement_id, empowerment_id):
                    raise MobileSyncValidationError("That empowerment could not be removed.")
            else:
                incoming = payload.get("choices")
                if not isinstance(incoming, dict):
                    raise MobileSyncValidationError("Empowerment choices must be an object.")
                existing = dict(getattr(empowerment, "choices", {}) or {})
                editable_keys = {str(key) for key in existing if not str(key).startswith("_")}
                if not editable_keys:
                    raise MobileSyncValidationError("This empowerment has no editable choices.")
                for key in editable_keys:
                    if key in incoming:
                        value = str(incoming.get(key) or "")
                        if len(value) > 10_000:
                            raise MobileSyncValidationError("Empowerment choice is too long.")
                        existing[key] = value
                empowerment.choices = existing

            self._validate_character()
            self._persist_and_refresh()
            return None

        if action == "species.edit":
            try:
                from backend_2_1 import ImprovementCatalogSystem  # type: ignore
            except ImportError as exc:
                raise MobileSyncValidationError(
                    f"Desktop build cannot edit a Species: {exc}"
                ) from exc

            character = self._character()
            improvement_id = str(payload.get("improvement_id") or "").strip()
            species = next(
                (
                    improvement
                    for improvement in character.improvements.list_of_taken_improvements
                    if str(getattr(improvement, "source", "") or "") == "species"
                    and (
                        not improvement_id
                        or str(getattr(improvement, "id", "") or "") == improvement_id
                    )
                ),
                None,
            )
            if species is None:
                raise MobileSyncValidationError(
                    "This character does not have an editable Species."
                )

            option = ImprovementCatalogSystem.get_option(species.catalog_id)
            if not isinstance(option, dict):
                raise MobileSyncValidationError(
                    "The Species catalog entry could not be found."
                )

            species_name = str(payload.get("species_name") or "").strip()
            if not species_name:
                raise MobileSyncValidationError("Species name is required.")

            incoming = (
                payload.get("choices")
                if isinstance(payload.get("choices"), dict)
                else {}
            )
            required = []
            for item in option.get("requires_choices", []) or []:
                key = (
                    str(item.get("key") or item.get("id") or item.get("name") or "")
                    if isinstance(item, dict)
                    else str(item)
                ).strip()
                if key:
                    required.append(key)

            current_choices = dict(getattr(species, "choices", {}) or {})
            for key in required:
                value = str(incoming.get(key) or "").strip()
                if not value:
                    raise MobileSyncValidationError(
                        f"Species choice '{key}' is required."
                    )
                current_choices[key] = value

            current_choices["_species_name"] = species_name
            species.choices = current_choices
            character.species_name = species_name

            self._validate_character()
            self._persist_and_refresh()
            return None

        if action == "species.add":
            try:
                from backend_2_1 import ImprovementSystem  # type: ignore
            except ImportError as exc:
                raise MobileSyncValidationError(f"Desktop build cannot add a Species: {exc}") from exc
            character = self._character()
            catalog_id = str(payload.get("catalog_id") or "").strip()
            choices = payload.get("choices") if isinstance(payload.get("choices"), dict) else {}
            species_name = str(payload.get("species_name") or "").strip()
            options = list(ImprovementSystem.get_species_options(character) or [])
            selected = next(
                (
                    option for option in options
                    if str(option.get("catalog_id") or option.get("id") or "") == catalog_id
                ),
                None,
            )
            if selected is None:
                raise MobileSyncValidationError("That Species option is no longer available.")
            safe_choices = {}
            allowed = []
            for item in selected.get("requires_choices", []) or []:
                key = (
                    str(item.get("key") or item.get("id") or item.get("name") or "")
                    if isinstance(item, dict) else str(item)
                ).strip()
                if key:
                    allowed.append(key)
            for key in allowed:
                value = str(choices.get(key) or "").strip()
                if not value:
                    raise MobileSyncValidationError(f"Species choice '{key}' is required.")
                safe_choices[key] = value
            safe_choices["_species_name"] = species_name
            if not species_name:
                raise MobileSyncValidationError("Species name is required.")
            if not ImprovementSystem.add_from_catalog(
                character=character,
                catalog_id=catalog_id,
                choices=safe_choices,
                source="species",
            ):
                raise MobileSyncValidationError("That Species could not be added.")
            self._validate_character()
            self._persist_and_refresh()
            return None

        if action == "note.link":
            self._note_link(payload)
            self._validate_character()
            self._persist_and_refresh()
            return None

        try:
            from .mobile_sync_v7 import handle_mobile_v7_action
        except ImportError:
            from mobile_sync_v7 import handle_mobile_v7_action

        v7 = handle_mobile_v7_action(self, action, payload)
        if v7.handled:
            if v7.mutated:
                self._validate_character()
                self._persist_and_refresh()
            return v7.result

        if action == "resource.change":
            self._handle_resource_change(payload)
        elif action == "identity.set":
            self._set_identity(payload)
        elif action == "inventory.add":
            self._inventory_add(payload)
        elif action == "inventory.update":
            self._inventory_update(payload)
        elif action == "inventory.remove":
            self._inventory_remove(payload)
        else:
            raise MobileSyncValidationError(f"Unsupported mobile action: {action}")

        self._validate_character()
        self._persist_and_refresh()
        return None

    # ------------------------------------------------------------------
    # Shared validation helpers
    # ------------------------------------------------------------------
    def _ensure_editable(self) -> None:
        readonly_check = getattr(self.window, "is_readonly_character", None)
        if callable(readonly_check) and bool(readonly_check()):
            raise MobileSyncValidationError(
                "This character is read-only on the computer and cannot be changed from the phone"
            )

    def _character(self) -> Any:
        character = getattr(self.window, "character", None)
        if character is None:
            raise MobileSyncValidationError("No character is currently open on the computer")
        return character

    def _validate_character(self) -> None:
        validate = getattr(self._character(), "validate", None)
        if callable(validate):
            validate()

    @staticmethod
    def _required_id(payload: dict, field: str = "id") -> str:
        value = str(payload.get(field, "")).strip()
        if not value or len(value) > 160:
            raise MobileSyncValidationError(f"Invalid {field}")
        return value

    @staticmethod
    def _bounded_text(
        value: Any,
        *,
        label: str,
        maximum: int,
        strip: bool = False,
    ) -> str:
        text = str(value if value is not None else "")
        if strip:
            text = text.strip()
        if len(text) > maximum:
            raise MobileSyncValidationError(f"{label} is too long")
        return text

    # ------------------------------------------------------------------
    # Resources
    # ------------------------------------------------------------------
    def _handle_resource_change(self, payload: dict) -> None:
        resource = str(payload.get("resource", ""))
        try:
            delta = int(payload.get("delta", 0))
        except (TypeError, ValueError) as exc:
            raise MobileSyncValidationError("Resource delta must be an integer") from exc

        if delta == 0:
            raise MobileSyncValidationError("Resource change cannot be zero")
        if abs(delta) > 100:
            raise MobileSyncValidationError("Resource change is too large")

        if resource == "HP":
            self._change_hp(delta)
        elif resource == "Adversity":
            self._change_adversity(delta)
        elif resource == "IP":
            self._change_ip(delta)
        else:
            raise MobileSyncValidationError(f"Unknown resource: {resource}")

    def _change_hp(self, delta: int) -> None:
        if self.hooks.hp_change is not None:
            self.hooks.hp_change(delta)
            return

        hp = getattr(self._character(), "HP", None)
        if hp is None:
            raise MobileSyncValidationError("This character has no HP resource")

        current = int(getattr(hp, "current_HP"))
        maximum = int(getattr(hp, "max_HP"))
        target = current + delta
        if target < 0 or target > maximum:
            raise MobileSyncValidationError(f"HP must stay between 0 and {maximum}")
        hp.current_HP = target

    def _change_adversity(self, delta: int) -> None:
        if self.hooks.adversity_change is not None:
            self.hooks.adversity_change(delta)
            return

        adversity = getattr(self._character(), "adversity", None)
        if adversity is None:
            raise MobileSyncValidationError("This character has no Adversity Token resource")

        current = int(getattr(adversity, "current_AT"))
        maximum = int(getattr(adversity, "max_AT"))
        target = current + delta
        if target < 0 or target > maximum:
            raise MobileSyncValidationError(
                f"Adversity Tokens must stay between 0 and {maximum}"
            )
        adversity.current_AT = target

    def _change_ip(self, delta: int) -> None:
        if self.hooks.ip_change is not None:
            self.hooks.ip_change(delta)
            return

        progression = getattr(self._character(), "progression", None)
        if progression is None:
            raise MobileSyncValidationError("This character has no Improvement Point resource")

        current = int(getattr(progression, "current_IP"))
        target = current + delta
        if target < 0:
            raise MobileSyncValidationError("Improvement Points cannot be negative")
        progression.current_IP = target

    # ------------------------------------------------------------------
    # Identity and inventory
    # ------------------------------------------------------------------
    def _set_identity(self, payload: dict) -> None:
        field = str(payload.get("field", "")).strip()
        character = self._character()

        if field == "name":
            character.name = self._bounded_text(
                payload.get("value", ""),
                label="Character name",
                maximum=self.MAX_NAME_CHARS,
                strip=True,
            )
        else:
            raise MobileSyncValidationError(
                f"Identity field cannot be edited from mobile: {field}"
            )

    def _inventory(self) -> Any:
        inventory = getattr(self._character(), "inventory", None)
        if inventory is None or not hasattr(inventory, "list_of_items"):
            raise MobileSyncValidationError("This character has no inventory")
        return inventory

    def _inventory_add(self, payload: dict) -> None:
        name = self._bounded_text(
            payload.get("name", ""),
            label="Item name",
            maximum=self.MAX_NAME_CHARS,
            strip=True,
        )
        description = self._bounded_text(
            payload.get("description", ""),
            label="Item description",
            maximum=self.MAX_ITEM_DESCRIPTION_CHARS,
        )
        try:
            quantity = max(0, int(payload.get("quantity", 1)))
        except (TypeError, ValueError) as exc:
            raise MobileSyncValidationError("Item quantity must be a number") from exc

        if quantity > 1_000_000:
            raise MobileSyncValidationError("Item quantity is too large")

        inventory = self._inventory()
        item_type = self._inventory_item_type(inventory)
        requested_id = str(payload.get("id") or "").strip()
        if requested_id and len(requested_id) > 160:
            raise MobileSyncValidationError("Invalid inventory item id")

        inventory.list_of_items.append(
            item_type(
                id=requested_id or str(uuid4()),
                name=name,
                description=description,
                quantity=quantity,
                expanded=True,
            )
        )

    def _inventory_update(self, payload: dict) -> None:
        item_id = self._required_id(payload)
        item = self._find_inventory_item(item_id)

        if "name" in payload:
            item.name = self._bounded_text(
                payload.get("name", ""),
                label="Item name",
                maximum=self.MAX_NAME_CHARS,
                strip=True,
            )
        if "description" in payload:
            item.description = self._bounded_text(
                payload.get("description", ""),
                label="Item description",
                maximum=self.MAX_ITEM_DESCRIPTION_CHARS,
            )
        if "quantity" in payload:
            try:
                quantity = max(0, int(payload.get("quantity", 0)))
            except (TypeError, ValueError) as exc:
                raise MobileSyncValidationError("Item quantity must be a number") from exc
            if quantity > 1_000_000:
                raise MobileSyncValidationError("Item quantity is too large")
            item.quantity = quantity

        if "expanded" in payload:
            item.expanded = bool(payload.get("expanded"))

    def _inventory_remove(self, payload: dict) -> None:
        item_id = self._required_id(payload)
        inventory = self._inventory()
        original_count = len(inventory.list_of_items)
        inventory.list_of_items = [
            item
            for item in inventory.list_of_items
            if str(getattr(item, "id", "")) != item_id
        ]
        if len(inventory.list_of_items) == original_count:
            raise MobileSyncValidationError("Inventory item no longer exists")

    def _find_inventory_item(self, item_id: str) -> Any:
        for item in self._inventory().list_of_items:
            if str(getattr(item, "id", "")) == item_id:
                return item
        raise MobileSyncValidationError("Inventory item no longer exists")

    @staticmethod
    def _inventory_item_type(inventory: Any):
        existing = list(getattr(inventory, "list_of_items", []))
        if existing:
            return type(existing[0])

        try:
            from backend_2_1 import InventoryItem  # type: ignore
        except ImportError as exc:
            raise MobileSyncValidationError(
                "The desktop build cannot create inventory items from mobile"
            ) from exc

        return InventoryItem

    # ------------------------------------------------------------------
    # Desktop persistence / refresh
    # ------------------------------------------------------------------
    def _persist_and_refresh(self) -> None:
        if self.hooks.save_after_change is not None:
            self.hooks.save_after_change()
        else:
            mark_dirty = getattr(self.window, "mark_dirty", None)
            if not callable(mark_dirty):
                raise RuntimeError(
                    "Desktop frontend does not expose mark_dirty; "
                    "provide save_after_change hook"
                )
            mark_dirty(auto_save=True)

        if self.hooks.refresh_after_change is not None:
            self.hooks.refresh_after_change()
        else:
            refresh = getattr(self.window, "refresh_ui", None)
            if callable(refresh):
                refresh()
