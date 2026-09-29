from maxapi import Bot, Dispatcher
from maxapi.webhook.fastapi import FastAPIMaxWebhook

from save_config import settings
from bot import handlers

bot = Bot(token=settings.MAX_BOT_TOKEN)

dp = Dispatcher()

dp.include_routers(handlers.router)

# webhook = FastAPIMaxWebhook(dp=dp, bot=bot)