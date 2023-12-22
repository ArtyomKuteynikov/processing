import os
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

DB_HOST = os.environ.get("DB_HOST")
DB_PORT = os.environ.get("DB_PORT")
DB_NAME = os.environ.get("DB_NAME")
DB_USER = os.environ.get("DB_USER")
DB_PASS = os.environ.get("DB_PASS")

AUTH_URL = os.environ.get("AUTH_URL")
WALLET_URL = os.environ.get("WALLET_URL")
SUMSUB_URL = os.environ.get("SUMSUB_URL")
NOTIFICATION_URL = os.environ.get("NOTIFICATION_URL")

LINK = os.environ.get("LINK")

MIGRATION_TABLE = os.environ.get("MIGRATION_TABLE")

SECRET_AUTH = os.environ.get("SECRET_AUTH")
SECRET_SYSTEM = os.environ.get("SECRET_SYSTEM")

CAPTCHA_ID = os.environ.get("CAPTCHA_ID")
CAPTCHA_KEY = os.environ.get("CAPTCHA_KEY")
CAPTCHA_SERVER = os.environ.get("CAPTCHA_SERVER")


class Settings(BaseModel):
    authjwt_secret_key: str = SECRET_AUTH
    authjwt_algorithm: str = "HS256"
    authjwt_access_token_expires: int = 3600  # default 15 minute
    authjwt_refresh_token_expires: int = 31000000  # default 30 days
