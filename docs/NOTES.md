# VBC-Analytics - Learning Notes

A running log of domain conepts, technical decisions for the vbc-analytics project. Updated as I build.


---

## 1. Project Overview
**Name:** `VBC-Analytics`

**Goal:** Build a healthcare claims data pipeline and analytics prototype that ingests claims-like
data, validates it against clinical and structural rules, stores it in MySQL, and surfaces quality insights.

**Why this shape:** This mirrors the work of professionals who works with data and supports a value-based care (VBC) analyticsc.
Ingesting, cleaning, validating and queryinng healthcare data. Not building ML models. Building
the foundation that models depends on.

**Stack (chosen to match industry tools):**
-Python (pandas, mysql-connector-python, python-dotenv)
-Mysql (MariaDB locally)

---

## 2. Healthcare Domain Knowledge

### 2.1 Value-Based Care (VBC)

Two payment models in US healthcare:

-**Fee-For-Service (FFS):** Provider is paid for each service delivered.
Incentive: do more like more test, more procedures, more nights in hospital.
-**Value-Based Care (VBC):** Provider is paid based on patients outcomes and
total cost of care for a defined population. Incentive: keep patients well.

Under VBC, providers often recieve a **capitated payment** - a fixed upfront
amount to manage a population (eg. "$10M to manage 1000 diabetics for year.").
If actual spend is less, the provider keeps the difference as profit. If more,
they absorb the loss.

Key insights: **In VBC, providers profit by preventing care, not by delivering
it - but only if patients stay healty.**

### 2.2 Risk Adjustment & HCC

You cannot judge a provider without adjusting for how sick their patients are.
Otherwise doctors who treat the sickest patients look worst on cost.

- **HCC (Hierarchical Condition Category):** A CMS (Centers for Medicare and Medicaids Services)
risk-adjustment model. Every diagnosis maps to a category with a risk weight. Sum of weights
become a patient's risk score.
- **Risk score:** A prediction of a patient's expected future cost. Computed
*before* the cost occurs - it is a forecast, not a record.

### 2.3 Key VBC Metrics

- **PMPM (Per Member Per Month):** Cost per patient per month. Standard normalizer
in VBC contracts.
- **Attribution:** Assigning each patient to a primary care provider. Determines
who is accountable for outcomes.
- **Care Gap:** A recommened service that a patient with a chronic condition has not
received (eg. diabetic without recent HbA1c test).
-**Potentially Avoidable Admission:** An ER visit or hospitalization that could have
been prevented with better outpatient care. VBC penalizes these.

### 2.4 Cliams Data

The billing records created when a provider submits a bill to an insurer. Primary data
source for VBC analytics. Contains diagnosis codes (ICD-10), procedure codes, provider
IDs, dates, and amounts.

## 3. Data Privacy & Goverance

### 3.1 PHI - Protected Health Information

Under HIPAA, 18 indentifiers combined with health data make a record PHI. The most common
ones are names, address, phone, email, SSN, dates (except year), medical record numbers.

### 3.2 Why we dropped `Name`

- It is PHI. Storing it introduces legal liability without analytical value.
- Analytics works on populations, not individuals. Names contribute nothing.
- Real architecture separates identity from clinical data. (Identity table and Clinical table)

### 3.3 Minimum Necessary Principle

Analytics engineers almost never need to touch PHI tables. Dropping `Name` at ingestion is a
demonstration of this principle.

---

## 4. Database Concepts

### 4.1 Database Schema Types

- **Conceptual Schema:** The high-level view of what the business needs - entities,
relationships, business rules. No mentioni of tables, columns or SQL. You'd
describe it in plain English or an ER diagram.
Example: "A patient has many admissions; each admission has one provider and one hospital."

- **Logical Schema:** The same thing translated into a specific data model - usally relational.
Tables, columns, keys, foreign keys. No mention of storage. This is what my create_admissions.sql
file is. It says "there is a table admissions, it has these columns with these types." Portable
you could implement it in MySQL, PostgreSQL, etc

- **Physical Schema:** How the data is actually stored on disk. Indexes, partitions, file
organization, storage engines (InnoDB vs MyISAM), tablespaces, sharding. This is DBA territory
Example: "admission is stored in InnoDB, partitioned by admission year, with a B-tree index
on medical_condition."


### 4.2 Keys

- **Natural key:** A column that exists in the data and is unique (eg. `claims_id`, `patient_id`).
Real datasets have these
- **Surrogate key:** An invented identifier (eg. `AUTO_INCREMENT`). Used when no natural
key exists. Our dataset required this.
- **Primary key:** The unique identifier for a row. Not null, not repeated.

### 4.3 Why we created `admission_id`

Our synthetic dataset has no natural key. No unique column. No patient ID. So we added
a surrogate key. This is also why we can't do incremental loads or longitudinal analysis,
the data is a snapshot, not a time seires.

### 4.4 DECIMAL vs FLOAT

`FLOAT` is imprecise (ie. 0.1 + 0.2 != 0.3) because of floating point representation and
has approximate values, the computer may produce a slightly different result. Never
use it for money. Use `DECIMAL(precision, scale)` for exact arithmetic. We used `DECIMAL(10, 2)`
for `billing_amount`.

### 4.5 Transaction - ACID

Every write happens inside a transaction. Changes are staged until `COMMIT`. On error,
`ROLLBACK` undoes everythinig. This is **atomicity** - either the whole batch succeeds or
none of it does.

---

## 5. ETL & Data Engineering

### 5.1 What "ETL" Means

- **Extracts:** Read from a source (CSV, API, database)
- **Transform:** Clean, validate, rename, enrich
- **Load:** Insert into target system (database, warehouse).

My `main.py` is a small ETL pipeline.

### 5.2 Batch vs Loop Inserts

Looping 55000 `INSERT` statement = 55000 round-trips between Python and MySQL. Slow and
crash-fragile.

`executemany()` = one batched operation. Fast, atomic.

**Rule:** Round-trips are expensive. Bytes are cheap.

### 5.3 Idempotency and Load Modes

An **idempotent** script produces the same result no matter how many times it runs. We
support three modes:

- `refresh` (default): drop/tranculate + reload. Reproducible.
- `skip`: if data exists, do nothing.
- `append`: insert without cleaning. Requires a natural key to avoid duplicates - which
this dataset lacks.

### 5.4 CREATE TABLE IF NOT EXISTS — a Trap

`IF NOT EXISTS` checks the *name*, not the columns. If an old table with the
same name but a different schema exists, it silently does nothing. Then your
`INSERT` fails with "Unknown column."

Fix for reproducible pipelines: `DROP TABLE IF EXISTS` + `CREATE TABLE`.

### 5.5 SQL in files vs inline

- **Standalone SQL** (schema, analytical queries) -> `.sql` files.
Reviewable, executable by a DBA, version-controlled as SQL.
- **SQL that depends on Python** (parameterized `INSERT` with %s) -> inline.
It is not valid SQL on its own.

### 5.6 ORM vs Raw SQL

- **Object Relational Mapping** (SQLALchemy, Hibernate): Used by application developers.
Portable, type-safe, hides SQL.
- **Raw SQL** (`.sql` files + connector): Used by data engineers and analysts.
Transparent, tunable and reviewable.

---

## 6. Data Quality (DQ)

### 6.1 Two Categories

**Structural DQ (objectively wrong):**
- Null in required column
- Negative billing amount
- Age outside 0-150
- Discharge date before admission date
- Invalid value in a coded column (eg. gender, admission_type)

**Clinical / Domain DQ (suspicious, not broken):**
- Emergency bills lower than Elective
- Cancer cheaper than Arthritis
- Long stays for minor conditions

Structural rules can be automated. Clinical rules requires domain knowledge.

### 6.2 Severity Levels

- **Warning:** Unusual but possible. Flag, do not block.
- **Reject:** Impossible but isolated. Quarantine to a `rejected_*` table.
- **Fatal:** Systemic pattern. Halt the pipeline, alert a human.

Blindly quarantining on every failure is dangerous. A systemic bug would silently empty
the main table. Blindly halting on envery warning is fragile.

### 6.3 Fault Injection

You cannot trust a DQ rule until you have seen it fire.

**Fault injection:** Deliberately corrupt a known number of rows, run the DQ rules, and
confirm the failures match what you injected. If they don't, the rules are broken.

This is how we validate DQ rules before trusting a clean report.

### 6.4 Fault Injection - Design Decisions

**Ordered rows, not random:**
Faults target specific `admission_id` ranges (1-5, 6-10, ...) in a fixed order. This makes
runs deterministic and reproducible. Random selection would need a seed to be reliable,
and would obscure which IDs were broken. Ordered rows also make the DQ report traceable -
every failing ID maps back to a known injection

**UPDATE, not INSERT:**
Faults corrupt existing rows in place rather than adding new ones. Reasons:
- Row count stays constant (55500), so chaos vs real comparison is purely a
value diff, not a count diff
- It mirros the real failure mode: production data usally arrives corrupted in place,
not as extra garbage rows.
- Every failing row in the DQ report maps to a known injected ID.

---

## 7. Project Structure

```
vbc-analytics/
├── data/
│   └── healthcare_dataset.csv  # raw source (gitignored)
├── docs/
│   ├── NOTES.md
│   └── DATA_QUALITY_REPORT.md
├── sql/
│   └── schema/
│       └── create_admissions.sql  # standalone schema DDL
├── src/
│   └── vbc_analytics/
│       ├── __init__.py
│       ├── main.py  # ETL: CSV → MySQL
│       ├── inject_faults.py  # chaos table builder
│       └── utils.py  # DRY module (generic helpers)
├── .env  # DB credentials (gitignored)
├── .gitignore
└── pyproject.toml
```
---

## 8. Design Decision Log
| Decision | Rationale |
|----------|-----------|
| Dropped `Name` at ingestion | PHI; no analytical value |
| Table named `admissions` (not `patients`) | One row per visit, not per person |
| Added `admission_id` surrogate key | No natural key exists in this dataset |
| `Decimal(10, 2)` for billing | Exact arithmetic for money |
| Batch insert with `executemany` | Round-trips are expensive |
| `refresh` mode default | Only same mode without a natural key |
| SQL schema in `.sql` file | Standalone SQL belongs in files |
| INSERT template inline | Depends on Python's `%s` placeholders |
| Report-first DQ, remediation later | Diagnose before building the fix |
| Chos table for rule validation | Untested DQ rules are untrustworthy |

---

## 9. Talking Points

### On the project overall

> "I build a healthcare claims data pipeline in Python and MySQL. It ingests
> a claims-like dataset, drops PHI at ingestion, drives features like length of stay,
> and loads into a structured schema. Then I wrote a two-layer data quality audit -
> structural rules for impossible values and clinical rules for domain anomalities.
> To trust the rules, I injested known faults into a chaos copy of the data and confirmed the
> rules caught exactly what I broke."

### On dropping PHI

> "Names are PHI with zero analytical value. In a real system, the identity table
> lives separately and is owned by the clinical team, not by analytics. I dropped
> the name at ingestion and documented why."

### On the surrogate key

> "The dataset had no natural key, so I used an AUTO_INCREMENT primary key.
> That's fine for a snapshot, but it means I can't do longitudinal analysis or
> incremental loads - I'd need a real patient_id and claim_id for that."

### On the schema design

> "Right now it's a single flat table. If I were to move this to a warehouse,
> I'd normalize it into a start scheme design - an admissions fact table surrounded
> by patient, provider, and condition dimensions."

### On data quality

> "Structural DQ catches impossible values - negative bills, invalid dates, Clinical DQ
> catches anomalies that only make sense with domain knowledge - eg. Emergency admissions
> billing lower than Elective, which is backwards from real clinical practice.
> Both matter, but they need different tooling."

### On fault injection

> "A DQ rule that shows zero failures might be working, or it might be broken and never
> firing. I validate by deliberately injecting faults and checking the rule catches
> exactly what I injected. That's how I know the clean results on the real table
> are meaningful."

---

## 10. Glossary
| Term | Meaning |
|------|---------|
| **PHI** | Protected Health Information - identifiers under HIPAA |
| **EHR** | Electronic Health Record - the source system for clinical data |
| **VBC** | Value-Based Care - payment tied to outcomes, not volumes |
| **FFS** | Fee-For-Service - payment tied to services delivered |
| **HCC** | Hierarchical Condition Category - a risk adjustment model |
| **PMPM** | Per Member Per Month - a normalized cost metric |
| **Capitation** | Fixed upfront payment for managing a population |
| **Attribution** | Assigning a patient to an accountable provider |
| **Care Gap** | A missed recommened services for a chronic patient |
| **Claims** | Billing records submitted from provider to payer |
| **ETL** | Extract, Transform, Load |
| **DQ** | Data Quality |
| **Idempotent** | Same result regardless of how many times it runs |
| **OLTP** | Online Transaction Processing - write-optimized systems |
| **OLAP** | Online Analytical Processing - read-optimized systems |
| **ACID** | Atomicity, Consistency, Isolation, Durability |

---

## 11. Random things I might need

- **executemany with tuple-of-tuples:**
(admission_id,) in inject_fault.py - that trailing comma is essential.
(x,) is one-element tuple. Without the comma, (x) is just x in parentheses,
and executemany would error.

- **`CREATE TABLE` ... `LIKE` + `INSERT` ... `SELECT`**
`LIKE` copies the structure (columns, types, primary key). `INSERT SELECT` copies
the data. This is the standard way to clone a table in MySQL. Using
`CREATE TABLE AS SELECT` would have skipped the primary key - which we want
to keep.
