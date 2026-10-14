import logging
from pathlib import Path

# modules
from vbc_analytics.utils import PROJECT_ROOT, get_connection, load_sql

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

log = logging.getLogger(__name__)

ADMISSION_CHAOS_TABLE = PROJECT_ROOT / "sql" / "schema" / "create_chaos_admissions.sql"

# each fault target a distinct set of admission_ids, picked in order
# from the top of the table. Total rows broken = sums of counts.

FAULTS = [
    {
        "name": "negative_billilng",
        "description": "Billing amount set to -500.00",
        "count": 5,
        "sql": "UPDATE admission_chaos SET billing_amount = -500.00 WHERE admission_id = %s",
    },
    {
        "name": "discharge_before_admission",
        "description": "Discharge date set 3 days BEFORE admission date",
        "count": 5,
        "sql": (
            "UPDATE admission_chaos "
            "SET discharge_date = DATE_SUB(date_of_admission, INTERVAL 3 DAY) "
            "WHERE admission_id = %s"
        ),
    },
    {
        "name": "age_out_of_range",
        "description": "Age set to 200",
        "count": 5,
        "sql": "UPDATE admission_chaos SET age = 200 WHERE admission_id = %s",
    },
    {
        "name": "invalid_gender",
        "description": "Gender set to 'Unknown' (outside this system's domain)",
        "count": 5,
        "sql": "UPDATE admission_chaos SET gender = 'Unknown' WHERE admission_id = %s",
    },
    {
        "name": "null_medical_condition",
        "description": "Medical condition set to NULL",
        "count": 5,
        "sql": "UPDATE admission_chaos SET medical_condition = NULL WHERE admission_id = %s",
    },
    {
        "name": "negative_room_number",
        "description": "Room number set to -1",
        "count": 3,
        "sql": "UPDATE admission_chaos SET room_number = -1 WHERE admission_id = %s",
    },
    {
        "name": "future_admission_date",
        "description": "Admission date set to year 2099",
        "count": 3,
        "sql": (
            "UPDATE admission_chaos "
            "SET date_of_admission = '2099-01-01', discharge_date = '2099-01-05' "
            "WHERE admission_id = %s"
        ),
    },
]


# helpers


def rebuild_chaos_table(cursor, sql: str):
    # it drop and recreate admission_chaos as a full copy of admission.
    for statement in sql.split(";"):
        statement = statement.strip()
        if statement:
            cursor.execute(statement)

    cursor.execute("SELECT COUNT(*) FROM admission_chaos;")
    count = cursor.fetchone()[0]
    log.info("Rebuild admission_chaos with %d rows", count)


def pick_ids(cursor, count, offset):
    # select `count` admission_ids starting at `offset`, in a stable order.
    cursor.execute(
        """
            SELECT admission_id FROM admission_chaos
            ORDER BY admission_id LIMIT %s OFFSET %s
            """,
        (count, offset),
    )
    return [row[0] for row in cursor.fetchall()]


def inject_fault(cursor, fault, ids):
    cursor.executemany(fault["sql"], [(admission_id,) for admission_id in ids])
    log.info(
        "Injected '%s' into %d rows (ids: %s)",
        fault["name"],
        len(ids),
        ", ".join(str(i) for i in ids),
    )


def main():
    conn = get_connection()
    sql = load_sql(ADMISSION_CHAOS_TABLE)
    try:
        cursor = conn.cursor()
        rebuild_chaos_table(cursor, sql)

        offset = 0
        for fault in FAULTS:
            ids = pick_ids(cursor, fault["count"], offset)
            if len(ids) < fault["count"]:
                raise RuntimeError(
                    f"Not enough rows to inject fault {fault['name']}"
                    f"(needed {fault['count']}, got {len(ids)})"
                )

            inject_fault(cursor, fault, ids)
            offset += fault["count"]

        conn.commit()
    except Exception:
        conn.rollback()
        log.exception("Fault injection failed. Rolled back.")
        raise
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    main()
