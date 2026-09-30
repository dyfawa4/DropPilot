"""Twitch's channel reward groups, adapted to the original mining engine.

Only WATCH requirements qualify. Each channel is verified by Twitch, and reward
minutes are never estimated. Codes are fetched only when the user views them.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from constants import GQLPersistedQuery, State
from inventory import DropsCampaign, TimedDrop
from utils import Game, timestamp
from exceptions import MinerException

logger = logging.getLogger("TwitchDrops")
PROGRESS_QUERY = GQLPersistedQuery(
    "DropChannelCampaignsProgress",
    "ec6d1267667ef9e0bfbe11eef9e04e344b0a5384c4300dc685e75c27ac7b5a0b",
    variables={"channelID": ...},
)
CODE_INVENTORY_QUERY = GQLPersistedQuery(
    "Inventory", "e7197a7e03be13e423118005966d097a2f44045b3642bfdb70820e01c8129fd6",
    variables={"fetchRewardCampaigns": True},
)
CODE_QUERY = GQLPersistedQuery(
    "RewardCodeModal", "b48d2bd6e80366684092d14c97ced7a86497246c4dab0f3d877c7a308eefdd7f",
    variables={"rewardCampaignID": ..., "rewardID": ...},
)


async def earned_codes(twitch):
    response = await twitch.gql_request(CODE_INVENTORY_QUERY)
    inventory = ((response.get("data") or {}).get("currentUser") or {}).get("inventory") or {}
    result = {}
    for edge in (inventory.get("earnedDropRewards") or {}).get("edges") or []:
        node = edge.get("node") or {}
        item, campaign = node.get("item") or {}, node.get("campaign") or {}
        if item.get("distributionType") != "CODE" or not node.get("id") or not campaign.get("id"):
            continue
        game = campaign.get("game") or {}
        result[node["id"]] = {"id": node["id"], "campaign": campaign["id"],
            "rewardID": item.get("id") or node["id"],
            "name": item.get("name") or "兑换码奖励", "campaignName": campaign.get("name") or "",
            "game": game.get("displayName") or game.get("name") or "",
            "image": item.get("thumbnailURL") or "", "status": node.get("status") or "EARNED",
            "earnedAt": node.get("earnedAt") or ""}
    return result


async def reward_code(twitch, reward_id):
    # IDs must come from this account's earned inventory, never from arbitrary input.
    rewards = await earned_codes(twitch)
    metadata = rewards.get(reward_id)
    if metadata is None:
        raise ValueError("Twitch 尚未确认这项奖励已获得，请稍后刷新")
    response = await twitch.gql_request(CODE_QUERY.with_variables({
        "rewardCampaignID": metadata["campaign"], "rewardID": metadata["rewardID"]}))
    value = (((response.get("data") or {}).get("currentUser") or {}).get("inventory") or {}).get("rewardValue") or {}
    if not value.get("value"):
        raise ValueError("Twitch 暂未返回兑换码，请稍后重试或打开 Twitch 库存")
    return {"value": str(value["value"]), "expiresAt": value.get("expiresAt"), "name": metadata["name"]}


def watch_groups(data):
    for group in data.get("rewardGroups") or []:
        criteria = group.get("progressCriteria") or {}
        req = criteria.get("requirements") or {}
        if (criteria.get("requirementType") == "WATCH"
                and (req.get("minutesWatched") or 0) > 0
                and not req.get("subs") and not req.get("turboSubs")):
            rewards = group.get("rewards") or []
            # Badge/emote opt-in remains separate; do not bypass account linking
            # for direct entitlements. CODE requires no linked game account.
            if rewards and all(r.get("distributionType") == "CODE" for r in rewards):
                yield group


def normalize(data, game):
    groups = list(watch_groups(data))
    if not groups:
        return None
    drops = []
    for group in groups:
        edge = group.get("self") or {}
        required = group["progressCriteria"]["requirements"]["minutesWatched"]
        drops.append({
            "id": group["id"], "name": group["name"],
            "startAt": data["startAt"], "endAt": data["endAt"],
            "preconditionDrops": [], "requiredMinutesWatched": required,
            "benefitEdges": [{"benefit": {
                "id": r["id"], "name": r["name"], "distributionType": "CODE",
                "imageAssetURL": r.get("thumbnailURL") or data.get("imageURL") or "",
            }} for r in group["rewards"]],
            "self": {"dropInstanceID": None, "isClaimed": edge.get("status") == "CLAIMED",
                     "currentMinutesWatched": edge.get("currentMinutesWatched") or 0},
            "rewardStatus": edge.get("status") or "IN_PROGRESS",
        })
    return {
        "id": data["id"], "name": data["name"],
        "game": {"id": str(game.id), "name": game.name, "slug": game.slug,
                 "boxArtURL": data.get("imageURL") or ""},
        "self": {"isAccountConnected": False},
        "accountLinkURL": "https://www.twitch.tv/drops/inventory",
        "startAt": data["startAt"], "endAt": data["endAt"], "status": "ACTIVE",
        "allow": {"channels": []}, "timeBasedDrops": drops,
    }


class RewardDrop(TimedDrop):
    def __init__(self, campaign, data, claimed_benefits):
        super().__init__(campaign, data, claimed_benefits)
        self.reward_status = data.get("rewardStatus", "IN_PROGRESS")

    @property
    def earned(self):
        return self.is_claimed or self.real_current_minutes >= self.required_minutes

    @property
    def can_claim(self):
        # CODE rewards are issued by Twitch. Ordinary drop claim IDs do not apply.
        return False

    def _base_earn_conditions(self):
        return super()._base_earn_conditions() and not self.earned

    def update_minutes(self, new_minutes):
        self.real_current_minutes = min(self.required_minutes, max(0, int(new_minutes or 0)))
        self.extra_current_minutes = 0
        self._on_state_changed()

    def _bump_minutes(self, channel):
        return False


class RewardCampaign(DropsCampaign):
    is_reward = True

    def __init__(self, twitch, data, game, channels):
        normalized = normalize(data, game)
        if normalized is None:
            raise ValueError("No supported watch-time code rewards")
        super().__init__(twitch, normalized, {})
        self.timed_drops = {d["id"]: RewardDrop(self, d, {})
                            for d in normalized["timeBasedDrops"]}
        # These are verified channels, not an assumption that every stream earns it.
        self.allowed_channels = list(channels)
        self.redemption_url = data.get("detailsURL") or ""

    @property
    def eligible(self):
        return True

    @property
    def finished(self):
        return all(drop.earned for drop in self.drops)

    def bump_minutes(self, channel):
        pass


async def channel_rewards(twitch, channel):
    response = await twitch.gql_request(PROGRESS_QUERY.with_variables({"channelID": str(channel.id)}))
    return response.get("data", {}).get("channelDropCampaignsProgress") or []


async def discover(twitch, ordinary_campaigns, reward_games=()):
    """Discover rewards even when the old dashboard omits them entirely."""
    known_games = {c.game.name: c.game for c in ordinary_campaigns}
    games = []
    for name in twitch.settings.priority:
        if name in twitch.settings.exclude:
            continue
        game = known_games.get(name)
        if game is None:
            try:
                response = await twitch.gql_request({
                    "operationName": "FindRewardGame",
                    "query": "query FindRewardGame($name: String!) { game(name: $name) { id name displayName slug boxArtURL } }",
                    "variables": {"name": name},
                })
                data = response.get("data", {}).get("game")
                if data:
                    game = Game(data)
            except MinerException:
                logger.warning("无法查找奖励游戏：%s", name)
        if game is not None:
            games.append(game)
    # Auto mode also considers available reward games from the global dashboard.
    if twitch.settings.priority_mode.value != 0:
        for game in reward_games:
            if game.name not in twitch.settings.exclude and game not in games:
                games.append(game)
    found = {}
    async def probe(game):
        try:
            channels = await twitch.get_live_streams(game, limit=3, drops_enabled=True)
            if not channels:
                channels = await twitch.get_live_streams(game, limit=3, drops_enabled=False)
            for channel in channels:
                for data in await channel_rewards(twitch, channel):
                    if not list(watch_groups(data)) or not data.get("game"):
                        continue
                    if int(data["game"]["id"]) != game.id:
                        continue
                    now = datetime.now(timezone.utc)
                    if not timestamp(data["startAt"]) <= now < timestamp(data["endAt"]):
                        continue
                    channel.acl_based = True
                    channel._stream.drops_enabled = True
                    key = data["id"]
                    if key in found:
                        found[key].allowed_channels.append(channel)
                    else:
                        found[key] = RewardCampaign(twitch, data, game, [channel])
        except MinerException as exc:
            logger.warning("奖励活动探测失败 (%s): %s", game.name, exc)
    # Bound work and preserve Twitch's existing GQL rate limiter.
    semaphore = asyncio.Semaphore(3)
    async def bounded(game):
        async with semaphore:
            await probe(game)
    await asyncio.gather(*(bounded(game) for game in games))
    return list(found.values())


async def refresh_progress(twitch, channel):
    campaigns = [c for c in twitch.inventory
                 if isinstance(c, RewardCampaign) and channel in c.allowed_channels
                 and c.active]
    if not campaigns:
        return False
    try:
        data_by_id = {d["id"]: d for d in await channel_rewards(twitch, channel)}
    except MinerException as exc:
        logger.warning("兑换码奖励进度查询失败：%s", exc)
        return True  # Suppress estimated progress even on network errors.
    newly_earned = []
    for campaign in campaigns:
        data = data_by_id.get(campaign.id)
        if not data:
            # Twitch says this channel no longer qualifies. Select another verified stream.
            campaign.allowed_channels = [c for c in campaign.allowed_channels if c != channel]
            twitch.change_state(State.INVENTORY_FETCH)
            continue
        groups = {g["id"]: g for g in watch_groups(data)}
        for drop in campaign.drops:
            if drop.id not in groups:
                continue
            edge = groups[drop.id].get("self") or {}
            was_earned = drop.earned
            drop.is_claimed = edge.get("status") == "CLAIMED"
            drop.reward_status = edge.get("status") or "IN_PROGRESS"
            drop.update_minutes(edge.get("currentMinutesWatched") or 0)
            if drop.earned and not was_earned and campaign.id not in getattr(twitch.settings, "cancelled_campaigns", set()):
                newly_earned.append(drop)
            logger.info("奖励真实进度：%s %s/%s 分钟 (%s)", drop.name,
                        drop.real_current_minutes, drop.required_minutes, drop.reward_status)
    # Progress for every group can arrive together. Only the selected campaign
    # may drive the overview, and cancelled campaigns never take over the view.
    selected = (twitch.get_active_campaign(channel) if hasattr(twitch, "get_active_campaign")
                else next((c for c in campaigns if c.can_earn(channel)), None))
    if selected and (next_drop := selected.first_drop) is not None:
        next_drop.display(countdown=False)
    for drop in newly_earned:
        twitch.print(f"观看任务已完成：{drop.name}。可在活动库存查看兑换码。")
        twitch.gui.tray.notify(drop.name + " · 在活动库存查看兑换码", "奖励完成")
    if newly_earned:
        # A 60-minute code must be available without waiting for the 240-minute
        # group in the same campaign. Preserve the remaining groups and minutes.
        twitch.change_state(State.INVENTORY_FETCH)
    return True
