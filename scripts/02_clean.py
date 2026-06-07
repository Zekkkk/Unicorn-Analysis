import re
import sys

import pandas as pd
from pymongo import MongoClient
from pymongo.errors import PyMongoError, ServerSelectionTimeoutError


MONGO_URI = "mongodb://localhost:27017/"
DB_NAME = "unicorn_db"
RAW_COLLECTION = "companies"
CLEAN_COLLECTION = "companies_clean"


COLUMN_RENAMES = {
    "Company": "company",
    "Valuation ($B)": "valuation_b",
    "Date Joined": "date_joined",
    "Country": "country",
    "City": "city",
    "Industry": "industry",
    "Select Investors": "select_investors",
    "Select Inverstors": "select_investors",
    "Founded Year": "founded_year",
    "Total Raised": "total_raised",
    "Financial Stage": "financial_stage",
    "Investors Count": "investors_count",
    "Deal Terms": "deal_terms",
    "Portfolio Exits": "portfolio_exits",
}


CRITICAL_FIELDS = [
    "company",
    "valuation_b",
    "date_joined",
    "year_joined",
    "country",
    "industry",
    "founded_year",
    "years_to_unicorn",
]


INDUSTRY_CANONICAL_NAMES = {
    "artificial intelligence": "Artificial intelligence",
}


def connect_to_mongo() -> MongoClient:
    print(f"Connecting to MongoDB at {MONGO_URI}")
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    client.admin.command("ping")
    print("MongoDB connection successful.")
    return client


def parse_valuation(value):
    if pd.isna(value):
        return pd.NA

    cleaned = re.sub(r"[^0-9.]", "", str(value))
    if cleaned == "":
        return pd.NA

    return float(cleaned)


def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    print("Cleaning raw unicorn data.")
    df = df.rename(columns=COLUMN_RENAMES)

    for column in ["company", "country", "city", "industry", "select_investors"]:
        if column in df.columns:
            df[column] = df[column].astype("string").str.strip()

    df["industry"] = df["industry"].str.lower().map(INDUSTRY_CANONICAL_NAMES).fillna(df["industry"])

    df["valuation_b"] = df["valuation_b"].apply(parse_valuation)
    df["valuation_b"] = pd.to_numeric(df["valuation_b"], errors="coerce")

    df["date_joined"] = pd.to_datetime(df["date_joined"], errors="coerce")
    df["year_joined"] = df["date_joined"].dt.year

    df["founded_year"] = pd.to_numeric(df["founded_year"], errors="coerce")
    df["years_to_unicorn"] = df["year_joined"] - df["founded_year"]

    for column in ["founded_year", "year_joined", "years_to_unicorn"]:
        df[column] = df[column].round().astype("Int64")

    before_drop = len(df)
    df = df.dropna(subset=CRITICAL_FIELDS).copy()
    after_drop = len(df)

    for column in ["founded_year", "year_joined", "years_to_unicorn"]:
        df[column] = df[column].astype(int)

    print(f"Rows before cleaning: {before_drop:,}")
    print(f"Rows after dropping null critical fields: {after_drop:,}")
    print(f"Rows dropped: {before_drop - after_drop:,}")
    return df


def dataframe_to_documents(df: pd.DataFrame) -> list[dict]:
    object_df = df.astype(object).where(pd.notna(df), None)
    return object_df.to_dict(orient="records")


def main() -> int:
    try:
        client = connect_to_mongo()
        raw_collection = client[DB_NAME][RAW_COLLECTION]
        clean_collection = client[DB_NAME][CLEAN_COLLECTION]

        raw_docs = list(raw_collection.find({}, {"_id": 0}))
        if not raw_docs:
            print(
                f"No documents found in {DB_NAME}.{RAW_COLLECTION}. "
                "Run scripts/01_ingest.py first.",
                file=sys.stderr,
            )
            return 1

        print(f"Loaded {len(raw_docs):,} raw documents from MongoDB.")
        raw_df = pd.DataFrame(raw_docs)
        clean_df = clean_dataframe(raw_df)
        clean_docs = dataframe_to_documents(clean_df)

        print(f"Replacing documents in {DB_NAME}.{CLEAN_COLLECTION}")
        clean_collection.delete_many({})
        if clean_docs:
            clean_collection.insert_many(clean_docs)

        print(f"Saved {len(clean_docs):,} clean documents to {DB_NAME}.{CLEAN_COLLECTION}.")
        print(f"Average valuation: ${clean_df['valuation_b'].mean():.2f}B")
        print(f"Average years to unicorn: {clean_df['years_to_unicorn'].mean():.2f}")
        print("Cleaning complete.")
        client.close()
        return 0

    except KeyError as exc:
        print(f"Missing expected column during cleaning: {exc}", file=sys.stderr)
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
        print(f"Unexpected error during cleaning: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
