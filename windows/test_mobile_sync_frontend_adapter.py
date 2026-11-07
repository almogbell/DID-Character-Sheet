from __future__ import annotations

import unittest

from windows.mobile_sync_frontend_adapter import (
    DesktopSyncAdapter,
    FrontendHooks,
    MobileSyncValidationError,
)


class Box:
    pass


class FakeItem:
    def __init__(self, id, name, description, quantity=0, expanded=False):
        self.id = id
        self.name = name
        self.description = description
        self.quantity = quantity
        self.expanded = expanded

    def validate(self):
        self.quantity = max(0, int(self.quantity))


class FakeStorage:
    @staticmethod
    def character_to_dict(character):
        return {
            "name": character.name,
            "backstory": character.backstory,
            "HP": {"current_HP": character.HP.current_HP, "max_HP": character.HP.max_HP},
            "Adversity": {"current_AT": character.adversity.current_AT, "max_AT": character.adversity.max_AT},
            "progression": {"current_IP": character.progression.current_IP},
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
        }


class FakeWindow:
    def __init__(self):
        c = Box()
        c.name = "Test Hero"
        c.backstory = "Before"
        c.HP = Box()
        c.HP.current_HP = 6
        c.HP.max_HP = 8
        c.adversity = Box()
        c.adversity.current_AT = 2
        c.adversity.max_AT = 5
        c.progression = Box()
        c.progression.current_IP = 3
        c.inventory = Box()
        c.inventory.list_of_items = [FakeItem("item-1", "Rope", "Useful rope", 1, True)]
        self.character = c
        self.dirty_calls = []
        self.readonly = False

    def mark_dirty(self, auto_save=False):
        self.dirty_calls.append(auto_save)

    def is_readonly_character(self):
        return self.readonly


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.window = FakeWindow()
        self.adapter = DesktopSyncAdapter(self.window, FakeStorage)

    def test_state_uses_desktop_serializer(self):
        state = self.adapter.state_provider()
        self.assertEqual(state["name"], "Test Hero")
        self.assertEqual(state["HP"]["current_HP"], 6)

    def test_hp_change_uses_normal_dirty_autosave_path(self):
        self.adapter.command_handler("resource.change", {"resource": "HP", "delta": -1}, 0, "x")
        self.assertEqual(self.window.character.HP.current_HP, 5)
        self.assertEqual(self.window.dirty_calls, [True])

    def test_adversity_bounds_are_enforced(self):
        with self.assertRaises(MobileSyncValidationError):
            self.adapter.command_handler("resource.change", {"resource": "Adversity", "delta": 4}, 0, "x")
        self.assertEqual(self.window.character.adversity.current_AT, 2)

    def test_ip_cannot_be_negative(self):
        with self.assertRaises(MobileSyncValidationError):
            self.adapter.command_handler("resource.change", {"resource": "IP", "delta": -4}, 0, "x")
        self.assertEqual(self.window.character.progression.current_IP, 3)

    def test_readonly_character_rejects_mobile_mutation(self):
        self.window.readonly = True
        with self.assertRaises(MobileSyncValidationError):
            self.adapter.command_handler("resource.change", {"resource": "HP", "delta": -1}, 0, "x")
        self.assertEqual(self.window.character.HP.current_HP, 6)
        self.assertEqual(self.window.dirty_calls, [])

    def test_explicit_hooks_override_fallback_mutation(self):
        calls = []
        adapter = DesktopSyncAdapter(
            self.window,
            FakeStorage,
            FrontendHooks(
                hp_change=lambda delta: calls.append(("hp", delta)),
                save_after_change=lambda: calls.append(("save", None)),
                refresh_after_change=lambda: calls.append(("refresh", None)),
            ),
        )
        adapter.command_handler("resource.change", {"resource": "HP", "delta": 1}, 0, "x")
        self.assertEqual(calls, [("hp", 1), ("save", None), ("refresh", None)])
        self.assertEqual(self.window.character.HP.current_HP, 6)

    def test_identity_name_and_backstory_use_autosave_path(self):
        self.adapter.command_handler("identity.set", {"field": "name", "value": "  Mobile Hero  "}, 0, "x")
        self.adapter.command_handler("identity.set", {"field": "backstory", "value": "After"}, 1, "y")
        self.assertEqual(self.window.character.name, "Mobile Hero")
        self.assertEqual(self.window.character.backstory, "After")
        self.assertEqual(self.window.dirty_calls, [True, True])

    def test_species_is_not_free_text_editable(self):
        with self.assertRaises(MobileSyncValidationError):
            self.adapter.command_handler("identity.set", {"field": "species_name", "value": "Elf"}, 0, "x")

    def test_inventory_update_and_remove(self):
        self.adapter.command_handler(
            "inventory.update",
            {"id": "item-1", "name": "Silk Rope", "quantity": 2, "description": "50 feet"},
            0,
            "x",
        )
        item = self.window.character.inventory.list_of_items[0]
        self.assertEqual((item.name, item.quantity, item.description), ("Silk Rope", 2, "50 feet"))

        self.adapter.command_handler("inventory.remove", {"id": "item-1"}, 1, "y")
        self.assertEqual(self.window.character.inventory.list_of_items, [])

    def test_inventory_add_reuses_desktop_item_type(self):
        self.adapter.command_handler(
            "inventory.add",
            {"name": "Torch", "description": "Bright", "quantity": 3},
            0,
            "x",
        )
        items = self.window.character.inventory.list_of_items
        self.assertEqual(len(items), 2)
        self.assertIsInstance(items[-1], FakeItem)
        self.assertEqual((items[-1].name, items[-1].quantity, items[-1].expanded), ("Torch", 3, True))

    def test_missing_inventory_item_is_rejected_without_save(self):
        with self.assertRaises(MobileSyncValidationError):
            self.adapter.command_handler("inventory.update", {"id": "missing", "quantity": 2}, 0, "x")
        self.assertEqual(self.window.dirty_calls, [])

    def test_unknown_actions_are_rejected(self):
        with self.assertRaises(MobileSyncValidationError):
            self.adapter.command_handler("inventory.delete", {}, 0, "x")


if __name__ == "__main__":
    unittest.main()
