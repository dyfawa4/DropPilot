"""Ordinary rewards retain independent server progress and prerequisite rules."""
import copy
import json
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from datetime import datetime,timedelta,timezone
from unittest.mock import Mock,AsyncMock

from rewards import normalize
from utils import Game
from inventory import DropsCampaign
from constants import PriorityMode
from selection import campaign_selected


class OrdinaryRewardTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        data=json.loads((Path(__file__).resolve().parents[1]/'reward-api-redacted.json').read_text(encoding='utf-8'))['Progress']['data']['channelDropCampaignsProgress'][0]
        now=datetime.now(timezone.utc)
        data['startAt']=(now-timedelta(days=1)).strftime('%Y-%m-%dT%H:%M:%SZ')
        data['endAt']=(now+timedelta(days=1)).strftime('%Y-%m-%dT%H:%M:%SZ')
        normalized=normalize(data,Game(data['game']))
        normalized['self']['isAccountConnected']=True
        first=copy.deepcopy(normalized['timeBasedDrops'][0])
        normalized['timeBasedDrops']=[]
        for index,required in enumerate([15,30,60]):
            drop=copy.deepcopy(first)
            drop.update(id=f'drop-{index}',requiredMinutesWatched=required)
            drop['self']['currentMinutesWatched']=0
            drop['benefitEdges'][0]['benefit']['distributionType']='DIRECT_ENTITLEMENT'
            normalized['timeBasedDrops'].append(drop)
        self.client=NS(settings=NS(priority=[],exclude=set(),selected_campaigns={normalized['id']},
            cancelled_campaigns=set(),priority_mode=PriorityMode.PRIORITY_ONLY,enable_badges_emotes=False),
            paused=False,gui=NS(inv=NS(update_drop=Mock()),tray=NS(notify=Mock())),print=Mock(),
            gql_request=AsyncMock(return_value={'data':{'claimDropRewards':{'status':'ELIGIBLE_FOR_ALL'}}}))
        self.client.campaign_selected=lambda c:campaign_selected(self.client.settings,c)
        self.campaign=DropsCampaign(self.client,normalized,{})
        self.drops=list(self.campaign.drops)

    def test_server_update_does_not_invent_parallel_reward_progress(self):
        self.drops[0].update_minutes(10)
        self.assertEqual([d.real_current_minutes for d in self.drops],[10,0,0])
        self.drops[1].update_minutes(7)
        self.assertEqual([d.real_current_minutes for d in self.drops],[10,7,0])
        self.drops[0].update_minutes(15)
        self.assertEqual([d.real_current_minutes for d in self.drops],[15,7,0])

    async def test_claim_unlocks_prerequisite_without_resetting_other_progress(self):
        self.drops[1].precondition_drops=[self.drops[0].id]
        self.assertFalse(self.drops[1].can_earn())
        self.drops[0].update_minutes(15)
        self.drops[0].update_claim('fake-claim')
        self.assertTrue(await self.drops[0].claim())
        self.assertTrue(self.drops[1].can_earn())
        self.assertEqual(self.drops[2].real_current_minutes,0)
        self.assertFalse(self.campaign.finished)

    async def test_cancelled_campaign_cannot_claim_earned_ordinary_reward(self):
        self.drops[0].update_claim('fake-claim')
        self.client.settings.cancelled_campaigns.add(self.campaign.id)
        self.assertFalse(await self.drops[0]._claim())
        self.client.gql_request.assert_not_awaited()
