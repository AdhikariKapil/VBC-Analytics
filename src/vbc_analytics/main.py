import argparse
import logging
import os
from pathlib import Path

import mysql.connector
import pandas as pd
from dotenv import load_dotenv

# Configuration of logging and database
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CSV_PATH = PROJECT_ROOT / "data" / "healthcare_dataset.csv"
SQL_DIR = PROJECT_ROOT / "sql"
CREATE_ADMISSION_FILE = SQL_DIR / "schema" / "create_admissions.sql"

# the insert statement stays inline because it uses %s placeholders that only make sense to
# mysql-connector-python, not to a standalone SQL client
INSERT_SQL = """
    INSERT INTO admissions (
            age, gender, blood_type, medical_condition, date_of_admission, doctor, hospital, insurance_provider, billing_amount, room_number, admission_type, discharge_date, medication, test_results, length_of_stay
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
"""


# helpers
def parse_args():
    parser = argparse.ArgumentParser(description="Load healthcare CSV into MySQL")
    parser.add_argument(
        "--mode",
        choices=["refresh", "skip", "append"],
        default="refresh",
        help="refresh: truncate + reload | skip: no-op if data exists | append: insert without cleaning",
    )

    return parser.parse_args()


def load_sql(path: Path) -> str:
    # read .sql file from disk and return its contents as a string.
    if not path.exists():
        raise FileNotFoundError(f"SQL file not found: {path}")
    return path.read_text()


def get_connection():
    load_dotenv(PROJECT_ROOT / ".env")
    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT", 3306)),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME"),
    )
