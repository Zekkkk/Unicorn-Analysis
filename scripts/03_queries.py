import sys

from pymongo import MongoClient
from pymongo.errors import PyMongoError, ServerSelectionTimeoutError


MONGO_URI = "mongodb://localhost:27017/"
DB_NAME = "unicorn_db"
CLEAN_COLLECTION = "companies_clean"


def connect_to_mongo() -> MongoClient:
    print(f"Connecting to MongoDB at {MONGO_URI}")
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    client.admin.command("ping")
    print("MongoDB connection successful.")
    return client


def print_header(title: str) -> None:
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)


def print_ranked_count(rows: list[dict], label_key: str, count_key: str = "count") -> None:
    for index, row in enumerate(rows, start=1):
        print(f"{index:>2}. {row['_id']:<35} {row[count_key]:>5}")


def print_year_counts(rows: list[dict]) -> None:
    for row in rows:
        print(f"{row['_id']}: {row['count']} new unicorns")


def print_time_to_unicorn(rows: list[dict]) -> None:
    print(f"{'Industry':<35} {'Count':>7} {'Avg Years':>12} {'Avg Valuation ($B)':>20}")
    print("-" * 80)
    for row in rows:
        print(
            f"{row['_id']:<35} "
            f"{row['company_count']:>7} "
            f"{row['avg_years_to_unicorn']:>12.2f} "
            f"{row['avg_valuation_b']:>20.2f}"
        )


def run_queries(collection) -> None:
    industry_pipeline = [
        {"$group": {"_id": "$industry", "count": {"$sum": 1}}},
        {"$sort": {"count": -1, "_id": 1}},
        {"$limit": 10},
    ]

    country_pipeline = [
        {"$group": {"_id": "$country", "count": {"$sum": 1}}},
        {"$sort": {"count": -1, "_id": 1}},
        {"$limit": 10},
    ]

    unicorns_per_year_pipeline = [
        {"$group": {"_id": "$year_joined", "count": {"$sum": 1}}},
        {"$sort": {"_id": 1}},
    ]

    fastest_industries_2020_2022_pipeline = [
        {"$match": {"year_joined": {"$gte": 2020, "$lte": 2022}}},
        {"$group": {"_id": "$industry", "new_unicorns_2020_2022": {"$sum": 1}}},
        {"$sort": {"new_unicorns_2020_2022": -1, "_id": 1}},
        {"$limit": 10},
    ]

    time_to_unicorn_pipeline = [
        {
            "$group": {
                "_id": "$industry",
                "company_count": {"$sum": 1},
                "avg_years_to_unicorn": {"$avg": "$years_to_unicorn"},
                "avg_valuation_b": {"$avg": "$valuation_b"},
            }
        },
        {"$match": {"company_count": {"$gte": 5}}},
        {"$sort": {"avg_years_to_unicorn": 1, "company_count": -1}},
    ]

    print_header("1. Industry Analysis - Top 10 Industries by Unicorn Count")
    print_ranked_count(list(collection.aggregate(industry_pipeline)), "industry")

    print_header("2. Geographic Distribution - Top 10 Countries by Unicorn Count")
    print_ranked_count(list(collection.aggregate(country_pipeline)), "country")

    print_header("3A. Fastest Growing Sectors - New Unicorns Created Per Year")
    print_year_counts(list(collection.aggregate(unicorns_per_year_pipeline)))

    print_header("3B. Fastest Growing Industries from 2020 to 2022")
    growth_rows = list(collection.aggregate(fastest_industries_2020_2022_pipeline))
    for index, row in enumerate(growth_rows, start=1):
        print(f"{index:>2}. {row['_id']:<35} {row['new_unicorns_2020_2022']:>5}")

    print_header("4. Time to Unicorn - Average Years and Valuation by Industry")
    print_time_to_unicorn(list(collection.aggregate(time_to_unicorn_pipeline)))


def main() -> int:
    try:
        client = connect_to_mongo()
        collection = client[DB_NAME][CLEAN_COLLECTION]

        count = collection.count_documents({})
        if count == 0:
            print(
                f"No documents found in {DB_NAME}.{CLEAN_COLLECTION}. "
                "Run scripts/01_ingest.py and scripts/02_clean.py first.",
                file=sys.stderr,
            )
            return 1

        print(f"Running aggregation queries on {count:,} clean documents.")
        run_queries(collection)
        print("\nQuery analysis complete.")
        client.close()
        return 0

    except ServerSelectionTimeoutError:
        print(
            "MongoDB connection failed. Start MongoDB locally at mongodb://localhost:27017/ "
            "and rerun this script.",
            file=sys.stderr,
        )
        return 1
    except PyMongoError as exc:
        print(f"MongoDB error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Unexpected error during query analysis: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
