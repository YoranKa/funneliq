"""
Loads data/funnel_marketing_data.csv into the funnel_records table.

Uses the service_role key on purpose: this is an administrative, one-time
load, not something an app user does, so it should bypass RLS rather than
need a policy written for it.

Usage:
    python db/load_data.py
"""

import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from supabase import create_client

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

CSV_PATH = ROOT / "data" / "funnel_marketing_data.csv"
BATCH_SIZE = 500


def main():
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    if not key:
        raise SystemExit("SUPABASE_SERVICE_ROLE_KEY is empty in .env")

    client = create_client(url, key)

    df = pd.read_csv(CSV_PATH)
    df["referred"] = df["referred"].map({"Yes": True, "No": False})
    df["purchased"] = df["purchased"].astype(bool)
    df["upsell"] = df["upsell"].astype(bool)

    # NaN isn't valid JSON; ltv_months/cumulative_profit have real gaps
    # (see docs/package_1_findings.md), so those become SQL NULL instead.
    # pandas can't hold None in a float64 column (it silently reverts to
    # NaN), so the swap has to happen per-field after converting to dicts.
    records = df.to_dict(orient="records")
    for record in records:
        for field, value in record.items():
            if isinstance(value, float) and pd.isna(value):
                record[field] = None

    print(f"Loading {len(records)} rows into funnel_records...")
    for i in range(0, len(records), BATCH_SIZE):
        batch = records[i : i + BATCH_SIZE]
        client.table("funnel_records").insert(batch).execute()
        print(f"  inserted rows {i} - {i + len(batch)}")

    print("Done.")


if __name__ == "__main__":
    main()
