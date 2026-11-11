"""Runs the SQL pipeline (setup -> bronze -> silver -> gold -> checks) against Snowflake.

By default it connects to the local LocalStack Snowflake emulator.

Placeholders supported in the SQL files:
    <% data_dir %>        absolute path to data/raw
    <% each:PATTERN %>    the statement runs once per file in data/raw matching PATTERN

Usage:
    python scripts/run_pipeline.py
"""
import io
import re
import sys
import time
from pathlib import Path

import pandas as pd
import snowflake.connector
from snowflake.connector.util_text import split_statements

ROOT = Path(__file__).resolve().parents[1]
SQL_DIR = ROOT / "sql"
DATA_DIR = ROOT / "data" / "raw"
EACH = re.compile(r"<% each:([^%]+?) %>")

# Bronze table -> source files; row counts must match after loading
RECONCILE = {
    "SUPPLY_CHAIN.BRONZE.CHOKEPOINTS_DAILY_RAW": "chokepoints_daily_*.csv",
    "SUPPLY_CHAIN.BRONZE.CHOKEPOINTS_META_RAW": "chokepoints_meta_*.csv",
}


def connect() -> snowflake.connector.SnowflakeConnection:
    # Emulator accepts any credentials. For a real account, swap host/user/password.
    return snowflake.connector.connect(
        user="test",
        password="test",
        account="test",
        host="snowflake.localhost.localstack.cloud",
        port=4566,
        protocol="https",
    )


def expand(stmt: str) -> list[str]:
    """One statement per matching file for <% each:PATTERN %>, otherwise unchanged."""
    match = EACH.search(stmt)
    if not match:
        return [stmt]
    files = sorted(DATA_DIR.glob(match.group(1).strip()))
    if not files:
        sys.exit(f"No files in {DATA_DIR} match {match.group(1)!r}")
    return [EACH.sub(f.name, stmt) for f in files]


def label(stmt: str) -> str:
    text = " ".join(stmt.split()).replace(DATA_DIR.as_posix(), "data/raw")
    return text if len(text) <= 80 else text[:77] + "..."


def print_result(cur) -> None:
    cols = [d[0] for d in cur.description]
    rows = cur.fetchall()
    widths = [max([len(str(c))] + [len(str(r[i])) for r in rows]) for i, c in enumerate(cols)]
    print("    " + " | ".join(str(c).ljust(w) for c, w in zip(cols, widths)))
    print("    " + "-+-".join("-" * w for w in widths))
    for r in rows:
        print("    " + " | ".join(str(v).ljust(w) for v, w in zip(r, widths)))
    print()


def run_file(conn, path: Path) -> None:
    sql = path.read_text().replace("<% data_dir %>", DATA_DIR.as_posix())
    is_checks = "checks" in path.name
    print(f"\n== {path.name} ==")
    started = time.time()

    for raw, _ in split_statements(io.StringIO(sql), remove_comments=True):
        if not raw.strip():
            continue
        for stmt in expand(raw):
            if not is_checks:
                print(f"   {label(stmt)}", end="", flush=True)
            t = time.time()
            try:
                cur = conn.cursor().execute(stmt)
            except snowflake.connector.Error as e:
                print(f"\n\nFAILED in {path.name}:\n\n{stmt}\n\n{e}")
                sys.exit(1)
            if is_checks:
                if cur.description and not stmt.lstrip().upper().startswith("USE"):
                    print_result(cur)
            else:
                print(f"  ({time.time() - t:.1f}s)")

    print(f"OK  {path.name} ({time.time() - started:.1f}s)")


def reconcile(conn) -> None:
    """Row count in each bronze table must equal the rows in its source CSV files."""
    print("\n== reconcile bronze vs source files ==")
    for table, pattern in RECONCILE.items():
        expected = sum(len(pd.read_csv(f)) for f in DATA_DIR.glob(pattern))
        loaded = conn.cursor().execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        ok = loaded == expected
        print(f"   {'OK  ' if ok else 'FAIL'} {table}: {loaded:,} loaded / {expected:,} in CSV")
        if not ok:
            sys.exit("Bronze load is incomplete, stopping.")


def main() -> None:
    for pattern in RECONCILE.values():
        if not list(DATA_DIR.glob(pattern)):
            sys.exit(f"No {pattern} in {DATA_DIR}. Run first: python scripts/download_data.py")

    conn = connect()
    try:
        for path in sorted(SQL_DIR.glob("*.sql")):
            run_file(conn, path)
            if path.name.startswith("01_"):
                reconcile(conn)
    finally:
        conn.close()
    print("\nPipeline finished. Start the app: streamlit run app/streamlit_app.py")


if __name__ == "__main__":
    main()
