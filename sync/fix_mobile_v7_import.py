from pathlib import Path

p = Path(__file__).resolve().parents[1] / "windows" / "mobile_sync_frontend_adapter.py"
text = p.read_text(encoding="utf-8")
old = "        from mobile_sync_v7 import handle_mobile_v7_action\n        v7 = handle_mobile_v7_action(self, action, payload)"
new = "        try:\n            from .mobile_sync_v7 import handle_mobile_v7_action\n        except ImportError:\n            from mobile_sync_v7 import handle_mobile_v7_action\n        v7 = handle_mobile_v7_action(self, action, payload)"
if text.count(old) != 1:
    raise SystemExit(f"Expected one V7 import block, found {text.count(old)}")
p.write_text(text.replace(old, new, 1), encoding="utf-8")
print("Made mobile_sync_v7 import package-safe")
