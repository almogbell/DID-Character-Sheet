import importlib.util
import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('campaign_player_reveals', ROOT / 'campaign_player_reveals.py')
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class FakeClient:
    def __init__(self):
        self.queries = []

    def _request_json(self, method, path, *, query):
        self.queries.append((method, path, query))
        if path.endswith('campaign_entries'):
            return [{'entry_type': 'hook', 'title': 'Road', 'body': 'Find the gate', 'status': 'active'}]
        if path.endswith('campaign_character_effects'):
            return [{'name': 'Blessed', 'description': 'Gain hope', 'status': 'active'}]
        raise AssertionError('Unexpected path')


class CampaignRevealTests(unittest.TestCase):
    def test_hooks_visible_for_campaign_member_even_when_character_unlinked(self):
        client = FakeClient()
        entries, effects = module.load_player_reveals(client, 'camp-1', None)
        self.assertEqual(len(entries), 1)
        self.assertFalse(effects)
        self.assertEqual(len(client.queries), 1)
        self.assertEqual(client.queries[0][2]['visible_to_players'], 'eq.true')

    def test_private_effects_only_for_affected_character(self):
        client = FakeClient()
        entries, effects = module.load_player_reveals(client, 'camp-1', 'char-2')
        self.assertEqual(len(entries), 1)
        self.assertEqual(len(effects), 1)
        query = client.queries[1][2]
        self.assertEqual(query['campaign_character_id'], 'eq.char-2')
        self.assertEqual(query['visible_to_player'], 'eq.true')
        self.assertEqual(query['campaign_id'], 'eq.camp-1')

    def test_unlinked_character_sees_safe_explanation(self):
        self.assertIn('Link your character', module.format_effects([], False))

    def test_effects_and_hooks_display_content(self):
        entries = [{'entry_type':'quest','title':'Towers','body':'Visit both towers','status':'open'}]
        self.assertIn('Towers', module.format_entries(entries))
        self.assertIn('Visit both towers', module.format_entries(entries))
        self.assertIn('Blessed', module.format_effects([{'name':'Blessed'}], True))

    def test_no_links_or_public_access_override(self):
        source = (ROOT / 'campaign_player_reveals.py').read_text('utf8')
        self.assertNotIn('service_role', source)
        self.assertNotIn('authenticated=False', source)
        self.assertIn("'visible_to_player': 'eq.true'", source)

    def test_party_dashboard_shows_shared_hooks_not_private_effects(self):
        js = (ROOT / 'party_dashboard' / 'app.js').read_text('utf8')
        html = (ROOT / 'party_dashboard' / 'index.html').read_text('utf8')
        self.assertIn('function loadVisibleEntries()', js)
        self.assertIn('.eq("visible_to_players", true)', js)
        self.assertIn('visibleEntrySection', html)
        self.assertNotIn('campaign_character_effects', js)

    def test_version_and_installer_identity(self):
        frontend = (ROOT / 'frontend_2_8.py').read_text('utf8')
        iss = (ROOT / 'DID_Character_Sheet_Installer_with_icon.iss').read_text('utf8')
        self.assertIn('APP_VERSION = "1.0.14"', frontend)
        self.assertIn('#define MyAppVersion "1.0.14"', iss)
        self.assertIn('AppId={{0DCE3792-7789-4AE5-B5A7-18AB2A512928}', iss)

    def test_tab_strip_and_dashboard_packaged(self):
        ui = (ROOT / 'campaign_role_ui.py').read_text('utf8')
        spec = (ROOT / 'DID_Character_Sheet.spec').read_text('utf8')
        # 1.0.14 follow-up: fixed 280px host clipped the campaign labels.
        self.assertNotIn('tabs_host.setFixedWidth(280)', ui)
        self.assertIn('def _resize_campaign_tabs(self):', ui)
        self.assertIn('self._resize_campaign_tabs()', ui)
        self.assertIn('toolbar.insertWidget(0, tabs_host)', ui)
        self.assertIn('self._refresh_player_reveals()', ui)
        self.assertRegex(spec, r"\(['\"]party_dashboard['\"],\s*['\"]party_dashboard['\"]\)")


if __name__ == '__main__':
    unittest.main()
