# Unicorn Analysis

Runbook for the Unicorn Analysis PostgreSQL-to-MongoDB migration project.

## Prerequisites

- Python 3.12+
- PostgreSQL running locally
- MongoDB running locally or in Docker
- pgAdmin for manual PostgreSQL import/ERD screenshots

## Install Dependencies

```bash
cd /Users/zekoosmani/Unicorn-Analysis
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Start MongoDB

If the MongoDB Docker container already exists:

```bash
docker start unicorn-mongo
```

If it does not exist:

```bash
docker run --name unicorn-mongo -p 27017:27017 -d mongo:latest
```

Default MongoDB connection:

```text
mongodb://localhost:27017/
```

## PostgreSQL Setup

Create a PostgreSQL database named:

```text
unicorn_analysis
```

In pgAdmin, open Query Tool for `unicorn_analysis` and run:

```text
sql/01_schema.sql
```

Import the CSV into the staging table:

```text
Table: staging_unicorn_companies
File: data/Unicorn_Companies.csv
Format: CSV
Header: Yes
Delimiter: ,
Quote: "
Escape: "
```

Then run:

```text
sql/02_populate_relational_tables.sql
```

The expected final `companies` table count is:

```text
1035
```

## Environment Variables

Set the PostgreSQL connection string before running migration or validation.

Example for the local PostgreSQL setup:

```bash
export POSTGRES_DSN="postgresql://postgres:YOUR_PASSWORD@localhost:5433/unicorn_analysis"
```

Do not commit real passwords.

Optional MongoDB override:

```bash
export MONGO_URI="mongodb://localhost:27017/"
```

## Run Migration

```bash
python3 scripts/05_migrate_postgres_to_mongo.py
```

Expected result:

```text
Fetched 1035 company rows from PostgreSQL.
Migration complete.
MongoDB unicorn_db.companies_migrated document count: 1035
```

Run the migration a second time to prove idempotency:

```bash
python3 scripts/05_migrate_postgres_to_mongo.py
```

Expected second-run behavior:

```text
Inserted new documents: 0
MongoDB unicorn_db.companies_migrated document count: 1035
```

Migration log:

```text
outputs/migration.log
```

## Run Validation

```bash
python3 scripts/06_validate_migration.py
```

Expected result:

```text
[PASS] Record count
[PASS] Key-field checksum
[PASS] Country aggregate
[PASS] Industry aggregate
[PASS] Top valuation spot check
Validation passed: all checks passed.
```

Validation report:

```text
outputs/validation_report.txt
```

## Generate Visualizations

```bash
python3 scripts/04_visualize.py
```

The visualization reads from:

```text
MongoDB database: unicorn_db
MongoDB collection: companies_migrated
```

Generated charts:

```text
outputs/charts/01_industry_count.png
outputs/charts/02_country_count.png
outputs/charts/03_unicorns_per_year.png
outputs/charts/04_time_to_unicorn.png
outputs/charts/05_valuation_distribution.png
outputs/charts/06_top_valued.png
```

## Evidence Files

```text
outputs/relational_erd.png
outputs/relational_table_counts.png
outputs/relational_join_query.png
outputs/migration.log
outputs/validation_report.txt
outputs/charts/
REPORT.md
```

## Legacy Scripts

These scripts are kept from the original MongoDB-only version for reference:

```text
scripts/01_ingest.py
scripts/02_clean.py
scripts/03_queries.py
```

The final course pipeline uses:

```text
sql/01_schema.sql
sql/02_populate_relational_tables.sql
scripts/05_migrate_postgres_to_mongo.py
scripts/06_validate_migration.py
scripts/04_visualize.py
```
