"""Qt-free tests verifying campaign approval/decision RPCs execute off the GUI thread."""
from __future__ import annotations
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

SRC = Path(__file__).resolve().parents[1] / 'campaign_role_ui.py'
TEXT = SRC.read_text('utf-8')
tree = ast.parse(TEXT)
hub = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'CampaignsHubDialog')
names = ('_refresh_hub_from_button', '_refresh_selected_player_admission',
         '_finish_player_approval_refresh', '_decide_dm_character_request',
         '_finish_dm_character_decision')
functions = [n for n in hub.body if isinstance(n, ast.FunctionDef) and n.name in names]
assert len(functions) == len(names)
namespace = {'QMessageBox': SimpleNamespace(warning=Mock()),
             '_confirm_character_admission': Mock(return_value=True),
             'schedule_campaign_state_sync': Mock()}
exec(compile(ast.fix_missing_locations(ast.Module(body=functions, type_ignores=[])),
             str(SRC), 'exec'), namespace)


class Client:
    def __init__(self, state='pending', campaign='C1'):
        self.pending = dict(approval_status=state, campaign_id=campaign, request_id='R1')
        self.remote = dict(approval_status='approved')
        self.approval_reads = 0
        self.decisions = []
        self.link = dict(campaign_id=campaign, campaign_character_id='CH1')
        self.fail = False
    def get_pending_character_approval(self, character_id):
        self.approval_reads += 1
        return self.pending
    def refresh_pending_character_approval(self, character_id):
        if self.fail: raise ConnectionError('offline')
        return self.remote
    def get_character_link(self, character_id): return self.link
    def decide_character_approval(self, request_id, approve):
        self.decisions.append((request_id, approve))
        if self.fail: raise ConnectionError('offline')
        return {'status': 'approved' if approve else 'rejected'}


class Hub:
    _refresh_hub_from_button = namespace['_refresh_hub_from_button']
    _refresh_selected_player_admission = namespace['_refresh_selected_player_admission']
    _finish_player_approval_refresh = namespace['_finish_player_approval_refresh']
    _decide_dm_character_request = namespace['_decide_dm_character_request']
    _finish_dm_character_decision = namespace['_finish_dm_character_decision']
    def __init__(self):
        self.client = Client()
        self.current_player_campaign = {'id': 'C1'}
        self.current_dm_campaign = {'id': 'C1'}
        self.window = SimpleNamespace(character=SimpleNamespace(id='A1'))
        self.role_pages = SimpleNamespace(currentIndex=lambda: 1)
        self.reload_campaigns = Mock()
        self._refresh_dm_characters = Mock()
        self._refresh_player_details = Mock()
        self._approval_refresh_error = ''
        self._hub_closed = False
        self._hub_approval_epoch = 0
        self._hub_decision_epoch = 0
        self.jobs = []
        namespace['QMessageBox'].warning.reset_mock()
        namespace['_confirm_character_admission'].reset_mock(return_value=True)
        namespace['_confirm_character_admission'].return_value = True
        namespace['schedule_campaign_state_sync'].reset_mock()
    def _submit_hub_job(self, kind, generation, operation):
        self.jobs.append((kind, generation, operation))
    def run_job(self):
        kind, generation, operation = self.jobs.pop(0)
        try:
            result, error = operation(), None
        except Exception as e:
            result, error = None, str(e)
        if kind == 'approval' and generation == self._hub_approval_epoch:
            self._finish_player_approval_refresh(result, error)
        elif kind == 'dm_decision' and generation == self._hub_decision_epoch:
            self._finish_dm_character_decision(result, error)


class Tests(unittest.TestCase):
    def test_explicit_refresh_schedules_not_runs_rpc_on_gui_thread(self):
        h = Hub(); h._refresh_hub_from_button()
        h.reload_campaigns.assert_called_once()
        self.assertEqual(h.client.approval_reads, 1)  # local disk metadata
        self.assertEqual(len(h.jobs), 1)
    def test_no_hidden_dm_network_read(self):
        h=Hub(); h.role_pages=SimpleNamespace(currentIndex=lambda:0)
        self.assertFalse(h._refresh_selected_player_admission()); self.assertEqual(h.client.approval_reads,0)
    def test_pending_for_another_campaign_is_not_checked(self):
        h=Hub();h.client.pending['campaign_id']='C2'
        self.assertFalse(h._refresh_selected_player_admission());self.assertFalse(h.jobs)
    def test_rejected_local_status_does_not_trigger_poll(self):
        h=Hub();h.client.pending['approval_status']='rejected'
        self.assertFalse(h._refresh_selected_player_admission());self.assertFalse(h.jobs)
    def test_approved_correct_campaign_schedules_upload_only_after_worker_result(self):
        h=Hub();self.assertTrue(h._refresh_selected_player_admission())
        namespace['schedule_campaign_state_sync'].assert_not_called()
        h.run_job();namespace['schedule_campaign_state_sync'].assert_called_once_with(h.window)
    def test_approved_wrong_campaign_does_not_upload(self):
        h=Hub();h.client.link['campaign_id']='C2'
        self.assertTrue(h._refresh_selected_player_admission());h.run_job()
        namespace['schedule_campaign_state_sync'].assert_not_called()
    def test_rejection_does_not_upload(self):
        h=Hub();h.client.remote={'approval_status':'rejected'}
        self.assertTrue(h._refresh_selected_player_admission());h.run_job()
        namespace['schedule_campaign_state_sync'].assert_not_called()
    def test_offline_lookup_retains_pending(self):
        h=Hub();h.client.fail=True
        self.assertTrue(h._refresh_selected_player_admission());h.run_job()
        self.assertIn('offline',h._approval_refresh_error)
        self.assertEqual(h.client.pending['approval_status'],'pending')
    def test_stale_approval_result_not_applied(self):
        h=Hub();h._refresh_selected_player_admission()
        h.current_player_campaign={'id':'C2'}
        h.run_job();namespace['schedule_campaign_state_sync'].assert_not_called()
    def test_cancel_dm_dialog_does_not_call_server(self):
        h=Hub();namespace['_confirm_character_admission'].return_value=False
        h._decide_dm_character_request('R1',True,'Name',('Too much IP',),'C1')
        self.assertFalse(h.jobs)
    def test_stale_dm_request_blocked(self):
        h=Hub();h._decide_dm_character_request('R1',True,'Name',(),'C2')
        self.assertFalse(h.jobs);namespace['QMessageBox'].warning.assert_called_once()
    def test_dm_approve_rpc_is_not_run_on_gui_thread(self):
        h=Hub();h._decide_dm_character_request('R1',True,'Name',('Bad rule',),'C1')
        self.assertEqual(h.client.decisions,[])
        self.assertEqual(len(h.jobs),1)
        h.run_job();self.assertEqual(h.client.decisions,[('R1',True)])
        h._refresh_dm_characters.assert_called_once()
    def test_dm_reject_rpc_and_refresh(self):
        h=Hub();h._decide_dm_character_request('R1',False,'Name',('Bad rule',),'C1')
        h.run_job();self.assertEqual(h.client.decisions,[('R1',False)])
        h._refresh_dm_characters.assert_called_once()
    def test_dm_rpc_failure_refreshes_no_success(self):
        h=Hub();h.client.fail=True
        h._decide_dm_character_request('R1',True,'Name',(),'C1')
        h.run_job();namespace['QMessageBox'].warning.assert_called_once()
        h._refresh_dm_characters.assert_called_once()
    def test_preexisting_server_rpc_contract(self):
        cloud=(SRC.parent/'campaign_cloud.py').read_text('utf-8')
        self.assertIn('"/rest/v1/rpc/did_decide_character_approval"',cloud)
        self.assertIn('"/rest/v1/rpc/did_request_character_approval"',cloud)

if __name__ == '__main__': unittest.main()
