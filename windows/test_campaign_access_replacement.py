"""Tests that do not require installed PySide6 or live Supabase access."""
import ast
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parent
code = (ROOT / 'campaign_role_ui.py').read_text('utf-8')
module = ast.parse(code)
hub = next(n for n in module.body if isinstance(n, ast.ClassDef) and n.name == 'CampaignsHubDialog')
methods = {}
for fn in hub.body:
    if isinstance(fn, ast.FunctionDef) and fn.name in ('_campaign_character_record','_player_has_approved_character'):
        codeobj = compile(ast.Module(body=[fn],type_ignores=[]),str(ROOT/'campaign_role_ui.py'),'exec')
        ns = {}
        exec(codeobj,ns)
        methods[fn.name] = ns[fn.name]

class FakeHub:
    _campaign_character_record = methods['_campaign_character_record']
    _player_has_approved_character = methods['_player_has_approved_character']
    def __init__(self,links):
        self.current_player_campaign = {'id':'campaign-a'}
        self.client = SimpleNamespace(links=SimpleNamespace(all_links=lambda:links))

class TestAccess(unittest.TestCase):
    def test_no_link_denied(self):
        h=FakeHub({})
        self.assertIsNone(h._campaign_character_record()[0])
        self.assertFalse(h._player_has_approved_character())
    def test_rejected_denied(self):
        h=FakeHub({'c1':{'campaign_id':'campaign-a','approval_status':'rejected','request_id':'req1'}})
        self.assertEqual(h._campaign_character_record()[0],'c1')
        self.assertFalse(h._player_has_approved_character())
    def test_pending_denied(self):
        h=FakeHub({'c1':{'campaign_id':'campaign-a','approval_status':'pending','request_id':'req1'}})
        self.assertFalse(h._player_has_approved_character())
    def test_approved_allowed_with_other_open(self):
        h=FakeHub({'c1':{'campaign_id':'campaign-a','campaign_character_id':'cc1'}})
        self.assertTrue(h._player_has_approved_character())
    def test_unrelated_campaign_denied(self):
        h=FakeHub({'c1':{'campaign_id':'campaign-b','campaign_character_id':'cc1'}})
        self.assertFalse(h._player_has_approved_character())
    def test_approved_precedes_rejected(self):
        h=FakeHub({'c2':{'campaign_id':'campaign-a','approval_status':'rejected','request_id':'req1'},'c1':{'campaign_id':'campaign-a','campaign_character_id':'cc1'}})
        self.assertEqual(h._campaign_character_record()[0],'c1')
        self.assertTrue(h._player_has_approved_character())
    def test_replacement_has_correct_rpc_names(self):
        self.assertIn('/rest/v1/rpc/did_withdraw_campaign_character',code)
        self.assertIn('cancel_character_approval(request_id)',code)
    def test_hub_gates_details_and_dashboard(self):
        self.assertIn('if not self.current_player_campaign or not self._player_has_approved_character():',code)
        self.assertIn('if is_player and not self._player_has_approved_character():',code)
    def test_background_job_used(self):
        self.assertIn('self._submit_hub_job("player_replace", generation, withdraw)',code)

if __name__=='__main__': unittest.main()
