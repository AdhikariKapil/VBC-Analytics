import os
from pathlib import Path

import mysql.connector
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def get_connection():
    load_dotenv(PROJECT_ROOT / ".env")
    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT", 3306)),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME"),
    )


def load_sql(path: Path) -> str:
    # read .sql file from disk and return its contents as a string.
    if not path.exists():
        raise FileNotFoundError(f"SQL file not found: {path}")
    return path.read_text()
