"""Qt-independent regression checks for Problem 17 campaign loading.

Tests compile the production method bodies with mock Qt widgets. They don't
pretend to test physical Windows rendering or cloud latency.
"""
from __future__ import annotations

import ast
import copy
import queue
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

SOURCE = (Path(__file__).resolve().parents[1] / "campaign_role_ui.py").read_text("utf-8")
TREE = ast.parse(SOURCE)
HUB = next(x for x in TREE.body if isinstance(x, ast.ClassDef) and x.name == "CampaignsHubDialog")
JOB = next(x for x in TREE.body if isinstance(x, ast.ClassDef) and x.name == "_CampaignHubNetworkJob")


class FakeQRunnable:
    def __init__(self):
        pass


class FakeItem:
    def __init__(self, label):
        self.label = label
        self.flags_value = 0
        self.userdata = {}
    def setTextAlignment(self, alignment): self.alignment = alignment
    def setFlags(self, flags): self.flags_value = flags
    def flags(self): return self.flags_value
    def setData(self, role, value): self.userdata[role] = value


class FakeList:
    def __init__(self):
        self.items = []
        self.signals = []
        self.row = -1
        self.on_change = None
    def blockSignals(self, blocked): self.signals.append(blocked)
    def clear(self): self.items.clear(); self.row=-1
    def addItem(self, item): self.items.append(item)
    def count(self): return len(self.items)
    def currentRow(self): return self.row
    def setCurrentRow(self, index):
        previous = self.row
        self.row = index
        if previous != index and self.on_change is not None:
            self.on_change(index)


class FakeButton:
    def __init__(self): self.text = ""; self.enabled = True; self.tooltip = ""
    def setEnabled(self, value): self.enabled = value
    def setText(self, value): self.text = value
    def setToolTip(self, value): self.tooltip = value
    def fontMetrics(self):
        return SimpleNamespace(horizontalAdvance=lambda x:len(x)*8,elidedText=lambda x,_mode,w:x[:int(w/8)])


QT = SimpleNamespace(AlignmentFlag=SimpleNamespace(AlignCenter=1),
                     ItemFlag=SimpleNamespace(NoItemFlags=0, ItemIsEditable=2),
                     ItemDataRole=SimpleNamespace(UserRole=4),
                     TextElideMode=SimpleNamespace(ElideMiddle=1))


def isolate_method(name):
    node = copy.deepcopy(next(x for x in HUB.body if isinstance(x, ast.FunctionDef) and x.name == name))
    node.decorator_list = []
    mod = ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[]))
    namespace = {"_fit_button": lambda b: None, "QListWidgetItem": FakeItem,
                 "Qt": QT, "Empty": queue.Empty, "QLabel": lambda text:text}
    exec(compile(mod, "production_campaign_role_ui.py", "exec"), namespace)
    return namespace[name]


class Hub:
    reload_campaigns = isolate_method("reload_campaigns")
    _finish_campaign_reload = isolate_method("_finish_campaign_reload")
    _show_campaigns_loading = staticmethod(isolate_method("_show_campaigns_loading"))
    _drain_hub_results = isolate_method("_drain_hub_results")
    _refresh_discord_action_label = isolate_method("_refresh_discord_action_label")
    _finish_discord_label = isolate_method("_finish_discord_label")
    _restore_list_selection = isolate_method("_restore_list_selection")

    def __init__(self, service=None, client=None):
        self.service = service
        self.client = client
        self.dm_list = FakeList()
        self.player_list = FakeList()
        self.dm_campaigns = []
        self.player_campaigns = []
        self.current_dm_campaign = None
        self.current_player_campaign = None
        self.dm_tab_btn = FakeButton()
        self.player_tab_btn = FakeButton()
        self.refresh_btn = FakeButton()
        self.discord_settings_btn = FakeButton()
        self._hub_list_epoch = 0
        self._hub_dm_epoch = 0
        self._hub_discord_epoch = 0
        self._hub_player_link_epoch = 0
        self._hub_player_link_token = None
        self._hub_approval_epoch = 0
        self._hub_decision_epoch = 0
        self._resize_campaign_tabs = Mock()  # Current compact toolbar is independent of network tests.
        self._hub_closed = False
        self._hub_results = queue.SimpleQueue()
        self.submissions = []
        self.changes = []
        self.dm_list.on_change = self._dm_selection_changed
        self.player_list.on_change = self._player_selection_changed
        self._player_helper_needs_reload = False
    def _submit_hub_job(self, kind, generation, operation):
        self.submissions.append((kind, generation, operation))
    def _dm_selection_changed(self,row):
        self.current_dm_campaign = self.dm_campaigns[row] if 0 <= row < len(self.dm_campaigns) else None
        self.changes.append(("dm",row))
    def _player_selection_changed(self,row):
        self.current_player_campaign = self.player_campaigns[row] if 0 <= row < len(self.player_campaigns) else None
        self.changes.append(("player",row))
    def _finish_dm_characters(self,payload,error): self.changes.append(("details",payload,error))


class CampaignPerformanceTests(unittest.TestCase):
    def test_syntax_and_no_gui_from_network_job(self):
        self.assertIn('self.results.put',ast.get_source_segment(SOURCE,JOB))
        self.assertNotIn('QLabel(',ast.get_source_segment(SOURCE,JOB))
        ast.parse(SOURCE)

    def test_opening_campaigns_does_not_call_network_on_gui_thread(self):
        client=SimpleNamespace(user_id="U1")
        service=SimpleNamespace(list_campaigns=lambda:self.fail("called synchronously"))
        hub=Hub(service,client)
        hub.reload_campaigns()
        self.assertFalse(hub.refresh_btn.enabled)
        self.assertEqual(hub.dm_list.items[0].label,'Loading campaigns…')
        self.assertEqual(hub.submissions[0][:2],('list',1))
        self.assertEqual(hub.dm_campaigns,[])

    def test_worker_returns_data_without_touching_widgets(self):
        namespace={"QRunnable":FakeQRunnable}
        module=ast.fix_missing_locations(ast.Module(body=[copy.deepcopy(JOB)], type_ignores=[]))
        exec(compile(module,"production_worker.py","exec"),namespace)
        out=queue.SimpleQueue()
        job=namespace['_CampaignHubNetworkJob'](out,'list',4,lambda:'data')
        thread=threading.Thread(target=job.run)
        thread.start(); thread.join(timeout=1)
        self.assertEqual(out.get_nowait(),('list',4,'data',None))
        job=namespace['_CampaignHubNetworkJob'](out,'discord',5,lambda:1/0)
        job.run()
        kind,generation,payload,error=out.get_nowait()
        self.assertEqual((kind,generation,payload),('discord',5,None))
        self.assertIn('division by zero',error)

    def test_latest_list_wins_even_if_old_request_completes_last(self):
        hub=Hub(SimpleNamespace(list_campaigns=lambda:[]),SimpleNamespace(user_id='D'))
        hub.reload_campaigns()
        hub.reload_campaigns()
        hub._hub_results.put(('list',2,('D',[{'id':'new','name':'New','owner_user_id':'D'}]),None))
        hub._hub_results.put(('list',1,('D',[{'id':'old','name':'Old','owner_user_id':'D'}]),None))
        hub._drain_hub_results()
        self.assertEqual([x['id'] for x in hub.dm_campaigns],['new'])
        self.assertTrue(hub.refresh_btn.enabled)
        self.assertEqual(hub.dm_list.items[0].label,'New')

    def test_list_sort_and_correct_dm_vs_player(self):
        hub=Hub()
        hub._finish_campaign_reload(('owner',[{'id':'p','name':'Raven','owner_user_id':'other'},
                    {'id':'d2','name':'Zebra','owner_user_id':'owner'},
                    {'id':'d1','name':'apple','owner_user_id':'owner'}]),None)
        self.assertEqual([r['id'] for r in hub.dm_campaigns],['d1','d2'])
        self.assertEqual([r['id'] for r in hub.player_campaigns],['p'])
        self.assertEqual(hub.current_dm_campaign['id'],'d1')
        self.assertEqual(hub.current_player_campaign['id'],'p')

    def test_offline_refresh_keeps_previous_campaign(self):
        hub=Hub(service=SimpleNamespace(list_campaigns=lambda: []), client=SimpleNamespace(user_id='owner'))
        hub._finish_campaign_reload(('owner',[{'id':'old','name':'Saved','owner_user_id':'owner'}]),None)
        hub.reload_campaigns()
        hub._hub_results.put(('list',hub._hub_list_epoch,None,'Network timeout'))
        hub._drain_hub_results()
        self.assertEqual(hub.current_dm_campaign['id'],'old')
        self.assertIn('timeout',hub.refresh_btn.tooltip)
        self.assertTrue(hub.refresh_btn.enabled)

    def test_stale_campaign_details_never_replace_new_selection(self):
        hub=Hub()
        hub._hub_dm_epoch=2
        hub._hub_discord_epoch=6
        hub._hub_results.put(('dm',1,('old',[],[],None,None),None))
        hub._hub_results.put(('discord',5,('old',{'channel_name':'old'}),None))
        hub._drain_hub_results()
        self.assertEqual(hub.changes,[])
        self.assertEqual(hub.discord_settings_btn.text,'')

    def test_discord_fetch_does_not_block_or_duplicate(self):
        class NoNetwork:
            def get_discord_connection(self,*args):
                raise AssertionError('called on UI thread')
        hub=Hub(client=NoNetwork())
        hub.current_dm_campaign={'id':'C1'}
        hub._refresh_discord_action_label()
        self.assertEqual(hub.discord_settings_btn.text,'Checking Discord…')
        self.assertEqual(hub.submissions[-1][:2],('discord',1))
        self.assertEqual(hub.submissions[-1][2].__closure__ is not None,True)

    def test_old_discord_response_not_applied_to_another_campaign(self):
        hub=Hub()
        hub.current_dm_campaign={'id':'C2'}
        hub._finish_discord_label(('C1',{'channel_name':'stale'}),None)
        self.assertEqual(hub.discord_settings_btn.text,'')

    def test_newly_created_campaign_selected_after_async_reload(self):
        hub=Hub(service=SimpleNamespace(list_campaigns=lambda: []),client=SimpleNamespace(user_id='D'))
        hub._finish_campaign_reload(('D',[{'id':'old','name':'Old','owner_user_id':'D'}]),None)
        hub.reload_campaigns(select_dm_id='new')
        self.assertEqual(hub.current_dm_campaign['id'],'old')  # old list stays visible until load
        hub._hub_results.put(('list',hub._hub_list_epoch,
                              ('D',[{'id':'old','name':'Old','owner_user_id':'D'},
                                    {'id':'new','name':'New','owner_user_id':'D'}]),None))
        hub._drain_hub_results()
        self.assertEqual(hub.current_dm_campaign['id'],'new')

    def test_newly_joined_campaign_selected_after_async_reload(self):
        hub=Hub(service=SimpleNamespace(list_campaigns=lambda: []),client=SimpleNamespace(user_id='D'))
        hub.reload_campaigns(select_player_id='joined')
        hub._hub_results.put(('list',hub._hub_list_epoch,
                              ('D',[{'id':'joined','name':'Joined','owner_user_id':'other'},
                                    {'id':'other','name':'Other','owner_user_id':'other'}]),None))
        hub._drain_hub_results()
        self.assertEqual(hub.current_player_campaign['id'],'joined')

    def test_roster_and_approvals_fetch_in_parallel(self):
        from concurrent.futures import ThreadPoolExecutor
        barrier=threading.Barrier(2,timeout=0.6)
        class Client:
            def list_campaign_characters(self,campaign_id):
                barrier.wait()
                return [{'id':'char1'}]
            def list_pending_character_approvals(self,campaign_id):
                barrier.wait()
                return [{'id':'approval1'}]
        fn=isolate_method('_refresh_dm_characters')
        fn.__globals__['ThreadPoolExecutor']=ThreadPoolExecutor
        class FakeLabel:
            def __init__(self,text): self.text=text
            def setObjectName(self,name): pass
        fn.__globals__['QLabel']=FakeLabel
        class Scope:
            _hub_dm_epoch=0
            current_dm_campaign={'id':'C1'}
            client=Client()
            dm_character_layout=SimpleNamespace(addWidget=lambda label:None)
            def _clear_layout(self,layout): pass
            def _submit_hub_job(self,kind,generation,operation):
                self.operation=operation
        hub=Scope()
        fn(hub)
        camp_id,rows,approvals,err1,err2=hub.operation()
        self.assertEqual((camp_id,rows[0]['id'],approvals[0]['id'],err1,err2),
                         ('C1','char1','approval1',None,None))

    def test_cancelled_dialog_drops_queued_network_results(self):
        hub=Hub()
        hub._hub_closed=True
        hub._hub_results.put(('list',0,('owner',[{'id':'x'}]),None))
        hub._drain_hub_results()
        self.assertEqual(hub.dm_campaigns,[])

    def test_dm_refresh_method_only_queues_network(self):
        fn=isolate_method('_refresh_dm_characters')
        class FakeLabel:
            def __init__(self,txt):self.text=txt
            def setObjectName(self,x):pass
        ns=fn.__globals__;ns['QLabel']=FakeLabel
        class Scope:
            _hub_dm_epoch=0
            current_dm_campaign={'id':'DM1'}
            client=SimpleNamespace(list_campaign_characters=lambda *a:self.fail('network in GUI'))
        scope=Scope();scope.dm_character_layout=SimpleNamespace(addWidget=lambda w:None)
        scope._clear_layout=lambda _:None
        scope.jobs=[]
        scope._submit_hub_job=lambda kind,n,task:scope.jobs.append((kind,n,task))
        fn(scope)
        self.assertEqual(scope.jobs[0][:2],('dm',1))


if __name__=='__main__':unittest.main()
