import os
from pathlib import Path

from dotenv import load_dotenv

# Загружаем .env, лежащий рядом с этим файлом, независимо от текущей директории запуска
load_dotenv(Path(__file__).resolve().parent / ".env")


class settings():
    MAX_BOT_TOKEN = os.getenv("BOT_TOKEN")
    DB_PASSWORD = os.getenv("DB_PASSWORD")
    DATABASE_URL = os.getenv("DATABASE_URL")
    DB_CONNECTION_STRING = os.getenv("DB_CONNECTION_STRING") or (
        "DRIVER={ODBC Driver 17 for SQL Server};"
        "SERVER=127.0.0.1,1433;"
        "DATABASE=MaxBotDispecherTasks;"
        "UID=sa;"
        "PWD=YourStrong@Password1;"
        "Encrypt=no;"
        "TrustServerCertificate=yes;"
        "APP=MyPythonApp;"
    )
    # Связь с мини-приложением (отдельный сервис) по WebSocket. Выключить: MINIAPP_LINK=false
    MINIAPP_LINK = (os.getenv("MINIAPP_LINK") or "true").strip().lower() in ("1", "true", "yes", "on")
    MINIAPP_WS_URL = os.getenv("MINIAPP_WS_URL") or "ws://127.0.0.1:8000/ws/bot"
    BRIDGE_TOKEN = os.getenv("BRIDGE_TOKEN") or None      # общий секрет с CurrentMiniAppBackend
    ORG_CODE_SECRET = os.getenv("ORG_CODE_SECRET") or "QDXdZB3tAs7nlpxi"
