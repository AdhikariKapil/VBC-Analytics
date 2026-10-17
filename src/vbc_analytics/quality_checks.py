import argparse
import logging
from datetime import datetime
from pathlib import Path

from vbc_analytics.utils import PROJECT_ROOT, get_connection

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

CHECKS_DIR = PROJECT_ROOT / "sql" / "validation"
REPORT_PATH = PROJECT_ROOT / "docs" / "DATA_QUALITY_REPORT.md"


def parse_args():
    parser = argparse.ArgumentParser(description="Run DQ checks and write a report.")
    parser.add_argument(
        "--target",
        default="admissions",
        choices=["admissions", "chaos_admission"],
        help="Table to run DQ checks against (default: admissions)",
    )
    return parser.parse_args()


def find_check_fiels() -> list[Path]:
    # returns every .sql files under sql/validation
    files = sorted(CHECKS_DIR.glob("*.sql"))
    if not files:
        raise FileNotFoundError(f"No .sql check files found in {CHECKS_DIR}")
    return files


def render_sql(sql: str, target_table: str) -> str:
    # retarget a check file to a different table without touching the file itself
    if target_table == "admissions":
        return sql
    return sql.replace("FROM admissions", f"FROM {target_table}")


def run_check_file(cursor, sql: str) -> list[tuple[str, int]]:
    # execute one check file and return alist of (rule_name, failure_count).
    cleaned = sql.strip().rstrip(";").strip()
    cursor.execute(cleaned)
    return [(row[0], row[1]) for row in cursor.fetchall()]


def write_report(results: dict[str, list[tuple[str, int]]], target: str) -> Path:
    lines = []
    lines.append("# Data Quality Report")
    lines.append("")
    lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"**Target Table:** `{target}`")
    lines.append("")

    total_failures = 0
    for category, rows in result.items():
        lines.append(f"## {category.replace("_", " ").title()}")
        lines.append("")
        lines.append("| Rule | Failures |")
        lines.append("|------|----------|")
        for rule, count in rows:
            marker = "✔️" if count == 0 else ""
            lines.append(f"| `{rule}`{marker} | {count} |")
            total_failures += count
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(f"**Total failures across all rules:** {total_failures}")

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    return REPORT_PATH


def main():
    args = parse_args()
    log.info("Running DQ checks against '%s'", args.target)

    files = find_check_fiels()
    results: dict[str, list[tuple[str, int]]] = {}

    conn = get_connection()
    try:
        cursor = conn.cursor()
        for path in files:
            log.info("Running checks in '%s'", path.name)
            raw = path.read_text(encoding="utf-8")
            sql = render_sql(raw, args.target)
            results[path.stem] = run_check_file(cursor, sql)
    finally:
        cursor.close()
        conn.close()

    report_path = write_report(results, args.target)
    log.info("Report written to %s", report_path)


if __name__ == "__main__":
    main()
