"""Regression tests for durable, lossless roll recording and retry."""
import ast
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT))
from campaign_roll_outbox import DurableRollOutbox, RollOutboxError


class OutboxTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)

    def event(self, number):
        return {"event_id": f"roll-{number}", "character_id": "character-A", "sum": number}

    def test_survives_restart_with_all_rolls_even_after_200(self):
        outbox = DurableRollOutbox(self.folder)
        for index in range(230):
            self.assertTrue(outbox.enqueue(self.event(index)))
        self.assertEqual(len(DurableRollOutbox(self.folder)), 230)
        self.assertEqual(outbox.peek()["event_id"], "roll-0")

    def test_idempotent_enqueue_and_acknowledge(self):
        outbox = DurableRollOutbox(self.folder)
        self.assertTrue(outbox.enqueue(self.event(1)))
        self.assertFalse(outbox.enqueue(self.event(1)))
        self.assertEqual(len(outbox), 1)
        self.assertTrue(outbox.acknowledge("roll-1"))
        self.assertFalse(outbox.acknowledge("roll-1"))
        self.assertEqual(len(DurableRollOutbox(self.folder)), 0)

    def test_save_failure_leaves_existing_events_intact(self):
        outbox = DurableRollOutbox(self.folder)
        outbox.enqueue(self.event(1))
        with patch("campaign_roll_outbox.os.replace", side_effect=OSError("drive full")):
            with self.assertRaises(RollOutboxError):
                outbox.enqueue(self.event(2))
        self.assertEqual(len(outbox), 1)
        self.assertEqual(len(DurableRollOutbox(self.folder)), 1)

    def test_corrupt_file_is_preserved_not_overwritten(self):
        path = self.folder / "campaign_roll_outbox.json"
        path.write_text("{partial JSON", encoding="utf-8")
        with self.assertRaisesRegex(RollOutboxError, "preserved"):
            DurableRollOutbox(self.folder)
        self.assertEqual(path.read_text(), "{partial JSON")

    def test_worker_only_acknowledges_after_successful_upload(self):
        source = (ROOT / "campaign_runtime.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                  and n.name == "_flush_pending_rolls_worker")
        code = compile(ast.fix_missing_locations(ast.Module(body=[fn], type_ignores=[])),
                       str(ROOT / "campaign_runtime.py"), "exec")
        class CloudError(Exception):
            pass
        namespace = {"CampaignCloudError": CloudError}
        exec(code, namespace)
        outbox = DurableRollOutbox(self.folder)
        outbox.enqueue(self.event(1))
        outbox.enqueue(self.event(2))
        class Client:
            calls = []
            fail = True
            def upload_linked_roll_event(self, event):
                self.calls.append(event["event_id"])
                if self.fail:
                    raise CloudError("offline")
        client = Client()
        window = SimpleNamespace(_campaign_roll_outbox=outbox,
                                 _campaign_sync_status="", _campaign_runtime_error="")
        namespace["_flush_pending_rolls_worker"](window, client)
        self.assertEqual(window._campaign_sync_status, "Offline")
        self.assertEqual(len(DurableRollOutbox(self.folder)), 2)
        client.fail = False
        namespace["_flush_pending_rolls_worker"](window, client)
        self.assertEqual(len(DurableRollOutbox(self.folder)), 0)
        self.assertEqual(client.calls, ["roll-1", "roll-1", "roll-2"])


if __name__ == "__main__":
    unittest.main()
