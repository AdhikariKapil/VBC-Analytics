# Chaos Validation Report

**Generated:** 2026-10-31 19:26:35

Compares DQ rule failures on the real `admissions` table vs the fault-injected `admissions_chaos` table.

`Delta = Chaos - Real` isolates the effect of the fault injection.

| Rule | Injected | Real | Chaos | Delta | Status |
|------|----------|------|-------|-------|--------|
| `age_out_of_range` | 5 | 0 | 5 | +5 | ✅ Caught |
| `discharge_before_admission` | 5 | 0 | 5 | +5 | ✅ Caught |
| `future_admission_date` | 3 | 0 | 3 | +3 | ✅ Caught |
| `invalid_gender` | 5 | 0 | 5 | +5 | ✅ Caught |
| `los_inconsistent` | 0 | 0 | 8 | +8 | ⚠️ Emergent |
| `negative_billing` | 0 | 108 | 113 | +5 | ⚠️ Emergent |
| `negative_room_number` | 3 | 0 | 3 | +3 | ✅ Caught |
| `null_in_required_column` | 0 | 0 | 5 | +5 | ⚠️ Emergent |

**Injected faults caught: 21 / 21**

**Legend:**
- ✅ Caught — delta matches injected count
- ❌ Missed — injected faults did not appear in the DQ output (rule bug)
- ⚠️ Emergent — no injection, but chaos shows more failures than real (cascading effect, e.g. stored LOS going stale)
- — No injection, no delta