"""Source-contract regressions for the live-edit path. Requires no Android SDK.

Run: python -m unittest discover -s DID_Important_Tests -p test_problem04_phone_to_windows_sync.py -v
"""
from __future__ import annotations
import os
import pathlib
import re
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
VM_NAME = "DidCompanionViewModel.kt"
ENV_VAR = "DID_ANDROID_PROJECT"


def locate_android_viewmodel(windows_project=ROOT, android_project=None):
    """Locate the V8 Android source, even when these are two sibling projects.

    ``DID_ANDROID_PROJECT`` can point to the Android project root, its phase8
    directory, or directly to the Kotlin file. An explicit override is never
    silently ignored, because a wrong target would make these tests misleading.
    """
    windows_project = pathlib.Path(windows_project)
    override = android_project if android_project is not None else os.environ.get(ENV_VAR)
    if override:
        base = pathlib.Path(override).expanduser()
        candidates = [base, base / VM_NAME, base / "phase8" / VM_NAME]
        candidates = [p for p in candidates if p.name == VM_NAME]
    else:
        candidates = [
            windows_project / "phase8" / VM_NAME,                    # tests installed in Android
            windows_project.parent / "DIDAndroid" / "phase8" / VM_NAME, # sibling projects on Desktop
            windows_project / "DIDAndroid" / "phase8" / VM_NAME,     # combined checkout
        ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    searched = "\n  - ".join(str(p) for p in candidates)
    raise FileNotFoundError(
        f"Cannot find {VM_NAME}. Checked:\n  - {searched}\n"
        f"The Android project should be next to the Windows project as 'DIDAndroid', "
        f"or set {ENV_VAR} to its actual directory in PowerShell:\n"
        f"  $env:{ENV_VAR} = 'C:\\Users\\almog\\Desktop\\DIDAndroid'\n"
        "This is a test source-location issue, not evidence of a phone-sync failure."
    )


class AndroidSourceLocationTests(unittest.TestCase):
    def test_sibling_android_project(self):
        with tempfile.TemporaryDirectory() as folder:
            base = pathlib.Path(folder)
            vm = base / "DIDAndroid" / "phase8" / VM_NAME
            vm.parent.mkdir(parents=True)
            vm.write_text("test")
            self.assertEqual(locate_android_viewmodel(base / "current code", android_project=""), vm)

    def test_source_inside_project(self):
        with tempfile.TemporaryDirectory() as folder:
            base = pathlib.Path(folder)
            vm = base / "phase8" / VM_NAME
            vm.parent.mkdir(parents=True)
            vm.write_text("test")
            self.assertEqual(locate_android_viewmodel(base, android_project=""), vm)

    def test_explicit_project_override(self):
        with tempfile.TemporaryDirectory() as folder:
            base = pathlib.Path(folder)
            vm = base / "nonstandard" / "phase8" / VM_NAME
            vm.parent.mkdir(parents=True)
            vm.write_text("test")
            self.assertEqual(locate_android_viewmodel(base / "windows", android_project=base / "nonstandard"), vm)

    def test_missing_source_has_actionable_diagnostic(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(FileNotFoundError, r"DID_ANDROID_PROJECT"):
                locate_android_viewmodel(pathlib.Path(folder) / "current code", android_project="")


class PhoneToWindowsLiveSyncTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = locate_android_viewmodel().read_text(encoding="utf-8")

    def test_resource_edit_is_snapshot_state_action(self):
        self.assertRegex(self.source, r'SNAPSHOT_STATE_ACTIONS\s*=\s*setOf\([\s\S]*?"resource.set"')

    def test_live_edit_uses_granular_command(self):
        segment = self.source.split('if (action in SNAPSHOT_STATE_ACTIONS)', 1)[1].split('if (!sameCharacterAsPc', 1)[0]
        self.assertIn('shouldSendLiveMutation(', segment)
        self.assertRegex(segment, r'if \(sendLiveMutation\) \{[\s\S]*?enqueuePending\(\s*characterId, action, commandPayload')
        self.assertIn('commandQueue.addLast(', segment)
        self.assertIn('sendNextIfPossible()', segment)

    def test_offline_and_conflicts_keep_snapshots(self):
        segment = self.source.split('if (action in SNAPSHOT_STATE_ACTIONS)', 1)[1].split('if (!sameCharacterAsPc', 1)[0]
        self.assertIn('offlineStore.queueSnapshotSync(', segment)
        self.assertIn('preservePendingId = inFlightPendingId', segment)
        self.assertIn('hasPendingSnapshot = existingSnapshot', segment)
        self.assertIn('hasSyncConflict = characterId in conflictedCharacters', segment)

    def test_no_desktop_character_disables_granular_route(self):
        self.assertIn('if (character == null) {\n            liveCharacterId = null', self.source)
        self.assertIn('if (character.optBoolean("_mobile_library_only", false)) {\n            liveCharacterId = null', self.source)

    def test_reconnect_releases_stuck_inflight_request_without_losing_edit(self):
        source = self.source
        segment = source.split('private fun recoverUnacknowledgedCommand()', 1)[1].split('override fun onConnectionState', 1)[0]
        self.assertIn('offlineStore.queueSnapshotSync(interrupted.characterId)', segment)
        self.assertIn('inFlightRequestId = null', segment)
        self.assertIn('inFlightPendingId = null', segment)
        self.assertIn('inFlightAction = null', segment)
        self.assertNotIn('offlineStore.removePending(interrupted.id)', segment.split('else if (interrupted?.action == "dice.roll")')[0])
        self.assertIn('recoverUnacknowledgedCommand()', source.split('override fun onConnectionState', 1)[1])

    def test_no_pairing_changes(self):
        self.assertNotIn('Windows LAN address for QR', self.source)
        self.assertNotIn('PAIRING_LANDING_URL', self.source)


if __name__ == '__main__':
    unittest.main()
