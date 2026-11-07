"""Check required campaign modules without replacing them with unsafe stubs."""
from pathlib import Path
import sys
root = Path(__file__).resolve().parents[1]
required = [
    "campaign_shared", "campaign_runtime", "campaign_ui",
    "campaign_role_ui", "campaign_dashboard_bridge",
    "campaign_creation_wizard", "campaign_privacy", "campaign_party",
]
missing = [name for name in required if not (root / (name + ".py")).is_file()]
if missing:
    print("BLOCKED: campaign integration files missing:")
    for name in missing:
        print(" -", name + ".py")
    print("Restore these from the matching 1.0.11 campaign build; do not use empty stubs.")
    sys.exit(2)
print("PASS: campaign module files present")
