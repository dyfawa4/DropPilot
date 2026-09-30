"""Language changes and per-campaign cancellation must not corrupt a live session."""
import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

from constants import State, PriorityMode
from inventory import DropsCampaign
from modern_gui import Bridge, GUIManager, Store
import modern_gui
from translate import _
from ui_locale import catalogs


class LanguageTests(unittest.TestCase):
    def test_all_upstream_languages_cover_every_new_ui_string(self):
        from settings import default_settings
        self.assertEqual(default_settings["language"], "English")
        packs = catalogs()
        self.assertEqual(set(packs), set(_.languages))
        keys = set(packs["English"]["messages"])
        self.assertGreater(len(keys), 300)
        for name, pack in packs.items():
            with self.subTest(language=name):
                self.assertTrue(pack["locale"])
                if name != "简体中文":
                    self.assertEqual(set(pack["messages"]), keys)
                    self.assertTrue(all(isinstance(value, str) and value.strip() for value in pack["messages"].values()))

    def test_browser_bundle_matches_backend_catalog(self):
        source = (Path(__file__).resolve().parents[1] / "web/locales.js").read_text(encoding="utf-8")
        self.assertEqual(json.loads(source.removeprefix("globalThis.DropPilotLocales=").strip().removesuffix(";")), catalogs())


class LanguageAndCampaignActions(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.original_language = _.current
        self.settings = SimpleNamespace(language="简体中文", priority=["Same game"], exclude=set(),
            cancelled_campaigns=set(), priority_mode=PriorityMode.PRIORITY_ONLY,
            proxy="", tray_notifications=True, enable_badges_emotes=False,
            alter=Mock(), save=Mock())
        self.campaigns = [SimpleNamespace(id="code"), SimpleNamespace(id="ordinary")]
        self.client = SimpleNamespace(settings=self.settings, inventory=self.campaigns,
            stop_watching=Mock(), change_state=Mock())
        self.gui = SimpleNamespace(_twitch=self.client, clear_drop=Mock(),
            inv=SimpleNamespace(add_campaign=AsyncMock()))
        self.gui.publish_settings = lambda: GUIManager.publish_settings(self.gui)
        self.store = Store()
        self.store.update(account="test", phase="watching", active={"minutes": 17})
        self.patch = patch.object(modern_gui, "STORE", self.store)
        self.patch.start()
        self.bridge = Bridge()
        self.bridge._gui = self.gui

    async def asyncTearDown(self):
        _.set_language(self.original_language)
        self.patch.stop()

    async def test_language_switch_keeps_heartbeat_progress_and_priorities(self):
        for language in catalogs():
            await self.bridge._dispatch("settings", {"language": language})
            self.assertEqual(_.current, language)
            self.assertEqual(self.store.data["settings"]["language"], language)
        self.client.stop_watching.assert_not_called()
        self.client.change_state.assert_not_called()
        self.assertEqual(self.store.data["active"]["minutes"], 17)
        self.assertEqual(self.settings.priority, ["Same game"])

    async def test_invalid_language_does_not_change_persisted_setting(self):
        with self.assertRaises(ValueError):
            await self.bridge._dispatch("settings", {"language": "not-a-language"})
        self.assertEqual(self.settings.language, "简体中文")
        self.settings.save.assert_not_called()

    async def test_cancel_one_campaign_leaves_other_and_game_priority_intact(self):
        await self.bridge._dispatch("campaign_cancel", {"id": "code"})
        self.assertEqual(self.settings.cancelled_campaigns, {"code"})
        self.assertEqual(self.settings.priority, ["Same game"])
        self.client.stop_watching.assert_called_once()
        self.gui.clear_drop.assert_called_once()
        self.client.change_state.assert_called_once_with(State.GAMES_UPDATE)
        self.gui.inv.add_campaign.assert_awaited_once_with(self.campaigns[0])
        await self.bridge._dispatch("campaign_resume", {"id": "code"})
        self.assertFalse(self.settings.cancelled_campaigns)

    async def test_unknown_campaign_does_not_cancel_current_watch(self):
        with self.assertRaises(ValueError):
            await self.bridge._dispatch("campaign_cancel", {"id": "unknown"})
        self.client.stop_watching.assert_not_called()

    def test_cancelled_campaign_cannot_restart_from_cached_inventory(self):
        campaign = SimpleNamespace(id="code", _twitch=self.client, eligible=True,
            _base_can_earn=Mock(return_value=True), drops=[])
        self.settings.cancelled_campaigns.add("code")
        self.assertFalse(DropsCampaign.can_earn(campaign))
        self.assertFalse(DropsCampaign.can_earn_within(campaign, None))
        campaign._base_can_earn.assert_not_called()


if __name__ == "__main__":
    unittest.main()
