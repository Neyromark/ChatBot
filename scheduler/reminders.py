import asyncio
import logging
from datetime import datetime, timedelta

from maxapi import Bot

from db_instance import db
from models import Task, TaskInstance, User

logger = logging.getLogger(__name__)

REMIND_BEFORE_MINUTES = 10   # за сколько минут до начала и до дедлайна напоминать

_worker_task: asyncio.Task | None = None

# Уже отправленные напоминания: (вид, instance_id, момент). Хранится только в памяти.
_sent: set[tuple[str, int, datetime]] = set()


def _find(kind: str, now: datetime) -> list[dict]:
    """
    Экземпляры, у которых начало (kind="start") или дедлайн (kind="deadline")
    наступит в ближайшие REMIND_BEFORE_MINUTES минут (now < момент <= now + 10 мин).
    Проверка идёт каждую минуту, поэтому обычная задача попадает в окно ровно за 10 минут,
    а задача, созданная позже (когда до срока уже меньше 10 минут), — сразу после создания.
    Ничего не пишет в БД.
    """
    time_col = TaskInstance.planned_start if kind == "start" else TaskInstance.planned_end
    horizon = now + timedelta(minutes=REMIND_BEFORE_MINUTES)

    with db.session() as session:
        rows = (
            session.query(TaskInstance.instance_id, time_col, Task.title, User.max_id)
            .join(Task, Task.task_id == TaskInstance.task_id)
            .join(User, User.user_id == TaskInstance.assignee_user_id)
            .filter(
                TaskInstance.actual_end.is_(None),
                time_col > now,
                time_col <= horizon,
                User.max_id.isnot(None),
            )
            .all()
        )
    return [
        {"instance_id": iid, "when": when, "title": title, "max_id": max_id}
        for iid, when, title, max_id in rows
    ]


def _text(kind: str, item: dict, now: datetime) -> str:
    hhmm = item["when"].strftime("%H:%M")
    minutes = max(int((item["when"] - now).total_seconds() // 60) + 1, 1)
    if kind == "start":
        return f"Через {minutes} мин. начало выполнения задачи: {item['title']}\nНачало в {hhmm}."
    return f"Через {minutes} мин. истекает срок исполнения задачи: {item['title']}\nСрок исполнения: до {hhmm}."


async def _remind(bot: Bot) -> int:
    now = datetime.now()
    sent = 0
    for kind in ("start", "deadline"):
        for item in await asyncio.to_thread(_find, kind, now):
            key = (kind, item["instance_id"], item["when"])
            if key in _sent:
                continue
            _sent.add(key)   # помечаем ДО отправки — не будет дублей
            try:
                await bot.send_message(user_id=item["max_id"], text=_text(kind, item, now))
                sent += 1
            except Exception as e:
                logger.warning("Напоминание (%s) не доставлено %s: %s", kind, item["max_id"], e)
    # чистим отправленные напоминания, момент которых уже прошёл
    for key in [k for k in _sent if k[2] <= now]:
        _sent.discard(key)
    return sent


async def _worker(bot: Bot) -> None:
    while True:
        try:
            sent = await _remind(bot)
            if sent:
                logger.info("Напоминаний отправлено: %s", sent)
        except Exception as e:
            logger.exception("Ошибка воркера напоминаний: %s", e)
        # спим до начала следующей минуты
        now = datetime.now()
        await asyncio.sleep(max(60 - now.second - now.microsecond / 1_000_000, 1))


def start_reminder_worker(bot: Bot) -> asyncio.Task:
    global _worker_task
    if _worker_task is None or _worker_task.done():
        _worker_task = asyncio.create_task(_worker(bot))
        logger.info("Воркер напоминаний запущен (за %s мин)", REMIND_BEFORE_MINUTES)
    return _worker_task


async def stop_reminder_worker() -> None:
    global _worker_task
    if _worker_task and not _worker_task.done():
        _worker_task.cancel()
        try:
            await _worker_task
        except asyncio.CancelledError:
            pass
    _worker_task = None
