"""Problem 14 dashboard launch and UI regression guards (no PySide6/network required)."""
import pathlib
import shutil
import subprocess
import sys
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import campaign_party_bridge

class Problem14DashboardTests(unittest.TestCase):
    def test_party_launches_independent_loopback_port_each_time(self):
        with patch.object(campaign_party_bridge, 'prepare_party_dashboard_config'), \
             patch.object(campaign_party_bridge, 'prepare_dashboard_dir', return_value=ROOT / 'party_dashboard'), \
             patch.object(campaign_party_bridge, 'config_root', return_value=ROOT), \
             patch.object(campaign_party_bridge.subprocess, 'Popen') as popen:
            urls = [campaign_party_bridge.launch_party_dashboard_server('SECRET', ROOT) for _ in range(2)]
            self.assertNotEqual(urls[0], urls[1])
            for call, url in zip(popen.call_args_list, urls):
                cmd = call.args[0]
                self.assertIn('--port', cmd)
                port = int(cmd[cmd.index('--port') + 1])
                self.assertIn(f'127.0.0.1:{port}', url)
                self.assertNotIn('--reuse-existing', cmd)
                self.assertIn('#code=SECRET', url)
                self.assertEqual(call.kwargs['cwd'], str(ROOT))

    def test_dashboard_bridge_requests_scoped_access_tokens(self):
        for name in ('campaign_dashboard_bridge.py', 'campaign_party_bridge.py'):
            text = (ROOT / name).read_text(encoding='utf-8')
            self.assertIn('p_campaign_id', text)
            self.assertIn('dashboard_code', text)

    def test_stale_async_updates_guarded_in_both_dashboards(self):
        for name in ('dm_dashboard', 'party_dashboard'):
            src = (ROOT / name / 'app.js').read_text(encoding='utf-8')
            self.assertIn('const serial = ++campaignLoadSerial;', src)
            self.assertIn('serial !== campaignLoadSerial', src)
            self.assertIn('displayedCampaignId !==', src)
            self.assertIn('subscriptionCampaignId !== currentCampaignId', src)
            self.assertIn('if (els.dialog.open) els.dialog.close();', src)
            if shutil.which('node'):
                completed = subprocess.run(['node', '--check', str(ROOT / name / 'app.js')], capture_output=True, text=True)
                self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_dm_scopes_session_and_uses_local_result_before_commit(self):
        src = (ROOT / 'dm_dashboard/app.js').read_text(encoding='utf-8')
        self.assertIn('const nextSession = await loadSessionState(campaignId);', src)
        self.assertIn('activeSession = nextSession;', src)
        self.assertIn('const nextCharacters = characterResponse.data || [];', src)
        self.assertIn('characters = nextCharacters;', src)

    def test_party_npc_scoped_to_requested_campaign(self):
        src = (ROOT / 'party_dashboard/app.js').read_text(encoding='utf-8')
        self.assertIn('await loadVisibleNPCs(requestedCampaignId, serial);', src)
        self.assertIn('if (serial !== campaignLoadSerial || campaignId !== currentCampaignId) return;', src)

    def test_release_bundle_still_includes_both_dashboards(self):
        spec = (ROOT / 'DID_Character_Sheet.spec').read_text(encoding='utf-8')
        self.assertIn("('dm_dashboard', 'dm_dashboard')", spec)
        self.assertIn("('party_dashboard', 'party_dashboard')", spec)
        self.assertIn('dashboard_server', spec)

if __name__ == '__main__':
    unittest.main()
