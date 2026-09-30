<p align="center"><img src="docs/assets/droppilot.svg" width="88" alt="DropPilot"></p>
<h1 align="center">DropPilot</h1>
<p align="center">A modern desktop companion for Twitch Drops and watch-time redemption codes.</p>
<p align="center"><b>English</b> · <a href="README.zh-CN.md">简体中文</a> · <a href="https://github.com/dyfawa4/DropPilot/releases">Download for Windows</a></p>

## What it does

DropPilot finds eligible Twitch streams, tracks the watch time Twitch reports, claims supported regular Drops, and lets you view earned redemption codes. A dark dashboard makes priorities, progress and account status easier to follow.

Version **1.0.0** is an independent derivative of [DevilXD/TwitchDropsMiner](https://github.com/DevilXD/TwitchDropsMiner). It retains the upstream protocol layer and MIT attribution while replacing the desktop interface and adding support for Twitch's newer channel reward campaigns.

- Dark purple dashboard with a matching Windows title bar, system tray and notifications.
- Regular Drops and pure watch-time `CODE` rewards, including campaigns omitted from the older global campaign list.
- Separate progress bars for every reward. A 60-minute code becomes available without waiting for a 240-minute reward in the same campaign.
- Case-insensitive game search, ordered priorities, exclusions and automatic selection modes.
- Previous/next campaign browsing in the overview. Browsing does not switch the active stream.
- Explicit **Cancel campaign / Resume campaign** controls. Cancellation is independent of game priority and preserves Twitch's saved progress.
- Login, logout, account switching and a local HTTP/HTTPS proxy setting.
- **20 offline interface languages**, with English selected by default on a fresh installation. Changing language does not interrupt an active campaign. Arabic supports a right-to-left layout.

## Download and start

1. Download `DropPilot-Windows-1.0.0.zip` from [Releases](https://github.com/dyfawa4/DropPilot/releases).
2. Extract it to a writable folder and run `DropPilot.exe` on Windows 10/11, 64-bit. The desktop UI uses Microsoft Edge WebView2 Runtime.
3. Sign in through Twitch's official device authorization page. You do not enter your Twitch password into DropPilot.
4. Open **Settings** to select your language and campaign mode. Search for a game such as `minecraft` to add it to your priority list, or choose an automatic mode to browse other eligible campaigns.

The **Campaign inventory** shows activities, their requirements and all reward progress bars. Once Twitch confirms a code reward is earned, use **View code**, then **Copy code**. DropPilot does not redeem rewards on external sites or in games.

Use **Pause** to stop all automatic watching temporarily. Use **Cancel campaign** on the overview, an inventory card or campaign details to stop selecting streams for one activity; **Resume campaign** enables it again. Removing a game from priorities changes selection preferences. In *Priority games only* mode, that game will no longer be selected.

If one stream qualifies for multiple activities, Twitch may still count its viewing time for a cancelled activity while another activity is being watched. Cancellation cannot erase server-side progress.

**Run in background** hides the window to the system tray and continues watching. Click the tray icon to restore it. Closing the application stops its worker.

## Supported rewards and known limits

- Regular Drops retain upstream eligibility, account-link and reward-precondition rules.
- New code campaigns must require watching only and distribute `CODE` rewards. Subscriptions, gifted subscriptions, Turbo and other paid requirements are not automated.
- Badge/emote compatibility is optional; zero watch minutes alone never mean a reward has been earned.
- Displayed progress comes from Twitch. DropPilot does not invent local watch minutes or watch multiple games simultaneously for one account.
- Code delivery depends on Twitch and the campaign. A completed watch requirement does not guarantee Twitch's code endpoint is currently available. For example, Aurora Cape has returned an unavailable code through both the official inventory and the tool. Another campaign's live code delivery is being verified; see [validation notes](docs/TESTING.md).
- Twitch may delay inventory updates, omit campaigns, or stop counting an ineligible stream. DropPilot periodically checks streams again, and you can refresh manually.
- This release targets Windows. Linux/macOS packaging and automatic start at Windows login are not provided.

## Languages

English, 简体中文, 繁體中文, 日本語, Čeština, Dansk, Deutsch, Español, Français, Indonesian, Italiano, Nederlandse, Norsk, Polski, Português, Română, Türkçe, Русский, Українська and العربية.

Upstream protocol/status translations are retained. New interface strings live in `web/locales.json`; the initial additional translations use machine translation with reviewed English and selected corrections. Contributions from native speakers are welcome. Catalogs are bundled locally; changing languages sends no interface text to a translation service.

After editing `web/locales.json`, regenerate its browser bundle with `python scripts/sync_ui_locales.py`, then run the tests. `scripts/build_ui_locales.py` is an optional developer utility that regenerates translations online from static interface text only; it is never called by the app.

## Develop and test

Use Python 3.13 and Node.js 24 on Windows:

```powershell
py -3.13 -m venv env
env\Scripts\python.exe -m pip install -r requirements.txt -r requirements-modern.txt
npm ci
env\Scripts\python.exe main.py
env\Scripts\python.exe -m unittest discover -s tests -v
npm test
env\Scripts\pyinstaller.exe --noconfirm DropPilot.spec
```

The executable is written to `dist/DropPilot.exe`. GitHub Actions runs the backend checks, exercises all 20 languages and builds the same modern application. Versions remain `1.0.0`; the workflow does not append a Git revision.

The core files are `engine.py` (watch lifecycle), `rewards.py` (channel code campaigns), `modern_gui.py` (thread-safe state and command bridge), `modern_main.py` (desktop host) and `web/` (interface). The original Tk interface remains in `gui.py` for reference; the original entry point and build workflow are preserved under `docs/reference/` and are not used in the new build.

## Local data and reporting issues

Login cookies, settings, WebView storage, cache and logs stay in the application's folder and are excluded from Git. Never include these files when sharing your own copy. Code values are returned only to the view dialog; they are excluded from application snapshots, diagnostics and log exports.

When reporting a problem, include the app version, the public campaign name, the selection mode and a redacted error message. Do not post a redemption code or login session.

## License and attribution

[MIT License](LICENSE). Original work © DevilXD; DropPilot additions © DropPilot contributors. The protocol implementation derives from upstream commit `cce367b9558b7ea7c50539a086d03b6f8075c87f`. Original license notices and authorship are retained.
