import os
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
os.environ.setdefault("MPLCONFIGDIR", str(ROOT_DIR / ".matplotlib-cache"))

import matplotlib.pyplot as plt
import pandas as pd
from pymongo import MongoClient
from pymongo.errors import PyMongoError, ServerSelectionTimeoutError
import seaborn as sns


MONGO_URI = "mongodb://localhost:27017/"
DB_NAME = "unicorn_db"
CLEAN_COLLECTION = "companies_clean"
CHART_DIR = ROOT_DIR / "outputs" / "charts"


def connect_to_mongo() -> MongoClient:
    print(f"Connecting to MongoDB at {MONGO_URI}")
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    client.admin.command("ping")
    print("MongoDB connection successful.")
    return client


def load_clean_data() -> pd.DataFrame:
    client = connect_to_mongo()
    collection = client[DB_NAME][CLEAN_COLLECTION]
    docs = list(collection.find({}, {"_id": 0}))
    client.close()

    if not docs:
        raise ValueError(
            f"No documents found in {DB_NAME}.{CLEAN_COLLECTION}. "
            "Run scripts/01_ingest.py and scripts/02_clean.py first."
        )

    df = pd.DataFrame(docs)
    print(f"Loaded {len(df):,} clean rows for visualization.")
    return df


def annotate_horizontal_bars(ax, decimals: int = 0, suffix: str = "") -> None:
    for patch in ax.patches:
        value = patch.get_width()
        if pd.isna(value):
            continue
        label = f"{value:.{decimals}f}{suffix}"
        ax.annotate(
            label,
            (value, patch.get_y() + patch.get_height() / 2),
            xytext=(5, 0),
            textcoords="offset points",
            va="center",
            ha="left",
            fontsize=9,
        )


def save_chart(fig, filename: str) -> None:
    CHART_DIR.mkdir(parents=True, exist_ok=True)
    output_path = CHART_DIR / filename
    fig.tight_layout()
    fig.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved {output_path}")


def plot_industry_count(df: pd.DataFrame) -> None:
    data = df["industry"].value_counts().head(10).sort_values()
    fig, ax = plt.subplots(figsize=(10, 6))
    sns.barplot(x=data.values, y=data.index, ax=ax, color="#2f80ed")
    ax.set_title("Top 10 Industries by Unicorn Count")
    ax.set_xlabel("Number of Unicorn Companies")
    ax.set_ylabel("Industry")
    annotate_horizontal_bars(ax)
    save_chart(fig, "01_industry_count.png")


def plot_country_count(df: pd.DataFrame) -> None:
    data = df["country"].value_counts().head(10).sort_values()
    fig, ax = plt.subplots(figsize=(10, 6))
    sns.barplot(x=data.values, y=data.index, ax=ax, color="#16a085")
    ax.set_title("Top 10 Countries by Unicorn Count")
    ax.set_xlabel("Number of Unicorn Companies")
    ax.set_ylabel("Country")
    annotate_horizontal_bars(ax)
    save_chart(fig, "02_country_count.png")


def plot_unicorns_per_year(df: pd.DataFrame) -> None:
    data = df.groupby("year_joined").size().sort_index()
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(data.index, data.values, marker="o", linewidth=2.5, color="#c0392b")
    ax.fill_between(data.index, data.values, alpha=0.2, color="#c0392b")
    ax.set_title("New Unicorns Created Per Year")
    ax.set_xlabel("Year Joined Unicorn Club")
    ax.set_ylabel("Number of New Unicorns")
    ax.grid(True, alpha=0.3)
    save_chart(fig, "03_unicorns_per_year.png")


def plot_time_to_unicorn(df: pd.DataFrame) -> None:
    data = (
        df.groupby("industry")
        .agg(avg_years_to_unicorn=("years_to_unicorn", "mean"), company_count=("company", "count"))
        .query("company_count >= 5")
        .sort_values("avg_years_to_unicorn")
        .head(10)
        .sort_values("avg_years_to_unicorn", ascending=False)
    )

    fig, ax = plt.subplots(figsize=(10, 6))
    sns.barplot(x=data["avg_years_to_unicorn"], y=data.index, ax=ax, color="#8e44ad")
    ax.set_title("Fastest Industries by Average Years to Unicorn")
    ax.set_xlabel("Average Years to Reach $1B Valuation")
    ax.set_ylabel("Industry")
    annotate_horizontal_bars(ax, decimals=1)
    save_chart(fig, "04_time_to_unicorn.png")


def plot_valuation_distribution(df: pd.DataFrame) -> None:
    data = df[df["valuation_b"] < 20]["valuation_b"]
    fig, ax = plt.subplots(figsize=(10, 6))
    sns.histplot(data, bins=25, kde=True, ax=ax, color="#f39c12")
    ax.set_title("Distribution of Unicorn Valuations Under $20B")
    ax.set_xlabel("Valuation ($B)")
    ax.set_ylabel("Number of Companies")
    save_chart(fig, "05_valuation_distribution.png")


def plot_top_valued(df: pd.DataFrame) -> None:
    data = df.nlargest(10, "valuation_b").sort_values("valuation_b")
    fig, ax = plt.subplots(figsize=(10, 6))
    sns.barplot(x=data["valuation_b"], y=data["company"], ax=ax, color="#34495e")
    ax.set_title("Top 10 Highest Valued Unicorn Companies")
    ax.set_xlabel("Valuation ($B)")
    ax.set_ylabel("Company")
    annotate_horizontal_bars(ax, decimals=1, suffix="B")
    save_chart(fig, "06_top_valued.png")


def main() -> int:
    try:
        print("Generating unicorn analysis charts.")
        sns.set_theme(style="whitegrid")
        df = load_clean_data()

        plot_industry_count(df)
        plot_country_count(df)
        plot_unicorns_per_year(df)
        plot_time_to_unicorn(df)
        plot_valuation_distribution(df)
        plot_top_valued(df)

        print("Visualization complete.")
        return 0

    except ServerSelectionTimeoutError:
        print(
            "MongoDB connection failed. Start MongoDB locally at mongodb://localhost:27017/ "
            "and rerun this script.",
            file=sys.stderr,
        )
        return 1
    except (PyMongoError, ValueError) as exc:
        print(f"Visualization error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Unexpected error during visualization: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
