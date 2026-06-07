from pathlib import Path
import sys

import pandas as pd
from pymongo import MongoClient
from pymongo.errors import PyMongoError, ServerSelectionTimeoutError


MONGO_URI = "mongodb://localhost:27017/"
DB_NAME = "unicorn_db"
COLLECTION_NAME = "companies"
ROOT_DIR = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT_DIR / "data" / "Unicorn_Companies.csv"


def load_csv(csv_path: Path) -> pd.DataFrame:
    print(f"Loading CSV from {csv_path}")
    df = pd.read_csv(csv_path)

    if "Select Inverstors" in df.columns and "Select Investors" not in df.columns:
        df = df.rename(columns={"Select Inverstors": "Select Investors"})

    df = df.where(pd.notnull(df), None)
    print(f"Loaded {len(df):,} rows and {len(df.columns)} columns.")
    return df


def connect_to_mongo() -> MongoClient:
    print(f"Connecting to MongoDB at {MONGO_URI}")
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    client.admin.command("ping")
    print("MongoDB connection successful.")
    return client


def main() -> int:
    try:
        if not CSV_PATH.exists():
            raise FileNotFoundError(f"CSV file not found: {CSV_PATH}")

        df = load_csv(CSV_PATH)
        documents = df.to_dict(orient="records")

        client = connect_to_mongo()
        collection = client[DB_NAME][COLLECTION_NAME]

        print(f"Replacing documents in {DB_NAME}.{COLLECTION_NAME}")
        collection.delete_many({})

        if documents:
            result = collection.insert_many(documents)
            inserted_count = len(result.inserted_ids)
        else:
            inserted_count = 0

        print(f"Inserted {inserted_count:,} documents into {DB_NAME}.{COLLECTION_NAME}.")
        print("Ingestion complete.")
        client.close()
        return 0

    except FileNotFoundError as exc:
        print(f"File error: {exc}", file=sys.stderr)
        return 1
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
        print(f"Unexpected error during ingestion: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
