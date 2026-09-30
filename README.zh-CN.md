<p align="center"><img src="docs/assets/droppilot.svg" width="88" alt="DropPilot"></p>
<h1 align="center">DropPilot · 掉宝助手</h1>
<p align="center">现代化的 Twitch 掉宝与观看兑换码桌面工具。</p>
<p align="center"><a href="README.md">English</a> · <b>简体中文</b> · <a href="https://github.com/dyfawa4/DropPilot/releases">下载 Windows 版</a></p>

## 功能

DropPilot 会寻找符合条件的 Twitch 直播、读取真实观看时长、自动领取支持的普通掉宝，并让你查看已获得的兑换码。深色仪表盘集中展示优先游戏、活动进度和账户状态。

当前版本为 **1.01**，基于 [DevilXD/TwitchDropsMiner](https://github.com/DevilXD/TwitchDropsMiner) 独立二创。保留原项目的协议实现与 MIT 署名，重新设计桌面界面，新增 Twitch 频道兑换码活动支持。

- 深色紫色仪表盘、Windows 深色标题栏、系统托盘与奖励通知。
- 支持普通掉宝和纯观看 `CODE` 奖励，包括旧全局列表遗漏的频道活动。
- 每项奖励独立显示进度。60 分钟兑换码达到要求后即可刷新库存，不必等待同场活动的 240 分钟奖励。
- 游戏搜索忽略大小写，支持优先顺序、排除列表和自动选择模式。
- 总览支持左右浏览活动，浏览不会切换后台正在观看的直播。
- 明确的“开始获取／取消获取／恢复获取”。未选择的活动显示“开始获取”，需要关联账户的活动需先关联，已有进度保留。
- 支持登录、退出登录、切换账户和 HTTP/HTTPS 代理。
- **20 种离线界面语言**。全新安装默认 English，切换语言即时生效且不打断获取；阿拉伯语支持从右向左的布局。

## 下载与使用

1. 从 [Releases](https://github.com/dyfawa4/DropPilot/releases) 下载 `DropPilot-Windows-1.01.zip`。
2. 解压到可写目录，在 Windows 10/11 64 位系统运行 `DropPilot.exe`。桌面界面依赖 Microsoft Edge WebView2 Runtime。
3. 通过 Twitch 官方设备授权页面登录，不需要在 DropPilot 中输入 Twitch 密码。
4. 在“设置”选择界面语言和获取模式。搜索 `minecraft` 等关键词，选择游戏加入优先列表；也可以选择自动模式获取其他符合条件的活动。

“活动库存”展示活动条件和各项奖励的进度条。Twitch 确认兑换码奖励已获得后，点击“查看兑换码”，再点击“复制兑换码”。工具不会代替你在官网或游戏内兑换。

“暂停获取”会临时停止所有自动观看。“取消获取”可在总览、活动卡片或详情中停止为单个活动选择频道，之后可以“恢复获取”。取消获取和移出优先均有确认弹窗。“移出优先”只调整排序，已启动任务继续获取，停止任务请使用“取消获取”。“我的任务”独立保留已启动、已取消和已有进度的合格活动，不依赖优先列表。

在“所选任务与优先游戏”模式下，点击“开始获取”只选择这项活动，不会自动把游戏加入优先列表。符合条件的优先游戏活动也会自动排队，自动模式还可选择其他合格活动。存在活动记录或观看进度不代表已经启动任务。

需要绑定的活动在卡片和详情中显示可点击的“关联游戏账户”。这表示把 Twitch 绑定到游戏或发行商账户，与登录 Twitch 是两件事。在浏览器完成关联后返回并刷新活动；没有有效绑定链接时，按钮会打开 Twitch 库存。

如果同一直播同时满足多个活动，继续为另一活动观看时，Twitch 仍可能给已取消的活动累计时长。“取消获取”不会删除服务端进度。

“后台运行”会收起到系统托盘并继续获取，点击托盘图标可恢复窗口。关闭程序会停止后台任务。

## 支持范围与已知限制

- 普通掉宝沿用原项目的资格、账号关联和前置奖励规则。
- 新版兑换码活动仅处理纯观看、奖励类型为 `CODE` 的活动；不会自动完成订阅、赠送订阅、Turbo 等付费条件。
- 徽章和表情兼容支持为可选设置。要求观看 0 分钟不代表账户已经获得奖励。
- 显示的分钟数来自 Twitch，不使用本地估算。同一账户不会同时观看多个游戏来累计进度。
- 兑换码的发放取决于 Twitch 和活动服务。达到观看要求不保证接口当时能返回兑换码。CONTROL Resonant 的 60 分钟 Sierra Suit 兑换码已在桌面程序中成功读取；Aurora Cape 在工具和官方库存中都曾显示兑换码不可用，见[验证记录](docs/TESTING.md)。
- Twitch 可能延迟库存更新、遗漏活动或停止给不符合条件的频道计时。工具会定期检查，也可以手动刷新。
- 本版以 Windows 为目标，未提供 Linux/macOS 安装包和开机自启注册功能。

## 多语言

English、简体中文、繁體中文、日本語、Čeština、Dansk、Deutsch、Español、Français、Indonesian、Italiano、Nederlandse、Norsk、Polski、Português、Română、Türkçe、Русский、Українська、العربية。

保留原项目的网络与状态翻译；新增界面词条位于 `web/locales.json`。新增语言初版采用机器翻译，英文核心文案和部分词条经过校正，欢迎母语使用者改进翻译。语言包随程序离线提供，运行时切换语言不会向翻译服务发送内容。

修改 `web/locales.json` 后运行 `python scripts/sync_ui_locales.py` 更新浏览器语言包，再执行测试。`scripts/build_ui_locales.py` 是可选开发工具，只会在线翻译静态界面文案，不读取账户数据，程序不会调用它。

## 开发与测试

Windows 环境使用 Python 3.13 和 Node.js 24：

```powershell
py -3.13 -m venv env
env\Scripts\python.exe -m pip install -r requirements.txt -r requirements-modern.txt
npm ci
env\Scripts\python.exe main.py
env\Scripts\python.exe -m unittest discover -s tests -v
npm test
env\Scripts\pyinstaller.exe --noconfirm DropPilot.spec
```

输出文件为 `dist/DropPilot.exe`。GitHub Actions 会执行后端测试、20 种语言的界面测试，并打包现代界面。版本保持 `1.01`，构建流程不会追加 Git 提交号。

主要代码：`engine.py` 管理观看生命周期；`rewards.py` 处理频道兑换码活动；`modern_gui.py` 提供线程安全状态与指令桥接；`modern_main.py` 承载桌面窗口；`web/` 保存界面。原版 Tk 界面保留在 `gui.py` 中供参考，原入口和构建流程位于 `docs/reference/`，新版构建不使用它们。

## 本地数据与问题反馈

登录 Cookie、设置、WebView 数据、缓存和日志保存在程序目录，Git 已忽略这些文件。分享自己的程序目录时不要包含它们。兑换码仅在查看弹窗中返回，不进入状态快照、诊断记录和日志导出。

反馈问题时可提供程序版本、公开活动名称、获取模式和已脱敏的错误信息，不要上传兑换码或登录会话。

## 许可证与来源

[MIT License](LICENSE)。原始作者 DevilXD，新版改动由 DropPilot contributors 提供。协议代码基于原项目提交 `cce367b9558b7ea7c50539a086d03b6f8075c87f`，保留原许可证和署名。
