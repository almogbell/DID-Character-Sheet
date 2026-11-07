"""Small data safety and API authority regression suite."""
import unittest

from test_support import app_dir
app_dir()

import backend_2_1 as backend
import character_API as api


class CoreTests(unittest.TestCase):
    def test_api_controls_owned_description(self):
        character = backend.Character.create_new_character("Authority")
        option = backend.ImprovementCatalogSystem.get_option("animal_buddy", character)
        item = backend.Improvement(id="buddy", catalog_id="animal_buddy",
                                   name="Old", cost=3, description="STALE SAVED TEXT", choices={})
        character.improvements.list_of_taken_improvements.append(item)
        display = backend.ImprovementSystem.build_improvement_display(character, item)
        self.assertIn("When your buddy helps", display["summary"])
        self.assertIn("<b>d4</b>", display["summary"])
        self.assertNotIn("STALE SAVED TEXT", display["summary"])

    def test_empowerment_ability_names_come_from_api(self):
        harm = api.SPELLCASTING_EMPOWERMENT_NOTE_HTML["harm_slinger"]
        enchant = api.SPELLCASTING_EMPOWERMENT_NOTE_HTML["expert_enchanter"]
        for name in ("Area harm", "Extended range", "Damage and effect"):
            self.assertIn(f"<b>{name}:</b>", harm)
        for name in ("Area enchantment", "Very far range", "Extended duration"):
            self.assertIn(f"<b>{name}:</b>", enchant)

    def test_empty_notes_have_independent_ids(self):
        character = backend.Character.create_new_character("Notes")
        character.notes.list_of_notes.extend([
            backend.CharacterNote(id="blank-a"), backend.CharacterNote(id="blank-b")])
        character.notes.remove("blank-a")
        self.assertEqual([note.id for note in character.notes.list_of_notes], ["blank-b"])

    def test_color_and_linked_notes_survive_serialization(self):
        character = backend.Character.create_new_character("Colors")
        character.notes.list_of_notes.append(backend.CharacterNote(
            id="one", title="Mighty", text="Effects", color="#a1b2c3",
            linked_improvement_id="imp-1", expanded=False))
        restored = backend.CharacterStorageSystem.character_from_dict(
            backend.CharacterStorageSystem.character_to_dict(character))
        note = restored.notes.list_of_notes[0]
        self.assertEqual((note.id, note.color, note.linked_improvement_id, note.expanded),
                         ("one", "#a1b2c3", "imp-1", False))

    def test_multiple_portraits_survive_serialization(self):
        character = backend.Character.create_new_character("Portraits")
        data = ["data:image/png;base64,AA==", "data:image/jpeg;base64,AA=="]
        for value in data:
            self.assertTrue(backend.ImageSystem.add_image(character, value))
        restored = backend.CharacterStorageSystem.character_from_dict(
            backend.CharacterStorageSystem.character_to_dict(character))
        self.assertEqual([image.image_data for image in restored.image.images], data)
        self.assertEqual(restored.image.current_index, 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
