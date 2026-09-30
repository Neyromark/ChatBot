# import requests
# from config import max_token
#
# response = requests.get(
#     "https://platform-api2.max.ru/me",
#     headers={"Authorization": max_token},
#     verify=False
# )
# print(response.json())

import asyncio
import logging

from save_config import settings
from database import Database
from mailing.queue import start_worker
from mailing.miniapp_link import start_miniapp_link, stop_miniapp_link
from scheduler import start_worker as start_schedule_worker, start_reminder_worker


from models import Base
from bot.dispatcher import bot, dp


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)


async def main():
    db = Database(settings.DB_CONNECTION_STRING, echo=False)
    db.connect()

    db.create_all()
    db.migrate()

    logging.info("Таблицы проверены/созданы")
    await bot.delete_webhook()
    logging.info("Webhook удалён")

    start_worker(bot)
    start_schedule_worker()
    start_reminder_worker(bot)
    start_miniapp_link(bot)


    logging.info("Запуск бота...")
    try:
        await dp.start_polling(bot)
    finally:
        await stop_miniapp_link()
        db.dispose()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Бот остановлен")