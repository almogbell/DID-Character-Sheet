from pathlib import Path

path = Path(__file__).with_name("mobile_companion_controller.py")
text = path.read_text(encoding="utf-8")
old = '''        self.adapter.command_handler(action, payload, base_revision, request_id)\n        # MobileSyncServer will increment/broadcast immediately after this\n        # callback returns. Capture the new signature here so the poller does\n        # not interpret the same mobile mutation as a second desktop mutation.\n        self._capture_baseline()\n'''
new = '''        result = self.adapter.command_handler(action, payload, base_revision, request_id)\n        # MobileSyncServer will increment/broadcast immediately after this\n        # callback returns. Capture the new signature here so the poller does\n        # not interpret the same mobile mutation as a second desktop mutation.\n        self._capture_baseline()\n        return result\n'''
if old not in text:
    if 'result = self.adapter.command_handler(action, payload, base_revision, request_id)' in text and 'return result' in text:
        print('mobile_companion_controller.py is already fixed.')
        raise SystemExit(0)
    raise RuntimeError('Could not find the expected mobile command block. Make sure this script is beside the current mobile_companion_controller.py.')
backup = path.with_suffix('.py.before_dice_cloud.bak')
backup.write_text(text, encoding='utf-8')
path.write_text(text.replace(old, new, 1), encoding='utf-8')
print('Fixed mobile_companion_controller.py and created backup:', backup.name)
