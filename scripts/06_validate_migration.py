import hashlib
import json
import os
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
import sys

import psycopg
from psycopg.rows import dict_row
from pymongo import MongoClient
from pymongo.errors import PyMongoError, ServerSelectionTimeoutError


MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
DB_NAME = "unicorn_db"
COLLECTION_NAME = "companies_migrated"
ROOT_DIR = Path(__file__).resolve().parents[1]
REPORT_PATH = ROOT_DIR / "outputs" / "validation_report.txt"


POSTGRES_KEY_FIELD_QUERY = """
SELECT
    c.company_id,
    c.company_name,
    c.valuation_b,
    EXTRACT(YEAR FROM c.date_joined)::INTEGER AS year_joined,
    c.founded_year,
    co.country_name,
    ci.city_name,
    ind.industry_name,
    COUNT(cin.investor_id)::INTEGER AS investor_count_actual
FROM companies c
JOIN countries co ON c.country_id = co.country_id
LEFT JOIN cities ci ON c.city_id = ci.city_id
JOIN industries ind ON c.industry_id = ind.industry_id
LEFT JOIN company_investors cin ON c.company_id = cin.company_id
GROUP BY
    c.company_id,
    c.company_name,
    c.valuation_b,
    c.date_joined,
    c.founded_year,
    co.country_name,
    ci.city_name,
    ind.industry_name
ORDER BY c.company_id;
"""


POSTGRES_COUNTRY_AGG_QUERY = """
SELECT co.country_name AS label, COUNT(*)::INTEGER AS count
FROM companies c
JOIN countries co ON c.country_id = co.country_id
GROUP BY co.country_name
ORDER BY co.country_name;
"""


POSTGRES_INDUSTRY_AGG_QUERY = """
SELECT ind.industry_name AS label, COUNT(*)::INTEGER AS count
FROM companies c
JOIN industries ind ON c.industry_id = ind.industry_id
GROUP BY ind.industry_name
ORDER BY ind.industry_name;
"""


POSTGRES_TOP_VALUATION_QUERY = """
SELECT c.company_name, c.valuation_b
FROM companies c
ORDER BY c.valuation_b DESC, c.company_name ASC
LIMIT 10;
"""


class ValidationReport:
    def __init__(self) -> None:
        self.lines: list[str] = []
        self.failed_checks = 0

    def add(self, line: str = "") -> None:
        self.lines.append(line)
        print(line)

    def check(self, name: str, passed: bool, detail: str) -> None:
        status = "PASS" if passed else "FAIL"
        if not passed:
            self.failed_checks += 1
        self.add(f"[{status}] {name}: {detail}")

    def write(self) -> None:
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        REPORT_PATH.write_text("\n".join(self.lines) + "\n", encoding="utf-8")


def get_postgres_dsn() -> str:
    dsn = os.getenv("POSTGRES_DSN")
    if not dsn:
        raise RuntimeError(
            "POSTGRES_DSN is required. Example: "
            'POSTGRES_DSN="postgresql://postgres:YOUR_PASSWORD@localhost:5433/unicorn_analysis" '
            "python3 scripts/06_validate_migration.py"
        )
    return dsn


def normalize_scalar(value):
    if isinstance(value, Decimal):
        return f"{float(value):.2f}"
    if isinstance(value, float):
        return f"{value:.2f}"
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if value is None:
        return ""
    return value


def normalize_key_record(record: dict) -> dict:
    return {
        "company_id": int(record["company_id"]),
        "company_name": normalize_scalar(record["company_name"]),
        "valuation_b": normalize_scalar(record["valuation_b"]),
        "country_name": normalize_scalar(record["country_name"]),
        "city_name": normalize_scalar(record["city_name"]),
        "industry_name": normalize_scalar(record["industry_name"]),
        "year_joined": normalize_scalar(record["year_joined"]),
        "founded_year": normalize_scalar(record["founded_year"]),
        "investor_count_actual": int(record["investor_count_actual"] or 0),
    }


def checksum_records(records: list[dict]) -> str:
    normalized = [normalize_key_record(record) for record in records]
    payload = json.dumps(normalized, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def aggregate_to_dict(rows: list[dict]) -> dict[str, int]:
    return {row["label"]: int(row["count"]) for row in rows}


def normalize_top_valuations(rows: list[dict]) -> list[tuple[str, str]]:
    return [
        (row["company_name"], normalize_scalar(row["valuation_b"]))
        for row in rows
    ]


def fetch_all(cursor, query: str) -> list[dict]:
    cursor.execute(query)
    return cursor.fetchall()


def fetch_postgres_data(connection: psycopg.Connection) -> dict:
    with connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*)::INTEGER AS count FROM companies;")
        source_count = cursor.fetchone()["count"]
        key_records = fetch_all(cursor, POSTGRES_KEY_FIELD_QUERY)
        country_counts = aggregate_to_dict(fetch_all(cursor, POSTGRES_COUNTRY_AGG_QUERY))
        industry_counts = aggregate_to_dict(fetch_all(cursor, POSTGRES_INDUSTRY_AGG_QUERY))
        top_valuations = normalize_top_valuations(fetch_all(cursor, POSTGRES_TOP_VALUATION_QUERY))

    return {
        "count": source_count,
        "checksum": checksum_records(key_records),
        "country_counts": country_counts,
        "industry_counts": industry_counts,
        "top_valuations": top_valuations,
    }


def fetch_mongo_data(collection) -> dict:
    key_records = []
    for document in collection.find({}, {"_id": 0}).sort("postgres_company_id", 1):
        key_records.append(
            {
                "company_id": document.get("postgres_company_id"),
                "company_name": document.get("company"),
                "valuation_b": document.get("valuation_b"),
                "country_name": (document.get("location") or {}).get("country"),
                "city_name": (document.get("location") or {}).get("city"),
                "industry_name": (document.get("industry") or {}).get("name"),
                "year_joined": document.get("year_joined"),
                "founded_year": document.get("founded_year"),
                "investor_count_actual": document.get("investor_count_actual"),
            }
        )

    country_counts = {
        row["_id"]: row["count"]
        for row in collection.aggregate(
            [
                {"$group": {"_id": "$location.country", "count": {"$sum": 1}}},
                {"$sort": {"_id": 1}},
            ]
        )
    }

    industry_counts = {
        row["_id"]: row["count"]
        for row in collection.aggregate(
            [
                {"$group": {"_id": "$industry.name", "count": {"$sum": 1}}},
                {"$sort": {"_id": 1}},
            ]
        )
    }

    top_valuations = [
        (row["company"], normalize_scalar(row["valuation_b"]))
        for row in collection.find({}, {"_id": 0, "company": 1, "valuation_b": 1})
        .sort([("valuation_b", -1), ("company", 1)])
        .limit(10)
    ]

    return {
        "count": collection.count_documents({}),
        "checksum": checksum_records(key_records),
        "country_counts": country_counts,
        "industry_counts": industry_counts,
        "top_valuations": top_valuations,
    }


def compare_dicts(source: dict, target: dict) -> tuple[bool, str]:
    if source == target:
        return True, f"{len(source)} groups match"

    missing = sorted(set(source) - set(target))
    extra = sorted(set(target) - set(source))
    mismatched = sorted(
        key for key in set(source).intersection(target)
        if source[key] != target[key]
    )
    details = []
    if missing:
        details.append(f"missing in MongoDB: {missing[:5]}")
    if extra:
        details.append(f"extra in MongoDB: {extra[:5]}")
    if mismatched:
        details.append(f"count mismatches: {[(key, source[key], target[key]) for key in mismatched[:5]]}")
    return False, "; ".join(details)


def validate() -> int:
    report = ValidationReport()
    report.add("Migration Validation Report")
    report.add("===========================")
    report.add(f"PostgreSQL source: companies")
    report.add(f"MongoDB target: {DB_NAME}.{COLLECTION_NAME}")
    report.add("")

    postgres_connection = None
    mongo_client = None

    try:
        postgres_connection = psycopg.connect(get_postgres_dsn(), row_factory=dict_row)
        mongo_client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        mongo_client.admin.command("ping")
        collection = mongo_client[DB_NAME][COLLECTION_NAME]

        source = fetch_postgres_data(postgres_connection)
        target = fetch_mongo_data(collection)

        report.check(
            "Record count",
            source["count"] == target["count"],
            f"PostgreSQL={source['count']}, MongoDB={target['count']}",
        )
        report.check(
            "Key-field checksum",
            source["checksum"] == target["checksum"],
            f"PostgreSQL={source['checksum']}, MongoDB={target['checksum']}",
        )

        countries_passed, countries_detail = compare_dicts(
            source["country_counts"],
            target["country_counts"],
        )
        report.check("Country aggregate", countries_passed, countries_detail)

        industries_passed, industries_detail = compare_dicts(
            source["industry_counts"],
            target["industry_counts"],
        )
        report.check("Industry aggregate", industries_passed, industries_detail)

        report.check(
            "Top valuation spot check",
            source["top_valuations"] == target["top_valuations"],
            f"PostgreSQL={source['top_valuations']}, MongoDB={target['top_valuations']}",
        )

        report.add("")
        if report.failed_checks:
            report.add(f"Validation failed: {report.failed_checks} check(s) failed.")
            return_code = 1
        else:
            report.add("Validation passed: all checks passed.")
            return_code = 0

        report.add(f"Report written to {REPORT_PATH}")
        return return_code

    except RuntimeError as exc:
        report.check("Configuration", False, str(exc))
        return 1
    except psycopg.Error as exc:
        report.check("PostgreSQL connection/query", False, str(exc))
        return 1
    except ServerSelectionTimeoutError:
        report.check("MongoDB connection", False, "Start MongoDB locally and rerun validation.")
        return 1
    except PyMongoError as exc:
        report.check("MongoDB query", False, str(exc))
        return 1
    except Exception as exc:
        report.check("Unexpected validation error", False, str(exc))
        return 1
    finally:
        report.write()
        if postgres_connection is not None:
            postgres_connection.close()
        if mongo_client is not None:
            mongo_client.close()


if __name__ == "__main__":
    raise SystemExit(validate())
