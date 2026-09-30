"""UI adapter: no widgets or networking on the desktop's UI thread.

The worker owns miner objects. The web UI receives immutable JSON snapshots and
queues validated commands back to that worker. No tokens cross the UI bridge.
"""
from __future__ import annotations

import asyncio
import copy
import logging
import threading
import time
import webbrowser
from collections import deque
from datetime import datetime
from types import SimpleNamespace
from urllib.parse import urlsplit

from constants import State, PriorityMode
from exceptions import ExitRequest
from yarl import URL
from version import __version__
from translate import _


class Store:
    def __init__(self):
        self.lock = threading.RLock()
        self.revision = 0
        self.data = {"status": "准备连接 Twitch…", "phase": "loading", "account": None,
                     "paused": False, "channels": {}, "campaigns": {}, "games": [],
                     "settings": {}, "active": None, "watching": None, "websockets": {}, "earnedCodes": {},
                     "login": None, "logs": [], "started": time.time(), "version": __version__}

    def update(self, **values):
        with self.lock:
            if any(self.data.get(k) != v for k, v in values.items()):
                self.data.update(values)
                self.revision += 1

    def entry(self, section, key, value):
        with self.lock:
            if self.data[section].get(str(key)) != value:
                self.data[section][str(key)] = value
                self.revision += 1

    def remove(self, section, key):
        with self.lock:
            self.data[section].pop(str(key), None)
            self.revision += 1

    def log(self, message, level="info"):
        with self.lock:
            self.data["logs"].append({"time": datetime.now().strftime("%H:%M:%S"),
                                      "message": str(message), "level": level})
            self.data["logs"] = self.data["logs"][-400:]
            self.revision += 1

    def snapshot(self, revision=-1):
        with self.lock:
            if revision == self.revision:
                return {"revision": self.revision}
            return {"revision": self.revision, **copy.deepcopy(self.data)}


STORE = Store()
WINDOW = None


def image_url(value):
    value = str(value or "")
    if urlsplit(value).scheme not in ("http", "https"):
        return ""
    return value.replace("{width}", "285").replace("{height}", "380")


def serialize_drop(drop):
    return {"id": drop.id, "name": drop.name, "rewards": drop.rewards_text(),
            "image": image_url(drop.benefits[0].image_url) if drop.benefits else "",
            "minutes": drop.real_current_minutes, "required": drop.required_minutes,
            "claimed": drop.is_claimed, "earned": getattr(drop, "earned", drop.is_claimed),
            "available": drop.can_earn(),
            "reward": bool(getattr(drop.campaign, "is_reward", False)),
            "rewardStatus": getattr(drop, "reward_status", ""),
            "campaign": drop.campaign.id, "game": drop.campaign.game.name,
            "campaignName": drop.campaign.name}


def serialize_campaign(campaign):
    drops = list(campaign.drops)
    # Upstream uses zero-minute drops as an engine skip condition. It is not
    # evidence that the account earned a subscription or other non-watch reward.
    finished = bool(drops) and all(
        d.is_claimed or (bool(getattr(campaign, "is_reward", False)) and getattr(d, "earned", False))
        for d in drops)
    return {"id": campaign.id, "name": campaign.name, "game": campaign.game.name,
            "image": image_url(campaign.image_url), "eligible": campaign.eligible,
            "active": campaign.active, "upcoming": campaign.upcoming,
            "finished": finished, "earnable": campaign.can_earn(), "end": campaign.ends_at.isoformat(),
            "cancelled": campaign.id in getattr(getattr(getattr(campaign, "_twitch", None), "settings", None), "cancelled_campaigns", set()),
            "start": campaign.starts_at.isoformat(),
            "reward": bool(getattr(campaign, "is_reward", False)),
            "link": campaign.link_url,
            "channels": [c.name for c in campaign.allowed_channels],
            "drops": [serialize_drop(d) for d in drops]}


class Status:
    def update(self, text):
        STORE.update(status=str(text))

    def clear(self):
        self.update("")


class Login:
    def __init__(self, gui):
        self.gui = gui

    def update(self, status, user_id):
        account = getattr(self.gui._twitch._auth_state, "user_login", str(user_id)) if user_id is not None else None
        STORE.update(account=account)
        if user_id is not None:
            STORE.update(login=None)

    async def ask_enter_code(self, page_url, user_code):
        STORE.update(login={"url": str(page_url), "code": user_code},
                     status="请在浏览器完成 Twitch 登录", phase="login")
        # User explicitly presses the in-app login button to open the browser.

    def clear(self, **kwargs):
        pass

    async def ask_login(self):
        raise RuntimeError("请使用 Twitch 官方设备授权登录")


class Progress:
    def minute_almost_done(self):
        return True

    def stop_timer(self):
        pass


class Inventory:
    def clear(self):
        STORE.update(campaigns={})

    async def add_campaign(self, campaign):
        STORE.entry("campaigns", campaign.id, serialize_campaign(campaign))

    def update_drop(self, drop):
        STORE.entry("campaigns", drop.campaign.id, serialize_campaign(drop.campaign))
        with STORE.lock:
            active = STORE.data["active"]
        if active and active["id"] == drop.id:
            STORE.update(active=serialize_drop(drop))


class Channels:
    def __init__(self):
        self.selected = None

    def display(self, channel, *, add=False):
        STORE.entry("channels", channel.id, {"id": channel.id, "name": channel.name,
                    "url": str(channel.url), "online": channel.online,
                    "game": channel.game.name if channel.game else "—",
                    "viewers": channel.viewers or 0, "drops": channel.drops_enabled,
                    "verified": channel.acl_based})

    def remove(self, channel):
        STORE.remove("channels", channel.id)

    def clear(self):
        self.selected = None
        STORE.update(channels={})

    def get_selection(self):
        return self.selected

    def clear_selection(self):
        self.selected = None

    def set_watching(self, channel):
        STORE.update(watching=channel.id, phase="watching")

    def clear_watching(self):
        STORE.update(watching=None)


class Websockets:
    def update(self, idx, status=None, topics=None):
        with STORE.lock:
            value = dict(STORE.data["websockets"].get(str(idx), {}))
        if status is not None:
            value["status"] = status
        if topics is not None:
            value["topics"] = topics
        STORE.entry("websockets", idx, value)

    def remove(self, idx):
        STORE.remove("websockets", idx)


class Tray:
    def __init__(self, gui):
        self.gui = gui
        self.icon = None

    def start(self):
        import pystray
        from PIL import Image
        from utils import resource_path
        from ui_locale import text
        try:
            image = Image.open(resource_path("icons/droppilot.ico"))
            self.icon = pystray.Icon("DropPilot", image, "DropPilot", menu=pystray.Menu(
                pystray.MenuItem(lambda item: text("总览"), lambda: self.restore(), default=True),
                pystray.MenuItem(lambda item: text("关闭"), lambda: self.gui.loop.call_soon_threadsafe(self.gui.close)),
            ))
            self.icon.run_detached()
        except Exception as exc:
            STORE.log("托盘图标启动失败：" + str(exc), "warning")

    def restore(self):
        if WINDOW is not None:
            WINDOW.show()
            WINDOW.restore()

    def minimize(self):
        if self.icon is None:
            raise ValueError("系统托盘暂不可用，请使用窗口最小化按钮")
        if WINDOW is not None:
            WINDOW.hide()

    def notify(self, message, title="奖励完成", **kwargs):
        from ui_locale import text
        if self.icon and self.gui._twitch.settings.tray_notifications:
            try:
                self.icon.notify(message, text(title))
            except Exception:
                pass

    def change_icon(self, state):
        phase = {"idle": "idle", "maint": "loading", "active": "watching", "error": "error"}.get(state)
        if phase and not STORE.data["paused"]:
            STORE.update(phase=phase)

    def update_title(self, drop):
        from ui_locale import text
        if self.icon:
            self.icon.title = "DropPilot · " + (drop.rewards_text() if drop else text("掉宝助手"))

    def stop(self):
        if self.icon:
            self.icon.stop()
            self.icon = None


class UIHandler(logging.Handler):
    def emit(self, record):
        # Only normal messages. Never enable request/payload logging in the UI.
        if record.name.endswith((".gql", ".websocket")):
            return
        STORE.log(self.format(record), "error" if record.levelno >= 40 else
                  "warning" if record.levelno >= 30 else "info")


class GUIManager:
    def __init__(self, twitch):
        self._twitch = twitch
        self.loop = asyncio.get_running_loop()
        self._closed = asyncio.Event()
        self._retry = asyncio.Event()
        self.status = Status()
        self.login = Login(self)
        self.inv = Inventory()
        self.channels = Channels()
        self.progress = Progress()
        self.websockets = Websockets()
        self.tray = Tray(self)
        self.help = SimpleNamespace(_invalidate_button=SimpleNamespace(config=lambda **k: None))
        self._handler = UIHandler()
        logging.getLogger("TwitchDrops").addHandler(self._handler)
        self.publish_settings()

    def publish_settings(self):
        s = self._twitch.settings
        STORE.update(settings={"priority": list(s.priority), "exclude": sorted(s.exclude),
                               "mode": s.priority_mode.value, "proxy": str(s.proxy),
                               "notifications": s.tray_notifications,
                               "badges": s.enable_badges_emotes,
                               "language": s.language,
                               "cancelledCampaigns": sorted(s.cancelled_campaigns)})
        if WINDOW is not None:
            try:
                from ui_locale import text
                WINDOW.set_title("DropPilot · " + text("掉宝助手"))
            except Exception:
                pass

    @property
    def close_requested(self):
        return self._closed.is_set()

    @property
    def running(self):
        return not self.close_requested

    def start(self):
        if self.tray.icon is None:
            self.tray.start()

    def prevent_close(self):
        pass

    def close(self, *args):
        self._closed.set()
        self._twitch.close()

    async def wait_until_closed(self):
        await self._closed.wait()

    async def coro_unless_closed(self, coro):
        task = asyncio.ensure_future(coro)
        closing = asyncio.create_task(self._closed.wait())
        try:
            done, _ = await asyncio.wait((task, closing), return_when=asyncio.FIRST_COMPLETED)
            if closing in done:
                raise ExitRequest()
            return await task
        finally:
            for item in (task, closing):
                if not item.done():
                    item.cancel()
            await asyncio.gather(task, closing, return_exceptions=True)

    def save(self, *, force=False):
        pass

    def stop(self):
        pass

    def close_window(self):
        self.tray.stop()
        logging.getLogger("TwitchDrops").removeHandler(self._handler)
        if self.close_requested and WINDOW is not None:
            try:
                WINDOW.destroy()
            except Exception:
                pass

    def grab_attention(self, *, sound=True):
        self.tray.restore()

    def set_games(self, games):
        STORE.update(games=sorted(set(g.name for g in games) | set(self._twitch.settings.priority)))

    def display_drop(self, drop, **kwargs):
        STORE.update(active=serialize_drop(drop))
        self.tray.update_title(drop)

    def clear_drop(self):
        STORE.update(active=None)

    def print(self, message):
        STORE.log(message)


class Bridge:
    """The complete allowlisted public API exposed to the local webview."""
    def __init__(self):
        self._gui = None
        self._closing = threading.Event()

    def get_state(self, revision=-1):
        return STORE.snapshot(int(revision))

    def ui_ready(self):
        STORE.update(uiReady=True)
        STORE.log("桌面界面已连接")
        return {"ok": True}

    def action(self, name, payload=None):
        if name not in {"pause", "resume", "refresh", "priority_add", "priority_remove",
                        "priority_move", "exclude_add", "exclude_remove", "settings", "switch",
                        "open", "login", "tray", "quit", "clear_logs", "reauth", "logout", "export_logs",
                        "read_code", "search_games", "campaign_cancel", "campaign_resume"}:
            return {"ok": False, "error": "未知操作"}
        payload = payload or {}
        if not isinstance(payload, dict):
            return {"ok": False, "error": "操作参数格式错误"}
        if self._gui is None:
            return {"ok": False, "error": "正在启动，请稍后再试"}
        future = asyncio.run_coroutine_threadsafe(self._dispatch(name, payload), self._gui.loop)
        try:
            return future.result(timeout=40 if name == "read_code" else 10 if name == "search_games" else 5)
        except Exception as exc:
            future.cancel()
            if name == "read_code":
                return {"ok": False, "error": "暂时无法获取兑换码，请稍后重试或打开 Twitch 库存"}
            return {"ok": False, "error": str(exc)}

    async def _dispatch(self, name, payload):
        gui = self._gui
        client = gui._twitch
        settings = client.settings
        if name == "search_games":
            from game_search import search_games
            result = await search_games(client, payload.get("query", ""), STORE.data["games"])
            if result["games"]:
                STORE.update(games=sorted(set(STORE.data["games"]) | set(result["games"])))
            return result
        elif name == "pause":
            client.paused = True
            client.stop_watching()
            client.change_state(State.IDLE)
            STORE.update(paused=True, phase="paused", status="已暂停自动获取")
        elif name == "resume":
            if STORE.data["phase"] == "logged_out":
                gui._retry.set()
                return {"ok": True}
            client.paused = False
            STORE.update(paused=False, phase="loading")
            client.change_state(State.INVENTORY_FETCH)
        elif name == "refresh":
            if STORE.data["phase"] == "logged_out":
                return {"ok": False, "error": "请先登录 Twitch 账户"}
            if STORE.data["phase"] == "error":
                gui._retry.set()
            else:
                client.change_state(State.INVENTORY_FETCH)
        elif name in {"campaign_cancel", "campaign_resume"}:
            campaign_id = str(payload.get("id", ""))
            campaign = next((c for c in client.inventory if c.id == campaign_id), None)
            if campaign is None:
                raise ValueError("活动已变更，请刷新后重试")
            if name == "campaign_cancel":
                settings.cancelled_campaigns.add(campaign_id)
                # Stop the current heartbeat before scheduling another activity.
                client.stop_watching()
                gui.clear_drop()
            else:
                settings.cancelled_campaigns.discard(campaign_id)
            settings.alter()
            settings.save()
            gui.publish_settings()
            await gui.inv.add_campaign(campaign)
            client.change_state(State.GAMES_UPDATE)
        elif name in {"priority_add", "priority_remove", "exclude_add", "exclude_remove"}:
            game = str(payload.get("game", "")).strip()
            if not game or len(game) > 160:
                raise ValueError("请输入完整的 Twitch 游戏分类名称")
            from game_search import normalized
            known = STORE.data["games"] + list(settings.priority) + list(settings.exclude)
            game = next((g for g in known if normalized(g) == normalized(game)), game)
            if name == "priority_add":
                settings.exclude.discard(game)
                if game not in settings.priority:
                    settings.priority.append(game)
            elif name == "priority_remove":
                if game in settings.priority:
                    settings.priority.remove(game)
            elif name == "exclude_add":
                settings.exclude.add(game)
            else:
                settings.exclude.discard(game)
            channel = client.watching_channel.get_with_default(None)
            if channel is not None and channel.game is not None and channel.game.name == game:
                if name == "exclude_add" or (name == "priority_remove"
                        and settings.priority_mode is PriorityMode.PRIORITY_ONLY):
                    client.stop_watching()
            settings.alter()
            settings.save()
            gui.publish_settings()
            client.change_state(State.INVENTORY_FETCH)
        elif name == "priority_move":
            game = str(payload["game"])
            idx = settings.priority.index(game)
            target = max(0, min(len(settings.priority) - 1, idx + int(payload["direction"])))
            settings.priority.insert(target, settings.priority.pop(idx))
            settings.alter()
            settings.save()
            gui.publish_settings()
            client.change_state(State.GAMES_UPDATE)
        elif name == "settings":
            if "language" in payload:
                from ui_locale import catalogs
                language = str(payload["language"])
                if language not in catalogs():
                    raise ValueError("Unrecognized language")
                _.set_language(language)
                settings.language = language
            if "mode" in payload:
                settings.priority_mode = PriorityMode(int(payload["mode"]))
            if "notifications" in payload:
                settings.tray_notifications = bool(payload["notifications"])
            if "badges" in payload:
                settings.enable_badges_emotes = bool(payload["badges"])
            if "proxy" in payload:
                proxy = str(payload["proxy"]).strip()
                parts = urlsplit(proxy)
                if proxy and (parts.scheme not in {"http", "https"} or not parts.hostname or parts.username):
                    raise ValueError("请输入 HTTP/HTTPS 代理地址，例如 http://127.0.0.1:7898")
                settings.proxy = URL(proxy)
            settings.save()
            gui.publish_settings()
            if any(key != "language" for key in payload):
                client.change_state(State.INVENTORY_FETCH)
        elif name == "switch":
            channel = client.channels.get(int(payload["id"]))
            if channel is None or not client.can_watch(channel):
                raise ValueError("此频道当前无法推进选定活动")
            gui.channels.selected = channel
            client.change_state(State.CHANNEL_SWITCH)
        elif name in {"open", "login"}:
            if name == "login" and STORE.data["phase"] == "logged_out":
                gui._retry.set()
                return {"ok": True}
            url = str(payload.get("url", "https://www.twitch.tv/drops/inventory"))
            parsed = urlsplit(url)
            if parsed.scheme != "https" or not parsed.hostname or parsed.username:
                raise ValueError("仅支持安全的 HTTPS 网页链接")
            webbrowser.open(url)
        elif name == "read_code":
            if not STORE.data["account"]:
                raise ValueError("请先登录 Twitch 账户")
            from rewards import reward_code
            task = asyncio.create_task(reward_code(client, str(payload.get("id", ""))))
            client._code_tasks.add(task)
            try:
                code = await asyncio.wait_for(task, timeout=30)
                if self._gui is not gui or not STORE.data["account"]:
                    raise ValueError("账户已退出")
                # Deliberately excluded from STORE, logs, exports and diagnostics.
                return {"ok": True, "code": code}
            finally:
                client._code_tasks.discard(task)
        elif name == "tray":
            gui.tray.minimize()
        elif name == "quit":
            self._closing.set()
            gui.close()
            if WINDOW is not None:
                WINDOW.destroy()
        elif name == "clear_logs":
            STORE.update(logs=[])
        elif name == "export_logs":
            from constants import WORKING_DIR
            path = WORKING_DIR / "DropPilot-日志.txt"
            snapshot = STORE.snapshot()
            path.write_text("\n".join(f"{r['time']} [{r['level']}] {r['message']}"
                                      for r in snapshot["logs"]), encoding="utf-8")
            return {"ok": True, "message": "日志已保存到程序目录：DropPilot-日志.txt"}
        elif name in {"reauth", "logout"}:
            client.paused = True
            client.stop_watching()
            for task in tuple(getattr(client, "_code_tasks", ())):
                task.cancel()
            client._restart_reason = name
            client._auth_state.clear()
            if client._session is not None:
                client._session.cookie_jar.clear()
            client.close()
            run_task = getattr(client, "_run_task", None)
            if run_task is not None:
                run_task.cancel()
            STORE.update(account=None, login=None, active=None, watching=None, channels={}, earnedCodes={},
                         campaigns={}, games=list(settings.priority),
                         paused=True, phase="logged_out", status="已退出账户 · 登录后继续自动获取")
            if name == "reauth":
                gui._retry.set()
        return {"ok": True}
