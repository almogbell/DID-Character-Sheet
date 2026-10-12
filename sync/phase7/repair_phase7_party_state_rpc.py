from __future__ import annotations

import py_compile
from pathlib import Path


OLD = '''def upload_party_state(client, campaign_id, campaign_character_id, state):\n    rows = client._request_json(\n        "POST",\n        "/rest/v1/party_character_state",\n        query={\n            "on_conflict": "campaign_character_id",\n            "select": "campaign_character_id,campaign_id,updated_at",\n        },\n        body={\n            "campaign_character_id": str(campaign_character_id),\n            "campaign_id": str(campaign_id),\n            "state": state,\n        },\n        prefer="resolution=merge-duplicates,return=representation",\n    )\n    return rows[0] if isinstance(rows, list) and rows else None\n'''

NEW = '''def upload_party_state(client, campaign_id, campaign_character_id, state):\n    # Use the owner-checked RPC instead of a direct PostgREST table upsert.\n    # PostgREST merge-duplicates can require UPDATE privileges on conflict/key\n    # columns as well as state, which produced table-level 403 errors before\n    # RLS was even evaluated. The RPC performs the same ownership checks in\n    # one controlled SECURITY DEFINER operation.\n    rows = client._request_json(\n        "POST",\n        "/rest/v1/rpc/did_upsert_party_character_state",\n        body={\n            "p_campaign_id": str(campaign_id),\n            "p_campaign_character_id": str(campaign_character_id),\n            "p_state": state,\n        },\n    )\n    return rows[0] if isinstance(rows, list) and rows else None\n'''


def find_project_root():
    candidates = [Path.cwd(), Path(__file__).resolve().parent]
    for candidate in list(candidates):
        candidates.extend(candidate.parents[:4])
    seen = set()
    for root in candidates:
        root = root.resolve()
        if root in seen:
            continue
        seen.add(root)
        if (root / "frontend_2_8.py").is_file() and (root / "campaign_party.py").is_file():
            return root
    raise FileNotFoundError("Could not find the installed DID project root")


def main():
    root = find_project_root()
    path = root / "campaign_party.py"
    text = path.read_text(encoding="utf-8")

    if '/rest/v1/rpc/did_upsert_party_character_state' in text:
        changed = False
    else:
        if OLD not in text:
            raise RuntimeError("Could not safely locate upload_party_state in campaign_party.py")
        text = text.replace(OLD, NEW, 1)
        path.write_text(text, encoding="utf-8")
        changed = True

    py_compile.compile(str(path), doraise=True)
    print("Party state RPC client: " + ("PASS" if changed else "already installed"))
    print("campaign_party.py compile: PASS")


if __name__ == "__main__":
    main()
