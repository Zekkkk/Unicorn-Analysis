# Unicorn Analysis Project Report

## Introduction

This project demonstrates a relational-to-NoSQL migration pipeline for global unicorn startup data. The goal is to show how data can be modeled in a relational database, migrated into a document database with transformations, validated after migration, and visualized from the NoSQL side.

The source dataset is `data/Unicorn_Companies.csv`. The final analysis is based on MongoDB documents produced from PostgreSQL, not directly from the CSV.

## Relational Database Design

The relational source database is PostgreSQL. The database is named `unicorn_analysis`.

The raw CSV is first imported into `staging_unicorn_companies`. From there, the data is normalized into these tables:

```text
countries
cities
industries
companies
investors
company_investors
```

The `companies` table stores the main company facts, including valuation, date joined, founded year, and source investor count. `countries`, `cities`, and `industries` remove repeated text values into lookup tables. `investors` stores unique investor names. `company_investors` models the many-to-many relationship between companies and investors.

The schema uses primary keys, foreign keys, unique constraints, `NOT NULL` constraints, and `CHECK` constraints. The ERD is saved at:

```text
outputs/relational_erd.png
```

Relational population and join evidence are saved at:

```text
outputs/relational_table_counts.png
outputs/relational_join_query.png
```

The SQL files are:

```text
sql/01_schema.sql
sql/02_populate_relational_tables.sql
```

## Choice of NoSQL Database

MongoDB was selected because the analysis is company-centered. Each chart and query usually needs the company, valuation, location, industry, and investor data together. A document model fits this access pattern because those related attributes can be embedded in one company document.

Redis was considered as a key-value alternative. It would be useful for fast lookups or caching specific company records, but it is less natural for ad hoc analytical queries, grouped aggregations, and nested company documents.

Neo4j was considered as a graph alternative. It would model companies, investors, countries, and industries as connected nodes, which is useful for relationship exploration. However, the project's main workload is aggregate analysis and charting, not deep graph traversal.

Cassandra was also considered as a column-family alternative. It can scale large write-heavy workloads, but it requires query-first table design and is more complex than needed for this dataset and local demonstration.

MongoDB provides the best balance for this project: flexible documents, embedded related data, aggregation support, and simple local setup.

## NoSQL Data Model

The MongoDB target is:

```text
Database: unicorn_db
Collection: companies_migrated
```

Each MongoDB document represents one company. The relational model is mapped into a denormalized document structure:

```text
postgres_company_id
company
valuation_b
date_joined
year_joined
founded_year
years_to_unicorn
valuation_tier
location.country
location.city
industry.name
investors
investor_count_actual
investors_count_source
total_raised
financial_stage
deal_terms
portfolio_exits
```

Location and industry are embedded because the visualizations group directly by country and industry. Investors are embedded as an array because the project needs company-centered analysis and the investor names are usually read together with each company.

## Migration Process

The migration script is:

```text
scripts/05_migrate_postgres_to_mongo.py
```

It connects to PostgreSQL using `POSTGRES_DSN` and to MongoDB using `MONGO_URI`, which defaults to `mongodb://localhost:27017/`.

The script joins the normalized relational tables and writes one document per company into MongoDB. It computes derived fields during migration:

```text
year_joined
years_to_unicorn
valuation_tier
investor_count_actual
```

The migration is idempotent. It uses `postgres_company_id` as the unique upsert key with MongoDB `replace_one(..., upsert=True)`. Running the script twice updates existing documents instead of duplicating them.

The latest migration log is saved at:

```text
outputs/migration.log
```

## Validation

The validation script is:

```text
scripts/06_validate_migration.py
```

It compares PostgreSQL and MongoDB using:

```text
record count
SHA-256 checksum over key fields
country aggregate counts
industry aggregate counts
top valuation spot check
```

The validation result is saved at:

```text
outputs/validation_report.txt
```

The latest validation passed all checks:

```text
PostgreSQL count: 1035
MongoDB count: 1035
Country aggregate: 46 groups match
Industry aggregate: 33 groups match
```

## Visualization Layer

The visualization script is:

```text
scripts/04_visualize.py
```

It reads exclusively from:

```text
unicorn_db.companies_migrated
```

The generated charts are:

```text
outputs/charts/01_industry_count.png
outputs/charts/02_country_count.png
outputs/charts/03_unicorns_per_year.png
outputs/charts/04_time_to_unicorn.png
outputs/charts/05_valuation_distribution.png
outputs/charts/06_top_valued.png
```

The charts use migrated and derived MongoDB fields such as `industry.name`, `location.country`, `year_joined`, `years_to_unicorn`, and `valuation_b`.

## Conclusion

The project now demonstrates an end-to-end database migration workflow. PostgreSQL is used for normalized relational modeling with constraints and relationships. MongoDB is used for denormalized analytical documents. Python scripts handle migration, transformation, validation, and visualization.

The main known limitation is dataset size. The available CSV contains 1,037 rows, and the normalized migration produces 1,035 company records. Therefore, the requirement for one relational table with 10,000 or more records is not satisfied in this version.
