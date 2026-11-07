import unittest
from pathlib import Path
import os
ROOT=Path(os.environ.get('DID_ANDROID_PROJECT',str(Path.home()/'Desktop'/'DIDAndroid')))
class AndroidContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store=(ROOT/'phase8'/'DidOfflineStore.kt').read_text(encoding='utf-8')
        cls.vm=(ROOT/'phase8'/'DidCompanionViewModel.kt').read_text(encoding='utf-8')
        cls.screen=(ROOT/'phase8'/'Phase9CompanionSheetV8.kt').read_text(encoding='utf-8')
    def test_earlier_synced_version_stored(self):
        self.assertIn('synced_character',self.store)
        self.assertIn('base_character',self.store)
    def test_hp_at_only_choice(self):
        self.assertIn('requeueResourceDecision(conflict.characterId, "pc")',self.vm)
        self.assertIn('requeueResourceDecision(conflict.characterId, "phone")',self.vm)
        self.assertIn('hp_at_choice',self.vm)
    def test_upsert_retries_after_revision_race(self):
        self.assertIn('code == "STALE_REVISION" && rejectedAction == "character.upsert_snapshot"',self.vm)
    def test_buttons_are_resource_specific(self):
        self.assertIn('Windows HP/AT',self.screen)
        self.assertIn('Phone HP/AT',self.screen)
if __name__=='__main__':unittest.main()
