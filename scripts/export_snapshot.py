"""Exports the GOLD tables to data/gold/*.csv.

The app falls back to these files when Snowflake isn't reachable, so it can be
deployed (e.g. Streamlit Community Cloud) or run without the emulator.

Usage:
    python scripts/export_snapshot.py
"""
from pathlib import Path

import pandas as pd

from run_pipeline import connect

OUT = Path(__file__).resolve().parents[1] / "data" / "gold"
TABLES = ["chokepoint_weekly", "disruption_monitor", "red_sea_rerouting"]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    conn = connect()
    try:
        for table in TABLES:
            cur = conn.cursor().execute(f"select * from supply_chain.gold.{table}")
            df = pd.DataFrame(cur.fetchall(), columns=[d[0].lower() for d in cur.description])
            df.to_csv(OUT / f"{table}.csv", index=False)
            print(f"{table}: {len(df):,} rows -> data/gold/{table}.csv")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
