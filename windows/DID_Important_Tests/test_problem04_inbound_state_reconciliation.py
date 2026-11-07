"""Problem 4: source-contract regression checks for Windows -> Pocket DID.

These run without an Android SDK. They are not substitutes for a device test.
Works when the Windows project and DIDAndroid are sibling directories.
"""
import os
import re
import unittest
from pathlib import Path


HERE = Path(__file__).resolve()
WINDOWS_ROOT = HERE.parents[1]


def android_root():
    override = os.environ.get('DID_ANDROID_ROOT', '').strip()
    if override:
        target = Path(override).expanduser()
        if target.is_file():
            raise FileNotFoundError(f'DID_ANDROID_ROOT must be a directory: {target}')
        return target
    candidates = [
        WINDOWS_ROOT.parent / 'DIDAndroid',
        WINDOWS_ROOT / 'DIDAndroid',
        WINDOWS_ROOT.parent / 'DIDAndroid (2)',
    ]
    for candidate in candidates:
        if (candidate / 'phase8' / 'DidCompanionViewModel.kt').is_file():
            return candidate
    raise FileNotFoundError(
        'Could not locate DIDAndroid/phase8. Install the Android patch in the '
        'sibling DIDAndroid project, or set DID_ANDROID_ROOT to its full path. '
        'Checked: ' + ', '.join(map(str, candidates))
    )


class InboundStateContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = android_root()
        cls.vm = (root / 'phase8' / 'DidCompanionViewModel.kt').read_text(encoding='utf-8')
        cls.v8 = (root / 'phase8' / 'Phase9CompanionSheetV8.kt').read_text(encoding='utf-8')

    def test_optimistic_resource_cache_reconciles_hp_while_command_pending(self):
        self.assertRegex(
            self.v8,
            r'LaunchedEffect\(snapshot\.hp\.current, pending\)\s*\{\s*shownHp\s*=\s*snapshot\.hp\.current\s*\}',
        )
        self.assertNotRegex(self.v8, r'if\s*\(!pending\)\s*shownHp')

    def test_optimistic_resource_cache_reconciles_at_while_command_pending(self):
        self.assertRegex(
            self.v8,
            r'LaunchedEffect\(snapshot\.adversity\.current, pending\)\s*\{\s*shownAt\s*=\s*snapshot\.adversity\.current\s*\}',
        )
        self.assertNotRegex(self.v8, r'if\s*\(!pending\)\s*shownAt')

    def test_connection_status_discards_old_ui_pending_ids(self):
        part = self.vm.split('override fun onConnectionState(state:', 1)[1].split('private fun syncPcCharacterLibrary', 1)[0]
        self.assertIn('recoverUnacknowledgedCommand()', part)
        self.assertIn('pendingRequestIds = emptySet()', part)

    def test_connection_requests_canonical_state(self):
        part = self.vm.split('override fun onConnectionState(state:', 1)[1].split('private fun syncPcCharacterLibrary', 1)[0]
        self.assertIn('syncClient.requestFreshState()', part)

    def test_inbound_state_is_applied_to_snapshot(self):
        part = self.vm.split('override fun onCharacterState(revision:', 1)[1].split('override fun onCommandAccepted(', 1)[0]
        self.assertIn('DidCharacterSnapshot.fromJson(displayedCharacter)', part)
        self.assertIn('snapshot = parsedSnapshot ?: current.snapshot', part)

    def test_working_granular_outbound_path_is_preserved(self):
        self.assertIn('shouldSendLiveMutation(', self.vm)
        self.assertIn('offlineStore.enqueuePending(\n                        characterId, action, commandPayload,', self.vm)
        self.assertIn('syncClient.sendCommand(command.action, command.payload)', self.vm)


if __name__ == '__main__':
    unittest.main(verbosity=2)
