#!/usr/bin/env python3
"""
Sync residential_buildings_unit_types data to Supabase.
Reads 839 unit type records from local PostgreSQL database or CSV fallback,
and upserts them into Supabase via Supabase Service Role Client or direct PostgreSQL connection.
"""

import os
import sys
import csv
import asyncio
import asyncpg
from typing import List, Dict, Any
from dotenv import load_dotenv
from supabase import create_client

# Load environment variables
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://whyhouse:whyhouse@localhost:5432/whyhouse")

# Path to fallback CSV
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(SCRIPT_DIR)
WORKSPACE_DIR = os.path.dirname(BACKEND_DIR)
CSV_FALLBACK_PATH = os.path.join(WORKSPACE_DIR, ".me", "old_260813", "residential_buildings_unit_types.csv")


async def fetch_unit_types_from_local_db() -> List[Dict[str, Any]]:
    db_url = DATABASE_URL
    if "@database" in db_url:
        db_url = db_url.replace("@database", "@localhost")
    print(f"Connecting to local DB ({db_url}) to fetch unit types...")
    conn = await asyncpg.connect(db_url)
    try:
        rows = await conn.fetch("""
            SELECT pnu, exclusive_area, pyung_type, household_count
            FROM public.residential_buildings_unit_types
            ORDER BY id ASC;
        """)
        records = [
            {
                "pnu": r["pnu"],
                "exclusive_area": float(r["exclusive_area"]),
                "pyung_type": r["pyung_type"],
                "household_count": r["household_count"]
            }
            for r in rows
        ]
        print(f"Fetched {len(records)} unit types records from local DB.")
        return records
    finally:
        await conn.close()


def fetch_unit_types_from_csv() -> List[Dict[str, Any]]:
    if not os.path.exists(CSV_FALLBACK_PATH):
        raise FileNotFoundError(f"CSV fallback file not found at {CSV_FALLBACK_PATH}")
    print(f"Reading unit types from CSV fallback ({CSV_FALLBACK_PATH})...")
    records = []
    with open(CSV_FALLBACK_PATH, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            records.append({
                "pnu": row.get("pnu", "").strip(),
                "exclusive_area": float(row.get("exclusive_area", 0)),
                "pyung_type": int(float(row.get("pyung_type"))) if row.get("pyung_type") else None,
                "household_count": int(float(row.get("household_count"))) if row.get("household_count") else 0
            })
    print(f"Read {len(records)} unit types records from CSV.")
    return records


def sync_to_supabase(records: List[Dict[str, Any]]):
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in .env")

    print(f"Initializing Supabase client for {SUPABASE_URL}...")
    sb = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

    # Check if table exists in Supabase
    try:
        res = sb.table("residential_buildings_unit_types").select("count", count="exact").limit(1).execute()
        print(f"Supabase table 'residential_buildings_unit_types' current count: {res.count}")
    except Exception as e:
        print(f"Error checking Supabase table: {e}")
        print("Please ensure the migration SQL (supabase/migrations/20260813000000_create_residential_buildings_unit_types.sql) has been applied to Supabase!")
        sys.exit(1)

    print(f"Upserting {len(records)} records into Supabase in chunks...")
    chunk_size = 100
    total_upserted = 0
    for i in range(0, len(records), chunk_size):
        chunk = records[i:i + chunk_size]
        res = sb.table("residential_buildings_unit_types").upsert(chunk).execute()
        total_upserted += len(chunk)
        print(f"  Upserted {total_upserted}/{len(records)} records...")

    # Final count check
    res_final = sb.table("residential_buildings_unit_types").select("count", count="exact").limit(1).execute()
    print(f"\nSUCCESS! Supabase table 'residential_buildings_unit_types' now has {res_final.count} records.")


async def main():
    records = []
    try:
        records = await fetch_unit_types_from_local_db()
    except Exception as e:
        print(f"Could not fetch from local DB ({e}), falling back to CSV...")
        records = fetch_unit_types_from_csv()

    if not records:
        print("No unit types records found to sync.")
        sys.exit(1)

    sync_to_supabase(records)


if __name__ == "__main__":
    asyncio.run(main())
