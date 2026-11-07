from __future__ import annotations

import copy
import threading
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PySide6.QtCore import QTimer

from campaign_cloud import CampaignCloudClient, CampaignCloudError
from campaign_privacy import build_window_shared_state
from campaign_party import build_window_party_state, upload_party_state
from campaign_roll_outbox import DurableRollOutbox, RollOutboxError


STATE_DEBOUNCE_MS = 1200
RETRY_INTERVAL_MS = 10000


def _app_dir():
    # PyInstaller one-file extracts bundled configuration under _MEIPASS.
    # The module path is not a reliable resource directory when frozen.
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    return Path(__file__).resolve().parent


def initialize_campaign_runtime(window):
    if getattr(window, "_campaign_runtime_initialized", False):
        return

    window._campaign_runtime_initialized = True
    window._campaign_cloud_client = None
    window._campaign_runtime_error = ""
    window._campaign_sync_status = "Not connected"
    window._campaign_sync_lock = threading.Lock()
    window._campaign_pending_rolls = None  # Set only after the durable outbox is loaded.
    window._campaign_roll_outbox = None
    window._campaign_roll_flush_future = None
    window._campaign_sync_executor = ThreadPoolExecutor(
        max_workers=1,
        thread_name_prefix="did-campaign-sync",
    )

    try:
        window._campaign_cloud_client = CampaignCloudClient(
            app_dir=_app_dir(),
        )
    except Exception as error:
        window._campaign_runtime_error = str(error)
        window._campaign_sync_status = "Campaign unavailable"

    # The same AppData directory stores campaign character links and roll
    # events.  Load existing unsent rolls even if the cloud is unavailable.
    try:
        from campaign_cloud import _default_user_data_dir
        directory = (window._campaign_cloud_client.user_data_dir
                     if window._campaign_cloud_client is not None
                     else _default_user_data_dir())
        window._campaign_roll_outbox = DurableRollOutbox(directory)
        window._campaign_pending_rolls = window._campaign_roll_outbox
    except RollOutboxError as error:
        # An unreadable file must not be replaced by an empty outbox.
        window._campaign_runtime_error = str(error)
        window._campaign_sync_status = "Sync error"

    window._campaign_state_timer = QTimer(window)
    window._campaign_state_timer.setSingleShot(True)
    window._campaign_state_timer.setInterval(STATE_DEBOUNCE_MS)
    window._campaign_state_timer.timeout.connect(
        lambda: _submit_state_sync(window)
    )

    # If the internet disappears, retain the newest state and pending rolls.
    # Re-try quietly; the ordinary desktop character sheet remains usable.
    window._campaign_retry_timer = QTimer(window)
    window._campaign_retry_timer.setInterval(RETRY_INTERVAL_MS)
    window._campaign_retry_timer.timeout.connect(
        lambda: retry_campaign_sync(window)
    )
    window._campaign_retry_timer.start()

    if hasattr(window, "set_shared_roll_event_callback"):
        window.set_shared_roll_event_callback(
            lambda event: queue_campaign_roll(window, event)
        )

    restore_campaign_connection(window)
    if window._campaign_roll_outbox is None:
        window._campaign_sync_status = "Sync error"
    elif len(window._campaign_roll_outbox):
        window._campaign_sync_status = "Pending sync"


def campaign_client(window):
    if not getattr(window, "_campaign_runtime_initialized", False):
        initialize_campaign_runtime(window)
    return getattr(window, "_campaign_cloud_client", None)


def campaign_sync_status(window):
    return str(getattr(window, "_campaign_sync_status", "Not connected"))


def current_character_link(window):
    client = campaign_client(window)
    if client is None:
        return None
    character = getattr(window, "character", None)
    character_id = str(getattr(character, "id", "") or "").strip()
    if not character_id:
        return None
    try:
        return client.get_character_link(character_id)
    except Exception:
        return None


def restore_campaign_connection(window):
    client = campaign_client(window)
    if client is None:
        return None
    link = current_character_link(window)
    window._campaign_sync_status = "Connected" if isinstance(link, dict) else "Not connected"
    return link


def schedule_campaign_state_sync(window):
    if not current_character_link(window):
        return
    timer = getattr(window, "_campaign_state_timer", None)
    if timer is not None:
        window._campaign_sync_status = "Pending sync"
        timer.start()


def sync_current_character_now(window):
    if not current_character_link(window):
        return False
    _submit_state_sync(window)
    return True


def retry_campaign_sync(window):
    client = campaign_client(window)
    character = getattr(window, "character", None)
    character_id = str(getattr(character, "id", "") or "").strip()
    if client is not None and character_id:
        pending = client.get_pending_character_approval(character_id)
        if isinstance(pending, dict) and pending.get("approval_status") == "pending":
            executor = getattr(window, "_campaign_sync_executor", None)
            future = getattr(window, "_campaign_approval_check_future", None)
            if executor is not None and (future is None or future.done()):
                # Supabase polling is on the existing worker, never on Qt's GUI
                # thread. A stale request cannot upload until the DM approves.
                def check_approval():
                    try:
                        result = client.refresh_pending_character_approval(character_id)
                        if isinstance(result, dict) and result.get("approval_status") == "approved":
                            window._campaign_sync_status = "Pending sync"
                        elif isinstance(result, dict) and result.get("approval_status") == "rejected":
                            window._campaign_sync_status = "DM rejected character"
                    except Exception as error:
                        window._campaign_runtime_error = str(error)
                window._campaign_approval_check_future = executor.submit(check_approval)
            return

    if not current_character_link(window):
        return

    status = campaign_sync_status(window)
    pending_rolls = getattr(window, "_campaign_pending_rolls", None)
    has_pending_rolls = bool(pending_rolls)

    if status in {"Offline", "Sync error", "Pending sync"}:
        _submit_state_sync(window)
    elif has_pending_rolls:
        _submit_roll_flush(window)


def queue_campaign_roll(window, event):
    if not isinstance(event, dict):
        return
    if not current_character_link(window):
        return

    outbox = getattr(window, "_campaign_roll_outbox", None)
    if outbox is None:
        window._campaign_sync_status = "Sync error"
        window._campaign_runtime_error = (
            getattr(window, "_campaign_runtime_error", "")
            or "Pending dice-roll storage is unavailable; roll not queued"
        )
        return

    try:
        outbox.enqueue(event)  # Commit to disk before submitting a network job.
    except RollOutboxError as error:
        window._campaign_sync_status = "Sync error"
        window._campaign_runtime_error = str(error)
        return

    window._campaign_sync_status = "Pending sync"
    _submit_roll_flush(window)


def _submit_state_sync(window):
    client = campaign_client(window)
    link = current_character_link(window)
    if client is None or not isinstance(link, dict):
        return

    try:
        state = build_window_shared_state(window, link=link)
        party_state = build_window_party_state(window, link=link)
    except Exception as error:
        window._campaign_sync_status = "Sync error"
        window._campaign_runtime_error = str(error)
        return

    campaign_character_id = str(link.get("campaign_character_id") or "").strip()
    if not campaign_character_id:
        return

    executor = getattr(window, "_campaign_sync_executor", None)
    if executor is None:
        return

    window._campaign_sync_status = "Syncing"

    def job():
        try:
            client.upload_character_state(campaign_character_id, state)
            try:
                upload_party_state(
                    client,
                    link.get("campaign_id"),
                    campaign_character_id,
                    party_state,
                )
            except Exception:
                # Party sharing is supplemental. A removed/inactive character
                # must not break the ordinary DM-safe character sync.
                pass
            window._campaign_sync_status = "Synced"
            window._campaign_runtime_error = ""
            _flush_pending_rolls_worker(window, client)
        except CampaignCloudError as error:
            window._campaign_sync_status = "Offline"
            window._campaign_runtime_error = str(error)
        except Exception as error:
            window._campaign_sync_status = "Sync error"
            window._campaign_runtime_error = str(error)

    executor.submit(job)


def _submit_roll_flush(window):
    client = campaign_client(window)
    executor = getattr(window, "_campaign_sync_executor", None)
    outbox = getattr(window, "_campaign_roll_outbox", None)
    if client is None or executor is None or outbox is None or not len(outbox):
        return
    previous = getattr(window, "_campaign_roll_flush_future", None)
    if previous is not None and not previous.done():
        return  # The active worker will inspect the same durable queue.
    window._campaign_roll_flush_future = executor.submit(_flush_pending_rolls_worker, window, client)


def _flush_pending_rolls_worker(window, client):
    outbox = getattr(window, "_campaign_roll_outbox", None)
    if outbox is None:
        return

    while True:
        event = outbox.peek()
        if event is None:
            return

        try:
            # Upload is idempotent on event_id. A crash after server success
            # but before disk acknowledgement is safely retried next launch.
            client.upload_linked_roll_event(event)
            outbox.acknowledge(str(event["event_id"]))
        except CampaignCloudError as error:
            window._campaign_sync_status = "Offline"
            window._campaign_runtime_error = str(error)
            return
        except Exception as error:
            window._campaign_sync_status = "Sync error"
            window._campaign_runtime_error = str(error)
            return

        window._campaign_sync_status = "Synced"
        window._campaign_runtime_error = ""
