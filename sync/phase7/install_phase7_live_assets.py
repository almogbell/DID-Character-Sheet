from __future__ import annotations

import py_compile
import shutil
from pathlib import Path


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
        if (root / "frontend_2_8.py").is_file():
            return root
    raise FileNotFoundError("Could not find the DID project root.")


def copy_if_changed(source: Path, target: Path):
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and target.read_bytes() == source.read_bytes():
        return False
    shutil.copy2(source, target)
    return True


def main():
    support = Path(__file__).resolve().parent
    root = find_project_root()

    required = (
        support / "party_dashboard" / "live.js",
        support / "campaign_supabase_phase7_live.sql",
        support / "phase7_party_smoke_test.py",
    )
    missing = [str(path.name) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError("Missing Phase 7 live files: " + ", ".join(missing))

    changed = []
    if copy_if_changed(support / "party_dashboard" / "live.js", root / "party_dashboard" / "live.js"):
        changed.append("party_dashboard/live.js")
    if copy_if_changed(support / "campaign_supabase_phase7_live.sql", root / "campaign_supabase_phase7_live.sql"):
        changed.append("campaign_supabase_phase7_live.sql")
    if copy_if_changed(support / "phase7_party_smoke_test.py", root / "phase7_party_smoke_test.py"):
        changed.append("phase7_party_smoke_test.py")

    py_compile.compile(str(root / "phase7_party_smoke_test.py"), doraise=True)

    print("Party Dashboard live session client: PASS")
    print("Party Dashboard shared-roll SQL migration: PASS")
    print("Phase 7 end-to-end smoke test: PASS")
    print("Live assets copied: " + (", ".join(changed) if changed else "already installed"))


if __name__ == "__main__":
    main()
