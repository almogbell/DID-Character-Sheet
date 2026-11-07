"""Tests for campaign-only progression restrictions. No Qt required."""
import ast
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from campaign_tools_policy import campaign_tools_locked, window_campaign_tools_locked
from campaign_cloud import CampaignLinkStore

ROOT = Path(__file__).resolve().parent

class CampaignProgressionPolicyTests(unittest.TestCase):
    def test_standalone_not_locked(self):
        self.assertFalse(campaign_tools_locked('char-one'))
        self.assertFalse(campaign_tools_locked('char-one', link={}))
        self.assertFalse(campaign_tools_locked('char-one', link={'campaign_id': ''}))

    def test_campaign_linked_locked(self):
        self.assertTrue(campaign_tools_locked('char-one', link={
            'campaign_id': 'campaign-one', 'campaign_character_id': 'linked-row',
        }))

    def test_pending_campaign_locked_only_for_same_character(self):
        pending = {'campaign_id': 'campaign-one', 'character_id': 'char-one'}
        self.assertTrue(campaign_tools_locked('char-one', pending=pending))
        self.assertFalse(campaign_tools_locked('char-two', pending=pending))
        self.assertFalse(campaign_tools_locked('char-one', pending={'campaign_id': '', 'character_id': 'char-one'}))

    def test_removed_link_unlocked(self):
        self.assertFalse(campaign_tools_locked('char-one', link={
            'campaign_id': 'campaign-one', 'status': 'removed',
        }))

    def test_standalone_creation_rules_do_not_trigger_campaign_lock(self):
        with tempfile.TemporaryDirectory() as folder:
            win = SimpleNamespace(character=SimpleNamespace(id='standalone',creation_rules_active=True),
                _campaign_cloud_client=SimpleNamespace(user_data_dir=folder))
            self.assertFalse(window_campaign_tools_locked(win))

    def test_locally_persisted_links_survive_restart(self):
        with tempfile.TemporaryDirectory() as folder:
            store = CampaignLinkStore(folder)
            store.set('char-one', {'campaign_id': 'campaign-one', 'campaign_character_id': 'linked-row'})
            win = SimpleNamespace(character=SimpleNamespace(id='char-one'),
                _campaign_cloud_client=SimpleNamespace(user_data_dir=folder))
            self.assertTrue(window_campaign_tools_locked(win))
            win.character.id = 'char-two'
            self.assertFalse(window_campaign_tools_locked(win))

    def test_pending_window_character_without_database_link(self):
        win = SimpleNamespace(character=SimpleNamespace(id='char-one'),
            _pending_campaign_character={'campaign_id':'campaign-one','character_id':'char-one'})
        self.assertTrue(window_campaign_tools_locked(win))

    def test_all_four_entry_points_enforce_guard(self):
        front=(ROOT/'frontend_2_8.py').read_text(encoding='utf-8')
        character=(ROOT/'character_display_ui.py').read_text(encoding='utf-8')
        for source, method in [(front,'adjust_resources_from_ui'),(front,'open_improvement_editor_from_ui'),
            (character,'level_up_from_ui'),(character,'grant_ip_from_ui')]:
            tree=ast.parse(source)
            defs=[n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name==method]
            self.assertEqual(len(defs),1)
            checks=[n for n in ast.walk(defs[0]) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='is_campaign_character_for_tools']
            self.assertTrue(checks,method)

    def test_tools_menu_hides_actions_when_campaign_locked(self):
        source=(ROOT/'frontend_2_8.py').read_text(encoding='utf-8')
        tree=ast.parse(source)
        method=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='toggle_tools_menu')
        for label in ('Level Up','Adjust Resources','Improvement Editor'):
            matches=[n for n in ast.walk(method) if isinstance(n,ast.Constant) and n.value==label]
            self.assertEqual(len(matches),1,label)
            ancestors=[]
            def walk(node, parents):
                if node is matches[0]:
                    ancestors.extend(parents)
                    return
                for child in ast.iter_child_nodes(node):walk(child,parents+[node])
            walk(method,[])
            self.assertTrue(any(isinstance(node,ast.If) and isinstance(node.test,ast.UnaryOp) and isinstance(node.test.operand,ast.Name) and node.test.operand.id=='campaign_locked' for node in ancestors),label)

if __name__ == '__main__': unittest.main()
