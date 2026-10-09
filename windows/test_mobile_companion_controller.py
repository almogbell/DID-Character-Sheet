from __future__ import annotations

import unittest
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QMenu, QWidget

from windows.mobile_companion_controller import MobileCompanionController


class Box:
    pass


class FakeStorage:
    @staticmethod
    def character_to_dict(character):
        return {
            "id": character.id,
            "name": character.name,
            "HP": {
                "current_HP": character.HP.current_HP,
                "max_HP": character.HP.max_HP,
            },
            "Adversity": {
                "current_AT": character.adversity.current_AT,
                "max_AT": character.adversity.max_AT,
            },
            "progression": {"current_IP": character.progression.current_IP},
        }


class FakeWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.character = self._character("c1")
        self.dirty_calls = []
        self.refresh_calls = 0

    @staticmethod
    def _character(char_id):
        c = Box()
        c.id = char_id
        c.name = "Test Hero"
        c.HP = Box()
        c.HP.current_HP = 6
        c.HP.max_HP = 8
        c.adversity = Box()
        c.adversity.current_AT = 2
        c.adversity.max_AT = 5
        c.progression = Box()
        c.progression.current_IP = 3
        return c

    def mark_dirty(self, auto_save=False):
        self.dirty_calls.append(auto_save)

    def refresh_all(self):
        self.refresh_calls += 1

    def is_readonly_character(self):
        return False


class FakeServer:
    def __init__(self, *, desktop_version, state_provider, command_handler, parent=None):
        self.desktop_version = desktop_version
        self.state_provider = state_provider
        self.command_handler = command_handler
        self.parent = parent
        self.started = 0
        self.stopped = 0
        self.desktop_changes = 0
        self.character_changes = 0
        self.listening = False

    def start(self):
        self.started += 1
        self.listening = True
        return True

    def stop(self):
        self.stopped += 1
        self.listening = False

    def is_listening(self):
        return self.listening

    def notify_desktop_change(self):
        self.desktop_changes += 1

    def notify_active_character_changed(self):
        self.character_changes += 1


class ControllerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def make_controller(self):
        self.window = FakeWindow()
        self.addCleanup(self.window.deleteLater)
        patcher = patch("windows.mobile_companion_controller.MobileSyncServer", FakeServer)
        patcher.start()
        self.addCleanup(patcher.stop)
        controller = MobileCompanionController(
            window=self.window,
            storage_system=FakeStorage,
            app_version="1.0.10",
        )
        self.addCleanup(controller.shutdown)
        return controller

    def test_server_starts_immediately_for_saved_phone_reconnects(self):
        controller = self.make_controller()
        self.assertEqual(controller.server.started, 1)
        self.assertTrue(controller.server.is_listening())

    def test_desktop_mutation_is_detected_and_broadcast(self):
        controller = self.make_controller()
        self.window.character.HP.current_HP = 5
        controller._poll_desktop_state()
        self.assertEqual(controller.server.desktop_changes, 1)
        self.assertEqual(controller.server.character_changes, 0)

    def test_active_character_switch_emits_character_event(self):
        controller = self.make_controller()
        self.window.character = FakeWindow._character("c2")
        controller._poll_desktop_state()
        self.assertEqual(controller.server.character_changes, 1)

    def test_mobile_mutation_does_not_double_count_in_poller(self):
        controller = self.make_controller()
        controller.server.command_handler(
            "resource.change",
            {"resource": "HP", "delta": -1},
            0,
            "request-1",
        )
        self.assertEqual(self.window.character.HP.current_HP, 5)
        controller._poll_desktop_state()
        self.assertEqual(controller.server.desktop_changes, 0)
        self.assertEqual(controller.server.character_changes, 0)

    def test_tools_menu_gets_mobile_companion_action_once(self):
        controller = self.make_controller()
        menu = QMenu(self.window)
        menu.addAction("New Character")
        menu.addAction("Load Character")
        check = menu.addAction("Check for Updates")
        menu.addAction("How to Use")

        controller._maybe_add_tools_action(menu)
        controller._maybe_add_tools_action(menu)

        texts = [action.text() for action in menu.actions()]
        self.assertEqual(texts.count("Mobile Companion"), 1)
        self.assertLess(texts.index("Mobile Companion"), texts.index(check.text()))

    def test_unrelated_menu_is_not_modified(self):
        controller = self.make_controller()
        menu = QMenu(self.window)
        menu.addAction("Delete")
        menu.addAction("Rename")
        controller._maybe_add_tools_action(menu)
        self.assertNotIn("Mobile Companion", [action.text() for action in menu.actions()])


if __name__ == "__main__":
    unittest.main()
