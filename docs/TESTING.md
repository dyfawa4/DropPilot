# Validation / 验证记录

## Automated checks / 自动化检查

- 30 Python tests cover reward eligibility, independent watch-time groups, partial code completion, account logout, pending request cancellation, detached snapshots and bounded logs.
- Per-campaign cancellation retains game priorities, excludes the campaign from cached selection, and leaves other campaigns available. Incidental server progress never lets a cancelled campaign take over the overview.
- Language validation checks every upstream language and the same 354 modern interface keys across all translated catalogs.
- UI tests exercise 20 languages × six pages, custom mode selection, immediate language switching, case-insensitive game search, campaign browsing, cancellation/resume and the code dialog. The demonstration code is an explicitly fake value.
- Tests verify that changing language retains the active progress, game names are preserved, code values are unchanged, and closing a code dialog removes the value from the DOM.

30 项 Python 测试覆盖奖励资格、独立计时、单项兑换码完成后刷新、账户退出、网络请求取消、状态快照与日志上限。界面测试覆盖 20 种语言与六个页面，并验证新增菜单、搜索、活动切换、取消／恢复和兑换码弹窗。示例兑换码明确标记为假值。

## Desktop and live checks / 桌面与实测

The packaged Windows desktop has been checked for UI readiness, authentication, dark native title-bar styling and real Twitch progress. An independent live test confirmed automatic campaign selection with an empty priority list and stop/pause behavior. Browser checks additionally covered keyboard selection of the custom menu and the Arabic layout.

已检查打包后的 Windows 程序启动、登录、深色原生标题栏及 Twitch 真实进度。此前实测验证空优先列表下的自动选择、暂停和取消；浏览器检查补充验证自定义菜单键盘操作及阿拉伯语布局。

CONTROL Resonant's independent code groups require 60, 120 and 240 minutes. Live progress has increased for all three groups. Delivery of the first real code is still being verified; do not interpret this as a successful real-code retrieval test yet. Aurora Cape's code has been unavailable through both the tool and the official Twitch inventory.

CONTROL Resonant 的三个兑换码奖励分别要求 60、120、240 分钟，已经读到三组真实进度增长。第一项真实兑换码的发放仍在验证，目前不能把它记为码值读取成功。Aurora Cape 在本工具和 Twitch 官方库存中均出现兑换码不可用。

No credentials, account identifiers, redemption codes, personal settings or live account snapshots are included in this repository. Longer 120/240-minute completion remains unverified in a continuous real-world run.

仓库不包含登录凭据、账户标识、真实兑换码、个人设置或实测账户快照。120／240 分钟奖励完成暂未进行连续实测。
