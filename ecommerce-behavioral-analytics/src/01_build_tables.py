"""Step 1: run the SQL pipeline in DuckDB.

Builds `recsys.duckdb` in the repository root (event tables, all_events,
cart_items, user_features, user_segments, user_sessions, cohort_retention,
transitions, category_abandonment) and prints the result of every query in
sql/ecommerce_behavioral_analysis.sql.

Run from the repository root:  python src/01_build_tables.py
"""
import os
import re
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
SQL_FILE = ROOT / "sql" / "ecommerce_behavioral_analysis.sql"
DB_FILE = ROOT / "recsys.duckdb"
DATA = ROOT / "data" / "product_buy_sample.parquet"


def statements(sql: str):
    sql = re.sub(r"/\*.*?\*/", "", sql, flags=re.S)        # drop block comments
    for stmt in sql.split(";"):
        if re.sub(r"--.*", "", stmt).strip():
            yield stmt.strip()


def main():
    if not DATA.exists():
        raise SystemExit(f"Sample data not found in data/. See data/README.md.")
    os.chdir(ROOT)                                          # SQL uses paths relative to the repo root
    con = duckdb.connect(str(DB_FILE))
    for stmt in statements(SQL_FILE.read_text()):
        result = con.execute(stmt)
        code = re.sub(r"--.*", "", stmt).strip().upper()
        if code.startswith(("SELECT", "WITH")):
            print(result.df().to_string(index=False), end="\n\n")
    counts = {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
              for t in ["all_events", "cart_items", "user_segments", "user_sessions"]}
    print("Tables built:", counts)
    con.close()


if __name__ == "__main__":
    main()
