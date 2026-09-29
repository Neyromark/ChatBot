import logging

from maxapi import Bot
from sqlalchemy.orm import Session

from db_instance import db
from models import Announcement, AnnouncementRecipient, User
from mailing.sender import broadcast


logger = logging.getLogger(__name__)

def get_unread_max_ids(session: Session, announcement_id: int) -> list[int]:
    """
    Возвращает MAX user_id всех получателей объявления, у которых is_read = False.
    Внутренний User.UserId маппится на User.MaxId через JOIN.
    """
    rows = (
        session.query(User.max_id)
        .join(AnnouncementRecipient,
              AnnouncementRecipient.user_id == User.user_id)
        .filter(
            AnnouncementRecipient.announcement_id == announcement_id,
            AnnouncementRecipient.is_read == False,
            User.max_id.isnot(None),
        )
        .all()
    )
    return [r[0] for r in rows]


def format_announcement_text(ann: Announcement) -> str:
    title = ann.title or "Без заголовка"
    return f"{title}\n\n{ann.body}"


async def send_announcement(bot: Bot, announcement_id: int) -> dict:
    from bot.ManagerTextAndButton import Buttons

    with db.session() as session:
        ann = (
            session.query(Announcement)
            .filter(Announcement.announcement_id == announcement_id)
            .first()
        )
        if ann is None:
            logger.warning("Announcement %s not found", announcement_id)
            return {"sent": 0, "failed": 0, "total": 0}

        # 👇 Внутренние UserId → MAX user_id
        max_ids = get_unread_max_ids(session, announcement_id)
        text = format_announcement_text(ann)

    if not max_ids:
        logger.info("Announcement %s: нет получателей", announcement_id)
        return {"sent": 0, "failed": 0, "total": 0}

    attachments = [Buttons.builder_announcement_read(announcement_id).as_markup()]

    stats = await broadcast(bot, max_ids, text, attachments=attachments)
    logger.info("Announcement %s broadcast: %s", announcement_id, stats)
    return stats