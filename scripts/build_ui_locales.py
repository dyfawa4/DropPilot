"""Refresh the bundled UI catalogs from public, static interface strings only.

This optional developer utility uses Google's translation service. It never
loads settings, cookies, inventory, user information, game data or reward codes.
The application uses the generated files entirely offline.
"""
import concurrent.futures
import json
from pathlib import Path
import re
import time
import urllib.parse
import urllib.request

BASE = Path(__file__).resolve().parents[1]
LANGUAGES = {
    "English": "en", "简体中文": "zh-CN", "繁體中文": "zh-TW", "日本語": "ja",
    "Čeština": "cs", "Dansk": "da", "Deutsch": "de", "Español": "es",
    "Français": "fr", "Indonesian": "id", "Italiano": "it", "Nederlandse": "nl",
    "Norsk": "no", "Polski": "pl", "Português": "pt", "Română": "ro",
    "Türkçe": "tr", "Русский": "ru", "Українська": "uk", "العربية": "ar",
}

# Reviewed wording for the main workflow and new capabilities. Other text is
# generated below; contributors can improve any target language in locales.json.
REVIEWED = """
总览|Overview
活动库存|Campaign inventory
直播频道|Live channels
运行日志|Activity log
设置|Settings
关于|About
掉宝助手|Drops assistant
工作空间|Workspace
本地桌面版|Desktop edition
掉宝控制台|Drops dashboard
关注你想要的游戏，剩下的交给 DropPilot。|Choose your games. DropPilot takes care of the rewards.
优先游戏|Priority games
排除游戏|Excluded games
可获取活动|Available campaigns
优先游戏活动|Priority campaigns
在线频道|Live channels
已完成奖励|Earned rewards
正在获取奖励|Earning rewards
自动领取|Auto claim
兑换码奖励|Code reward
查看全部奖励|View all rewards
查看活动|View campaign
上一个活动|Previous campaign
下一个活动|Next campaign
活动进度|Campaign progress
已取消获取|Cancelled
取消获取|Cancel campaign
恢复获取|Resume campaign
活动已恢复获取|Campaign resumed
已取消获取，进度已保留|Campaign cancelled. Your progress is saved.
取消获取这个活动？|Cancel this campaign?
停止为该活动选择频道，已有进度保留，游戏优先顺序不变。|Stop selecting streams for this campaign. Progress and game priorities are saved.
如果同一直播还用于其他活动，Twitch 仍可能同时记录进度。|If the same stream is watched for another campaign, Twitch may still count time for both.
进度已保留|Progress saved
等待获取|Queued
刷新活动|Refresh campaigns
暂停获取|Pause
继续获取|Resume
后台运行|Run in background
收起到系统托盘，保持后台获取；点击托盘图标可恢复窗口|Hide to the system tray and keep earning. Click the tray icon to restore the window.
显示语言|Display language
语言|Language
多语言|Multilingual
立即切换界面语言，正在进行的获取不会中断。|Change the language immediately without interrupting active campaigns.
获取偏好|Earning preferences
挖掘范围|Campaign selection
获取模式|Selection mode
仅获取优先游戏|Priority games only
优先即将结束的活动|Ending soonest
优先频道较少的活动|Fewest available channels
优先获取即将结束的活动|Prioritize campaigns ending soonest
优先获取频道较少的活动|Prioritize campaigns with fewer channels
只观看优先列表中的游戏|Watch only games in your priority list
自动选择活动，按截止时间排序|Select campaigns automatically by end date
自动选择活动，优先频道较少的游戏|Select automatically, preferring fewer available channels
优先列表决定游戏顺序，排除列表始终生效。|Priorities determine game order. Exclusions always apply.
奖励完成通知|Reward notifications
奖励完成时，通过 Windows 托盘通知你。|Receive a Windows tray notification when a reward is earned.
徽章和表情奖励|Badge and emote rewards
启用额外奖励类型的兼容支持。|Enable support for additional reward types.
网络连接|Network connection
使用本机代理访问 Twitch，留空则直接连接。|Use a local proxy for Twitch. Leave blank for a direct connection.
更换代理后请重启应用，确保实时连接也使用新地址。|Restart after changing the proxy so live connections also use the new address.
代理地址|Proxy address
代理|Proxy
账户|Account
可获取活动数量|Available campaign count
保存|Save
列表越靠上，获取优先级越高。|Games higher in the list are watched first.
这些游戏的活动不会自动获取。|Campaigns for these games will not be selected automatically.
暂无排除项|No exclusions
兑换码观看活动已自动启用，无需关联游戏账号。达到要求后，可在活动库存查看、复制兑换码，再按活动说明兑换。|Watch-time code campaigns are enabled automatically. No game account link is required. Once earned, view and copy the code in your campaign inventory and follow the redemption instructions.
加入优先|Add priority
移出优先|Remove priority
加入优先游戏|Add to priority games
移出优先游戏|Remove from priority games
添加优先游戏|Add priority game
添加为优先游戏|Add as priority game
添加游戏|Add game
添加第一个游戏|Add your first game
上移|Move up
下移|Move down
移除|Remove
提高优先级|Raise priority
排除一个游戏|Exclude a game
加入排除列表|Add to exclusions
搜索游戏|Search games
输入 minecraft 等关键词|Enter keywords, such as minecraft
输入关键词搜索 Twitch 游戏分类，再点击结果选择。|Search Twitch game categories by keyword, then select a result.
输入关键词筛选，点击结果选择游戏。|Type a keyword to filter, then select a game.
没有匹配的分类，可尝试其他关键词或输入完整名称。|No matching categories. Try another keyword or enter the exact name.
个匹配 · 游戏名称不区分大小写|matches · Game search is case-insensitive
正在搜索 Twitch 分类…|Searching Twitch categories…
在线搜索暂不可用，显示已发现的游戏。|Online search is unavailable. Showing known games.
已在优先列表|Already prioritized
有进行中的活动|Active campaign
请输入游戏名称|Enter a game name
搜索游戏、活动或奖励|Search games, campaigns or rewards
搜索频道或游戏|Search channels or games
搜索运行记录|Search log entries
已获得的兑换码|Earned redemption codes
查看兑换码|View code
复制兑换码|Copy code
兑换码已复制|Code copied
已选中兑换码，按 Ctrl+C 复制|Code selected. Press Ctrl+C to copy.
点击查看真实兑换码。兑换码不会出现在运行日志中。|View the real code. Redemption codes are excluded from activity logs.
正在读取兑换码|Retrieving code
正在向 Twitch 获取这项已获得的奖励…|Retrieving this earned reward from Twitch…
兑换码暂不可用|Code temporarily unavailable
暂时无法获取兑换码，请稍后重试或打开 Twitch 库存|The code is unavailable. Try again later or check your Twitch inventory.
请稍后重试|Try again later
请按活动说明完成兑换。|Follow the campaign instructions to redeem your reward.
有效期至|Expires
观看完成后可在本工具查看和复制兑换码，也可打开 Twitch 库存。|After watching, view and copy your code here or open your Twitch inventory.
打开 Twitch 库存|Open Twitch inventory
查看 Twitch 库存|View Twitch inventory
观看任务已完成|Watch requirement completed
观看任务已完成。|Watch requirement completed.
观看完成|Watch complete
奖励已领取|Reward claimed
已领取|Claimed
已获得|Earned
尚未确认获得|Not confirmed as earned
其他活动条件|Other campaign requirements
需满足其他条件|Other requirements apply
查看 Twitch 活动条件|Check requirements on Twitch
待获取|Not earned
需要观看|Watch for
已观看|Watched
还需约|About
后完成|remaining
分钟|minutes
小时|hours
项奖励|rewards
个活动|campaigns
截止时间：|Ends:
截止|ends
详情|Details
已完成|Completed
全部|All
可获取|Available
普通掉宝|Regular Drops
兑换码|Redemption code
即将开始|Upcoming
已结束|Ended
需关联账户|Account link required
进行中|In progress
暂无观看奖励|No watch-time rewards
加载更多活动|Load more campaigns
暂时没有匹配的活动|No matching campaigns
先添加优先游戏，或切换到「全部」查看其他活动。|Add a priority game or select All to browse other campaigns.
尝试调整筛选条件，或刷新活动。|Try another filter or refresh campaigns.
还没有可观看的频道|No eligible streams yet
找到可推进的活动后，符合条件的直播频道会出现在这里。|Eligible streams will appear here when a campaign is available.
查看全部|View all
最近动态|Recent activity
实时记录|Live updates
一切准备就绪|Ready to go
活动发现和进度更新会记录在这里。|Campaign discoveries and progress updates appear here.
包含普通掉宝和兑换码奖励|Regular Drops and code rewards
按游戏顺序自动选择|Automatically selected by game priority
直播结束后自动寻找下一频道|Automatically find another stream when one ends
当前库存中已完成的奖励|Earned rewards in your current inventory
导出日志|Export log
清空|Clear
所有活动会在后台记录，最多保留最近 400 条。|The latest 400 activity entries are retained.
没有匹配的记录|No matching entries
游戏分类|Game category
状态|Status
观众|Viewers
正在观看|Watching
直播中|Live
已离线|Offline
打开频道|Open stream
切换|Switch
活动条件已核对|Campaign eligibility verified
掉宝频道|Drops stream
符合条件的频道：|Eligible streams:
频道按活动条件自动核对。|Streams are checked against campaign requirements.
账户与连接设置|Account and connection settings
退出登录|Log out
退出当前账户|Log out of this account
切换账户|Switch account
登录账户|Log in
登录并开始|Log in and start
尚未登录|Not logged in
已登录|Logged in
未登录|Not logged in
已登录 · 点击管理|Logged in · Manage account
已连接到 Twitch|Connected to Twitch
连接 Twitch 账户|Connect Twitch account
连接你的 Twitch 账户|Connect your Twitch account
通过 Twitch 官方设备授权登录。|Log in with Twitch's official device authorization.
退出登录会停止获取并清除本机新版的登录会话，游戏设置会保留。|Logging out stops earning and clears this app's local session. Game settings are kept.
将停止自动获取，并清除 DropPilot 的登录会话。游戏顺序、代理等设置会保留。之后可以重新登录或更换账户。|Stop earning and clear the DropPilot login session. Game priorities and proxy settings are kept. You can log in again or switch accounts.
重新连接 Twitch|Reconnect Twitch
将清除本地登录会话并重新进行官方授权。优先游戏和其他设置会保留。|Clear the local session and authorize again through Twitch. Priorities and other settings are kept.
登录后即可自动获取奖励。请通过 Twitch 官方网页完成授权。|Log in to start earning. Authorize through the official Twitch website.
点击下面的按钮打开 Twitch 官方授权页面，按提示输入授权码。|Open Twitch's official authorization page and enter the displayed code.
完成授权后，DropPilot 会自动继续。无需在这里输入密码。|DropPilot continues automatically after authorization. No password is needed here.
打开 Twitch 授权页|Open Twitch authorization
正在请求 Twitch 授权码|Requesting Twitch authorization code
正在请求 Twitch 授权，请稍候|Requesting Twitch authorization. Please wait.
正在请求新的授权码|Requesting a new authorization code
已退出登录，自动获取已停止|Logged out. Automatic earning has stopped.
管理|Manage
关闭|Close
取消|Cancel
稍后|Later
继续|Continue
等待登录|Waiting for login
等待活动|Waiting for campaigns
正在自动获取|Earning automatically
正在检查活动|Checking campaigns
正在选择频道|Selecting stream
需要重新连接|Reconnect required
重新连接|Reconnect
已暂停|Paused
正在连接|Connecting
连接中|Connecting
已连接|Connected
等待连接|Waiting for connection
点击登录账户|Click to log in
优先游戏已就绪|Priority games ready
先添加你想要的游戏|Add your preferred games first
正在自动寻找游戏活动|Finding game campaigns automatically
正在初始化…|Initializing…
所有进度均来自 Twitch|All progress is reported by Twitch
最近更新|Updated
真实进度|Verified progress
桌面服务暂未响应|Desktop service is not responding
设置已保存|Settings saved
已暂停，进度会保留|Paused. Your progress is saved.
已继续自动获取|Automatic earning resumed
已加入优先游戏，正在检查活动|Game prioritized. Checking campaigns.
已移除优先游戏|Game removed from priorities
优先顺序已更新|Priority order updated
已加入排除列表|Game excluded
已移出排除列表|Game removed from exclusions
操作已完成|Done
操作未完成|Action was not completed
操作失败：|Action failed:
界面正在连接桌面服务|Connecting to the desktop service
你的下一份奖励|Your next reward
登录账户，继续获取奖励。|Log in to keep earning.
休息一下，奖励不会丢。|Take a break. Your progress is saved.
准备好，等待下一次掉宝。|Ready for the next reward.
正在寻找下一份奖励…|Finding your next reward…
正在自动寻找活动。|Finding campaigns automatically.
从你喜欢的游戏开始。|Start with your favorite game.
继续获取后，会从 Twitch 保存的进度接着进行。|Resume from the progress saved by Twitch.
已达到观看要求。在活动库存查看、复制兑换码。|has met the watch requirement. View and copy the code in your campaign inventory.
正在检查活动和符合条件的直播频道，稍候会自动开始。|Checking campaigns and eligible streams. Earning will start automatically.
目前没有可推进的活动或在线频道。我们会定期重新检查，也可以手动刷新。|No eligible campaigns or live streams right now. Checks run periodically, or you can refresh.
自动模式会选择符合条件的活动，无需添加优先游戏。暂时无可观看活动时，会定期重新检查。|Automatic mode selects eligible campaigns without priorities. Checks continue periodically when no stream is available.
添加游戏到优先列表，DropPilot 就会为你寻找正在进行的掉宝活动。|Add a game to your priorities and DropPilot will find active Drops campaigns.
还没有优先游戏。添加一个，开始收集奖励。|Add a priority game to start collecting rewards.
当前使用自动模式，无需添加优先游戏。|Automatic mode is enabled. Priority games are optional.
还没有优先游戏。|No priority games yet.
自动等待|Waiting automatically
正在检查|Checking
准备好你的下一份奖励|Ready for your next reward
关于 DropPilot|About DropPilot
一个更清晰、更流畅的 Twitch 掉宝桌面工具。|A clearer, smoother desktop tool for Twitch Drops.
现代化掉宝桌面工具|A modern Twitch Drops desktop app
查看活动、观看要求与奖励进度，选择你想获取的游戏。|Browse campaigns, watch requirements and reward progress. Choose your games.
自动跟随符合活动条件的频道，也可以手动切换。|Follow eligible streams automatically or switch manually.
查看连接、活动发现与进度更新的记录。|Review connection, campaign discovery and progress updates.
调整游戏顺序、挖掘范围与连接设置。|Adjust game priorities, campaign selection and connections.
奖励与活动|Rewards and campaigns
符合活动条件的直播|Eligible live streams
连接与进度记录|Connection and progress history
游戏、账户与连接|Games, account and connection
原项目|Original project
深色控制台 · 多语言 · 独立后台任务|Dark dashboard · Multilingual · Background worker
普通掉宝 + 兑换码观看活动|Regular Drops + watch-time redemption codes
真实分钟数|Verified watch minutes
原项目 MIT License · 保留署名|Original MIT License · Attribution retained
界面|Interface
奖励|Rewards
进度|Progress
授权|License
库存|Inventory
"""


def translate_batch(values, target, source="en"):
    url = "https://translate.googleapis.com/translate_a/single?" + urllib.parse.urlencode(
        {"client": "gtx", "sl": source, "tl": target, "dt": "t", "q": "\n".join(values)})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(url, timeout=25) as response:
                payload = json.load(response)
            lines = "".join(item[0] for item in payload[0] if item[0]).split("\n")
            if len(lines) != len(values):
                if len(values) > 1:
                    middle = len(values) // 2
                    return translate_batch(values[:middle], target, source) + translate_batch(values[middle:], target, source)
                raise ValueError("Translation line count changed")
            return [value.strip() for value in lines]
        except Exception:
            if attempt == 2:
                raise
            time.sleep(attempt + 1)


def batches(items, max_chars=1800):
    batch, length = [], 0
    for item in items:
        if batch and length + len(item[1]) > max_chars:
            yield batch
            batch, length = [], 0
        batch.append(item)
        length += len(item[1]) + 1
    if batch:
        yield batch


def main():
    english = dict(line.split("|", 1) for line in REVIEWED.strip().splitlines())
    sources = ["web/app.js", "web/index.html", "modern_gui.py", "modern_main.py", "engine.py", "game_search.py", "rewards.py"]
    for source in sources:
        content = (BASE / source).read_text(encoding="utf-8")
        for word in re.findall(r"[\u4e00-\u9fff][\u4e00-\u9fffA-Za-z0-9 /·，。；、：！？「」（）…+＋:().-]*", content):
            word = word.strip()
            if len(word) <= 250:
                english.setdefault(word, None)
    missing = [key for key, value in english.items() if value is None]
    for batch in batches([(key, key) for key in missing]):
        values = translate_batch([value for _, value in batch], "en", "zh-CN")
        english.update(zip([key for key, _ in batch], values))
    if not all(english.values()):
        raise ValueError("Empty English translation")
    packs = {"简体中文": {"locale": "zh-CN", "messages": {}},
             "English": {"locale": "en", "messages": english}}
    tasks = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        for name, target in LANGUAGES.items():
            if name in packs:
                continue
            packs[name] = {"locale": target, "messages": {}}
            for batch in batches(list(english.items())):
                source = "en" if target != "zh-TW" else "zh-CN"
                values = [value if source == "en" else key for key, value in batch]
                future = pool.submit(translate_batch, values, target, source)
                tasks[future] = name, [key for key, _ in batch]
        for future in concurrent.futures.as_completed(tasks):
            name, keys = tasks[future]
            packs[name]["messages"].update(zip(keys, future.result()))
    packs = {name: packs[name] for name in LANGUAGES}
    (BASE / "web/locales.json").write_text(json.dumps(packs, ensure_ascii=False, indent=2), encoding="utf-8")
    (BASE / "web/locales.js").write_text("globalThis.DropPilotLocales=" + json.dumps(packs, ensure_ascii=False, separators=(",", ":")) + ";\n", encoding="utf-8")
    print(f"Generated {len(packs)} offline languages, {len(english)} translated UI strings each.")


if __name__ == "__main__":
    main()
