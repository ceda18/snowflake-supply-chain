"""Downloads IMF PortWatch data (ArcGIS REST API) into data/raw/. Always replaces existing files.

Daily data starts in START_YEAR: enough history for the Red Sea crisis (from late 2023)
plus a year-over-year baseline, and small enough for the local emulator.

Each dataset is written in chunks of CHUNK_ROWS rows (name_000.csv, name_001.csv, ...),
because the LocalStack Snowflake emulator loads at most 50,000 rows per file with COPY INTO.

Usage:
    python scripts/download_data.py
"""
import time
from pathlib import Path

import pandas as pd
import requests

BASE = "https://services9.arcgis.com/weJ1QsnbMYJlCHdG/arcgis/rest/services"
START_YEAR = 2023
DATASETS = {
    # name: (ArcGIS service, row filter)
    "chokepoints_meta": ("PortWatch_chokepoints_database", "1=1"),                 # reference data
    "chokepoints_daily": ("Daily_Chokepoints_Data", f"year >= {START_YEAR}"),     # daily transits
}
OUT = Path(__file__).resolve().parents[1] / "data" / "raw"
OUT.mkdir(parents=True, exist_ok=True)
CHUNK_ROWS = 25_000

session = requests.Session()


def get(url: str, **params) -> dict:
    r = session.get(url, params={"f": "json", **params}, timeout=60)
    r.raise_for_status()
    data = r.json()
    if "error" in data:
        raise RuntimeError(data["error"])
    return data


def fetch_all(service: str, where: str) -> pd.DataFrame:
    layer = f"{BASE}/{service}/FeatureServer/0"
    info = get(layer)
    oid = info["objectIdField"]
    page = info.get("maxRecordCount", 1000)
    total = get(f"{layer}/query", where=where, returnCountOnly="true")["count"]
    print(f"{service}: {total:,} rows")

    rows, last = [], -1
    while True:                                         # keyset pagination: OID > last seen
        t = time.time()
        data = get(f"{layer}/query", where=f"({where}) AND {oid} > {last}", outFields="*",
                   returnGeometry="false", orderByFields=oid, resultRecordCount=page)
        feats = data.get("features", [])
        if not feats:
            break
        rows += [f["attributes"] for f in feats]
        last = feats[-1]["attributes"][oid]
        print(f"  {len(rows):,}/{total:,}  ({time.time() - t:.1f}s)", flush=True)
    return pd.DataFrame(rows)


for name, (service, where) in DATASETS.items():
    df = fetch_all(service, where)
    for old in OUT.glob(f"{name}*.csv"):                # remove previous files, incl. old chunks
        old.unlink()
    n_files = 0
    for start in range(0, len(df), CHUNK_ROWS):
        df.iloc[start:start + CHUNK_ROWS].to_csv(OUT / f"{name}_{n_files:03d}.csv", index=False)
        n_files += 1
    print(f"-> {name}: {len(df):,} rows in {n_files} file(s) | columns: {list(df.columns)}\n")
