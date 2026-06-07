# Unicorn Analysis Project Report

## Introduction

This project demonstrates an end-to-end migration from a relational database to a NoSQL database. The dataset contains global unicorn startup companies, meaning private companies valued at one billion dollars or more. The final pipeline starts with a CSV file, loads and normalizes it in PostgreSQL, migrates it into MongoDB as denormalized documents, validates the result, and generates visualizations from MongoDB.

The project was originally a MongoDB analysis project, but it was redesigned to satisfy the course objective: demonstrate relational modeling, NoSQL modeling, programmatic migration, transformation, validation, and visualization.

## Why This Project Was Chosen

Unicorn company data is a good fit for this assignment because it has natural relationships and useful analysis dimensions. A company belongs to a country, city, and industry. A company can also have many investors, and the same investor can appear in many companies. This makes the dataset suitable for relational modeling with multiple joinable tables.

At the same time, the final analysis is company-centered. Most useful questions ask about each company together with its valuation, industry, location, founding year, date joined, and investors. That makes the dataset suitable for MongoDB after migration because the related data can be embedded into one company document.

The topic is also easy to explain in a presentation because the business meaning is clear: where unicorns are located, which industries produce the most unicorns, how quickly companies reach unicorn status, and which companies have the highest valuations.

## Relational Database Design

The relational source database is PostgreSQL. The database is named `unicorn_analysis`.

The CSV is first imported into a staging table:

```text
staging_unicorn_companies
```

The staging table stores the raw CSV fields as text so the original import is simple and recoverable. After import, the data is normalized into these relational tables:

```text
countries
cities
industries
companies
investors
company_investors
```

The `companies` table is the main entity table. It stores company name, valuation, date joined, founded year, total raised, financial stage, investor count, deal terms, portfolio exits, and foreign keys to country, city, and industry.

The `countries`, `cities`, and `industries` tables remove repeated text values and make the schema cleaner. The `investors` table stores unique investor names. The `company_investors` table is a junction table that handles the many-to-many relationship between companies and investors.

The schema includes primary keys, foreign keys, unique constraints, `NOT NULL` constraints, and `CHECK` constraints. Examples include a check that valuation is at least one billion and a check that investor count cannot be negative.

Schema files:

```text
sql/01_schema.sql
sql/02_populate_relational_tables.sql
```

Evidence files:

```text
outputs/relational_erd.png
outputs/relational_table_counts.png
outputs/relational_join_query.png
```

The PostgreSQL population produced 1,035 company records after normalization.

## Choice of NoSQL Database

MongoDB was chosen as the NoSQL target because the final access pattern is document-oriented and company-centered. Each analysis needs company data together with location, industry, valuation, and investors. MongoDB allows those related fields to be stored together in a single document, which avoids repeated joins during analysis and visualization.

Redis was considered as a key-value alternative. It would be useful for fast lookups or caching a company by key, but it is not as natural for grouped analytical queries, nested data, or chart generation.

Neo4j was considered as a graph alternative. It would model companies, investors, countries, and industries as connected nodes, which would be useful for exploring investor networks. However, this project focuses more on aggregate analytics than graph traversal.

Cassandra was considered as a column-family alternative. It is strong for large-scale distributed writes and query-specific table design, but it is more complex than necessary for this local migration and visualization project.

MongoDB was the best fit because it supports flexible documents, embedded arrays, aggregation queries, and simple local development.

## MongoDB Data Model

The MongoDB target is:

```text
Database: unicorn_db
Collection: companies_migrated
```

Each document represents one company. The relational tables are mapped into a denormalized document structure:

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

Country and city are embedded under `location` because location is usually read together with the company. Industry is embedded because most charts group companies by industry. Investors are embedded as an array because the visualization and company-level analysis do not require separate investor updates.

This is a deliberate denormalization step. PostgreSQL stores normalized relational data; MongoDB stores analysis-ready company documents.

## Migration Process

The migration script is:

```text
scripts/05_migrate_postgres_to_mongo.py
```

The script connects to PostgreSQL using `POSTGRES_DSN` and connects to MongoDB using `MONGO_URI`, which defaults to:

```text
mongodb://localhost:27017/
```

The migration joins the normalized PostgreSQL tables and creates one MongoDB document per company. It is not a one-to-one table copy. It transforms the relational data by embedding related values and computing derived fields.

Derived fields include:

```text
year_joined
years_to_unicorn
valuation_tier
investor_count_actual
```

The script is idempotent. It uses `postgres_company_id` as the unique upsert key and writes documents with MongoDB `replace_one(..., upsert=True)`. Running the migration multiple times updates the same documents instead of creating duplicates.

The latest migration output is saved in:

```text
outputs/migration.log
```

## Validation Results

The validation script is:

```text
scripts/06_validate_migration.py
```

The script compares PostgreSQL and MongoDB using several checks:

```text
record count
SHA-256 checksum over key fields
country aggregate counts
industry aggregate counts
top valuation spot check
```

The validation report is saved at:

```text
outputs/validation_report.txt
```

The latest validation passed all checks:

```text
PostgreSQL count: 1035
MongoDB count: 1035
Country aggregate: 46 groups match
Industry aggregate: 33 groups match
Top valuation spot check: passed
```

This proves that the migrated MongoDB collection matches the PostgreSQL source for the selected validation fields and aggregate queries.

## Visualization Results

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

The visualizations use migrated MongoDB fields such as `industry.name`, `location.country`, `year_joined`, `years_to_unicorn`, and `valuation_b`. This proves that the migrated NoSQL collection is usable for analysis.

## Conclusion

This project demonstrates relational modeling, NoSQL modeling, programmatic migration, transformation, validation, and visualization. PostgreSQL is used to show normalized relational structure and constraints. MongoDB is used to show denormalized document modeling for analysis. Python connects the two systems and validates the migration.

The main limitation is dataset size. The available CSV contains 1,037 rows, and the normalized relational migration produces 1,035 company records. The course requirement for one table with 10,000 or more records is not satisfied in this version. This limitation is documented honestly, while the rest of the migration pipeline is complete and working.
