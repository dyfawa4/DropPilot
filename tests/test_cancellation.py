import asyncio
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch, AsyncMock
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine import Engine
from constants import PriorityMode
from modern_gui import GUIManager
from twitch import Twitch

class CancellationTests(unittest.IsolatedAsyncioTestCase):
    async def test_inventory_cancellation_joins_all_parallel_requests(self):
        started = asyncio.Event()
        entered = 0
        finished = 0
        async def fetch(chunk):
            nonlocal entered, finished
            entered += 1
            if entered == 2:
                started.set()
            try:
                await asyncio.Event().wait()
            finally:
                finished += 1
        responses = [
            {"data": {"currentUser": {"inventory": {
                "dropCampaignsInProgress": [], "gameEventDrops": []}}}},
            {"data": {"currentUser": {"dropCampaigns": [
                {"id": str(i), "status": "ACTIVE"} for i in range(21)]}}},
        ]
        client = SimpleNamespace(gui=SimpleNamespace(status=SimpleNamespace(update=Mock())),
            gql_request=AsyncMock(side_effect=responses), fetch_campaigns=fetch)
        task = asyncio.create_task(Twitch.fetch_inventory(client))
        await started.wait()
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertEqual(finished, 2)

    async def test_cancelling_wrapper_cancels_pending_network_operation(self):
        cancelled = asyncio.Event()
        entered = asyncio.Event()
        async def network_operation():
            entered.set()
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()
        gui = SimpleNamespace(_closed=asyncio.Event())
        outer = asyncio.create_task(GUIManager.coro_unless_closed(gui, network_operation()))
        await entered.wait()
        outer.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await outer
        self.assertTrue(cancelled.is_set())

    def test_removed_and_excluded_games_cannot_restart_from_stale_channels(self):
        client = object.__new__(Engine)
        client.settings = SimpleNamespace(priority=["Other game"], exclude=set(),
                                           priority_mode=PriorityMode.PRIORITY_ONLY)
        client.paused = False
        client.wanted_games = []
        game=SimpleNamespace(name="Cancelled game",is_special=lambda:False)
        channel=SimpleNamespace(game=game,online=True,drops_enabled=True)
        client.inventory=[SimpleNamespace(id='task',game=game,can_earn=lambda channel:True)]
        client.wanted_games=[game]
        self.assertFalse(client.can_watch(channel))
        client.settings.priority.append("Cancelled game")
        self.assertTrue(client.can_watch(channel))
        client.settings.exclude.add("Cancelled game")
        self.assertFalse(client.can_watch(channel))
