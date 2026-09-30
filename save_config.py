import os
from pathlib import Path

from dotenv import load_dotenv

# Загружаем .env, лежащий рядом с этим файлом, независимо от текущей директории запуска
load_dotenv(Path(__file__).resolve().parent / ".env")


def _odbc_value(value: str) -> str:
    """Значение ODBC-атрибута в фигурных скобках: пароль с «@», «;», «=» не ломает строку; «}» удваивается."""
    return "{" + value.replace("}", "}}") + "}"


class settings():
    MAX_BOT_TOKEN = os.getenv("BOT_TOKEN")

    # --- SQL Server: строка собирается из переменных окружения/.env (пароль в коде не хранится) ---
    # В Docker DB_HOST — имя контейнера БД (mssql_server), а не 127.0.0.1 (это был бы сам контейнер бота).
    DB_HOST = os.getenv("DB_HOST") or "127.0.0.1"
    DB_PORT = os.getenv("DB_PORT") or "1433"
    DB_NAME = os.getenv("DB_NAME") or "MaxBotDispecherTasks"
    DB_USER = os.getenv("DB_USER") or "sa"
    DB_PASSWORD = os.getenv("DB_PASSWORD")
    DB_DRIVER = os.getenv("DB_DRIVER") or "ODBC Driver 17 for SQL Server"
    DATABASE_URL = os.getenv("DATABASE_URL")          # не используется ботом, оставлен для совместимости
    # Полная ODBC-строка из окружения имеет приоритет; иначе собираем из DB_* выше.
    DB_CONNECTION_STRING = os.getenv("DB_CONNECTION_STRING") or (
        f"DRIVER={_odbc_value(DB_DRIVER)};"
        f"SERVER={DB_HOST},{DB_PORT};"
        f"DATABASE={_odbc_value(DB_NAME)};"
        f"UID={_odbc_value(DB_USER)};"
        f"PWD={_odbc_value(DB_PASSWORD or '')};"
        "Encrypt=no;"
        "TrustServerCertificate=yes;"
        "APP=MaxChatBot;"
    )
    # Связь с мини-приложением (отдельный сервис) по WebSocket. Выключить: MINIAPP_LINK=false
    MINIAPP_LINK = (os.getenv("MINIAPP_LINK") or "true").strip().lower() in ("1", "true", "yes", "on")
    MINIAPP_WS_URL = os.getenv("MINIAPP_WS_URL") or "ws://127.0.0.1:8000/ws/bot"
    BRIDGE_TOKEN = os.getenv("BRIDGE_TOKEN") or None      # общий секрет с CurrentMiniAppBackend
    # Секрет подписи кодов организаций. Задаётся только в .env (значение по умолчанию убрано из кода).
    # ВАЖНО: в .env должно стоять ТО ЖЕ значение, что использовалось раньше, иначе выданные коды перестанут работать.
    ORG_CODE_SECRET = os.getenv("ORG_CODE_SECRET")
