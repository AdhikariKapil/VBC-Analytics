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


def load_and_clean_csv(csv_path: Path) -> pd.DataFrame:
    log.info("Reading CSV from %s", csv_path)
    df = pd.read_csv(CSV_PATH)

    # drop PHI
    df = df.drop(columns=["Name"])

    # parse dates and derive length_of_stay
    df["Date of Admission"] = pd.to_datetime(df["Date of Admission"])
    df["Discharge Date"] = pd.to_datetime(df["Discharge Date"])
    df["LengthOfStay"] = (df["Discharge Date"] - df["Date of Admission"]).dt.days

    # rename to snake_case to match the db schema
    df = df.rename(
        columns={
            "Age": "age",
            "Gender": "gender",
            "Blood Type": "blood_type",
            "Medical Condition": "medical_condition",
            "Date of Admission": "date_of_admission",
            "Doctor": "doctor",
            "Hospital": "hospital",
            "Insurance Provider": "insurance_provider",
            "Billing Amount": "billing_amount",
            "Room Number": "room_number",
            "Admission Type": "admission_type",
            "Discharge Date": "discharge_date",
            "Medication": "medication",
            "Test Results": "test_results",
            "LengthOfStay": "length_of_stay",
        }
    )

    return df


def create_table(cursor, sql: str):
    cursor.execute(sql)


def table_has_rows(cursor) -> bool:
    cursor.execute("SELECT COUNT(*) FROM admissions")
    return cursor.fetchone()[0] > 0


def truncate_table(cursor):
    cursor.execute("TRUNCATE TABLE admissions")


def build_rows(df: pd.DataFrame) -> list:
    return [tuple(row) for row in df.itertuples(index=False, name=None)]


def insert_rows(cursor, rows: list):
    cursor.executemany(INSERT_SQL, rows)


# main
def main():
    args = parse_args()
    log.info("Starting load in '%s' mode", args.mode)

    df = load_and_clean_csv(CSV_PATH)
    rows = build_rows(df)
    log.info("Prepared %d rows for insertion", len(rows))

    schema_sql = load_sql(CREATE_ADMISSION_FILE)

    conn = get_connection()
    try:
        cursor = conn.cursor()
        create_table(cursor, schema_sql)

        if args.mode == "skip" and table_has_rows(cursor):
            log.info("Table already has data. Skipping load.")
            return

        if args.mode == "refresh":
            truncate_table(cursor)
            log.info("Table truncated.")

        insert_rows(cursor, rows)
        conn.commit()
        log.info("Successfully inserted %d rows.", len(rows))
    except Exception:
        conn.rollback()
        log.exception("Load failed. Transaction rolled back")
        raise
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    main()
