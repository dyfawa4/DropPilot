"""DropPilot engine: upstream protocol layer plus guarded lifecycle policies."""
from datetime import datetime, timedelta, timezone
import asyncio
import logging
from time import time

from twitch import Twitch
from constants import State, PriorityMode, GQL_QUERIES, WATCH_INTERVAL
from inventory import DropsCampaign
from rewards import RewardCampaign, refresh_progress, earned_codes
from modern_gui import GUIManager, STORE
from utils import task_wrapper
from exceptions import MinerException


class Engine(Twitch):
    def __init__(self, settings):
        self.paused = False
        self._code_tasks = set()
        super().__init__(settings, gui_factory=GUIManager)

    async def fetch_inventory(self):
        await super().fetch_inventory()
        try:
            STORE.update(earnedCodes=await earned_codes(self))
        except MinerException:
            self.print("兑换码库存暂时无法更新，可稍后刷新活动重试。")

    def change_state(self, state):
        if self.paused and state is not State.EXIT:
            state = State.IDLE
        super().change_state(state)

    def can_watch(self, channel):
        game = channel.game
        if game is None or game.name in self.settings.exclude:
            return False
        if self.settings.priority_mode is PriorityMode.PRIORITY_ONLY:
            if game.name not in self.settings.priority and not any(
                    g.is_special() and g.name in self.settings.priority for g in self.wanted_games):
                return False
        return not self.paused and super().can_watch(channel)

    @task_wrapper
    async def process_notifications(self, user_id, message):
        if message.get("type") == "create-notification":
            kind = ((message.get("data") or {}).get("notification") or {}).get("type", "")
            if "drop" in kind or "reward_campaign" in kind:
                # Code notifications can contain the only redemption link. Keep them.
                self.change_state(State.INVENTORY_FETCH)

    async def _maintenance_task(self):
        # Re-discover eligible streams without waiting a full hour when idle.
        await asyncio.sleep(600)
        self.change_state(State.INVENTORY_FETCH)

    def watch(self, channel, *, update_status=True):
        if self.paused:
            return
        super().watch(channel, update_status=update_status)
        campaign = self.get_active_campaign(channel)
        if campaign and campaign.first_drop:
            campaign.first_drop.display(countdown=False)

    @task_wrapper(critical=True)
    async def _watch_loop(self):
        logger = logging.getLogger("TwitchDrops")
        previous = None
        stalled = 0
        while True:
            channel = await self.watching_channel.get()
            if not self.can_watch(channel):
                self.stop_watching()
                continue
            started = time()
            if not await channel.send_watch():
                logger.warning("观看心跳失败：%s", channel.name)
            await asyncio.sleep(20)
            if self.paused or self.watching_channel.get_with_default(None) != channel:
                continue
            handled = await refresh_progress(self, channel)
            if not handled:
                try:
                    response = await self.gql_request(GQL_QUERIES["CurrentDrop"].with_variables(
                        {"channelID": str(channel.id)}))
                    data = response.get("data", {}).get("currentUser", {}).get("dropCurrentSession")
                    if data and (drop := self._drops.get(data["dropID"])):
                        drop.update_minutes(data["currentMinutesWatched"])
                        drop.display(countdown=False)
                except MinerException as exc:
                    logger.warning("掉宝进度查询失败：%s", exc)
            campaign = self.get_active_campaign(channel)
            current = (channel.id, tuple((d.id, d.real_current_minutes) for d in campaign.drops)) if campaign else None
            stalled = stalled + 1 if current == previous else 0
            previous = current
            if stalled >= 5:
                self.print("Twitch 暂未报告新进度，正在重新检查活动与频道。")
                self.change_state(State.INVENTORY_FETCH)
                stalled = 0
            await self._watch_sleep(max(0, WATCH_INTERVAL.total_seconds() - (time() - started)))
