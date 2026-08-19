#!/usr/bin/env python3
"""
warehouse_to_supermarkets.py

For a fixed origin ("Warehouse") and a list of Auckland supermarkets, fetches
TomTom drive-time estimates in BOTH directions (Warehouse -> Store and
Store -> Warehouse) at 8 times of day, for a representative weekday and a
representative Saturday. Writes two CSV files.

SETUP
    1. Get a free TomTom API key (no credit card needed):
       https://developer.tomtom.com/user/register
    2. pip install requests
    3. Run:
       python warehouse_to_supermarkets.py --key YOUR_KEY

    Optional: pick which specific weekday/Saturday to use (must be future
    dates), otherwise it defaults to the next Wednesday and next Saturday:
       python warehouse_to_supermarkets.py --key YOUR_KEY \
           --weekday-date 2026-08-26 --saturday-date 2026-08-29

COST
    55 destinations x 8 times x 2 directions x 2 day-types = 1,760 requests.
    Free tier allows 2,500/day, so this fits in a single run.

WHAT THE NUMBER MEANS
    Each figure is TomTom's predicted "typical" travel time for that
    departure time and day of week (historicTrafficTravelTimeInSeconds),
    rounded to the nearest minute. It is a single estimate, not a range.
"""

import argparse
import csv
import sys
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests

NZ_TZ = ZoneInfo("Pacific/Auckland")

WAREHOUSE_LAT = -36.9079041
WAREHOUSE_LON = 174.7281051

# name, longitude, latitude (as supplied by the user)
DESTINATIONS = [
    ("New World Albany", 174.710513, -36.7281436),
    ("New World Birkenhead", 174.7114858, -36.8114278),
    ("New World Botany", 174.9114914, -36.9338828),
    ("New World Browns Bay", 174.7472869, -36.7159615),
    ("New World Devonport", 174.7961934, -36.8295102),
    ("New World Eastridge", 174.829238, -36.86099),
    ("New World Green Bay", 174.6790458, -36.9308233),
    ("New World Hobsonville", 174.6449706, -36.7993487),
    ("New World Howick", 174.9248668, -36.904065),
    ("New World Long Bay", 174.7396625, -36.6852502),
    ("New World Metro Shore City", 174.7699787, -36.787821),
    ("New World Metro Queen St", 174.7657806, -36.8464718),
    ("New World Milford", 174.7648051, -36.7722983),
    ("New World Mt Albert", 174.726019, -36.8803127),
    ("New World Mt Roskill", 174.7344444, -36.9086111),
    ("New World New Lynn", 174.6855069, -36.9108233),
    ("New World Newmarket", 174.7779037, -36.8720079),
    ("New World Ormiston", 174.911826, -36.9645274),
    ("New World Papakura", 174.9411007, -37.064268),
    ("New World Papatoetoe", 174.8539063, -36.9802417),
    ("New World Point Chevalier", 174.7127114, -36.8697645),
    ("New World Remuera", 174.7976545, -36.8819007),
    ("New World Southmall", 174.8967004, -37.0225053),
    ("New World Stonefields", 174.831971, -36.8902739),
    ("New World Victoria Park", 174.7512927, -36.8486497),
    ("Pak'nSave Albany", 174.7071498, -36.730108),
    ("Pak'nSave Botany", 174.9128891, -36.9305535),
    ("Pak'nSave Clendon", 174.867622, -37.0328005),
    ("Pak'nSave Glen Innes", 174.855104, -36.875811),
    ("Pak'nSave Highland Park", 174.9068675, -36.8990418),
    ("Pak'nSave Henderson", 174.6325345, -36.8772956),
    ("Pak'nSave Lincoln Road", 174.6281678, -36.8574574),
    ("Pak'nSave Mangere", 174.7970282, -36.9684476),
    ("Pak'nSave Manukau", 174.880734, -36.9878442),
    ("Pak'nSave Mt Albert", 174.7055616, -36.8933172),
    ("Pak'nSave Ormiston", 174.9148097, -36.9650866),
    ("Pak'nSave Papakura", 174.9311235, -37.0535182),
    ("Pak'nSave Royal Oak", 174.7746132, -36.9100403),
    ("Pak'nSave Sylvia Park", 174.8400897, -36.9133467),
    ("Pak'nSave Wairau Road", 174.744093, -36.778998),
    ("Pak'nSave Westgate", 174.6085373, -36.8204832),
    ("Four Square Botany Junction", 174.90233, -36.9651717),
    ("Four Square Britomart", 174.7676134, -36.8445238),
    ("Four Square Cockle Bay", 174.9392803, -36.9042058),
    ("Four Square Eden Terrace", 174.7598679, -36.8655491),
    ("Four Square Ellerslie", 174.8096805, -36.8979098),
    ("Four Square Fair Price Henderson", 174.614478, -36.863634),
    ("Four Square Glen Eden", 174.651446, -36.910914),
    ("Four Square Hobsonville", 174.6492036, -36.7982349),
    ("Four Square Lancaster", 174.694978, -36.789503),
    ("Four Square Onehunga", 174.7851014, -36.9187942),
    ("Four Square Remuera", 174.8117388, -36.8804982),
    ("Four Square Pakuranga Heights", 174.8895497, -36.9151401),
    ("Four Square St Heliers", 174.8577912, -36.8508932),
    ("Four Square Torbay", 174.750635, -36.6949969),
]

TIMES = ["08:00", "09:00", "10:00", "11:00", "14:00", "15:00", "16:00", "17:00"]

BASE_URL = "https://api.tomtom.com/routing/1/calculateRoute"


def next_weekday_date(ref_date, target_idx):
    """Next date (strictly after ref_date) that falls on the given weekday index (Mon=0..Sun=6)."""
    days_ahead = (target_idx - ref_date.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7
    return ref_date + timedelta(days=days_ahead)


def build_depart_at(date_str, time_str):
    dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
    dt = dt.replace(tzinfo=NZ_TZ)
    return dt.isoformat(timespec="seconds")


def fetch_typical_minutes(api_key, origin, dest, depart_at, session, retries=5):
    """origin/dest are (lat, lon) tuples. Returns minutes (int) or None."""
    locations = f"{origin[0]},{origin[1]}:{dest[0]},{dest[1]}"
    url = f"{BASE_URL}/{locations}/json"
    params = {
        "key": api_key,
        "traffic": "true",
        "departAt": depart_at,
        "computeTravelTimeFor": "all",
        "routeType": "fastest",
        "travelMode": "car",
    }
    for attempt in range(retries):
        try:
            resp = session.get(url, params=params, timeout=30)
        except requests.exceptions.RequestException as e:
            wait = min(2 ** attempt, 30)
            print(f"  Network error ({e.__class__.__name__}), retrying in {wait}s...", file=sys.stderr)
            time.sleep(wait)
            continue
        if resp.status_code == 200:
            data = resp.json()
            summary = data["routes"][0]["summary"]
            seconds = summary.get("historicTrafficTravelTimeInSeconds")
            if seconds is None:
                seconds = summary.get("travelTimeInSeconds")
            return round(seconds / 60) if seconds is not None else None
        if resp.status_code == 429:
            wait = min(2 ** attempt, 30)
            print(f"  Rate limited, waiting {wait}s...", file=sys.stderr)
            time.sleep(wait)
            continue
        if resp.status_code >= 500:
            wait = min(2 ** attempt, 30)
            print(f"  Server error {resp.status_code}, retrying in {wait}s...", file=sys.stderr)
            time.sleep(wait)
            continue
        print(f"  Error {resp.status_code}: {resp.text[:200]}", file=sys.stderr)
        return None
    print("  Giving up on this request after repeated errors, recording as N/A.", file=sys.stderr)
    return None


def run_day(api_key, date_str, day_label, out_path, session):
    warehouse = (WAREHOUSE_LAT, WAREHOUSE_LON)
    total = len(DESTINATIONS) * len(TIMES) * 2
    done = 0

    print(f"\n=== {day_label} ({date_str}) ===")

    # Open in write mode and flush after every row, so progress survives a crash.
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["Destination", "Time", "ToStore_mins", "FromStore_mins"])
        writer.writeheader()
        f.flush()

        for name, lon, lat in DESTINATIONS:
            store = (lat, lon)
            for t in TIMES:
                depart_at = build_depart_at(date_str, t)

                to_store = fetch_typical_minutes(api_key, warehouse, store, depart_at, session)
                done += 1
                print(f"[{done}/{total}] {name} @ {t} (to store): {to_store}")
                time.sleep(0.25)

                from_store = fetch_typical_minutes(api_key, store, warehouse, depart_at, session)
                done += 1
                print(f"[{done}/{total}] {name} @ {t} (from store): {from_store}")
                time.sleep(0.25)

                writer.writerow({
                    "Destination": name,
                    "Time": t,
                    "ToStore_mins": to_store if to_store is not None else "N/A",
                    "FromStore_mins": from_store if from_store is not None else "N/A",
                })
                f.flush()

    print(f"Written: {out_path}")


def main():
    parser = argparse.ArgumentParser(description="Warehouse <-> supermarket drive times via TomTom")
    parser.add_argument("--key", required=True, help="TomTom API key")
    parser.add_argument("--weekday-date", help="Weekday date YYYY-MM-DD (future). Defaults to next Wednesday.")
    parser.add_argument("--saturday-date", help="Saturday date YYYY-MM-DD (future). Defaults to next Saturday.")
    args = parser.parse_args()

    today = datetime.now(NZ_TZ).date()
    weekday_date = args.weekday_date or next_weekday_date(today, 2).isoformat()  # Wed
    saturday_date = args.saturday_date or next_weekday_date(today, 5).isoformat()  # Sat

    session = requests.Session()
    run_day(args.key, weekday_date, "Weekday", "../weekday_times.csv", session)
    run_day(args.key, saturday_date, "Saturday", "../saturday_times.csv", session)

    print("\nDone. Files written: weekday_times.csv, saturday_times.csv")


if __name__ == "__main__":
    main()