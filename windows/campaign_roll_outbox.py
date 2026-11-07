"""Durable, idempotent outbox for campaign dice events.

Events are written to AppData *before* any network send.  The cloud API uses
``event_id`` as an idempotency key, so retrying after a crash is safe.
This module deliberately has no Qt dependency and never stores auth tokens.
"""
from __future__ import annotations

import copy
import json
import os
import tempfile
import threading
from pathlib import Path


OUTBOX_FILENAME = "campaign_roll_outbox.json"


class RollOutboxError(RuntimeError):
    """An event could not be durably recorded or acknowledged."""


class DurableRollOutbox:
    def __init__(self, directory: Path):
        self.path = Path(directory) / OUTBOX_FILENAME
        self._lock = threading.RLock()
        self._events = self._load()

    def _load(self) -> list[dict]:
        if not self.path.exists():
            return []
        try:
            with self.path.open("r", encoding="utf-8") as stream:
                payload = json.load(stream)
            if not isinstance(payload, dict) or payload.get("version") != 1:
                raise ValueError("unsupported outbox format")
            records = payload.get("rolls")
            if not isinstance(records, list):
                raise ValueError("rolls must be a list")
            ids = set()
            for event in records:
                if not isinstance(event, dict):
                    raise ValueError("roll must be an object")
                event_id = str(event.get("event_id") or "").strip()
                if not event_id or event_id in ids:
                    raise ValueError("missing or duplicated roll event_id")
                ids.add(event_id)
            return records
        except (OSError, ValueError, TypeError, UnicodeError) as exc:
            # Never rename/delete an unreadable outbox: it may contain the only
            # copy of rolls which have not yet reached the campaign server.
            raise RollOutboxError(
                f"Cannot read {self.path}. The file has been preserved; "
                f"please back it up before attempting a repair: {exc}"
            ) from exc

    def _save(self, events: list[dict]) -> None:
        tmp_name = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=self.path.parent,
                prefix=f".{self.path.stem}-", suffix=".tmp", delete=False,
            ) as stream:
                tmp_name = stream.name
                json.dump({"version": 1, "rolls": events}, stream, ensure_ascii=False)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(tmp_name, self.path)
        except (OSError, ValueError, TypeError) as exc:
            raise RollOutboxError(f"Could not save pending dice rolls: {exc}") from exc
        finally:
            if tmp_name:
                try:
                    Path(tmp_name).unlink(missing_ok=True)
                except OSError:
                    pass

    def __len__(self) -> int:
        with self._lock:
            return len(self._events)

    def peek(self) -> dict | None:
        with self._lock:
            return copy.deepcopy(self._events[0]) if self._events else None

    def enqueue(self, event: dict) -> bool:
        if not isinstance(event, dict):
            raise RollOutboxError("Roll event must be an object")
        event_id = str(event.get("event_id") or "").strip()
        if not event_id:
            raise RollOutboxError("Roll event has no event_id; it cannot be safely retried")
        with self._lock:
            if any(str(roll.get("event_id") or "") == event_id for roll in self._events):
                return False
            updated = [*self._events, copy.deepcopy(event)]
            self._save(updated)  # Preserve existing memory state if the write fails.
            self._events = updated
            return True

    def acknowledge(self, event_id: str) -> bool:
        event_id = str(event_id or "").strip()
        if not event_id:
            raise RollOutboxError("Cannot acknowledge a roll without event_id")
        with self._lock:
            if not any(str(item.get("event_id") or "") == event_id for item in self._events):
                return False
            updated = [item for item in self._events if str(item.get("event_id") or "") != event_id]
            self._save(updated)
            self._events = updated
            return True
