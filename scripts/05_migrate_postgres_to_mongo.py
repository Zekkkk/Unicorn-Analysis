import logging
import os
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
import sys

import psycopg
from psycopg.rows import dict_row
from pymongo import ASCENDING, MongoClient, ReplaceOne
from pymongo.errors import PyMongoError, ServerSelectionTimeoutError


MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
DB_NAME = "unicorn_db"
COLLECTION_NAME = "companies_migrated"
ROOT_DIR = Path(__file__).resolve().parents[1]
LOG_PATH = ROOT_DIR / "outputs" / "migration.log"


COMPANY_QUERY = """
SELECT
    c.company_id,
    c.company_name,
    c.valuation_b,
    c.date_joined,
    EXTRACT(YEAR FROM c.date_joined)::INTEGER AS year_joined,
    c.founded_year,
    c.total_raised,
    c.financial_stage,
    c.investors_count,
    c.deal_terms,
    c.portfolio_exits,
    co.country_name,
    ci.city_name,
    ind.industry_name,
    COALESCE(
        ARRAY_AGG(inv.investor_name ORDER BY inv.investor_name)
            FILTER (WHERE inv.investor_name IS NOT NULL),
        ARRAY[]::VARCHAR[]
    ) AS investors
FROM companies c
JOIN countries co ON c.country_id = co.country_id
LEFT JOIN cities ci ON c.city_id = ci.city_id
JOIN industries ind ON c.industry_id = ind.industry_id
LEFT JOIN company_investors cin ON c.company_id = cin.company_id
LEFT JOIN investors inv ON cin.investor_id = inv.investor_id
GROUP BY
    c.company_id,
    c.company_name,
    c.valuation_b,
    c.date_joined,
    c.founded_year,
    c.total_raised,
    c.financial_stage,
    c.investors_count,
    c.deal_terms,
    c.portfolio_exits,
    co.country_name,
    ci.city_name,
    ind.industry_name
ORDER BY c.company_id;
"""


def configure_logging() -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.FileHandler(LOG_PATH, mode="w", encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


def get_postgres_dsn() -> str:
    dsn = os.getenv("POSTGRES_DSN")
    if not dsn:
        raise RuntimeError(
            "POSTGRES_DSN is required. Example: "
            'POSTGRES_DSN="postgresql://postgres:YOUR_PASSWORD@localhost:5433/unicorn_analysis" '
            "python scripts/05_migrate_postgres_to_mongo.py"
        )
    return dsn


def connect_to_postgres(dsn: str) -> psycopg.Connection:
    logging.info("Connecting to PostgreSQL.")
    connection = psycopg.connect(dsn, row_factory=dict_row)
    logging.info("PostgreSQL connection successful.")
    return connection


def connect_to_mongo() -> MongoClient:
    logging.info("Connecting to MongoDB at %s.", MONGO_URI)
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    client.admin.command("ping")
    logging.info("MongoDB connection successful.")
    return client


def to_plain_value(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def valuation_tier(valuation_b: float) -> str:
    if valuation_b >= 50:
        return "mega unicorn"
    if valuation_b >= 10:
        return "decacorn"
    return "unicorn"


def row_to_document(row: dict) -> dict:
    company_id = row["company_id"]
    company_name = row["company_name"]
    valuation_b = to_plain_value(row["valuation_b"])
    date_joined = row["date_joined"]
    year_joined = row["year_joined"]
    founded_year = row["founded_year"]

    if not company_id or not company_name:
        raise ValueError("Missing required company id or company name.")
    if valuation_b is None:
        raise ValueError(f"Missing valuation for company {company_name}.")
    if not date_joined or year_joined is None:
        raise ValueError(f"Missing date joined for company {company_name}.")

    years_to_unicorn = None
    if founded_year is not None:
        years_to_unicorn = int(year_joined) - int(founded_year)

    investors = [name for name in (row.get("investors") or []) if name]

    return {
        "postgres_company_id": company_id,
        "company": company_name,
        "valuation_b": valuation_b,
        "date_joined": to_plain_value(date_joined),
        "year_joined": year_joined,
        "founded_year": founded_year,
        "years_to_unicorn": years_to_unicorn,
        "valuation_tier": valuation_tier(valuation_b),
        "location": {
            "country": row["country_name"],
            "city": row["city_name"],
        },
        "industry": {
            "name": row["industry_name"],
        },
        "investors": investors,
        "investor_count_actual": len(investors),
        "investors_count_source": row["investors_count"],
        "total_raised": row["total_raised"],
        "financial_stage": row["financial_stage"],
        "deal_terms": row["deal_terms"],
        "portfolio_exits": row["portfolio_exits"],
        "migrated_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }


def fetch_company_rows(connection: psycopg.Connection) -> list[dict]:
    with connection.cursor() as cursor:
        cursor.execute(COMPANY_QUERY)
        rows = cursor.fetchall()
    logging.info("Fetched %s company rows from PostgreSQL.", len(rows))
    return rows


def build_operations(rows: list[dict]) -> tuple[list[ReplaceOne], int]:
    operations = []
    skipped_count = 0

    for row in rows:
        try:
            document = row_to_document(row)
            operations.append(
                ReplaceOne(
                    {"postgres_company_id": document["postgres_company_id"]},
                    document,
                    upsert=True,
                )
            )
        except Exception as exc:
            skipped_count += 1
            logging.exception(
                "Skipping company row %s because transformation failed: %s",
                row.get("company_id"),
                exc,
            )

    return operations, skipped_count


def ensure_indexes(collection) -> None:
    collection.create_index([("postgres_company_id", ASCENDING)], unique=True)
    collection.create_index([("company", ASCENDING)])
    collection.create_index([("location.country", ASCENDING)])
    collection.create_index([("industry.name", ASCENDING)])


def migrate() -> int:
    configure_logging()

    postgres_connection = None
    mongo_client = None

    try:
        postgres_connection = connect_to_postgres(get_postgres_dsn())
        mongo_client = connect_to_mongo()
        collection = mongo_client[DB_NAME][COLLECTION_NAME]

        ensure_indexes(collection)
        rows = fetch_company_rows(postgres_connection)
        operations, skipped_count = build_operations(rows)

        if not operations:
            logging.warning("No valid company documents were produced.")
            return 1

        result = collection.bulk_write(operations, ordered=False)
        final_count = collection.count_documents({})

        logging.info("Migration complete.")
        logging.info("Matched existing documents: %s", result.matched_count)
        logging.info("Inserted new documents: %s", result.upserted_count)
        logging.info("Modified documents: %s", result.modified_count)
        logging.info("Skipped source rows: %s", skipped_count)
        logging.info("MongoDB %s.%s document count: %s", DB_NAME, COLLECTION_NAME, final_count)
        logging.info("Migration log written to %s", LOG_PATH)
        return 0

    except RuntimeError as exc:
        logging.error("%s", exc)
        return 1
    except psycopg.Error as exc:
        logging.error("PostgreSQL error during migration: %s", exc)
        return 1
    except ServerSelectionTimeoutError:
        logging.error("MongoDB connection failed. Start MongoDB locally and rerun this script.")
        return 1
    except PyMongoError as exc:
        logging.error("MongoDB error during migration: %s", exc)
        return 1
    except Exception as exc:
        logging.exception("Unexpected migration error: %s", exc)
        return 1
    finally:
        if postgres_connection is not None:
            postgres_connection.close()
        if mongo_client is not None:
            mongo_client.close()


if __name__ == "__main__":
    raise SystemExit(migrate())
