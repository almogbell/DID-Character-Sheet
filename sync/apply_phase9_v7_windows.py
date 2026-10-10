from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: str, old: str, new: str) -> None:
    p = ROOT / path
    text = p.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"{path}: expected one match, found {text.count(old)} for {old[:80]!r}")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")


def main() -> None:
    server = "windows/mobile_sync_server.py"
    replace_once(server, "MAX_INBOUND_MESSAGE_BYTES = 64 * 1024", "MAX_INBOUND_MESSAGE_BYTES = 12 * 1024 * 1024")
    replace_once(
        server,
        "CommandHandler = Callable[[str, dict, int, str], None]",
        "CommandHandler = Callable[[str, dict, int, str], Optional[dict]]",
    )
    replace_once(
        server,
        "            self.command_handler(action, payload, base_revision, request_id)\n",
        "            command_result = self.command_handler(action, payload, base_revision, request_id)\n",
    )
    replace_once(
        server,
        '''        self._send(\n            client.socket,\n            {\n                "type": "command_ok",\n                "request_id": request_id,\n                "revision": self._revision,\n            },\n        )\n        self.broadcast_state()''',
        '''        response = {\n            "type": "command_ok",\n            "request_id": request_id,\n            "revision": self._revision,\n        }\n        if isinstance(command_result, dict):\n            response["result"] = command_result\n        self._send(client.socket, response)\n        self.broadcast_state()''',
    )

    adapter = "windows/mobile_sync_frontend_adapter.py"
    old_handler = '''    def command_handler(self, action: str, payload: dict, base_revision: int, request_id: str) -> None:\n        del base_revision, request_id  # revision validation belongs to MobileSyncServer\n        self._ensure_editable()\n        if not isinstance(payload, dict):\n            raise MobileSyncValidationError("Command payload must be an object")\n\n        if action == "resource.change":\n            self._handle_resource_change(payload)\n        elif action == "identity.set":\n            self._set_identity(payload)\n        elif action == "inventory.add":\n            self._inventory_add(payload)\n        elif action == "inventory.update":\n            self._inventory_update(payload)\n        elif action == "inventory.remove":\n            self._inventory_remove(payload)\n        else:\n            raise MobileSyncValidationError(f"Unsupported mobile action: {action}")\n\n        self._validate_character()\n        self._persist_and_refresh()\n'''
    new_handler = '''    def command_handler(self, action: str, payload: dict, base_revision: int, request_id: str) -> Optional[dict]:\n        del base_revision, request_id  # revision validation belongs to MobileSyncServer\n        self._ensure_editable()\n        if not isinstance(payload, dict):\n            raise MobileSyncValidationError("Command payload must be an object")\n\n        # V7 actions are kept in a small companion module so the existing\n        # finished desktop adapter remains readable and the desktop model stays\n        # authoritative. Dice is read-only; other V7 actions use the same\n        # validate/autosave/refresh path as existing mobile edits.\n        from mobile_sync_v7 import handle_mobile_v7_action\n        v7 = handle_mobile_v7_action(self, action, payload)\n        if v7.handled:\n            if v7.mutated:\n                self._validate_character()\n                self._persist_and_refresh()\n            return v7.result\n\n        if action == "resource.change":\n            self._handle_resource_change(payload)\n        elif action == "identity.set":\n            self._set_identity(payload)\n        elif action == "inventory.add":\n            self._inventory_add(payload)\n        elif action == "inventory.update":\n            self._inventory_update(payload)\n        elif action == "inventory.remove":\n            self._inventory_remove(payload)\n        else:\n            raise MobileSyncValidationError(f"Unsupported mobile action: {action}")\n\n        self._validate_character()\n        self._persist_and_refresh()\n        return None\n'''
    replace_once(adapter, old_handler, new_handler)

    delta = "sync/build_phase9_desktop_delta.py"
    replace_once(
        delta,
        '''FILES = (\n    "mobile_sync_frontend_adapter.py",\n)''',
        '''FILES = (\n    "mobile_sync_frontend_adapter.py",\n    "mobile_sync_server.py",\n    "mobile_sync_v7.py",\n)''',
    )
    p = ROOT / delta
    text = p.read_text(encoding="utf-8")
    start = text.index('README = """')
    end = text.index('"""\n\n\ndef build', start) + 3
    readme = '''README = """DID Character Sheet - Phase 9 V7 desktop delta\n\nUse this after the Phase 8 Windows companion is already installed and working.\n\n1. Close the Windows DID app.\n2. Copy all three Python files from this ZIP into the same current-code folder:\n   mobile_sync_frontend_adapter.py\n   mobile_sync_server.py\n   mobile_sync_v7.py\n3. Replace the older files when Windows asks.\n4. Start DID normally. You do NOT need to patch frontend_2_8.py again.\n\nV7 adds authoritative absolute HP/AT updates, resource adjustment, ordinary note\nediting, character-picture add/remove, safe Improvement choice/custom editing,\nand Windows-authoritative dice results. It also raises the authenticated message\nlimit only so selected character pictures can be transferred from the paired phone.\n"""'''
    p.write_text(text[:start] + readme + text[end:], encoding="utf-8")

    print("Applied Phase 9 V7 Windows sync upgrade")


if __name__ == "__main__":
    main()
