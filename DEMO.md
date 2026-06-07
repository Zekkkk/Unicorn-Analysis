# Demo Commands

```bash
cd /Users/zekoosmani/Unicorn-Analysis
source .venv/bin/activate
pip install -r requirements.txt
docker start unicorn-mongo
export POSTGRES_DSN="postgresql://postgres:3452@localhost:5433/unicorn_analysis"
python3 scripts/05_migrate_postgres_to_mongo.py
python3 scripts/05_migrate_postgres_to_mongo.py
python3 scripts/06_validate_migration.py
python3 scripts/04_visualize.py
open outputs/relational_erd.png
open outputs/validation_report.txt
open outputs/charts
```

```bash
docker run --name unicorn-mongo -p 27017:27017 -d mongo:latest
```
