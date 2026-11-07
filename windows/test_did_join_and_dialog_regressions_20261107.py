"""Source and isolated-controller tests for the 2026-11-07 campaign join changes.

Run without a live database, characters, or PySide6; no user data is touched.
"""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest

HERE = Path(__file__).resolve().parent
HUB = (HERE / 'campaign_role_ui.py').read_text(encoding='utf8')
FRONTEND = (HERE / 'frontend_2_8.py').read_text(encoding='utf8')


def extracted_method(source, class_name, method_name, globals_=None):
    module = ast.parse(source)
    klass = next(n for n in module.body if isinstance(n, ast.ClassDef) and n.name == class_name)
    fn = next(n for n in klass.body if isinstance(n, ast.FunctionDef) and n.name == method_name)
    space = dict(globals_ or {})
    exec(compile(ast.Module(body=[fn], type_ignores=[]), '<method>', 'exec'), space)
    return space[method_name]


class Stub:
    def __init__(self, value=''):
        self.value = value
        self.hidden = False
        self.enabled = True
        self.text = value
    def setText(self, text): self.text = text
    def setEnabled(self, enabled): self.enabled = enabled
    def hide(self): self.hidden = True
    def show(self): self.hidden = False
    def clear(self): self.text = ''
    def setCurrentIndex(self, i): self.value = i
    def currentRow(self): return self.value


class TestJoinFlow(unittest.TestCase):
    def test_join_has_separate_screen_and_character_choice(self):
        self.assertIn('self.player_workspace_stack.setCurrentIndex(1)', HUB)
        self.assertIn('page.addWidget(self._build_player_join_page())', HUB)
        self.assertIn('"+ Create New Using Campaign Rules"', HUB)
        self.assertIn('self.join_character_list', HUB)
        self.assertIn('self._populate_join_candidates(joined)', HUB)
        # The role join no longer publishes whichever character is open.
        fn = extracted_method(HUB, 'CampaignsHubDialog', '_resolve_player_invite')
        calls = []
        fake = SimpleNamespace(
            service=SimpleNamespace(join_campaign=lambda code, name: calls.append((code, name)) or {'id': 'camp', 'name': 'Camp'}),
            join_code_field=SimpleNamespace(text=lambda: 'A12B04'),
            join_confirm_btn=Stub(),
            join_cancel_btn=Stub(),
            join_code_section=Stub(),
            join_choice_section=Stub(),
            join_step_intro=Stub(),
            join_campaign_title=Stub(),
            _campaign_character_record=lambda campaign: (None, None),
            _populate_join_candidates=lambda campaign: calls.append(('choose', campaign['id'])),
        )
        fn(fake)
        self.assertEqual(calls, [('A12B04', 'Player'), ('choose', 'camp')])
        self.assertEqual(fake._joined_campaign_candidate['id'], 'camp')
        self.assertTrue(fake.join_code_section.hidden)
        self.assertFalse(fake.join_choice_section.hidden)

    def test_no_republication_when_join_code_accepted(self):
        fn = extracted_method(HUB, 'CampaignsHubDialog', '_submit_player_join')
        visited = []
        fake = SimpleNamespace(_joined_campaign_candidate=None,
                               _resolve_player_invite=lambda: visited.append('code'),
                               _use_selected_campaign_character=lambda: visited.append('selected'))
        fn(fake)
        self.assertEqual(visited, ['code'])
        fake._joined_campaign_candidate = {'id': 'camp'}
        fn(fake)
        self.assertEqual(visited, ['code', 'selected'])

    def test_linked_character_card_ignores_open_sheet(self):
        body = extracted_method(HUB, 'CampaignsHubDialog', '_campaign_character_record')
        records = {'a': {'campaign_id': 'camp', 'campaign_character_id': 'approved-id',
                         'character_name': 'Linked Hero'},
                   'b': {'campaign_id': 'elsewhere', 'campaign_character_id': 'wrong'}}
        fake = SimpleNamespace(current_player_campaign={'id':'camp'},
                               client=SimpleNamespace(links=SimpleNamespace(all_links=lambda: records)))
        character_id, record = body(fake)
        self.assertEqual(character_id, 'a')
        self.assertEqual(record['character_name'], 'Linked Hero')

    def test_rejected_access_guard_and_replacement_remain(self):
        self.assertIn('self.player_replace_character_btn.clicked.connect(self._replace_player_character)', HUB)
        self.assertIn('self.player_party_dashboard_btn.setVisible(is_approved)', HUB)
        self.assertIn('self.player_campaign_info_btn.setVisible(is_approved)', HUB)
        self.assertIn('if not self.current_player_campaign or not self._player_has_approved_character():', HUB)
        self.assertIn('/rest/v1/rpc/did_withdraw_campaign_character', HUB)
        self.assertIn('client.cancel_character_approval(request_id)', HUB)

    def test_creation_claim_persisted_on_first_save(self):
        self.assertIn('"invite_code": str(self.join_code_field.text() or "").strip()', HUB)
        self.assertIn("CampaignTemplateService(client).join_campaign(", FRONTEND)
        self.assertIn('"Creation Rules template"', HUB) if '"Creation Rules template"' in HUB else self.assertIn("character-creation template", HUB)


class TestAbilityRollAndPortrait(unittest.TestCase):
    def test_ability_roll_button_left_and_enter(self):
        start = FRONTEND.index('class FantasyDiceOptionsDialog(QDialog):')
        end = FRONTEND.index('class ', start + 8)
        dialog = FRONTEND[start:end]
        self.assertIn('buttons.addWidget(cancel_btn)\n        buttons.addStretch(1)\n        buttons.addWidget(roll_btn)', dialog)
        self.assertIn('roll_btn.setDefault(True)', dialog)
        self.assertIn('counter.lineEdit().installEventFilter(self)', dialog)
        self.assertIn('counter.interpretText()', dialog)
        self.assertIn('Qt.Key.Key_Return, Qt.Key.Key_Enter', dialog)

    def test_portrait_webp_and_png_normalization(self):
        start=FRONTEND.index('    def add_character_image_from_ui(self):')
        end=FRONTEND.index('    @qt_lifecycle_safe', start)
        method=FRONTEND[start:end]
        self.assertIn('*.webp', method)
        self.assertIn('Image.open(io.BytesIO(raw))', method)
        self.assertIn('image.save(output, "PNG")', method)
        self.assertIn('data:image/png;base64,', method)

    def test_invite_codes_are_in_clear_monospace(self):
        self.assertIn('self.join_code_field.setStyleSheet(', HUB)
        self.assertIn("font-family: Consolas", HUB)
        self.assertIn('self.join_code_field.returnPressed.connect(self._resolve_player_invite)', HUB)


if __name__ == '__main__':
    unittest.main()
