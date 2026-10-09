from __future__ import annotations

import py_compile
import shutil
import subprocess
import sys
from pathlib import Path


IMPORT_NEEDLE = "from improvement_editor import open_improvement_editor\nfrom uuid import uuid4\n"
IMPORT_REPLACEMENT = (
    "from improvement_editor import open_improvement_editor\n"
    "from uuid import uuid4\n"
    "from campaign_shared import build_shared_character_state, build_shared_roll_event\n"
)

INIT_NEEDLE = "        self._dice_final_rect = QRect()\n        self._dice_move_animation = None\n"
INIT_REPLACEMENT = (
    INIT_NEEDLE
    + "\n"
    + "        # Phase 1 campaign sharing: structured roll events stay in memory\n"
    + "        # until a later Supabase transport layer consumes them.\n"
    + "        self._shared_roll_events = deque(maxlen=200)\n"
    + "        self._shared_roll_event_callback = None\n"
)

METHOD_MARKER = "    def reconnect_character_references(self):\n"
METHOD_BLOCK = '''    def build_dm_shared_character_state(self):
        """Return the deliberately whitelisted character state safe for DM sync."""
        return build_shared_character_state(
            self.character
        )


    def recent_shared_roll_events(self):
        """Return structured rolls captured during this running app session."""
        return copy.deepcopy(
            list(
                getattr(
                    self,
                    "_shared_roll_events",
                    [],
                )
            )
        )


    def take_shared_roll_events(self):
        """Return and clear pending structured roll events for a future sync layer."""
        events = self.recent_shared_roll_events()
        queue = getattr(
            self,
            "_shared_roll_events",
            None,
        )
        if queue is not None:
            queue.clear()
        return events


    def set_shared_roll_event_callback(self, callback=None):
        """Install an optional transport callback without coupling dice to networking."""
        self._shared_roll_event_callback = (
            callback
            if callable(callback)
            else None
        )


    def _record_shared_roll_event(
        self,
        summary,
        character=None,
    ):
        """Convert one completed roll into the future DM-dashboard event format."""
        character = character or self.character
        event = build_shared_roll_event(
            character,
            summary,
        )

        queue = getattr(
            self,
            "_shared_roll_events",
            None,
        )
        if queue is None:
            self._shared_roll_events = deque(maxlen=200)
            queue = self._shared_roll_events

        queue.append(event)

        callback = getattr(
            self,
            "_shared_roll_event_callback",
            None,
        )
        if callable(callback):
            callback(
                copy.deepcopy(event)
            )

        return event


'''

ROLL_NEEDLE = '''        # The summary arrives once per completed roll (unlike receive_roll,
        # which duplicates the total). Roll history is deliberately session-only:
        # do not mark the character dirty or autosave because of a dice roll.
        try:
            owner = self._roll_history_owner or self.character
            entry = format_session_roll_entry(summary)
            owner.roll_history.append(entry)
            self._remember_session_roll_history(owner)
            self._refresh_session_roll_history_dialog()
        except (ValueError, TypeError, KeyError, OverflowError):
            traceback.print_exc()
'''

ROLL_REPLACEMENT = '''        # The summary arrives once per completed roll (unlike receive_roll,
        # which duplicates the total). Roll history is deliberately session-only:
        # do not mark the character dirty or autosave because of a dice roll.
        owner = self._roll_history_owner or self.character

        try:
            entry = format_session_roll_entry(summary)
            owner.roll_history.append(entry)
            self._remember_session_roll_history(owner)
            self._refresh_session_roll_history_dialog()
        except (ValueError, TypeError, KeyError, OverflowError):
            traceback.print_exc()

        # Phase 1 campaign sharing. This only records a structured in-memory
        # event; it performs no network request and does not affect the roll.
        try:
            self._record_shared_roll_event(
                summary,
                owner,
            )
        except (ValueError, TypeError, KeyError, OverflowError):
            traceback.print_exc()
'''


def find_project_root():
    candidates = [Path.cwd(), Path(__file__).resolve().parent]
    for candidate in list(candidates):
        candidates.extend(candidate.parents[:3])

    seen = set()
    for root in candidates:
        root = root.resolve()
        if root in seen:
            continue
        seen.add(root)
        if (root / "frontend_2_8.py").is_file():
            return root

    # Development copies sometimes carry a timestamp suffix.
    for root in candidates:
        root = root.resolve()
        matches = sorted(root.glob("frontend_2_8*.py"))
        if matches:
            return root

    raise FileNotFoundError(
        "Could not find frontend_2_8.py. Put this patcher in your 'current code' "
        "folder, or run it while Command Prompt is inside that folder."
    )


def find_frontend(root):
    exact = root / "frontend_2_8.py"
    if exact.is_file():
        return exact
    matches = sorted(root.glob("frontend_2_8*.py"))
    if not matches:
        raise FileNotFoundError("No frontend_2_8*.py file found")
    return matches[-1]


def replace_once(text, needle, replacement, label):
    count = text.count(needle)
    if count != 1:
        raise RuntimeError(
            f"Could not safely patch {label}: expected exactly one matching block, found {count}."
        )
    return text.replace(needle, replacement, 1)


def copy_if_needed(source, target):
    if source.resolve() == target.resolve():
        return
    shutil.copy2(source, target)


def main():
    root = find_project_root()
    frontend = find_frontend(root)
    support_dir = Path(__file__).resolve().parent

    module_source = support_dir / "campaign_shared.py"
    test_source = support_dir / "test_campaign_shared.py"
    if not module_source.is_file() or not test_source.is_file():
        raise FileNotFoundError(
            "Keep apply_phase1_patch.py, campaign_shared.py and test_campaign_shared.py "
            "together before running the patcher."
        )

    module_target = root / "campaign_shared.py"
    tests_dir = root / "DID_Important_Tests"
    test_target = tests_dir / "test_campaign_shared.py"

    print(f"Project:  {root}")
    print(f"Frontend: {frontend.name}")

    original = frontend.read_text(encoding="utf-8")
    text = original

    if "from campaign_shared import build_shared_character_state, build_shared_roll_event" not in text:
        text = replace_once(text, IMPORT_NEEDLE, IMPORT_REPLACEMENT, "campaign_shared import")

    if "self._shared_roll_events = deque(maxlen=200)" not in text:
        text = replace_once(text, INIT_NEEDLE, INIT_REPLACEMENT, "shared-roll initialization")

    if "def build_dm_shared_character_state(self):" not in text:
        text = replace_once(text, METHOD_MARKER, METHOD_BLOCK + METHOD_MARKER, "shared-data methods")

    if "self._record_shared_roll_event(" not in text:
        text = replace_once(text, ROLL_NEEDLE, ROLL_REPLACEMENT, "dice-summary hook")

    backup = frontend.with_name(frontend.name + ".before_phase1")
    if not backup.exists():
        shutil.copy2(frontend, backup)
        print(f"Backup:   {backup.name}")

    copy_if_needed(module_source, module_target)
    if tests_dir.is_dir():
        copy_if_needed(test_source, test_target)

    frontend.write_text(text, encoding="utf-8")

    py_compile.compile(str(module_target), doraise=True)
    py_compile.compile(str(frontend), doraise=True)
    print("Compile:  PASS")

    if test_target.is_file():
        completed = subprocess.run(
            [sys.executable, str(test_target)],
            cwd=str(root),
            text=True,
            capture_output=True,
        )
        print(completed.stdout, end="")
        if completed.stderr:
            print(completed.stderr, end="")
        if completed.returncode != 0:
            raise SystemExit(completed.returncode)
        print("Phase 1 tests: PASS")

    if text == original:
        print("Phase 1 was already installed; no frontend changes were needed.")
    else:
        print("Phase 1 installed successfully.")

    print("\nNo Supabase or network connection has been enabled yet.")
    print("The app now produces DM-safe character snapshots and structured roll events in memory.")


if __name__ == "__main__":
    main()
