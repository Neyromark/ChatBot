import asyncio
import logging

from maxapi import Bot
from maxapi.exceptions.max import MaxApiError


logger = logging.getLogger(__name__)


async def send_to_user(bot, user_id, text, attachments=None, delay=0.05):
    if delay:
        await asyncio.sleep(delay)

    logger.info("→ Отправка user_id=%r (type=%s)", user_id, type(user_id).__name__)

    if not user_id:
        logger.warning("Пустой user_id, пропускаю")
        return False

    try:
        await bot.send_message(user_id=user_id, text=text, attachments=attachments or [])
        logger.info("✅ Доставлено user_id=%s", user_id)
        return True
    except MaxApiError as e:
        logger.warning("❌ MaxApiError user_id=%s: %s", user_id, e)
        return False
    except Exception as e:
        logger.exception("❌ Ошибка user_id=%s: %s", user_id, e)
        return False


async def broadcast(
    bot: Bot,
    user_ids: list[int],
    text: str,
    attachments: list | None = None,
    delay: float = 0.05,
) -> dict:
    """
    Массовая отправка. Возвращает статистику.
    """
    ok, fail = 0, 0
    for uid in user_ids:
        if await send_to_user(bot, uid, text, attachments, delay=delay):
            ok += 1
        else:
            fail += 1

    logger.info("Broadcast: доставлено %s, ошибок %s", ok, fail)
    return {"sent": ok, "failed": fail, "total": len(user_ids)}