"""UI completion must distinguish skipped conditions from earned rewards."""
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from modern_gui import serialize_campaign

class InventoryStatusTests(unittest.TestCase):
    def campaign(self, claimed=False, required=0, reward=False, earned=False, empty=False):
        now = datetime.now(timezone.utc)
        campaign = SimpleNamespace(id="test", name="Test", game=SimpleNamespace(name="Test game"),
            image_url="", eligible=True, active=True, upcoming=False, finished=True,
            ends_at=now, starts_at=now, is_reward=reward, link_url="https://www.twitch.tv/drops/inventory",
            allowed_channels=[], can_earn=lambda: required > 0 and not claimed and not earned)
        drop = SimpleNamespace(id="drop", name="Drop", benefits=[], required_minutes=required,
            real_current_minutes=required if earned else 0, is_claimed=claimed, earned=earned,
            campaign=campaign, can_earn=campaign.can_earn, rewards_text=lambda: "Reward")
        campaign.drops = [] if empty else [drop]
        return campaign

    def test_unclaimed_zero_minute_reward_is_not_completed(self):
        result = serialize_campaign(self.campaign())
        self.assertFalse(result["finished"])
        self.assertFalse(result["earnable"])

    def test_confirmed_non_watch_claim_is_completed(self):
        self.assertTrue(serialize_campaign(self.campaign(claimed=True))["finished"])

    def test_earned_code_watch_task_is_completed_without_ordinary_claim(self):
        self.assertTrue(serialize_campaign(self.campaign(required=15, reward=True, earned=True))["finished"])

    def test_no_rewards_is_not_a_completed_campaign(self):
        self.assertFalse(serialize_campaign(self.campaign(empty=True))["finished"])
