from save_config import settings
from database import Database


db = Database(settings.DB_CONNECTION_STRING, echo=False)
db.connect()