"""End-to-end Windows adapter command tests (no networking, no credentials)."""
import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mobile_sync_frontend_adapter import DesktopSyncAdapter, MobileSyncValidationError

class Char:
    def __init__(self,data):
        self.data=deepcopy(data);self.id=data['id'];self.name=data.get('name','Unnamed')
    def validate(self):
        if 'id' not in self.data:raise ValueError('id missing')
class Storage:
    SAVE_DIR=''
    @staticmethod
    def character_to_dict(ch):return deepcopy(ch.data)
    @staticmethod
    def character_from_dict(data):return Char(data)
    @staticmethod
    def export_character_file(ch,path):Path(path).write_text(json.dumps(ch.data),encoding='utf-8')
    @staticmethod
    def import_character_file(path):return Char(json.loads(Path(path).read_text(encoding='utf-8')))
    @staticmethod
    def looks_like_character_file(path):return True

class SyncIntegrationTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        Storage.SAVE_DIR=self.temp.name
        self.base={'id':'hero','name':'Hero','HP':{'current_HP':8},'Adversity':{'current_AT':2},
                   'notes':{'list_of_notes':[{'id':'n','title':'Note','text':'Original'}]},
                   'inventory':{'list_of_items':[{'id':'i','name':'Sword','quantity':1,'description':''}]}}
        self.path=Path(self.temp.name)/'Hero.didchar'
        self.path.write_text(json.dumps(self.base))
        self.window=SimpleNamespace(character=None,unsaved_changes=False)
        self.adapter=DesktopSyncAdapter(self.window,Storage)
        self.adapter.cloud_sync=None
        self.adapter._mobile_tombstones=lambda: {}
    def payload(self, phone, pref=None, base=None):
        b=base or self.base
        result={'character':phone,'base_character':b,'base_hash':self.adapter._character_content_hash(b)}
        if pref:result['hp_at_choice']=pref
        return result
    def test_two_new_items_auto_merge_without_dialog(self):
        pc=deepcopy(self.base);h=deepcopy(self.base)
        pc['inventory']['list_of_items'].append({'id':'pc','name':'Rope','quantity':1})
        h['inventory']['list_of_items'].append({'id':'h','name':'Potion','quantity':2})
        self.path.write_text(json.dumps(pc))
        result=self.adapter.command_handler('character.upsert_snapshot',self.payload(h),0,'1')
        saved=json.loads(self.path.read_text())
        self.assertEqual({x['id'] for x in saved['inventory']['list_of_items']},{'i','pc','h'})
        self.assertEqual(result['content_hash'],self.adapter._character_content_hash(saved))
    def test_concurrent_hp_conflict_requires_choice_non_hp_merged(self):
        pc=deepcopy(self.base);h=deepcopy(self.base)
        pc['HP']['current_HP']=7
        h['HP']['current_HP']=6
        h['notes']['list_of_notes'].append({'id':'new','title':'New','text':'Phone note'})
        self.path.write_text(json.dumps(pc))
        with self.assertRaises(MobileSyncValidationError) as exc:
            self.adapter.command_handler('character.upsert_snapshot',self.payload(h),0,'2')
        self.assertTrue(str(exc.exception).startswith('HP_AT_CONFLICT:HP'))
        self.assertEqual(json.loads(self.path.read_text())['HP']['current_HP'],7)
        result=self.adapter.command_handler('character.upsert_snapshot',self.payload(h,pref='phone'),0,'3')
        self.assertEqual(result['character']['HP']['current_HP'],6)
        self.assertEqual(len(result['character']['notes']['list_of_notes']),2)
    def test_concurrent_scalar_changes_are_recovered_in_sidecar(self):
        pc=deepcopy(self.base);h=deepcopy(self.base)
        pc['name']='PC Hero'
        h['name']='Phone Hero'
        self.path.write_text(json.dumps(pc))
        result=self.adapter.command_handler('character.upsert_snapshot',self.payload(h),0,'extra')
        self.assertEqual(result['character']['name'],'PC Hero')
        recovery=Path(str(self.path)+'.sync-alternatives.json')
        self.assertTrue(recovery.is_file())
        recovery_data=json.loads(recovery.read_text())
        self.assertEqual(recovery_data[0]['phone'],'Phone Hero')
        self.assertEqual(recovery_data[0]['pc'],'PC Hero')

    def test_unknown_base_preserves_existing_not_silent_overwrite(self):
        pc=deepcopy(self.base);h=deepcopy(self.base)
        pc['notes']['list_of_notes'][0]['text']='PC'
        h['notes']['list_of_notes'][0]['text']='Phone'
        self.path.write_text(json.dumps(pc))
        with self.assertRaises(MobileSyncValidationError) as exc:
            self.adapter.command_handler('character.upsert_snapshot',{'character':h,'base_hash':'notreal'},0,'4')
        self.assertTrue(str(exc.exception).startswith('SYNC_MERGE_NEEDS_BASE:'))
        self.assertEqual(json.loads(self.path.read_text())['notes']['list_of_notes'][0]['text'],'PC')
    def test_simultaneous_quantity_delta(self):
        pc=deepcopy(self.base);h=deepcopy(self.base)
        pc['inventory']['list_of_items'][0]['quantity']=3
        h['inventory']['list_of_items'][0]['quantity']=4
        self.path.write_text(json.dumps(pc))
        r=self.adapter.command_handler('character.upsert_snapshot',self.payload(h),0,'5')['character']
        self.assertEqual(r['inventory']['list_of_items'][0]['quantity'],6)
        self.assertEqual(len(r['inventory']['list_of_items']),1)

if __name__=='__main__':unittest.main()
