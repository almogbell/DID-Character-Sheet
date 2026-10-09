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


def replace_once_if_needed(text, old, new, label):
    if new in text:
        return text
    count = text.count(old)
    if count != 1:
        raise RuntimeError(
            f"Could not safely finalize {label}: expected one matching block, found {count}."
        )
    return text.replace(old, new, 1)


def main():
    support_dir = Path(__file__).resolve().parent
    patcher = support_dir / "apply_phase5_patch.py"
    if not patcher.is_file():
        raise FileNotFoundError("apply_phase5_patch.py is missing")

    # Run the normal installer first.
    runpy.run_path(str(patcher), run_name="__main__")

    root = find_project_root(__file__)

    # Finalize the player roll-sharing control refresh.
    campaign_ui = root / "campaign_ui.py"
    text = campaign_ui.read_text(encoding="utf-8")
    needle = "        self.unlink_btn.setEnabled(bool(restore_campaign_connection(self.window)))\n"
    replacement = needle + "        self._refresh_roll_share_checkbox()\n"
    text = replace_once_if_needed(
        text,
        needle,
        replacement,
        "the session roll-sharing control",
    )
    campaign_ui.write_text(text, encoding="utf-8")
    py_compile.compile(str(campaign_ui), doraise=True)

    # The dashboard uses a sentinel for the explicit campaign-wide roll view.
    # An empty value means "choose the active/latest session automatically".
    app_js = root / "dm_dashboard" / "app.js"
    js = app_js.read_text(encoding="utf-8")
    replacements = (
        (
            '    if (!validSelected) {\n',
            '    if (selectedSessionId !== "all" && !validSelected) {\n',
            "campaign-wide session selection",
        ),
        (
            '    if (!selectedSessionId) return;\n',
            '    if (!selectedSessionId || selectedSessionId === "all") return;\n',
            "campaign-wide snapshot selection",
        ),
        (
            '    campaignWide.value = "";\n',
            '    campaignWide.value = "all";\n',
            "campaign-wide selector value",
        ),
        (
            '    campaignWide.selected = !selectedSessionId;\n',
            '    campaignWide.selected = selectedSessionId === "all";\n',
            "campaign-wide selector state",
        ),
        (
            '      if (selectedSessionId) {\n        rollQuery = rollQuery.eq("session_id", selectedSessionId);\n      }\n',
            '      if (selectedSessionId && selectedSessionId !== "all") {\n        rollQuery = rollQuery.eq("session_id", selectedSessionId);\n      }\n',
            "campaign-wide roll query",
        ),
        (
            '      els.rollList.innerHTML = selectedSessionId\n',
            '      els.rollList.innerHTML = (selectedSessionId && selectedSessionId !== "all")\n',
            "campaign-wide empty-roll message",
        ),
    )
    for old, new, label in replacements:
        js = replace_once_if_needed(js, old, new, label)
    app_js.write_text(js, encoding="utf-8")

    print("Phase 5 UI finalization: PASS")


if __name__ == "__main__":
    main()
