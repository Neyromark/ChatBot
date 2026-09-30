"""
Канал «чат-бот ⇄ мини-приложение» по WebSocket. Бот — клиент: сам подключается к
CurrentMiniAppBackend (MINIAPP_WS_URL), переподключается с нарастающей паузой; сервисы независимы
и могут запускаться/падать в любом порядке.

мини-апп → бот   {"type":"notify","id":N,"maxId":123,"text":"..."}   → отправляем в MAX и отвечаем ack
бот → мини-апп   {"type":"ack","id":N,"ok":true|false,"error":"..."}
бот → мини-апп   {"type":"event","reason":"changed","orgIds":null}   → после коммита, затронувшего задачи

Бот НЕ читает таблицы мини-аппа: уведомления приходят только по этому каналу.
"""
import asyncio
import json
import logging
import threading

import aiohttp
from maxapi import Bot
from maxapi.exceptions.max import MaxApiError
from sqlalchemy import event
from sqlalchemy.orm import Session

from models import Task, TaskInstance
from save_config import settings

logger = logging.getLogger(__name__)

EVENT_DEBOUNCE = 0.3          # сливаем серию коммитов в одно событие
_TRACKED = (Task, TaskInstance)

_task: asyncio.Task | None = None
_loop: asyncio.AbstractEventLoop | None = None
_out: asyncio.Queue | None = None
_hooks_installed = False
_pending = threading.Event()


# ---------- хуки SQLAlchemy: «коммит затронул задачи» ----------
def _install_hooks() -> None:
    global _hooks_installed
    if _hooks_installed:
        return
    _hooks_installed = True

    @event.listens_for(Session, "after_flush")
    def _after_flush(session, _ctx):
        if any(isinstance(o, _TRACKED) for o in (*session.new, *session.dirty, *session.deleted)):
            session.info["miniapp_touched"] = True

    @event.listens_for(Session, "after_commit")
    def _after_commit(session):
        if session.info.pop("miniapp_touched", False):
            notify_miniapp_changed("changed")

    @event.listens_for(Session, "after_rollback")
    def _after_rollback(session):
        session.info.pop("miniapp_touched", None)


def notify_miniapp_changed(reason: str = "changed") -> None:
    """Потокобезопасно: можно вызывать из любого потока (handlers, to_thread, scheduler)."""
    loop, q = _loop, _out
    if loop is None or q is None or not settings.MINIAPP_LINK:
        return
    if _pending.is_set():                       # уже запланировано — сольётся
        return
    _pending.set()
    try:
        loop.call_soon_threadsafe(q.put_nowait, {"type": "event", "reason": reason, "orgIds": None})
    except RuntimeError:                        # цикл уже закрыт
        _pending.clear()


# ---------- обработка сообщений мини-аппа ----------
async def _handle_notify(bot: Bot, ws: aiohttp.ClientWebSocketResponse, msg: dict) -> None:
    ok, error = False, None
    try:
        await bot.send_message(user_id=msg["maxId"], text=msg["text"])
        ok = True
    except MaxApiError as e:
        error = f"MaxApiError: {e}"
        logger.warning("Уведомление %s не доставлено: %s", msg.get("id"), e)
    except Exception as e:
        error = str(e)
        logger.exception("Уведомление %s: ошибка отправки", msg.get("id"))
    try:
        await ws.send_str(json.dumps({"type": "ack", "id": msg.get("id"), "ok": ok, "error": error},
                                     ensure_ascii=False))
    except Exception:
        logger.warning("Не удалось отправить ack %s (связь потеряна)", msg.get("id"))


async def _session(bot: Bot, http: aiohttp.ClientSession) -> None:
    headers = {"Authorization": f"Bearer {settings.BRIDGE_TOKEN}"} if settings.BRIDGE_TOKEN else {}
    async with http.ws_connect(settings.MINIAPP_WS_URL, headers=headers, heartbeat=20) as ws:
        logger.info("Связь с мини-приложением установлена (%s)", settings.MINIAPP_WS_URL)

        async def pump_out() -> None:
            while True:
                item = await _out.get()
                if item.get("type") == "event":
                    await asyncio.sleep(EVENT_DEBOUNCE)
                    _pending.clear()
                await ws.send_str(json.dumps(item, ensure_ascii=False))

        pump = asyncio.create_task(pump_out())
        try:
            async for raw in ws:
                if raw.type != aiohttp.WSMsgType.TEXT:
                    continue
                try:
                    msg = json.loads(raw.data)
                except ValueError:
                    continue
                if isinstance(msg, dict) and msg.get("type") == "notify":
                    # доставляем последовательно: MAX ограничивает частоту, порядок сообщений важен
                    await _handle_notify(bot, ws, msg)
                    await asyncio.sleep(0.05)
        finally:
            pump.cancel()
            _pending.clear()


async def _worker(bot: Bot) -> None:
    delay = 1.0
    async with aiohttp.ClientSession() as http:
        while True:
            try:
                await _session(bot, http)
                delay = 1.0
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.warning("Мини-приложение недоступно (%s): %s. Повтор через %.0f с",
                               settings.MINIAPP_WS_URL, e.__class__.__name__, delay)
            await asyncio.sleep(delay)
            delay = min(delay * 2, 30.0)


def start_miniapp_link(bot: Bot) -> asyncio.Task | None:
    global _task, _loop, _out
    if not settings.MINIAPP_LINK:
        logger.info("Связь с мини-приложением отключена (MINIAPP_LINK=false)")
        return None
    if _task is None or _task.done():
        _loop = asyncio.get_running_loop()
        _out = asyncio.Queue()
        _install_hooks()
        _task = asyncio.create_task(_worker(bot))
        logger.info("Связь с мини-приложением: %s", settings.MINIAPP_WS_URL)
    return _task


async def stop_miniapp_link() -> None:
    global _task, _loop, _out
    if _task and not _task.done():
        _task.cancel()
        try:
            await _task
        except asyncio.CancelledError:
            pass
    _task, _loop, _out = None, None, None
