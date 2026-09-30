"""UI completion must distinguish skipped conditions from earned rewards."""
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from modern_gui import serialize_campaign
from constants import PriorityMode

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

    def test_only_eligible_selected_watch_campaigns_are_scheduled(self):
        c=self.campaign(required=60)
        settings=SimpleNamespace(priority=[],exclude=set(),cancelled_campaigns=set(),priority_mode=PriorityMode.PRIORITY_ONLY)
        c._twitch=SimpleNamespace(settings=settings)
        self.assertFalse(serialize_campaign(c)["scheduled"])
        settings.priority.append("Test game")
        self.assertTrue(serialize_campaign(c)["scheduled"])
        c.eligible=False
        self.assertFalse(serialize_campaign(c)["scheduled"])
        c.eligible=True
        settings.cancelled_campaigns.add("test")
        self.assertFalse(serialize_campaign(c)["scheduled"])
        settings.cancelled_campaigns.clear()
        settings.exclude.add("Test game")
        self.assertFalse(serialize_campaign(c)["scheduled"])
        settings.exclude.clear()
        settings.priority.clear()
        settings.priority_mode=PriorityMode.ENDING_SOONEST
        self.assertTrue(serialize_campaign(c)["scheduled"])
