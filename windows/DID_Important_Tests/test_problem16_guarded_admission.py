"""Offline acceptance tests for server-guarded campaign character admission.

Run from Windows app root:
  python -m unittest DID_Important_Tests.test_problem16_guarded_admission -v
No live credentials or PySide6 needed.
"""
import ast
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import importlib.util

ROOT = Path(__file__).resolve().parents[1] if Path(__file__).resolve().parent.name=='DID_Important_Tests' else Path(__file__).resolve().parent
CLOUD=(ROOT/'campaign_cloud.py').read_text(encoding='utf8')
ADMISSION=(ROOT/'campaign_admission.py').read_text(encoding='utf8')
SQL=(Path(__file__).resolve().parent/'PROBLEM_15_16_SERVER_ADMISSION.sql')
if not SQL.exists(): SQL=ROOT/'PROBLEM_15_16_SERVER_ADMISSION.sql'

class GuardedAdmissionTests(unittest.TestCase):
    def test_syntax(self):
        ast.parse(CLOUD); ast.parse(ADMISSION)
    def test_cloud_does_not_direct_insert_character(self):
        method=CLOUD.split('    def link_character(',1)[1].split('    def get_character_link(',1)[0]
        self.assertIn('/rest/v1/rpc/did_admit_compliant_character',method)
        self.assertNotIn('/rest/v1/campaign_characters',method)
        self.assertIn('creation_claim',method)
        self.assertIn('self.links.set',method)
    def test_local_admission_sends_creation_claim(self):
        self.assertIn('creation_claim=creation_claim_from_character(character)', ADMISSION)
    def test_claim_is_minimal_and_does_not_include_private_data(self):
        source=ADMISSION.split('def creation_claim_from_character',1)[1].split('def admit_character(',1)[0]
        for key in ('active','species_mode','improvement_overrides','template_custom_improvements','free_heightened_ability_slots'):
            self.assertIn(f'"{key}"',source)
        for key in ('inventory','notes','portrait','password','filepath'):
            self.assertNotIn(f'"{key}"',source)
    def _cloud_client(self):
        spec=importlib.util.spec_from_file_location("test_p16_cloud",ROOT/"campaign_cloud.py")
        mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
        self.addCleanup(lambda: None)
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        c=mod.CampaignCloudClient(user_data_dir=self.tmp.name,config={"url":"https://unit.invalid","key":"x"*32})
        return c
    def test_cloud_rpc_returns_active_record_and_remembers_link(self):
        c=self._cloud_client()
        requests=[]
        def fake_request(method,path,**kw):
            requests.append((method,path,kw))
            return {"id":"linked123","campaign_id":"camp1","active":True}
        c._request_json=fake_request
        response=c.link_character('camp1',{"kind":"character_state","character_id":"char1","name":"Aurora"},creation_claim={"active":True})
        self.assertEqual(response['id'],'linked123')
        self.assertEqual(requests[0][1],'/rest/v1/rpc/did_admit_compliant_character')
        self.assertEqual(requests[0][2]['body']['p_creation'],{'active':True})
        self.assertEqual(c.get_character_link('char1')['campaign_character_id'],'linked123')
    def test_missing_creation_proof_rejected_before_network(self):
        c=self._cloud_client();c._request_json=Mock(side_effect=AssertionError('should not connect'))
        with self.assertRaises(Exception):
            c.link_character('camp1',{'character_id':'char1','name':'Aurora'})
        c._request_json.assert_not_called()
    def test_server_failure_does_not_write_local_link(self):
        c=self._cloud_client();c._request_json=Mock(side_effect=RuntimeError('approval required'))
        with self.assertRaisesRegex(RuntimeError,'approval required'):
            c.link_character('camp1',{'character_id':'char1','name':'Aurora'},creation_claim={'active':True})
        self.assertIsNone(c.get_character_link('char1'))
    def test_server_admission_sql_is_guarded(self):
        sql=SQL.read_text('utf8')
        for name in ('private.did_is_campaign_member','campaign_character_approval_requests',
                     'campaign_record.character_template','private.did_sorted_text_array',
                     'CREATE OR REPLACE FUNCTION public.did_admit_compliant_character',
                     'REVOKE INSERT,UPDATE ON public.campaign_characters','actor uuid := auth.uid()'):
            self.assertIn(name,sql)
        self.assertIn("ar.status IN ('pending','rejected','approved')",sql)
        self.assertNotIn('cc.campaign_id = cc.campaign_id',sql)

if __name__=='__main__':unittest.main()
