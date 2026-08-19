#!/usr/bin/env python3
"""
route_times.py

For a set of pre-planned multi-stop delivery routes (JSON files produced by
your route-optimization step), fetches TomTom's predicted travel time for
each ENTIRE route (Origin -> stop 1 -> stop 2 -> ... -> Origin, in the given
order) as a single request per route, and writes a CSV comparing it to your
original estimated time.

INPUT FILE FORMAT
    Each input file is a JSON list of route objects, each with a "route"
    field like:
        ["Origin", "Some Store", "Origin"]
        ["Origin", ["Store A", "Store B", "Store C"], "Origin"]
    (stop order is preserved, not re-optimized)

SETUP
    1. Get a free TomTom API key (no credit card needed):
       https://developer.tomtom.com/user/register
    2. pip install requests
    3. Put chosen_routes_sat.txt, chosen_routes_weekdays.txt, and
       chosen_routes_weekdays_fr.txt in the same folder as this script
       (or point to them with --sat / --weekday / --weekday-fr).
    4. Run:
       python route_times.py --key YOUR_KEY

    Optional: pick specific dates (must be future). Otherwise defaults to
    the next Wednesday (weekday runs) and next Saturday:
       python route_times.py --key YOUR_KEY --weekday-date 2026-08-26 --saturday-date 2026-08-29 --time 08:00

OUTPUT
    weekday_route_times.csv
    weekday_fr_route_times.csv
    saturday_route_times.csv
    Each row = one route, with the original estimated time alongside
    TomTom's predicted time (typical traffic for that day/time) for
    comparison.
"""

import argparse
import csv
import json
import sys
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests

NZ_TZ = ZoneInfo("Pacific/Auckland")

WAREHOUSE_LAT = -36.9079041
WAREHOUSE_LON = 174.7281051

# name -> (lat, lon). Names match exactly what appears in the route JSON files.
NAME_COORDS = {
    "Origin": (WAREHOUSE_LAT, WAREHOUSE_LON),

    "New World Albany": (-36.7281436, 174.710513),
    "New World Birkenhead": (-36.8114278, 174.7114858),
    "New World Botany": (-36.9338828, 174.9114914),
    "New World Browns Bay": (-36.7159615, 174.7472869),
    "New World Devonport": (-36.8295102, 174.7961934),
    "New World Eastridge": (-36.86099, 174.829238),
    "New World Green Bay": (-36.9308233, 174.6790458),
    "New World Hobsonville": (-36.7993487, 174.6449706),
    "New World Howick": (-36.904065, 174.9248668),
    "New World Long Bay": (-36.6852502, 174.7396625),
    "New World Metro Shore City": (-36.787821, 174.7699787),
    "New World Metro Queen St": (-36.8464718, 174.7657806),
    "New World Milford": (-36.7722983, 174.7648051),
    "New World Mt Albert": (-36.8803127, 174.726019),
    "New World Mt Roskill": (-36.9086111, 174.7344444),
    "New World New Lynn": (-36.9108233, 174.6855069),
    "New World Newmarket": (-36.8720079, 174.7779037),
    "New World Ormiston": (-36.9645274, 174.911826),
    "New World Papakura": (-37.064268, 174.9411007),
    "New World Papatoetoe": (-36.9802417, 174.8539063),
    "New World Point Chevalier": (-36.8697645, 174.7127114),
    "New World Remuera": (-36.8819007, 174.7976545),
    "New World Southmall": (-37.0225053, 174.8967004),
    "New World Stonefields": (-36.8902739, 174.831971),
    "New World Victoria Park": (-36.8486497, 174.7512927),

    "Pak 'n Save Albany": (-36.730108, 174.7071498),
    "Pak 'n Save Botany": (-36.9305535, 174.9128891),
    "Pak 'n Save Clendon": (-37.0328005, 174.867622),
    "Pak 'n Save Glen Innes": (-36.875811, 174.855104),
    "Pak 'n Save Highland Park": (-36.8990418, 174.9068675),
    "Pak 'n Save Henderson": (-36.8772956, 174.6325345),
    "Pak 'n Save Lincoln Road": (-36.8574574, 174.6281678),
    "Pak 'n Save Mangere": (-36.9684476, 174.7970282),
    "Pak 'n Save Manukau": (-36.9878442, 174.880734),
    "Pak 'n Save Mt Albert": (-36.8933172, 174.7055616),
    "Pak 'n Save Ormiston": (-36.9650866, 174.9148097),
    "Pak 'n Save Papakura": (-37.0535182, 174.9311235),
    "Pak 'n Save Royal Oak": (-36.9100403, 174.7746132),
    "Pak 'n Save Sylvia Park": (-36.9133467, 174.8400897),
    "Pak 'n Save Wairau Road": (-36.778998, 174.744093),
    "Pak 'n Save Westgate": (-36.8204832, 174.6085373),

    "Four Square Botany Junction": (-36.9651717, 174.90233),
    "Four Square Britomart": (-36.8445238, 174.7676134),
    "Four Square Cockle Bay": (-36.9042058, 174.9392803),
    "Four Square Eden Terrace": (-36.8655491, 174.7598679),
    "Four Square Ellerslie": (-36.8979098, 174.8096805),
    "Four Square Fair Price Henderson": (-36.863634, 174.614478),
    "Four Square Glen Eden": (-36.910914, 174.651446),
    "Four Square Hobsonville": (-36.7982349, 174.6492036),
    "Four Square Lancaster": (-36.789503, 174.694978),
    "Four Square Onehunga": (-36.9187942, 174.7851014),
    "Four Square Remuera": (-36.8804982, 174.8117388),
    "Four Square Pakuranga Heights": (-36.9151401, 174.8895497),
    "Four Square St Heliers": (-36.8508932, 174.8577912),
    "Four Square Torbay": (-36.6949969, 174.750635),
}

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


def flatten_route(route_field):
    """route_field looks like ["Origin", "Store", "Origin"] or ["Origin", ["A","B"], "Origin"]."""
    stops = []
    for item in route_field:
        if isinstance(item, list):
            stops.extend(item)
        else:
            stops.append(item)
    return stops


def fetch_route_minutes(api_key, stop_names, depart_at, session, retries=5):
    """stop_names: ordered list of names, first and last are usually 'Origin'.
    Returns (typical_minutes, missing_names) - missing_names non-empty means we
    could not look up coordinates for one or more stops."""
    missing = [n for n in stop_names if n not in NAME_COORDS]
    if missing:
        return None, missing

    coords = [NAME_COORDS[n] for n in stop_names]
    locations = ":".join(f"{lat},{lon}" for lat, lon in coords)
    url = f"{BASE_URL}/{locations}/json"
    params = {
        "key": api_key,
        "traffic": "true",
        "departAt": depart_at,
        "computeTravelTimeFor": "all",
        "routeType": "fastest",
        "travelMode": "car",
        "computeBestOrder": "false",  # keep the given stop order, don't re-optimize
    }
    for attempt in range(retries):
        try:
            resp = session.get(url, params=params, timeout=30)
        except requests.exceptions.RequestException as e:
            wait = min(2 ** attempt, 30)
            print(f"    Network error ({e.__class__.__name__}), retrying in {wait}s...", file=sys.stderr)
            time.sleep(wait)
            continue
        if resp.status_code == 200:
            data = resp.json()
            summary = data["routes"][0]["summary"]
            seconds = summary.get("historicTrafficTravelTimeInSeconds")
            if seconds is None:
                seconds = summary.get("travelTimeInSeconds")
            return (round(seconds / 60) if seconds is not None else None), []
        if resp.status_code in (429,) or resp.status_code >= 500:
            wait = min(2 ** attempt, 30)
            print(f"    HTTP {resp.status_code}, retrying in {wait}s...", file=sys.stderr)
            time.sleep(wait)
            continue
        print(f"    Error {resp.status_code}: {resp.text[:200]}", file=sys.stderr)
        return None, []
    print("    Giving up after repeated errors, recording as N/A.", file=sys.stderr)
    return None, []


def process_file(api_key, in_path, date_str, out_path, session):
    with open(in_path) as f:
        routes = json.load(f)

    print(f"\n=== {in_path} -> {out_path} ({date_str}, times {TIMES}) ===")
    total_calls = len(routes) * len(TIMES)
    done = 0

    fieldnames = ["RouteIndex", "Stops", "Pallets", "OriginalEst_mins"] + TIMES

    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        f.flush()

        for i, r in enumerate(routes, start=1):
            stop_names = flatten_route(r["route"])
            stops_display = " -> ".join(stop_names)
            original_mins = round(r.get("total_time_sec", 0) / 60) if r.get("total_time_sec") is not None else "N/A"

            row = {
                "RouteIndex": i,
                "Stops": stops_display,
                "Pallets": r.get("total_pallets", ""),
                "OriginalEst_mins": original_mins,
            }

            missing_reported = False
            for t in TIMES:
                depart_at = build_depart_at(date_str, t)
                tomtom_mins, missing = fetch_route_minutes(api_key, stop_names, depart_at, session)
                done += 1

                if missing:
                    if not missing_reported:
                        print(f"  [{done}/{total_calls}] Route {i} SKIPPED - unknown stop name(s): {missing}")
                        missing_reported = True
                    row[t] = "N/A (unknown stop name)"
                else:
                    row[t] = tomtom_mins if tomtom_mins is not None else "N/A"
                    print(f"  [{done}/{total_calls}] Route {i} @ {t}: {row[t]} mins")

                time.sleep(0.25)

            writer.writerow(row)
            f.flush()

    print(f"Written: {out_path}")


def main():
    parser = argparse.ArgumentParser(description="Score pre-planned delivery routes with TomTom travel times across the day")
    parser.add_argument("--key", required=True, help="TomTom API key")
    parser.add_argument("--sat", default="chosen_routes_sat.txt", help="Path to Saturday routes JSON")
    parser.add_argument("--weekday", default="chosen_routes_weekdays.txt", help="Path to weekday routes JSON")
    parser.add_argument("--weekday-fr", default="chosen_routes_weekdays_fr.txt", help="Path to weekday fuel-reduction routes JSON")
    parser.add_argument("--weekday-date", help="Weekday date YYYY-MM-DD (future). Defaults to next Wednesday.")
    parser.add_argument("--saturday-date", help="Saturday date YYYY-MM-DD (future). Defaults to next Saturday.")
    args = parser.parse_args()

    today = datetime.now(NZ_TZ).date()
    weekday_date = args.weekday_date or next_weekday_date(today, 2).isoformat()  # Wed
    saturday_date = args.saturday_date or next_weekday_date(today, 5).isoformat()  # Sat

    session = requests.Session()

    process_file(args.key, args.weekday, weekday_date, "weekday_route_times.csv", session)
    process_file(args.key, args.weekday_fr, weekday_date, "weekday_fr_route_times.csv", session)
    process_file(args.key, args.sat, saturday_date, "saturday_route_times.csv", session)

    print("\nDone. Files written: weekday_route_times.csv, weekday_fr_route_times.csv, saturday_route_times.csv")


if __name__ == "__main__":
    main()