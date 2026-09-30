import asyncio
import copy
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rewards import earned_codes, reward_code
import modern_gui

class CodeTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.nodes = [{"id": "own-earned-reward", "status": "CLAIMABLE",
            "campaign": {"id": "campaign-a", "name": "Test", "game": {"name": "Test game"}},
            "item": {"id": "catalog-reward-id", "name": "Test reward", "distributionType": "CODE"}}]
        self.calls = []
        async def request(query):
            self.calls.append(query)
            if query["operationName"] == "Inventory":
                return {"data": {"currentUser": {"inventory": {"earnedDropRewards": {
                    "edges": [{"node": n} for n in self.nodes]}}}}}
            return {"data": {"currentUser": {"inventory": {"rewardValue": {
                "value": "EXAMPLE-UNIT-TEST-ONLY", "expiresAt": None}}}}}
        self.client = SimpleNamespace(gql_request=request, _code_tasks=set(), settings=SimpleNamespace())

    async def test_inventory_metadata_excludes_code_and_entitlements(self):
        other = copy.deepcopy(self.nodes[0])
        other["id"] = "direct-entitlement"
        other["item"]["distributionType"] = "DIRECT_ENTITLEMENT"
        self.nodes.append(other)
        metadata = await earned_codes(self.client)
        self.assertEqual(list(metadata), ["own-earned-reward"])
        self.assertNotIn("value", metadata["own-earned-reward"])
        self.assertEqual(len(self.calls), 1)

    async def test_rejects_reward_not_in_authenticated_inventory(self):
        with self.assertRaises(ValueError):
            await reward_code(self.client, "another-account-reward")
        self.assertEqual(len(self.calls), 1)

    async def test_code_is_returned_only_to_view_action(self):
        store = modern_gui.Store()
        store.update(account="test-account")
        bridge = modern_gui.Bridge()
        bridge._gui = SimpleNamespace(_twitch=self.client)
        with patch.object(modern_gui, "STORE", store):
            result = await bridge._dispatch("read_code", {"id": "own-earned-reward"})
        self.assertEqual(result["code"]["value"], "EXAMPLE-UNIT-TEST-ONLY")
        self.assertNotIn("EXAMPLE-UNIT-TEST-ONLY", str(store.snapshot()))
        self.assertFalse(self.client._code_tasks)
        self.assertEqual(self.calls[-1]["variables"]["rewardID"], "catalog-reward-id")

    async def test_logout_can_cancel_code_request_in_flight(self):
        event = asyncio.Event()
        async def slow_query(query):
            event.set()
            await asyncio.Event().wait()
        self.client.gql_request = slow_query
        store = modern_gui.Store()
        store.update(account="test-account")
        bridge = modern_gui.Bridge()
        bridge._gui = SimpleNamespace(_twitch=self.client)
        with patch.object(modern_gui, "STORE", store):
            task = asyncio.create_task(bridge._dispatch("read_code", {"id": "own-earned-reward"}))
            await event.wait()
            for child in tuple(self.client._code_tasks):
                child.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
        self.assertFalse(self.client._code_tasks)
