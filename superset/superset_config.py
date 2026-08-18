import os
from urllib.parse import quote_plus

DATABASE_HOST = os.getenv("DATABASE_HOST", "postgres")
DATABASE_PORT = os.getenv("DATABASE_PORT", "5432")
DATABASE_DB = os.getenv("DATABASE_DB", "pbm")
DATABASE_USER = os.getenv("DATABASE_USER", "postgres")
DATABASE_PASSWORD = os.getenv("DATABASE_PASSWORD", "postgres")

SQLALCHEMY_DATABASE_URI = (
    f"postgresql://{DATABASE_USER}:{quote_plus(DATABASE_PASSWORD)}"
    f"@{DATABASE_HOST}:{DATABASE_PORT}/{DATABASE_DB}"
)

SECRET_KEY = os.getenv("SUPERSET_SECRET_KEY", "pbm-demo-change-me")
TALISMAN_ENABLED = os.getenv("TALISMAN_ENABLED", "false").lower() in ("1", "true", "yes")

FEATURE_FLAGS = {
    "ENABLE_EXTENSIONS": True,
}

EXTENSIONS_PATH = os.getenv("EXTENSIONS_PATH", "/app/extensions")