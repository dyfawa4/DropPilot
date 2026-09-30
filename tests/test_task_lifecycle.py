"""Regression tests for disappearing tasks and independent scheduling."""
import asyncio
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch, AsyncMock

from constants import PriorityMode
from engine import Engine
from modern_gui import Inventory, Store
import modern_gui
import settings as settings_module
from settings import Settings
from selection import campaign_selected
from twitch import Twitch
from inventory import BaseDrop


class TaskLifecycleTests(unittest.IsolatedAsyncioTestCase):
    def setup_engine(self):
        client=object.__new__(Engine)
        client.settings=NS(priority=['Game'],exclude=set(),selected_campaigns=set(),cancelled_campaigns=set(),
            priority_mode=PriorityMode.PRIORITY_ONLY,alter=Mock(),save=Mock())
        game=NS(name='Game',is_special=lambda:False)
        client.wanted_games=[game]
        drop=NS(display=Mock())
        campaign=NS(id='started',game=game,remaining_minutes=30,first_drop=drop,
            can_earn=lambda channel: campaign.id not in client.settings.cancelled_campaigns)
        other=NS(id='other',game=game,remaining_minutes=1,first_drop=NS(display=Mock()),can_earn=lambda channel:True)
        client.inventory=[campaign]
        client.paused=False
        current=[None]
        client.watching_channel=NS(set=lambda channel:current.__setitem__(0,channel),
            get_with_default=lambda default:current[0] or default)
        client.gui=NS(tray=NS(change_icon=Mock()),channels=NS(set_watching=Mock()),publish_settings=Mock())
        channel=NS(game=game,online=True,drops_enabled=True,name='Streamer')
        return client,campaign,other,channel

    def test_started_task_survives_priority_removal_and_only_selected_task_drives_overview(self):
        client,campaign,other,channel=self.setup_engine()
        client.watch(channel,update_status=False)
        self.assertEqual(client.settings.selected_campaigns,{'started'})
        client.settings.priority.clear()
        client.inventory.append(other)
        self.assertTrue(client.can_watch(channel))
        self.assertIs(client.get_active_campaign(channel),campaign)
        self.assertFalse(campaign_selected(client.settings,other))
        client.settings.cancelled_campaigns.add('started')
        self.assertFalse(client.can_watch(channel))
        self.assertIsNone(client.get_active_campaign(channel))

    def test_pause_offline_exclusion_and_cancellation_override_started_task(self):
        client,campaign,other,channel=self.setup_engine()
        client.settings.selected_campaigns.add('started')
        client.settings.priority.clear()
        for blocker in ['paused','offline','excluded','cancelled']:
            with self.subTest(blocker=blocker):
                client.paused=blocker=='paused'
                channel.online=blocker!='offline'
                client.settings.exclude={'Game'} if blocker=='excluded' else set()
                client.settings.cancelled_campaigns={'started'} if blocker=='cancelled' else set()
                self.assertFalse(client.can_watch(channel))

    def test_task_selection_and_progress_ids_survive_settings_reload(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(settings_module,'SETTINGS_PATH',Path(folder)/'settings.json'):
            first=Settings(NS())
            first.selected_campaigns={'started'}
            first.cancelled_campaigns={'stopped'}
            first.priority=[]
            first.save()
            reloaded=Settings(NS())
            self.assertEqual(reloaded.selected_campaigns,{'started'})
            self.assertEqual(reloaded.cancelled_campaigns,{'stopped'})
            self.assertEqual(reloaded.priority,[])

    async def test_inventory_refresh_retains_complete_snapshot_until_commit(self):
        store=Store()
        store.update(campaigns={'old':{'minutes':17}})
        inventory=Inventory()
        with patch.object(modern_gui,'STORE',store),patch.object(modern_gui,'serialize_campaign',side_effect=lambda c:{'id':c.id,'minutes':c.minutes}):
            inventory.clear()
            self.assertEqual(store.snapshot()['campaigns'],{'old':{'minutes':17}})
            new=NS(id='new',minutes=18)
            await inventory.add_campaign(new)
            self.assertEqual(store.snapshot()['campaigns'],{'old':{'minutes':17}})
            inventory.replace_campaigns([new])
            self.assertEqual(store.snapshot()['campaigns'],{'new':{'id':'new','minutes':18}})

    async def test_aborted_inventory_refresh_leaves_previous_snapshot_visible(self):
        store=Store()
        store.update(campaigns={'old':{'minutes':17}})
        with patch.object(modern_gui,'STORE',store):
            Inventory().clear()
            # A failed/cancelled network fetch never commits a partial inventory.
            self.assertEqual(store.snapshot()['campaigns']['old']['minutes'],17)

    async def test_cancelled_websocket_claim_is_not_submitted(self):
        drop=NS(id='drop',campaign=NS(id='cancelled'),update_claim=Mock(),claim=AsyncMock(),display=Mock())
        client=NS(_drops={'drop':drop},watching_channel=NS(get_with_default=lambda default:None),
            campaign_selected=lambda c:False,paused=False)
        await Twitch.process_drops.__wrapped__(client,0,{'type':'drop-claim','data':{'drop_id':'drop','drop_instance_id':'fake'}})
        drop.claim.assert_not_awaited()
        drop.display.assert_not_called()

    async def test_incidental_websocket_progress_updates_record_without_starting_task(self):
        drop=NS(id='drop',name='Reward',campaign=NS(game='Game'),update_minutes=Mock(),display=Mock())
        client=NS(_drops={'drop':drop},watching_channel=NS(get_with_default=lambda default:None))
        await Twitch.process_drops.__wrapped__(client,0,{'type':'drop-progress','data':{
            'drop_id':'drop','current_progress_min':19,'required_progress_min':60}})
        drop.update_minutes.assert_called_once_with(19)
        drop.display.assert_not_called()

    async def test_paused_or_unselected_claim_guard_never_calls_network(self):
        for paused,selected in [(True,True),(False,False)]:
            client=NS(paused=paused,campaign_selected=lambda c:selected,gql_request=AsyncMock())
            drop=NS(is_claimed=False,_twitch=client,campaign=NS(),can_claim=True)
            self.assertFalse(await BaseDrop._claim(drop))
            client.gql_request.assert_not_awaited()

    def test_late_ordinary_progress_never_restores_stopped_or_other_task(self):
        for blocker in ['none', 'paused', 'cancelled', 'switched', 'other']:
            with self.subTest(blocker=blocker):
                campaign=NS(id='task')
                channel=NS(id=1)
                drop=NS(campaign=campaign,update_minutes=Mock(),display=Mock())
                client=NS(_drops={'drop':drop},paused=blocker=='paused',
                    watching_channel=NS(get_with_default=lambda default:None if blocker=='switched' else channel),
                    campaign_selected=lambda c:blocker!='cancelled',
                    get_active_campaign=lambda c:None if blocker=='other' else campaign)
                Engine.update_ordinary_progress(client,channel,{'dropID':'drop','currentMinutesWatched':19})
                drop.update_minutes.assert_called_once_with(19)
                if blocker=='none': drop.display.assert_called_once_with(countdown=False)
                else: drop.display.assert_not_called()


if __name__=='__main__': unittest.main()
