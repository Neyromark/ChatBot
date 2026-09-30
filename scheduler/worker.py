import asyncio
import logging

from db_instance import db
from services import generate_regular_instances, REGULAR_DAYS_AHEAD

logger = logging.getLogger(__name__)

DAYS_AHEAD = REGULAR_DAYS_AHEAD   # текущая и следующая недели (как на сайте)
INTERVAL_SECONDS = 3600   # как часто дополняем (раз в час)

_worker_task: asyncio.Task | None = None


def _generate_once() -> int:
    with db.session() as session:
        return generate_regular_instances(session, days_ahead=DAYS_AHEAD)


async def _worker() -> None:
    while True:
        try:
            # синхронная работа с БД — выносим из event loop
            created = await asyncio.to_thread(_generate_once)
            logger.info("Регулярные задачи: создано экземпляров %s", created)
        except Exception as e:
            logger.exception("Ошибка генерации регулярных задач: %s", e)
        await asyncio.sleep(INTERVAL_SECONDS)


def start_worker() -> asyncio.Task:
    global _worker_task
    if _worker_task is None or _worker_task.done():
        _worker_task = asyncio.create_task(_worker())
        logger.info("Воркер регулярных задач запущен")
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
