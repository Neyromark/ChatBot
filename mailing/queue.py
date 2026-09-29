import asyncio
import logging

from maxapi import Bot

logger = logging.getLogger(__name__)

_queue: asyncio.Queue[int] | None = None
_worker_task: asyncio.Task | None = None


def get_queue() -> asyncio.Queue[int]:
    global _queue
    if _queue is None:
        _queue = asyncio.Queue()
    return _queue


def enqueue_announcement(announcement_id: int) -> None:
    """НЕ async — кладёт и сразу выходит. Не блокирует."""
    q = get_queue()
    q.put_nowait(announcement_id)
    logger.info("Announcement %s в очереди (size=%s)", announcement_id, q.qsize())


async def _worker(bot: Bot) -> None:
    from mailing.announcements import send_announcement

    q = get_queue()
    while True:
        announcement_id = await q.get()
        try:
            stats = await send_announcement(bot, announcement_id)
            logger.info("Рассылка %s: %s", announcement_id, stats)
        except Exception as e:
            logger.exception("Ошибка рассылки %s: %s", announcement_id, e)
        finally:
            q.task_done()


def start_worker(bot: Bot) -> asyncio.Task:
    global _worker_task
    if _worker_task is None or _worker_task.done():
        _worker_task = asyncio.create_task(_worker(bot))
        logger.info("Announcement worker запущен")
    return _worker_task


async def stop_worker() -> None:
    global _worker_task
    if _worker_task and not _worker_task.done():
        _worker_task.cancel()
        try:
            await _worker_task
        except asyncio.CancelledError:
            pass
    _worker_task = None