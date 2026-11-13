import logging
from datetime import datetime
from pathlib import Path

from vbc_analytics.inject_faults import FAULTS
from vbc_analytics.quality_checks import find_check_files, render_sql, run_check_file
from vbc_analytics.utils import PROJECT_ROOT, get_connection

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

REPORT_PATH = PROJECT_ROOT / "docs" / "CHAOS_VALIDATION.md"

# Fault names in inject_faults.py don't all match rule names in the SQL.
# This maps injected-fault names to their corresponding rule names.
FAULT_TO_RULE = {
    "null_medical_condition": "null_in_required_col",
}


def run_checks_against(cursor, target: str) -> dict[str, int]:
    """Run every DQ check file against a target table. Returns {rule: count}."""
    results: dict[str, int] = {}
    for path in find_check_files():
        raw = path.read_text(encoding="utf-8")
        sql = render_sql(raw, target)
        for rule, count in run_check_file(cursor, sql):
            results[rule] = count
    return results


def main():
    conn = get_connection()
    try:
        cursor = conn.cursor()
        log.info("Running DQ checks against 'admissions'")
        real = run_checks_against(cursor, "admissions")
        log.info("Running DQ checks against 'admissions_chaos'")
        chaos = run_checks_against(cursor, "admissions_chaos")
    finally:
        cursor.close()
        conn.close()

    injected = {FAULT_TO_RULE.get(f["name"], f["name"]): f["count"] for f in FAULTS}

    lines = [
        "# Chaos Validation Report",
        "",
        f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "Compares DQ rule failures on the real `admissions` table vs the "
        "fault-injected `admissions_chaos` table.",
        "",
        "`Delta = Chaos - Real` isolates the effect of the fault injection.",
        "",
        "| Rule | Injected | Real | Chaos | Delta | Status |",
        "|------|----------|------|-------|-------|--------|",
    ]

    total_injected = 0
    total_caught = 0

    for rule in sorted(set(real) | set(chaos)):
        inj = injected.get(rule, 0)
        r = real.get(rule, 0)
        c = chaos.get(rule, 0)
        delta = c - r

        if inj > 0 and delta >= inj:
            status = "✅ Caught"
            total_caught += inj
        elif inj > 0:
            status = "❌ Missed"
        elif delta > 0:
            status = "⚠️ Emergent"
        else:
            status = "—"

        total_injected += inj
        lines.append(f"| `{rule}` | {inj} | {r} | {c} | {delta:+d} | {status} |")

    lines += [
        "",
        f"**Injected faults caught: {total_caught} / {total_injected}**",
        "",
        "**Legend:**",
        "- ✅ Caught — delta matches injected count",
        "- ❌ Missed — injected faults did not appear in the DQ output (rule bug)",
        "- ⚠️ Emergent — no injection, but chaos shows more failures than real "
        "(cascading effect, e.g. stored LOS going stale)",
        "- — No injection, no delta",
    ]

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    log.info("Validation report written to %s", REPORT_PATH)


if __name__ == "__main__":
    main()
