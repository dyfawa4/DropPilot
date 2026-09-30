# Validation / 验证记录

## Automated checks / 自动化检查

- 56 Python tests cover task selection and persistence, priority removal, cancellation and resume, pause/offline/exclusion guards, account switching, eligibility, independent progress, claim prerequisites, request cancellation, atomic inventory refresh and code snapshot privacy.
- Started campaign IDs are independent of priority ordering. Removing a priority retains the task; cancelling it prevents selection and automatic claiming. Incidental Twitch progress updates the record without starting a task or taking over the overview.
- Late progress responses after pause, cancellation or channel switching retain reported minutes without reviving the stopped task or sending completion notifications.
- Inventory refresh commits a complete snapshot. Interrupted or failed refreshes do not replace the display with an empty or partial inventory.
- Unclaimed zero-minute rewards are not marked completed. Ordinary progress changes only the reward Twitch reports; separate code groups keep their own confirmed watch time.
- UI checks cover 20 languages × six pages and 363 translation keys, language switching, case-insensitive search, campaign browsing, custom menus, start/cancel/resume, account-link buttons and code dialogs.
- Cancellation and priority removal are tested with confirmation, dismissal and Escape. Cancelling an unrelated task does not clear the current task. Removing an active task's priority keeps its progress and overview card.
- Link-required activities show an enabled account-link action without selecting a task. Invalid binding URLs fall back to Twitch inventory.
- Fake demonstration codes are explicitly labelled. Closing the code dialog removes its value from the DOM.

56 项 Python 测试覆盖任务选择与持久化、移出优先、取消与恢复、暂停／离线／排除、账户切换、资格判断、独立进度、领取前置条件、请求取消、库存原子刷新以及兑换码快照隐私。界面测试覆盖 20 种语言、六个页面和 363 项词条，并验证确认弹窗、开始／取消／恢复、关联按钮、搜索、活动切换和兑换码弹窗。

## Desktop and live checks / 桌面与实测

The Windows desktop has been checked for startup, authentication, dark title-bar styling and real Twitch progress. A dedicated live CONTROL Resonant regression verified all seven conditions: task started, watching continued after priority removal, refresh retained the task, Twitch progress increased, cancellation stopped watching, cancellation retained the record, and resuming worked without adding the game back to priorities. The test used one watch worker and did not change personal settings.

已检查 Windows 桌面启动、登录、深色标题栏及 Twitch 真实进度。CONTROL Resonant 专项实测通过七项条件：启动任务、移出优先后继续观看、刷新后保留记录、服务端进度增长、取消后停止观看、取消后保留记录、不加入优先也能恢复。实测仅运行一个观看工作进程，未改动个人设置。

CONTROL Resonant's code groups require 60, 120 and 240 minutes. Live progress has increased for all three groups, and the 60-minute Sierra Suit code was successfully displayed in the desktop app. Aurora Cape was unavailable in both the official Twitch inventory and the tool, so that failure does not establish a general code-endpoint failure. Continuous completion of the 120/240-minute rewards remains unverified.

CONTROL Resonant 的三组兑换码奖励分别要求 60、120、240 分钟，已读到各组真实进度增长，60 分钟 Sierra Suit 兑换码已在桌面程序成功显示。Aurora Cape 在 Twitch 官方库存和本工具均不可用，该现象不能证明通用兑换码接口故障。120／240 分钟奖励的连续完成仍未实测。

No credentials, account identifiers, real redemption codes, personal settings, private logs or live account snapshots are included in the repository or release archive. These checks cover the stated scenarios; they are not a guarantee that every Twitch campaign or upstream service response is supported.

仓库与发布压缩包不包含登录凭据、账户标识、真实兑换码、个人设置、私人日志或实测账户快照。以上检查覆盖所列场景，不代表所有 Twitch 活动或服务端响应均已验证。
