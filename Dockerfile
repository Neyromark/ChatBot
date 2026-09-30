# CurrentChatBot — MAX-бот (long polling) + воркеры рассылок/напоминаний + WebSocket-клиент мини-аппа.
# Входящих портов НЕТ: бот сам ходит в MAX API и сам подключается к мини-аппу.
#
# Сборка для сервера (linux/amd64; на Mac с Apple Silicon — через эмуляцию):
#   docker build --platform linux/amd64 -t current-chatbot:latest .
#   docker save current-chatbot:latest -o current-chatbot-amd64.tar
#
# ВНИМАНИЕ: .env (BOT_TOKEN, DB_PASSWORD, BRIDGE_TOKEN) вшивается в образ — секреты видны каждому,
# у кого есть образ или архив .tar. Храните архив так же, как сам .env.

# bookworm (Debian 12) закреплён явно: для trixie репозиторий Microsoft подписан другим ключом.
FROM python:3.13-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    # Адреса внутри сети Docker mssql-net. python-dotenv не перекрывает уже заданные переменные,
    # поэтому эти значения главнее строк из .env (там 127.0.0.1 для локального запуска).
    # Изменить без пересборки: docker run -e DB_HOST=... -e MINIAPP_WS_URL=...
    DB_HOST=mssql_server \
    DB_PORT=1433 \
    MINIAPP_WS_URL=ws://current-miniapp-backend:8000/ws/bot

# Microsoft ODBC Driver 17 for SQL Server (нужен pyodbc). Тот же драйвер, что у мини-аппа.
# Ключ кладётся в /usr/share/keyrings/microsoft-prod.gpg: prod.list для Debian ссылается на него через signed-by.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl gnupg2 apt-transport-https ca-certificates \
    && curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor > /usr/share/keyrings/microsoft-prod.gpg \
    && curl -fsSL "https://packages.microsoft.com/config/debian/$(. /etc/os-release && echo "$VERSION_ID")/prod.list" > /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql17 unixodbc libgssapi-krb5-2 \
    && apt-mark manual libgssapi-krb5-2 \
    && apt-get purge -y --auto-remove curl gnupg2 apt-transport-https \
    && rm -rf /var/lib/apt/lists/* \
    # драйвер должен загружаться: иначе сборка падает сразу, а не бот на сервере
    && ! ldd /opt/microsoft/msodbcsql17/lib64/libmsodbcsql-17*.so* | grep -q "not found"

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

# Код бота и .env (save_config.py читает /app/.env).
COPY . .

RUN useradd --system --uid 10001 --home-dir /app app && chown -R app:app /app
USER app

# Бот без HTTP-сервера: проверяем, что процесс main.py жив.
HEALTHCHECK --interval=60s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import os,sys; sys.exit(0 if any(b'main.py' in open(f'/proc/{p}/cmdline','rb').read() for p in os.listdir('/proc') if p.isdigit()) else 1)"

CMD ["python", "main.py"]
