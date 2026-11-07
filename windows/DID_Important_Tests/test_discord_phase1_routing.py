import tempfile
import unittest
from pathlib import Path

from discord_integration import (
    empty_config,
    resolve_channel_binding,
    save_config,
    set_binding,
    validate_config_for_start,
)


def binding(name, guild, channel):
    return {
        "campaign_name": name,
        "guild_id": str(guild),
        "channel_id": str(channel),
    }


class DiscordPhase1RoutingTests(unittest.TestCase):
    def test_two_campaigns_in_same_server_route_by_exact_channel(self):
        config = empty_config()
        config = set_binding(config, "campaign-a", binding("Dragon", 100, 1001))
        config = set_binding(config, "campaign-b", binding("Space", 100, 1002))

        a = resolve_channel_binding(config, 100, 1001)
        b = resolve_channel_binding(config, 100, 1002)
        self.assertEqual(a[0], "campaign-a")
        self.assertEqual(b[0], "campaign-b")

    def test_unmapped_channel_never_falls_back_to_only_campaign_in_server(self):
        config = empty_config()
        config = set_binding(config, "campaign-a", binding("Dragon", 100, 1001))
        self.assertIsNone(resolve_channel_binding(config, 100, 9999))

    def test_same_channel_number_in_different_server_is_independent(self):
        config = empty_config()
        config = set_binding(config, "campaign-a", binding("Dragon", 100, 1001))
        config = set_binding(config, "campaign-b", binding("Space", 200, 1001))
        self.assertEqual(resolve_channel_binding(config, 100, 1001)[0], "campaign-a")
        self.assertEqual(resolve_channel_binding(config, 200, 1001)[0], "campaign-b")

    def test_same_server_channel_cannot_be_assigned_twice(self):
        config = empty_config()
        config = set_binding(config, "campaign-a", binding("Dragon", 100, 1001))
        with self.assertRaisesRegex(ValueError, "only one DID campaign"):
            set_binding(config, "campaign-b", binding("Space", 100, 1001))

    def test_start_requires_home_channel_for_enabled_campaign(self):
        config = empty_config()
        config["bot_token"] = "token"
        config["application_id"] = "12345"
        config = set_binding(config, "campaign-a", binding("Dragon", 100, ""))
        with self.assertRaisesRegex(ValueError, "Home Channel ID is required"):
            validate_config_for_start(config)

    def test_corrupt_duplicate_config_fails_closed(self):
        config = empty_config()
        config["campaigns"] = {
            "campaign-a": binding("Dragon", 100, 1001),
            "campaign-b": binding("Space", 100, 1001),
        }
        self.assertIsNone(resolve_channel_binding(config, 100, 1001))
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "only one DID campaign"):
                save_config(config, Path(tmp))


if __name__ == "__main__":
    unittest.main(verbosity=2)
