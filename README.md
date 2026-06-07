# Unicorn Analysis

University data engineering project by Fortan Zaimi and Zeqirija Osmani.

This project demonstrates a relational-to-NoSQL migration pipeline using a real-world unicorn startup dataset. The source data starts as `data/Unicorn_Companies.csv`, is loaded into a normalized PostgreSQL relational schema, migrated into MongoDB as denormalized company documents, validated with automated checks, and visualized from the MongoDB side.

## Project Structure

```text
unicorn-analysis/
├── data/
│   └── Unicorn_Companies.csv
├── sql/
│   ├── 01_schema.sql
│   └── 02_populate_relational_tables.sql
├── scripts/
│   ├── 01_ingest.py
│   ├── 02_clean.py
│   ├── 03_queries.py
│   ├── 04_visualize.py
│   ├── 05_migrate_postgres_to_mongo.py
│   └── 06_validate_migration.py
├── outputs/
│   ├── charts/
│   ├── relational_erd.png
│   ├── relational_table_counts.png
│   ├── relational_join_query.png
│   ├── migration.log
│   └── validation_report.txt
├── notebooks/
│   └── analysis.ipynb
├── REPORT.md
├── requirements.txt
└── README.md
```

## Setup

Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Start MongoDB with Docker:

```bash
docker run --name unicorn-mongo -p 27017:27017 -d mongo:latest
```

If the container already exists:

```bash
docker start unicorn-mongo
```

MongoDB defaults to:

```text
mongodb://localhost:27017/
```

PostgreSQL is expected to contain a database named:

```text
unicorn_analysis
```

In the local development setup used for this project, PostgreSQL runs on port `5433`. Pass the PostgreSQL connection string through `POSTGRES_DSN`. Do not commit database passwords.

Example:

```bash
export POSTGRES_DSN="postgresql://postgres:YOUR_PASSWORD@localhost:5433/unicorn_analysis"
```

## PostgreSQL Relational Setup

Create the PostgreSQL database in pgAdmin:

```sql
CREATE DATABASE unicorn_analysis;
```

Open the `unicorn_analysis` database in pgAdmin Query Tool and run:

```text
sql/01_schema.sql
```

This creates the staging table and normalized relational tables:

```text
staging_unicorn_companies
countries
cities
industries
companies
investors
company_investors
```

Import the CSV into `staging_unicorn_companies` using pgAdmin Import/Export:

```text
data/Unicorn_Companies.csv
```

Use CSV format with header enabled.

Then run:

```text
sql/02_populate_relational_tables.sql
```

This normalizes the staging data into the relational schema and includes count and join queries for evidence.

Relational evidence is saved in:

```text
outputs/relational_erd.png
outputs/relational_table_counts.png
outputs/relational_join_query.png
```

## Migration to MongoDB

Run the PostgreSQL-to-MongoDB migration:

```bash
POSTGRES_DSN="postgresql://postgres:YOUR_PASSWORD@localhost:5433/unicorn_analysis" python3 scripts/05_migrate_postgres_to_mongo.py
```

The migration reads the normalized PostgreSQL tables and writes denormalized documents to:

```text
MongoDB database: unicorn_db
MongoDB collection: companies_migrated
```

The migrated documents embed location, industry, and investor data, and include derived fields such as:

```text
year_joined
years_to_unicorn
valuation_tier
investor_count_actual
```

The migration is idempotent. It uses `postgres_company_id` as the upsert key, so running the script repeatedly does not duplicate documents.

Migration output is logged to:

```text
outputs/migration.log
```

## Validation

Run the automated validation layer:

```bash
POSTGRES_DSN="postgresql://postgres:YOUR_PASSWORD@localhost:5433/unicorn_analysis" python3 scripts/06_validate_migration.py
```

The validation compares PostgreSQL and MongoDB using:

- record counts
- SHA-256 checksum over key fields
- country-level aggregates
- industry-level aggregates
- top valuation spot checks

Expected result:

```text
Validation passed: all checks passed.
```

The validation report is saved to:

```text
outputs/validation_report.txt
```

## Visualization

Generate charts from MongoDB:

```bash
python3 scripts/04_visualize.py
```

The visualization reads exclusively from:

```text
unicorn_db.companies_migrated
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

## Legacy Scripts

The original CSV-to-MongoDB workflow is still present for reference:

```text
scripts/01_ingest.py
scripts/02_clean.py
scripts/03_queries.py
```

The course-compliant pipeline is the PostgreSQL-to-MongoDB workflow using `sql/`, `scripts/05_migrate_postgres_to_mongo.py`, `scripts/06_validate_migration.py`, and `scripts/04_visualize.py`.

## Known Limitation

The dataset contains 1,037 CSV rows, and the relational migration produces 1,035 company records after normalization. The course requirement for one table with 10,000 or more records is not satisfied in this version.
