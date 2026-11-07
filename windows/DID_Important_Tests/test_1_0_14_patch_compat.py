"""1.0.14 regression tests for layout-independent hook loading."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('did114_patcher', ROOT / 'apply_did_1_0_14.py')
PATCH = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PATCH)

JS = '''const app = (() => {
  async function loadCurrentCampaign() {
    renderParty();
    await loadVisibleNPCs();
    subscribeRealtime();
  }
  async function loadVisibleNPCs() { return true; }
  function subscribeRealtime() {
    channel = client.channel("test")
      .on("postgres_changes", {table:"party_character_state"}, function() {})
      .subscribe(status => {});
  }
})();
'''

class CampaignPatchCompatibilityTests(unittest.TestCase):
    def test_original_refresh_layout(self):
        updated = PATCH.patch_party_js(JS)
        self.assertIn('await loadVisibleEntries();', updated)
        self.assertIn('function loadVisibleEntries()', updated)
        self.assertIn('table: "campaign_entries"', updated)

    def test_rearranged_npc_loading(self):
        source = JS.replace('await loadVisibleNPCs();',
                            'await Promise.all([loadVisibleNPCs(), loadSessionRolls()]);')
        updated = PATCH.patch_party_js(source)
        self.assertIn('await loadVisibleEntries();', updated)
        self.assertIn('await Promise.all', updated)

    def test_no_npc_loader_call(self):
        source = JS.replace('    await loadVisibleNPCs();\n', '')
        updated = PATCH.patch_party_js(source)
        self.assertIn('renderParty();\n    await loadVisibleEntries();', updated)

    def test_reordered_subscription(self):
        source = JS.replace('.on("postgres_changes", {table:"party_character_state"}, function() {})',
                            '.on(\'postgres_changes\', {event:"*",table:"party_character_state"}, () => {})')
        updated = PATCH.patch_party_js(source)
        self.assertIn('table: "campaign_entries"', updated)

    def test_sync_refresh_uses_promise_not_await(self):
        source = JS.replace('async function loadCurrentCampaign()', 'function loadCurrentCampaign()')
        source = source.replace('await loadVisibleNPCs();', 'loadVisibleNPCs();')
        updated = PATCH.patch_party_js(source)
        self.assertIn('loadVisibleEntries().catch', updated)
        self.assertNotIn('await loadVisibleEntries();', updated)

    def test_arrow_realtime_subscription_supported(self):
        source = JS.replace('function subscribeRealtime() {', 'const subscribeRealtime = () => {')
        updated = PATCH.patch_party_js(source)
        self.assertIn('function loadVisibleEntries()', updated)
        self.assertIn('table: "campaign_entries"', updated)

    def test_rerun_no_duplicate_hooks_or_subscription(self):
        once = PATCH.patch_party_js(JS)
        twice = PATCH.patch_party_js(once)
        self.assertEqual(once, twice)
        self.assertEqual(once.count('function loadVisibleEntries()'), 1)
        self.assertEqual(once.count('table: "campaign_entries"'), 1)

    def test_unfamiliar_refresh_stops_instead_of_guessing(self):
        source = JS.replace('    renderParty();\n', '').replace('    await loadVisibleNPCs();\n', '')
        source = source.replace('    subscribeRealtime();\n','')
        with self.assertRaisesRegex(RuntimeError, 'cannot locate a safe refresh'):
            PATCH.patch_party_js(source)

    def test_html_with_different_attribute_order(self):
        html = '<main>\n  <div class="summary-text" id="partySummary"></div>\n</main>'
        changed = PATCH.patch_party_html(html)
        self.assertIn('visibleEntryGrid', changed)
        self.assertLess(changed.index('visibleEntryGrid'),changed.index('partySummary'))
        self.assertEqual(PATCH.patch_party_html(changed), changed)

    def test_html_uses_party_grid_when_summary_absent(self):
        html = '<main>\n  <section id="partyGrid"></section>\n</main>'
        changed = PATCH.patch_party_html(html)
        self.assertIn('visibleEntryGrid', changed)

    def test_html_missing_targets_stops(self):
        with self.assertRaisesRegex(RuntimeError, 'cannot find a unique'):
            PATCH.patch_party_html('<main></main>')

if __name__ == '__main__': unittest.main()
