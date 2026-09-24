"""Build the client-level sample used in this project from the full RecSys 2025 dataset.

Users are drawn from the purchase log, and every event for those users is kept, so
complete journeys stay intact. Output: data/*_sample.parquet

Usage:  python scripts/sample_recsys.py --data-dir /path/to/extracted/recsys_data
Note:   the original sample in this project was drawn without a fixed seed
        (DuckDB USING SAMPLE). This version fixes the seed so the sample is reproducible.
"""
import argparse
import glob
import os

import duckdb

EVENTS = ["product_buy", "add_to_cart", "remove_from_cart", "page_visit", "search_query"]


def find(data_dir, name):
    hits = glob.glob(os.path.join(data_dir, "**", f"{name}.parquet"), recursive=True)
    if not hits:
        raise FileNotFoundError(f"{name}.parquet not found under {data_dir}")
    return hits[0].replace("\\", "/")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--out-dir", default="data")
    ap.add_argument("--n-rows", type=int, default=50_000, help="purchase rows to sample (~46.7k distinct users)")
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()
    os.makedirs(a.out_dir, exist_ok=True)
    con = duckdb.connect()
    paths = {n: find(a.data_dir, n) for n in EVENTS + ["product_properties"]}

    con.execute(f"""CREATE TEMP TABLE sample_clients AS
        SELECT DISTINCT client_id FROM read_parquet('{paths["product_buy"]}')
        USING SAMPLE reservoir({a.n_rows} ROWS) REPEATABLE ({a.seed})""")
    print("sampled users:", con.execute("SELECT COUNT(*) FROM sample_clients").fetchone()[0])

    for name in EVENTS:
        out = f"{a.out_dir}/{name}_sample.parquet"
        con.execute(f"""COPY (SELECT e.* FROM read_parquet('{paths[name]}') e JOIN sample_clients USING (client_id))
                        TO '{out}' (FORMAT PARQUET)""")
        rows = con.execute(f"SELECT COUNT(*) FROM read_parquet('{out}')").fetchone()[0]
        print(f"{name}: {rows:,} rows")

    con.execute(f"""COPY (SELECT DISTINCT p.* FROM read_parquet('{paths["product_properties"]}') p
        WHERE p.sku IN (SELECT sku FROM read_parquet('{a.out_dir}/product_buy_sample.parquet')
                        UNION SELECT sku FROM read_parquet('{a.out_dir}/add_to_cart_sample.parquet')))
        TO '{a.out_dir}/product_properties_sample.parquet' (FORMAT PARQUET)""")
    print("done")


if __name__ == "__main__":
    main()
