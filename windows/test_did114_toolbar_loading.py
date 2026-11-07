"""Source-level regression checks for DID Character Sheet 1.0.14 UI follow-up."""
from pathlib import Path
import ast
import importlib.util
import unittest

ROOT=Path(__file__).resolve().parent
SPEC=importlib.util.spec_from_file_location('did114_compact', ROOT/'patch_did114_toolbar_loading.py')
P=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(P)

class CompactToolbarTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ui=(ROOT/'campaign_role_ui.py').read_text(encoding='utf8')
        cls.loading=(ROOT/'ui_feedback.py').read_text(encoding='utf8')
    def test_source_syntax(self):
        ast.parse(self.ui)
        ast.parse(self.loading)
    def test_patch_idempotency(self):
        self.assertEqual(self.ui,P.patch_hub(self.ui))
        self.assertEqual(self.loading,P.patch_loading(self.loading))
    def test_single_toolbar_row(self):
        self.assertIn('toolbar.insertWidget(0, tabs_host)',self.ui)
        self.assertNotIn('root.addWidget(tabs_host, 0, Qt.AlignmentFlag.AlignLeft)',self.ui)
    def test_equal_campaign_tabs(self):
        self.assertIn('self._campaign_tabs_host.setFixedWidth(2 * width + 6)',self.ui)
        self.assertIn('button.setFixedSize(width, 38)',self.ui)
    def test_compact_help_refresh(self):
        self.assertIn('button.setFixedSize(help_width, 38)',self.ui)
        self.assertIn('QPushButton#CampaignRoleTab, QPushButton#CampaignToolbarButton',self.ui)
        self.assertNotIn('self.refresh_btn.setFixedSize(182, 40)',self.ui)
    def test_dm_actions_still_accessible(self):
        self.assertIn('self._campaign_actions_layout.addWidget(button)',self.ui)
        self.assertIn('self._campaign_actions_host.setVisible(',self.ui)
    def test_help_tabs_themed(self):
        self.assertIn('tabs.tabBar().setExpanding(False)',self.ui)
        self.assertIn('QTabBar::tab:selected { background:#fff1d6;',self.ui)
    def test_loading_compact_centered(self):
        self.assertIn('layout.setSizeConstraint(QLayout.SizeConstraint.SetFixedSize)',self.loading)
        self.assertIn('bounds = screen.availableGeometry()',self.loading)
        self.assertIn('self.status_label.setWordWrap(True)',self.loading)
    def test_loading_not_overridden_by_refresh_label(self):
        self.assertNotIn('self.refresh_btn.setText("Loading…")',self.ui)
        self.assertIn('item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)',self.ui)

if __name__=='__main__':unittest.main()
