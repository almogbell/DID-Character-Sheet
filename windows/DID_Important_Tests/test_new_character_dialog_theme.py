"""Offline regression checks for New Character wizard visual refresh.

Run: python -m unittest discover -s DID_Important_Tests -p test_new_character_dialog_theme.py -v
No PySide6 is required for these source-preservation checks.
"""
import ast
import hashlib
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent.parent
NEW_WIZARD = ROOT / 'campaign_creation_wizard.py'


def _class_methods(source):
    module = ast.parse(source)
    cls = next(n for n in module.body if isinstance(n, ast.ClassDef) and n.name == 'CampaignCreationWizard')
    return {n.name: ast.dump(n, include_attributes=False) for n in cls.body if isinstance(n, ast.FunctionDef)}


class NewCharacterDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = NEW_WIZARD.read_text(encoding='utf-8')
        cls.original = Path(__file__).with_name('original_campaign_creation_wizard.py')
        # When installed into the project, original baseline is not required.

    def test_compiles(self):
        compile(self.text, str(NEW_WIZARD), 'exec')

    def test_existing_mode_identifiers_and_text_preserved(self):
        for name in ('Standalone character', 'standalone', 'Character for an existing campaign',
                     'existing', 'Join a campaign and create a character', 'join',
                     'Campaign invitation code', 'Your display name:',
                     'Create a normal character without campaign restrictions.'):
            with self.subTest(name=name):
                self.assertIn(name, self.text)

    def test_shared_fantasy_theme_for_both_modes(self):
        for expected in ('FANTASY_DIALOG_QSS', 'set_themed_stylesheet(self, NEW_CHARACTER_QSS)',
                         "self.setObjectName('CampaignCreationWizard')",
                         "QDialog#CampaignCreationWizard", 'QFrame#WizardCard',
                         'font-family: Georgia', 'background-color: #f7f1e5'):
            with self.subTest(expected=expected):
                self.assertIn(expected, self.text)

    def test_button_order_and_themes(self):
        self.assertLess(self.text.index("cancel = QPushButton('Cancel')"),
                        self.text.index("proceed = QPushButton('Continue')"))
        for expected in ('make_negative_button(cancel)', 'make_positive_button(proceed)',
                         'cancel.clicked.connect(self.reject)', 'proceed.clicked.connect(self.proceed)',
                         'buttons.addWidget(cancel)', 'buttons.addStretch()', 'buttons.addWidget(proceed)'):
            self.assertIn(expected, self.text)

    def test_modes_change_page_without_changing_flow(self):
        self.assertIn('self.mode.currentIndexChanged.connect(self.pages.setCurrentIndex)', self.text)
        self.assertIn('self.window.new_character_from_ui()', self.text)
        self.assertIn("if mode == 'join':", self.text)
        self.assertIn('self.service.join_campaign(code,', self.text)

    def test_no_connection_or_campaign_behavior_refactor(self):
        # Original method-body AST signatures: the dialog update must not
        # change campaign discovery, joining, or character creation logic.
        original_signatures = {
            '_load_campaigns': 'de1e7517194e5ced9210dc81f91aa9a3432cf502923cf7a113a126ac9f882fe4',
            'proceed': 'a72ee456819d464d7fe7118d2d8f0b46c490b64c0cf567680814bcab989e060b',
        }
        current_methods = _class_methods(self.text)
        for method, signature in original_signatures.items():
            current_hash = hashlib.sha256(current_methods[method].encode('utf-8')).hexdigest()
            self.assertEqual(current_hash, signature, method)


if __name__ == '__main__':
    unittest.main()
