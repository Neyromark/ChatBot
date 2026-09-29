# bot/instance.py
from maxapi import Bot, Dispatcher
from save_config import settings

BOT_TOKEN = settings.MAX_BOT_TOKEN
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()