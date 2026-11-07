"""Guard against the exact repeat-STOP from DID114_Debug.zip."""
import importlib.util
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('did114patch',ROOT/'patch_did114_sharing_refresh.py')
mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)

class ActualSourceCompatibility(unittest.TestCase):
    def test_party_scoped_request_does_not_require_obsolete_lines(self):
        s=(ROOT/'party_dashboard'/'app.js').read_text(encoding='utf-8-sig')
        self.assertIn('const requestedCampaignId = currentCampaignId;',s)
        self.assertIn('const serial = ++campaignLoadSerial;',s)
        self.assertIn('serial !== campaignLoadSerial',s)
        self.assertIn('subscribedCampaignId === currentCampaignId',s)
        self.assertEqual(s,mod.patch_js(s,dashboard='party'))

    def test_no_duplicate_counters(self):
        for dashboard in ('party_dashboard','dm_dashboard'):
            s=(ROOT/dashboard/'app.js').read_text(encoding='utf-8-sig')
            self.assertEqual(1,s.count('let campaignLoadSerial = 0;'))
            self.assertEqual(1,s.count('let subscribedCampaignId = "";'))

if __name__=='__main__':unittest.main()
