"""Problem 7: tests the real pairing method bodies without requiring PySide6.

Run from Windows source root:
  python -m unittest discover -s DID_Important_Tests -p 'test_problem07_pairing_lifecycle.py' -v
"""
from __future__ import annotations
import ast
import copy
import json
import math
import secrets
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch
import unittest

ROOT = Path(__file__).resolve().parent.parent
S = (ROOT/'mobile_sync_server.py').read_text(encoding='utf8')
U = (ROOT/'mobile_companion_dialog.py').read_text(encoding='utf8')


def method(src, klass, name, env=None):
    tree=ast.parse(src)
    cls=next(node for node in tree.body if isinstance(node,ast.ClassDef) and node.name==klass)
    func=copy.deepcopy(next(node for node in cls.body if isinstance(node,ast.FunctionDef) and node.name==name))
    func.decorator_list=[]
    ns=dict(env or {})
    exec(compile(ast.fix_missing_locations(ast.Module(body=[func],type_ignores=[])),'<original method>','exec'),ns)
    return ns[name]


class Signal:
    def __init__(self): self.values=[]
    def emit(self, value): self.values.append(value)


class FakeServer:
    def __init__(self):
        self._pairing_token=None
        self._pairing_expires_at=0.0
        self._pairing_payload=None
        self._pairing_last_end_reason=''
        self._server_id='server-identity'
        self.desktop_version='1.0.13'
        self.port=8765
        self.pairingChanged=Signal()
        self.clients_pinged=0
        self._clients={}
    def start(self):return True
    def pairing_lan_addresses(self):return [('Wi-Fi','192.168.1.20')]
    def _best_lan_ip(self):return '192.168.1.20'
    def connected_device_ids(self):return set()
    def _emit_client_count(self):pass

server_env={'secrets':secrets,'time':__import__('time'),'SYNC_PROTOCOL':1,'PAIRING_TTL_SECONDS':300,'Optional':__import__('typing').Optional}
begin=method(S,'MobileSyncServer','begin_pairing',server_env)
active=method(S,'MobileSyncServer','active_pairing_payload',server_env)
cancel=method(S,'MobileSyncServer','cancel_pairing',server_env)
heartbeat=method(S,'MobileSyncServer','_heartbeat_clients',server_env)
handle_pair=method(S,'MobileSyncServer','_handle_pair',{**server_env,'uuid':__import__('uuid'), 'MAX_DEVICE_ID_CHARS':128, 'MAX_DEVICE_NAME_CHARS':120, 'MAX_VERSION_CHARS':64})

FakeServer.begin_pairing=begin
FakeServer.active_pairing_payload=active
FakeServer.cancel_pairing=cancel
FakeServer._heartbeat_clients=heartbeat

class FakeWidget:
    def __init__(self):self.text='';self.enabled=None
    def setText(self,v):self.text=v
    def setEnabled(self,v):self.enabled=v

class FakeDialog:
    def __init__(self,server):
        self.server=server
        self._last_pairing_json=''
        self._pairing_explanation=''
        self._display_expires_at=0.0
        self.pairing_text=FakeWidget()
        self.copy_button=FakeWidget()
        self.cancel_pairing_button=FakeWidget()
        self.start_button=FakeWidget()
        self.status=FakeWidget()
        self.qrs=[]
        self.placeholder=[]
    def _set_qr_placeholder(self,msg):self.placeholder.append(msg)
    def _show_client_count(self,_count):pass
    def _qr_pixmap(self,value):return value
    def _show_qr_pixmap(self,value):self.qrs.append(value)

env_ui={
    'json':json,'time':__import__('time'),'math':math,
    'os':__import__('os'),
    'DEFAULT_PAIRING_LANDING_URL':'https://almogbell.github.io/DID-Character-Sheet/pair/',
    'make_pairing_landing_url':lambda p,u:'https://almogbell.github.io/DID-Character-Sheet/pair/#did=safe',
}
for name in ('_restore_pairing','_refresh_pairing_timer','_show_pairing','_copy_pairing','_cancel_pairing'):
    setattr(FakeDialog,name,method(U,'MobileCompanionDialog',name,env_ui))

class Tests(TestCase):
    def test_five_minute_temporary_code_and_exact_payload(self):
        fake=FakeServer()
        with patch('time.time',return_value=1000):
            p=fake.begin_pairing()
            self.assertEqual(p['expires_at'],1300)
            self.assertEqual(p['port'],8765)
            self.assertEqual(p['host'],'192.168.1.20')
            self.assertEqual(p['type'],'did_pairing')
            self.assertEqual(fake.active_pairing_payload(),p)
        self.assertEqual(len(fake.pairingChanged.values),1)

    def test_replacement_invalidates_prior_code(self):
        f=FakeServer()
        with patch('time.time',return_value=100):
            a=f.begin_pairing(); b=f.begin_pairing()
            self.assertNotEqual(a['pairing_token'],b['pairing_token'])
            self.assertEqual(f.active_pairing_payload()['pairing_token'],b['pairing_token'])
        self.assertEqual(len(f.pairingChanged.values),2)

    def test_cancellation_clears_secret_and_copyable_payload(self):
        f=FakeServer();f.begin_pairing()
        f.cancel_pairing()
        self.assertIsNone(f._pairing_token)
        self.assertIsNone(f._pairing_payload)
        self.assertIsNone(f.active_pairing_payload())
        self.assertEqual(f._pairing_last_end_reason,'cancelled')
        self.assertIsNone(f.pairingChanged.values[-1])

    def test_expiration_revokes_token_without_dialog(self):
        f=FakeServer()
        with patch('time.time',return_value=10):p=f.begin_pairing(ttl_seconds=30)
        with patch('time.time',return_value=42):f._heartbeat_clients()
        self.assertIsNone(f._pairing_token)
        self.assertIsNone(f._pairing_payload)
        self.assertEqual(f._pairing_last_end_reason,'expired')
        self.assertIsNone(f.pairingChanged.values[-1])

    def test_expired_code_does_not_reappear(self):
        f=FakeServer()
        with patch('time.time',return_value=100): f.begin_pairing(ttl_seconds=30)
        with patch('time.time',return_value=131):
            self.assertIsNone(f.active_pairing_payload())
        d=FakeDialog(f)
        d._restore_pairing()
        self.assertFalse(d.qrs)

    def test_restore_valid_qr_after_dialog_reopened(self):
        f=FakeServer(); p=f.begin_pairing()
        d=FakeDialog(f)
        d._restore_pairing()
        self.assertEqual(json.loads(d._last_pairing_json),p)
        self.assertEqual(len(d.qrs),1)
        self.assertTrue(d.copy_button.enabled)
        self.assertTrue(d.cancel_pairing_button.enabled)
        self.assertEqual(d.start_button.text,'New pairing code')
        d._restore_pairing()
        self.assertEqual(len(d.qrs),1,'Same QR should not be redrawn on every show')

    def test_cancel_button_disables_copy_and_removes_qr(self):
        f=FakeServer();f.begin_pairing()
        d=FakeDialog(f)
        f.pairingChanged.emit=lambda p:(FakeDialog._show_pairing(d,p))
        d._restore_pairing()
        d._cancel_pairing()
        self.assertFalse(d.copy_button.enabled)
        self.assertFalse(d.cancel_pairing_button.enabled)
        self.assertEqual(d._last_pairing_json,'')
        self.assertIn('cancelled',d.pairing_text.text.lower())

    def test_expiration_countdown(self):
        f=FakeServer()
        with patch('time.time',return_value=1000):f.begin_pairing(ttl_seconds=300)
        d=FakeDialog(f)
        with patch('time.time',return_value=1000):d._restore_pairing()
        self.assertIn('5:00',d.pairing_text.text)
        with patch('time.time',return_value=1299):d._refresh_pairing_timer()
        self.assertIn('0:01',d.pairing_text.text)
        with patch('time.time',return_value=1300):d._refresh_pairing_timer()
        self.assertFalse(d.copy_button.enabled)
        self.assertFalse(d.cancel_pairing_button.enabled)
        self.assertIn('expired',d.pairing_text.text.lower())

    def test_cancelled_or_replaced_codes_rejected_by_auth_handler(self):
        f=FakeServer()
        f._protocol_matches=lambda message:message.get('protocol')==1
        f._protocol_error=lambda: {'type':'error','code':'PROTOCOL_MISMATCH'}
        f.sent=[]
        f._send=lambda ws,message:f.sent.append(message)
        f._bounded_text=lambda v,n: str(v or '')[:n]
        f._settings={'devices':{}}
        f._save_settings=lambda:None
        f._disconnect_previous_sessions=lambda *_:None
        f._state_message=lambda:{'type':'state','character':None}
        f._emit_client_count=lambda:None
        class Ws:
            def close(self): pass
        client=SimpleNamespace(socket=Ws(), authenticated=False, device_id='', device_name='', android_version='')
        p1=f.begin_pairing()
        p2=f.begin_pairing()
        handle_pair(f,client,{'protocol':1,'pairing_token':p1['pairing_token'],'device_id':'phone1'})
        self.assertEqual(f.sent[-1]['code'],'PAIRING_EXPIRED_OR_INVALID')
        handle_pair(f,client,{'protocol':1,'pairing_token':p2['pairing_token'],'device_id':'phone1'})
        self.assertTrue(client.authenticated)
        self.assertEqual(f._pairing_last_end_reason,'completed')
        self.assertIsNone(f._pairing_token)
        self.assertIn('phone1',f._settings['devices'])
        self.assertEqual(f.sent[-2]['type'],'pair_ok')
        p3=f.begin_pairing()
        f.cancel_pairing()
        f.sent=[]
        handle_pair(f,client,{'protocol':1,'pairing_token':p3['pairing_token'],'device_id':'phone2'})
        self.assertEqual(f.sent[-1]['code'],'PAIRING_EXPIRED_OR_INVALID')

    def test_original_pairing_protocol_and_transport_remain(self):
        for check in ('"type": "pair_ok"', '"type": "pair_error"','"type": "did_pairing"',
                      'def _handle_hello(', 'def _handle_command(', 'def _reply_to_discovery('):
            self.assertIn(check,S)
        self.assertIn('make_pairing_landing_url(payload, landing)',U)
        self.assertIn('self.content_scroll = QScrollArea(self)',U)

    def test_copy_uses_current_not_expired_code(self):
        f=FakeServer()
        with patch('time.time',return_value=100):
            f.begin_pairing(ttl_seconds=30)
            d=FakeDialog(f)
            class Clipboard:
                def __init__(self): self.text=None
                def setText(self,v): self.text=v
            clipboard=Clipboard()
            FakeDialog._copy_pairing.__globals__['QGuiApplication']=SimpleNamespace(clipboard=lambda:clipboard)
            d._restore_pairing()
            d._copy_pairing()
            self.assertEqual(json.loads(clipboard.text)['pairing_token'],f._pairing_token)
        previous=clipboard.text
        with patch('time.time',return_value=131):
            d._copy_pairing()
        self.assertEqual(clipboard.text,previous, 'An expired code must not be copied again')
        self.assertFalse(d.copy_button.enabled)


if __name__=='__main__': unittest.main()
