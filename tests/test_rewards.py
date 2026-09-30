import asyncio
import copy
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from datetime import datetime, timedelta, timezone

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))
sys.argv[0] = str(BASE / "main.py")
from rewards import RewardCampaign, watch_groups, refresh_progress
from modern_gui import Store
from constants import PriorityMode, State
from utils import Game
from unittest.mock import AsyncMock, patch
from exceptions import MinerException
from rewards import discover


class RewardTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.data = json.loads((BASE / "reward-api-redacted.json").read_text(encoding="utf-8"))["Progress"]["data"]["channelDropCampaignsProgress"][0]
        now = datetime.now(timezone.utc)
        self.data["startAt"] = (now - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.data["endAt"] = (now + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.game = Game(self.data["game"])
        self.channel = SimpleNamespace(id=42, game=self.game)
        self.events = []
        self.client = SimpleNamespace(settings=SimpleNamespace(enable_badges_emotes=False),
            gui=SimpleNamespace(inv=SimpleNamespace(update_drop=lambda d: self.events.append(d.real_current_minutes)),
                                display_drop=lambda *a, **k: None,
                                tray=SimpleNamespace(notify=lambda *a: None)),
            print=lambda s: None, change_state=lambda s: self.events.append(s))

    def campaign(self):
        return RewardCampaign(self.client, self.data, self.game, [self.channel])

    async def test_late_code_progress_keeps_record_without_reviving_paused_task(self):
        campaign=self.campaign()
        self.client.inventory=[campaign]
        self.client.paused=False
        self.client.gui.display_drop=AsyncMock()
        self.client.gui.tray.notify=AsyncMock()
        async def delayed_progress(client,channel):
            self.client.paused=True
            data=copy.deepcopy(self.data)
            for group in data['rewardGroups']:
                group['self']['currentMinutesWatched']=group['progressCriteria']['requirements']['minutesWatched']
            return [data]
        with patch('rewards.channel_rewards',side_effect=delayed_progress):
            await refresh_progress(self.client,self.channel)
        self.assertTrue(campaign.finished)
        self.client.gui.display_drop.assert_not_called()
        self.client.gui.tray.notify.assert_not_called()
        self.assertNotIn(State.INVENTORY_FETCH,self.events)

    async def test_discovery_failure_preserves_task_but_never_unverified_watch(self):
        campaign=self.campaign()
        self.client.inventory=[campaign]
        self.client.settings.priority=[self.game.name]
        self.client.settings.priority_mode=PriorityMode.PRIORITY_ONLY
        self.client.settings.exclude=set()
        self.client.get_live_streams=AsyncMock(side_effect=MinerException('temporary'))
        result=await discover(self.client,[campaign])
        self.assertEqual(result,[campaign])
        self.assertEqual(campaign.allowed_channels,[])
        self.assertFalse(campaign.can_earn(self.channel))

    async def test_inventory_discovery_keeps_rewards_outside_priority_list(self):
        good=SimpleNamespace(id=42,game=self.game,_stream=SimpleNamespace(drops_enabled=False))
        self.client.inventory=[]
        self.client.settings.priority=[]
        self.client.settings.priority_mode=PriorityMode.PRIORITY_ONLY
        self.client.settings.exclude=set()
        self.client.get_live_streams=AsyncMock(return_value=[good])
        with patch('rewards.channel_rewards',return_value=[self.data]):
            result=await discover(self.client,[],[self.game])
        self.assertEqual(len(result),1)
        self.assertEqual(result[0].id,self.data['id'])

    async def test_known_code_campaign_remains_visible_after_priority_removed(self):
        campaign=self.campaign()
        self.client.inventory=[campaign]
        self.client.settings.priority=[]
        self.client.settings.priority_mode=PriorityMode.PRIORITY_ONLY
        self.client.settings.exclude=set()
        self.client.get_live_streams=AsyncMock(side_effect=MinerException('temporary'))
        old_minutes=campaign.drops.__iter__().__next__().real_current_minutes
        result=await discover(self.client,[])
        self.assertEqual(result,[campaign])
        self.assertEqual(next(iter(result[0].drops)).real_current_minutes,old_minutes)

    async def test_discovery_retries_broader_directory_when_first_streams_do_not_qualify(self):
        bad=SimpleNamespace(id=99,game=self.game)
        good=SimpleNamespace(id=42,game=self.game,_stream=SimpleNamespace(drops_enabled=False))
        self.client.inventory=[]
        self.client.settings.priority=[self.game.name]
        self.client.settings.priority_mode=PriorityMode.PRIORITY_ONLY
        self.client.settings.exclude=set()
        self.client.get_live_streams=AsyncMock(side_effect=[[bad],[bad,good]])
        async def query(client,channel): return [self.data] if channel.id==42 else []
        with patch('rewards.channel_rewards',side_effect=query):
            result=await discover(self.client,[self.campaign()])
        self.assertEqual(len(result),1)
        self.assertEqual(result[0].allowed_channels,[good])

    def test_watch_code_needs_no_game_account_link(self):
        campaign = self.campaign()
        self.assertFalse(campaign.linked)
        self.assertTrue(campaign.eligible)
        self.assertTrue(campaign.can_earn(self.channel))
        self.assertFalse(campaign.can_earn(SimpleNamespace(id=99, game=self.game)))

    def test_subscriptions_and_non_code_rewards_are_rejected(self):
        for field in ("subs", "turboSubs"):
            data = copy.deepcopy(self.data)
            data["rewardGroups"][0]["progressCriteria"]["requirements"][field] = 1
            self.assertEqual(list(watch_groups(data)), [])
        self.data["rewardGroups"][0]["rewards"][0]["distributionType"] = "DIRECT_ENTITLEMENT"
        self.assertEqual(list(watch_groups(self.data)), [])

    def test_long_task_uses_server_minutes_and_no_estimated_progress(self):
        self.data["rewardGroups"][0]["progressCriteria"]["requirements"]["minutesWatched"] = 240
        campaign = self.campaign()
        drop = campaign.first_drop
        initial = drop.current_minutes
        for _ in range(100):
            campaign.bump_minutes(self.channel)
        self.assertEqual(drop.current_minutes, initial)
        self.assertFalse(drop.can_claim)
        drop.update_minutes(180)
        self.assertEqual(drop.remaining_minutes, 60)
        self.assertFalse(campaign.finished)
        drop.update_minutes(240)
        self.assertTrue(campaign.finished)
        self.assertFalse(campaign.can_earn(self.channel))
        self.assertFalse(drop.is_claimed)  # earned is distinct from redeemed

    async def test_progress_updates_each_group_independently(self):
        extra = copy.deepcopy(self.data["rewardGroups"][0])
        extra["id"] = "second-watch-task"
        extra["self"]["currentMinutesWatched"] = 0
        extra["progressCriteria"]["requirements"]["minutesWatched"] = 60
        self.data["rewardGroups"].append(extra)
        campaign = self.campaign()
        self.client.inventory = [campaign]
        snapshot = copy.deepcopy(self.data)
        snapshot["rewardGroups"][0]["self"]["currentMinutesWatched"] = 10
        async def request(query):
            return {"data": {"channelDropCampaignsProgress": [snapshot]}}
        self.client.gql_request = request
        await refresh_progress(self.client, self.channel)
        drops = list(campaign.drops)
        self.assertEqual(drops[0].real_current_minutes, 10)
        self.assertEqual(drops[1].real_current_minutes, 0)

    async def test_completion_changes_selection_without_claiming_code(self):
        campaign = self.campaign()
        self.client.inventory = [campaign]
        snapshot = copy.deepcopy(self.data)
        snapshot["rewardGroups"][0]["self"]["currentMinutesWatched"] = 15
        async def request(query):
            return {"data": {"channelDropCampaignsProgress": [snapshot]}}
        self.client.gql_request = request
        await refresh_progress(self.client, self.channel)
        self.assertTrue(campaign.finished)
        self.assertIn(State.INVENTORY_FETCH, self.events)

    async def test_multiple_reward_groups_finish_and_select_independently(self):
        original = copy.deepcopy(self.data["rewardGroups"][0])
        self.data["rewardGroups"] = []
        for i, required in enumerate((15, 30, 60)):
            group = copy.deepcopy(original)
            group["id"] = f"reward-{i}"
            group["self"]["currentMinutesWatched"] = 0
            group["progressCriteria"]["requirements"]["minutesWatched"] = required
            self.data["rewardGroups"].append(group)
        campaign = self.campaign()
        self.client.inventory = [campaign]
        snapshot = copy.deepcopy(self.data)
        for group, minutes in zip(snapshot["rewardGroups"], (15, 30, 45)):
            group["self"]["currentMinutesWatched"] = minutes
        async def request(query):
            return {"data": {"channelDropCampaignsProgress": [snapshot]}}
        self.client.gql_request = request
        await refresh_progress(self.client, self.channel)
        self.assertEqual([d.earned for d in campaign.drops], [True, True, False])
        self.assertEqual(campaign.first_drop.id, "reward-2")
        self.assertFalse(campaign.finished)
        # Each earned code refreshes inventory without waiting for the last group.
        self.assertIn(State.INVENTORY_FETCH, self.events)
        self.events.clear()
        await refresh_progress(self.client, self.channel)
        self.assertNotIn(State.INVENTORY_FETCH, self.events)
        snapshot["rewardGroups"][2]["self"]["currentMinutesWatched"] = 60
        await refresh_progress(self.client, self.channel)
        self.assertTrue(campaign.finished)
        self.assertIsNone(campaign.first_drop)
        self.assertIn(State.INVENTORY_FETCH, self.events)

    async def test_overview_keeps_nearest_reward_when_long_groups_update(self):
        original = copy.deepcopy(self.data["rewardGroups"][0])
        self.data["rewardGroups"] = []
        for required in (240, 60, 120):
            group = copy.deepcopy(original)
            group["id"] = f"reward-{required}"
            group["self"]["currentMinutesWatched"] = 0
            group["progressCriteria"]["requirements"]["minutesWatched"] = required
            self.data["rewardGroups"].append(group)
        campaign = self.campaign()
        self.client.inventory = [campaign]
        displayed = []
        self.client.gui.display_drop = lambda drop, **kw: displayed.append(drop.id)
        async def request(query):
            snapshot = copy.deepcopy(self.data)
            for group in snapshot["rewardGroups"]:
                group["self"]["currentMinutesWatched"] = 4
            return {"data": {"channelDropCampaignsProgress": [snapshot]}}
        self.client.gql_request = request
        await refresh_progress(self.client, self.channel)
        self.assertEqual(displayed, ["reward-60"])
        self.assertEqual([d.real_current_minutes for d in campaign.drops], [4, 4, 4])

    async def test_cancelled_campaign_updates_server_minutes_without_stealing_overview(self):
        cancelled = self.campaign()
        self.data["id"] = "other-campaign"
        other = self.campaign()
        self.client.inventory = [cancelled, other]
        self.client.settings.cancelled_campaigns = {cancelled.id}
        displayed = []
        self.client.gui.display_drop = lambda drop, **kw: displayed.append(drop.campaign.id)
        cancelled_snapshot = copy.deepcopy(self.data)
        cancelled_snapshot["id"] = cancelled.id
        cancelled_snapshot["rewardGroups"][0]["self"]["currentMinutesWatched"] = 15
        other_snapshot = copy.deepcopy(self.data)
        other_snapshot["rewardGroups"][0]["self"]["currentMinutesWatched"] = 7
        async def request(query):
            return {"data": {"channelDropCampaignsProgress": [cancelled_snapshot, other_snapshot]}}
        self.client.gql_request = request
        await refresh_progress(self.client, self.channel)
        self.assertTrue(cancelled.finished)  # Twitch can record incidental progress.
        self.assertEqual(next(iter(other.drops)).real_current_minutes, 7)
        self.assertEqual(displayed, [other.id])
        self.assertNotIn(State.INVENTORY_FETCH, self.events)

    def test_ui_snapshot_is_detached_and_logs_bounded(self):
        store = Store()
        store.entry("channels", 42, {"name": "test"})
        snapshot = store.snapshot()
        snapshot["channels"]["42"]["name"] = "mutated"
        self.assertEqual(store.snapshot()["channels"]["42"]["name"], "test")
        for n in range(450):
            store.log(str(n))
        self.assertEqual(len(store.snapshot()["logs"]), 400)
        self.assertEqual(store.snapshot(store.revision), {"revision": store.revision})


if __name__ == "__main__":
    unittest.main()
