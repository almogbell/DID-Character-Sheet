from __future__ import annotations

import py_compile
import runpy
from pathlib import Path


def find_project_root(start):
    candidates = [Path.cwd(), Path(start).resolve().parent]
    for candidate in list(candidates):
        candidates.extend(candidate.parents[:4])
    seen = set()
    for root in candidates:
        root = root.resolve()
        if root in seen:
            continue
        seen.add(root)
        if (root / "frontend_2_8.py").is_file() and (root / "campaign_ui.py").is_file():
            return root
    raise FileNotFoundError("Could not find the DID project folder.")


def main():
    support_dir = Path(__file__).resolve().parent
    patcher = support_dir / "apply_phase5_patch.py"
    if not patcher.is_file():
        raise FileNotFoundError("apply_phase5_patch.py is missing")

    # Run the normal installer first.
    runpy.run_path(str(patcher), run_name="__main__")

    # Finalize the roll-sharing control refresh. This tiny second pass is kept
    # deliberately explicit so re-running the installer remains idempotent.
    root = find_project_root(__file__)
    campaign_ui = root / "campaign_ui.py"
    text = campaign_ui.read_text(encoding="utf-8")

    needle = "        self.unlink_btn.setEnabled(bool(restore_campaign_connection(self.window)))\n"
    replacement = needle + "        self._refresh_roll_share_checkbox()\n"

    if replacement not in text:
        count = text.count(needle)
        if count != 1:
            raise RuntimeError(
                "Could not safely finalize the session roll-sharing control: "
                f"expected one button-state block, found {count}."
            )
        text = text.replace(needle, replacement, 1)
        campaign_ui.write_text(text, encoding="utf-8")

    py_compile.compile(str(campaign_ui), doraise=True)
    print("Phase 5 UI finalization: PASS")


if __name__ == "__main__":
    main()
