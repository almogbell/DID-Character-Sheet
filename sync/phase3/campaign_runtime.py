from __future__ import annotations

import copy
import threading
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PySide6.QtCore import QTimer

from campaign_cloud import CampaignCloudClient, CampaignCloudError


STATE_DEBOUNCE_MS = 1200
MAX_PENDING_ROLLS = 200


def _app_dir():
    return Path(__file__).resolve().parent


def initialize_campaign_runtime(window):
    if getattr(window, "_campaign_runtime_initialized", False):
        return

    window._campaign_runtime_initialized = True
    window._campaign_cloud_client = None
    window._campaign_runtime_error = ""
    window._campaign_sync_status = "Not connected"
    window._campaign_sync_lock = threading.Lock()
    window._campaign_pending_rolls = deque(maxlen=MAX_PENDING_ROLLS)
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

    window._campaign_state_timer = QTimer(window)
    window._campaign_state_timer.setSingleShot(True)
    window._campaign_state_timer.setInterval(STATE_DEBOUNCE_MS)
    window._campaign_state_timer.timeout.connect(
        lambda: _submit_state_sync(window)
    )

    if hasattr(window, "set_shared_roll_event_callback"):
        window.set_shared_roll_event_callback(
            lambda event: queue_campaign_roll(window, event)
        )

    restore_campaign_connection(window)


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


def queue_campaign_roll(window, event):
    if not isinstance(event, dict):
        return
    if not current_character_link(window):
        return

    lock = getattr(window, "_campaign_sync_lock", None)
    queue = getattr(window, "_campaign_pending_rolls", None)
    if lock is None or queue is None:
        return

    with lock:
        event_id = str(event.get("event_id") or "")
        if event_id and any(str(item.get("event_id") or "") == event_id for item in queue):
            return
        queue.append(copy.deepcopy(event))

    window._campaign_sync_status = "Pending sync"
    _submit_roll_flush(window)


def _submit_state_sync(window):
    client = campaign_client(window)
    link = current_character_link(window)
    if client is None or not isinstance(link, dict):
        return

    try:
        state = window.build_dm_shared_character_state()
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
    if client is None or executor is None:
        return
    executor.submit(_flush_pending_rolls_worker, window, client)


def _flush_pending_rolls_worker(window, client):
    lock = getattr(window, "_campaign_sync_lock", None)
    queue = getattr(window, "_campaign_pending_rolls", None)
    if lock is None or queue is None:
        return

    while True:
        with lock:
            if not queue:
                return
            event = copy.deepcopy(queue[0])

        try:
            client.upload_linked_roll_event(event)
        except CampaignCloudError as error:
            window._campaign_sync_status = "Offline"
            window._campaign_runtime_error = str(error)
            return
        except Exception as error:
            window._campaign_sync_status = "Sync error"
            window._campaign_runtime_error = str(error)
            return

        event_id = str(event.get("event_id") or "")
        with lock:
            if queue and str(queue[0].get("event_id") or "") == event_id:
                queue.popleft()
            else:
                matching = next(
                    (
                        queued
                        for queued in queue
                        if str(queued.get("event_id") or "") == event_id
                    ),
                    None,
                )
                if matching is not None:
                    queue.remove(matching)
        window._campaign_sync_status = "Synced"
        window._campaign_runtime_error = ""
