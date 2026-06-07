# Unicorn Analysis

University data engineering project by Fortan Zaimi and Zeqirija Osmani.

This project analyzes global unicorn startups, companies valued at $1B or more, using Python, Pandas, PyMongo, MongoDB, Matplotlib, and Seaborn. The dataset is stored in `data/Unicorn_Companies.csv` and loaded into a local MongoDB database for NoSQL-style cleaning, aggregation, and reporting.

## Project Structure

```text
unicorn-analysis/
├── data/
│   └── Unicorn_Companies.csv
├── scripts/
│   ├── 01_ingest.py
│   ├── 02_clean.py
│   ├── 03_queries.py
│   └── 04_visualize.py
├── outputs/
│   └── charts/
├── notebooks/
│   └── analysis.ipynb
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
pip install pandas pymongo matplotlib seaborn jupyter
```

Start MongoDB with Docker:

```bash
docker run --name unicorn-mongo -p 27017:27017 -d mongo:latest
```

If the container already exists, start it again:

```bash
docker start unicorn-mongo
```

All scripts use this connection string:

```text
mongodb://localhost:27017/
```

## How to Run

Run the scripts in order from the project root:

```bash
python scripts/01_ingest.py
python scripts/02_clean.py
python scripts/03_queries.py
python scripts/04_visualize.py
```

Then open the notebook:

```bash
jupyter notebook notebooks/analysis.ipynb
```

## Scripts

`scripts/01_ingest.py` loads `data/Unicorn_Companies.csv` with Pandas and inserts all rows into MongoDB database `unicorn_db`, collection `companies`.

`scripts/02_clean.py` reads from `companies`, cleans valuation, date, founded year, and derived fields, then saves clean documents to `companies_clean`.

`scripts/03_queries.py` runs MongoDB aggregation pipelines for the four analysis objectives and prints ranked results.

`scripts/04_visualize.py` reads clean data from MongoDB and saves six PNG charts to `outputs/charts/`.

## Analysis Areas

1. Industry Analysis: identifies the top industries by unicorn company count.
2. Geographic Distribution: compares the countries with the largest unicorn ecosystems.
3. Fastest Growing Sectors: tracks new unicorns by year and highlights industries that grew fastest from 2020 to 2022.
4. Time to Unicorn: calculates the average number of years required to reach $1B valuation by industry and compares average industry valuations.

## Generated Charts

The visualization script creates:

```text
outputs/charts/01_industry_count.png
outputs/charts/02_country_count.png
outputs/charts/03_unicorns_per_year.png
outputs/charts/04_time_to_unicorn.png
outputs/charts/05_valuation_distribution.png
outputs/charts/06_top_valued.png
```
