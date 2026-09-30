import os
class settings():
    MAX_BOT_TOKEN = os.getenv("BOT_TOKEN")
    DB_PASSWORD = os.getenv("DB_PASSWORD")
    DATABASE_URL = os.getenv("DATABASE_URL")
    DB_CONNECTION_STRING = (
        "DRIVER={ODBC Driver 17 for SQL Server};"
        "SERVER=127.0.0.1,1433;"
        "DATABASE=MaxBotDispecherTasks;"
        "UID=sa;"
        "PWD=YourStrong@Password1;"
        "Encrypt=no;"
        "TrustServerCertificate=yes;"
        "APP=MyPythonApp;"
    )
    ORG_CODE_SECRET= "QDXdZB3tAs7nlpxi"