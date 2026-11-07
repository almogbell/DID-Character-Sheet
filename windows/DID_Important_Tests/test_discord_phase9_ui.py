from __future__ import annotations

import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UI = ROOT / 'discord_integration_ui.py'


class DiscordPhase9UITests(unittest.TestCase):
    """Hosted Discord setup contract, replacing obsolete local-bot UI assertions."""

    @classmethod
    def setUpClass(cls):
        cls.source = UI.read_text(encoding='utf-8')
        cls.tree = ast.parse(cls.source)
        cls.dialog = next(n for n in cls.tree.body if isinstance(n, ast.ClassDef) and n.name == 'DiscordIntegrationDialog')
        cls.methods = {n.name: n for n in cls.dialog.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}

    def method(self, name):
        self.assertIn(name, self.methods)
        return ast.get_source_segment(self.source, self.methods[name])

    def test_source_parses(self):
        self.assertIsInstance(self.tree, ast.Module)

    def test_hosted_flow_uses_campaign_client(self):
        for method, call in (
            ('refresh_all', 'discord_service_config('),
            ('refresh_connection', 'get_discord_connection('),
            ('create_connect_code', 'create_discord_connect_code('),
            ('disconnect_campaign', 'disconnect_discord_campaign('),
        ):
            self.assertIn(call, self.method(method))

    def test_campaign_scoping_is_explicit(self):
        for name in ('refresh_connection', 'create_connect_code', 'disconnect_campaign'):
            self.assertIn('self.campaign_id', self.method(name))

    def test_connection_code_and_discord_command(self):
        code = self.method('create_connect_code')
        self.assertIn('self.pending_code', code)
        self.assertIn('expires_at', code)
        self.assertIn('/did-connect', code)
        self.assertIn('self.poll_timer.start()', code)
        self.assertIn('QApplication.clipboard().setText(self.pending_code)', self.method('copy_code'))

    def test_install_url_comes_from_service_configuration(self):
        method = self.method('open_install_url')
        self.assertIn('self.service_config.get("install_url")', method)
        self.assertIn('webbrowser.open(url)', method)

    def test_connection_polling_and_cleanup(self):
        constructor = self.method('__init__')
        self.assertIn('self.poll_timer.timeout.connect(self.refresh_connection)', constructor)
        self.assertIn('self.endpoint_timer.timeout.connect(self.check_endpoint_verification)', constructor)
        self.assertIn('self.poll_timer.stop()', self.method('refresh_connection'))
        self.assertIn('self.poll_timer.stop()', self.method('show_unavailable'))

    def test_no_local_bot_launch_or_manual_token_form_for_players(self):
        self.assertNotIn('launch_bot(', self.source)
        self.assertNotIn('self.token.setEchoMode', self.source)
        self.assertNotIn('form.addRow("Session Channel', self.source)
        self.assertIn('stop_bot()', self.source)  # Cleanup of any old local process.
        self.assertIn('self.developer_credentials.hide()', self.method('show_unavailable'))

    def test_developer_bootstrap_requires_endpoint_verification(self):
        self.assertIn('bootstrap_official_discord(', self.method('finish_developer_credentials'))
        check = self.method('check_endpoint_verification')
        self.assertIn('discord_service_config(', check)
        self.assertIn('endpoint_verified', check)
        self.assertIn('endpoint_verified', self.method('refresh_all'))

    def test_connected_state_has_change_and_disconnect(self):
        setup = self.method('_build_connected_page')
        self.assertIn('self.show_setup', setup)
        self.assertIn('self.disconnect_campaign', setup)
        self.assertIn('self.pages.setCurrentIndex(0)', self.method('show_setup'))

    def test_developer_credentials_not_required_for_campaign_setup(self):
        setup = self.method('_build_setup_page')
        self.assertIn('self.open_install_url', setup)
        self.assertIn('self.create_connect_code', setup)
        self.assertNotIn('bot_token', setup)
        self.assertNotIn('guild_id', setup)
        self.assertNotIn('dm_role_id', setup)


if __name__ == '__main__':
    unittest.main()
