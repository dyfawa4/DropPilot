"""DropPilot desktop entrypoint. UI and asyncio worker run independently."""
from multiprocessing import freeze_support
from pathlib import Path
import asyncio
import logging
import logging.handlers
import sys
import threading
from types import SimpleNamespace


def main():
    import truststore
    truststore.inject_into_ssl()
    import modern_gui
    from engine import Engine
    from settings import Settings
    from constants import LOCK_PATH, LOG_PATH, FILE_FORMATTER, WORKING_DIR
    from translate import _
    from utils import lock_file, resource_path
    import webview

    if "--version" in sys.argv:
        from version import __version__
        print(f"DropPilot {__version__} / TwitchDropsMiner cce367b + channel rewards")
        return
    success, lock = lock_file(LOCK_PATH)
    if not success:
        return
    args = SimpleNamespace(log=True, tray=False, dump=False,
                           debug_gql=logging.WARNING, debug_ws=logging.WARNING,
                           logging_level=logging.INFO)
    settings = Settings(args)
    _.set_language(settings.language)
    logger = logging.getLogger("TwitchDrops")
    logger.setLevel(logging.INFO)
    handler = logging.handlers.RotatingFileHandler(LOG_PATH, maxBytes=2_000_000,
                                                   backupCount=2, encoding="utf-8")
    handler.setFormatter(FILE_FORMATTER)
    logger.addHandler(handler)
    logging.getLogger("TwitchDrops.gql").setLevel(logging.WARNING)
    logging.getLogger("TwitchDrops.websocket").setLevel(logging.WARNING)
    bridge = modern_gui.Bridge()
    finished = threading.Event()

    async def worker():
        while not bridge._closing.is_set():
            modern_gui.STORE.update(phase="loading", status="正在连接 Twitch…",
                                    paused=False, channels={}, active=None, watching=None,
                                    websockets={}, earnedCodes={})
            client = Engine(settings)
            bridge._gui = client.gui
            try:
                client._run_task = asyncio.create_task(client.run())
                await client._run_task
            except asyncio.CancelledError:
                if not getattr(client, "_restart_reason", None) and not client.gui.close_requested:
                    raise
            except Exception as exc:
                logger.exception("自动获取遇到错误")
                modern_gui.STORE.update(phase="error", status="连接中断 · 点击重新连接重试")
                client.print(str(exc))
            finally:
                try:
                    await client.shutdown()
                    settings.save(force=True)
                except Exception:
                    logger.exception("关闭网络会话时遇到错误")
                if getattr(client, "_restart_reason", None) in {"reauth", "logout"}:
                    from constants import COOKIES_PATH
                    COOKIES_PATH.unlink(missing_ok=True)
                    modern_gui.STORE.update(account=None, login=None, active=None,
                                            watching=None, channels={}, earnedCodes={}, paused=True,
                                            phase="logged_out", status="已退出账户 · 登录后继续自动获取")
                if not client.gui.close_requested:
                    closed = asyncio.create_task(client.gui.wait_until_closed())
                    retry = asyncio.create_task(client.gui._retry.wait())
                    _, pending = await asyncio.wait((closed, retry), return_when=asyncio.FIRST_COMPLETED)
                    for task in pending:
                        task.cancel()
                client.gui.close_window()
            if client.gui.close_requested:
                break
        finished.set()

    def run_worker():
        asyncio.run(worker())

    if "--diagnostics" in sys.argv:
        def diagnostics():
            from time import sleep
            import json
            while not finished.is_set():
                snap = modern_gui.STORE.snapshot()
                report = {"uiReady": snap.get("uiReady", False), "phase": snap["phase"],
                          "status": snap["status"], "authenticated": bool(snap["account"]),
                          "campaigns": len(snap["campaigns"]), "channels": len(snap["channels"]),
                          "active": snap["active"], "paused": snap["paused"]}
                report["darkTitlebarApplied"] = snap.get("darkTitlebarApplied", False)
                (WORKING_DIR / "diagnostics.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
                sleep(3)
        threading.Thread(target=diagnostics, name="DropPilot-diagnostics", daemon=True).start()

    window = webview.create_window(
        "DropPilot · Drops assistant", str(resource_path("web/index.html")), js_api=bridge,
        width=1360, height=900, min_size=(1040, 700), background_color="#101016",
        text_select=True,
    )
    modern_gui.WINDOW = window
    def dark_titlebar():
        # Native Windows titlebar preserves resizing, snap and keyboard shortcuts.
        if sys.platform != "win32":
            return
        import ctypes
        try:
            hwnd = int(window.native.Handle.ToInt64())
            applied = []
            for attribute, value in ((20, 1), (34, 0x28212F), (35, 0x161010), (36, 0xEFE8E3)):
                data = ctypes.c_int(value)
                applied.append(ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    ctypes.c_void_p(hwnd), attribute, ctypes.byref(data), ctypes.sizeof(data)) == 0)
            modern_gui.STORE.update(darkTitlebarApplied=all(applied))
        except Exception:
            logger.warning("系统标题栏配色暂不可用")
    window.events.shown += dark_titlebar
    def on_closing():
        bridge._closing.set()
        if bridge._gui:
            bridge._gui.loop.call_soon_threadsafe(bridge._gui.close)
    window.events.closing += on_closing
    thread = threading.Thread(target=run_worker, name="DropPilot-worker", daemon=True)
    thread.start()
    try:
        webview.start(gui="edgechromium", private_mode=False,
                      storage_path=str(WORKING_DIR / "webview-data"),
                      icon=str(resource_path("icons/droppilot.ico")))
    finally:
        on_closing()
        finished.wait(12)
        lock.close()


if __name__ == "__main__":
    freeze_support()
    import logging.handlers
    main()
