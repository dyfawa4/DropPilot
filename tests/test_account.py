"""Check account transitions without reading or deleting real credentials."""
import asyncio
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))
sys.argv[0] = str(BASE / "modern_main.py")
import modern_gui


class AccountTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.store = modern_gui.Store()
        self.store.update(account="test-account", phase="watching", active={"minutes": 7})
        self.store.entry("campaigns", "old-account-campaign", {"claimed": True})
        self.patch = patch.object(modern_gui, "STORE", self.store)
        self.patch.start()
        self.run_task = asyncio.create_task(asyncio.Event().wait())
        self.client = SimpleNamespace(settings=SimpleNamespace(priority=["Test game"]),
            paused=False, stop_watching=Mock(), close=Mock(),
            _auth_state=SimpleNamespace(clear=Mock()),
            _session=SimpleNamespace(cookie_jar=SimpleNamespace(clear=Mock())),
            _run_task=self.run_task, change_state=Mock())
        self.gui = SimpleNamespace(_twitch=self.client, _retry=asyncio.Event())
        self.bridge = modern_gui.Bridge()
        self.bridge._gui = self.gui

    async def asyncTearDown(self):
        self.run_task.cancel()
        await asyncio.gather(self.run_task, return_exceptions=True)
        self.patch.stop()

    async def test_logout_stops_running_request_and_clears_session(self):
        result = await self.bridge._dispatch("logout", {})
        await asyncio.gather(self.run_task, return_exceptions=True)
        self.assertTrue(result["ok"])
        self.assertTrue(self.run_task.cancelled())
        self.client.stop_watching.assert_called_once()
        self.client._auth_state.clear.assert_called_once()
        self.client._session.cookie_jar.clear.assert_called_once()
        self.assertEqual(self.client.settings.priority, ["Test game"])
        self.assertEqual(self.store.snapshot()["phase"], "logged_out")
        self.assertIsNone(self.store.snapshot()["account"])
        self.assertIsNone(self.store.snapshot()["active"])
        self.assertFalse(self.store.snapshot()["campaigns"])
        self.assertFalse(self.gui._retry.is_set())

    async def test_logged_out_login_restarts_worker_without_opening_inventory(self):
        await self.bridge._dispatch("logout", {})
        with patch.object(modern_gui.webbrowser, "open") as open_browser:
            self.assertFalse((await self.bridge._dispatch("refresh", {}))["ok"])
            self.assertTrue((await self.bridge._dispatch("login", {}))["ok"])
            self.assertTrue(self.gui._retry.is_set())
            open_browser.assert_not_called()

    async def test_switch_account_requests_new_authorization(self):
        await self.bridge._dispatch("reauth", {})
        self.assertEqual(self.client._restart_reason, "reauth")
        self.assertTrue(self.gui._retry.is_set())


if __name__ == "__main__":
    unittest.main()
