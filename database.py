import logging
import re
from pathlib import Path

import pyodbc
from contextlib import contextmanager


from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from save_config import settings
from models import Base

logger = logging.getLogger(__name__)

MIGRATION_SQL_FILE = Path(__file__).resolve().parent / "fix_weekday_mask.sql"



class Database:

    def __init__(self, connection_string: str, echo: bool = False):
        self.connection_string = connection_string
        self.echo = echo
        self._engine = None
        self._session_factory = None

    def connect(self) -> None:
        self._engine = create_engine(
            "mssql+pyodbc://",
            creator=self._get_raw_connection,
            echo=self.echo,
            fast_executemany=True,
            pool_pre_ping=True,
            pool_recycle=3600,
        )
        self._session_factory = sessionmaker(
            bind=self._engine,
            autoflush=False,
            expire_on_commit=False,
        )

    def _get_raw_connection(self):
        return pyodbc.connect(self.connection_string)

    def create_all(self) -> None:
        Base.metadata.create_all(self._engine)

    def migrate(self) -> None:
        """
        Выполняет fix_weekday_mask.sql при каждом запуске бота (create_all() существующие
        таблицы не меняет). Скрипт идемпотентен: пересоздаёт CK_Schedule_Rule_WeekdayMask
        с диапазоном 0..127 (маска 0 нужна разовым задачам).
        """
        for batch in self._read_sql_batches(MIGRATION_SQL_FILE):
            with self._engine.begin() as conn:
                result = conn.exec_driver_sql(batch)
                if result.returns_rows:
                    for row in result.fetchall():
                        logger.info("migrate: %s", tuple(row))
        logger.info("Миграция %s выполнена", MIGRATION_SQL_FILE.name)

    @staticmethod
    def _read_sql_batches(path: Path) -> list[str]:
        """
        Делит T-SQL файл на пакеты по строкам GO. Команды GO и USE понимают только
        SSMS/sqlcmd, драйвер их не примет: GO убираем, пакеты с USE пропускаем
        (база уже выбрана в строке подключения).
        """
        text = path.read_text(encoding="utf-8")
        batches = []
        for part in re.split(r"^\s*GO\s*$", text, flags=re.IGNORECASE | re.MULTILINE):
            code = re.sub(r"/\*.*?\*/", "", part, flags=re.DOTALL)          # /* ... */
            code = re.sub(r"--[^\n]*", "", code).strip()                      # -- ...
            if code and not re.match(r"USE\b", code, flags=re.IGNORECASE):
                batches.append(code)
        return batches

    def drop_all(self) -> None:
        Base.metadata.drop_all(self._engine)

    @contextmanager
    def session(self) -> Session:
        session = self._session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def test_connection(self) -> str:
        with self._engine.connect() as conn:
            return conn.exec_driver_sql("SELECT @@VERSION").scalar()

    def dispose(self) -> None:
        if self._engine:
            self._engine.dispose()