"""
sim.py — Monte Carlo simulation of the fixed routing schedule.

Evaluates how a fixed MILP-chosen routing plan performs under randomised

Methodology:
  - Demand: bootstrap resampling from the cleaned historical data
    (load_demand()), independently per store.

  - Traffic: each route's TomTom-observed multiplier at its 4 nearest
    sampled times (AM: 08/09/10/11, PM: 14/15/16/17) is used to anchor a
    uniform band (+/- BAND_WIDTH) around the multiplier for the sampled
    time closest to when that route is actually run.

  - Capacity breach: if sampled demand pushes a route's cumulative load
    past 16 pallets partway through its stop sequence, the route is
    truncated at that point — cost only accrues up to the breach, and
    every pallet at the breaking stop and any stop after it counts as
    undelivered.
"""

import json
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from load_data import load_demand, load_durations
from demand_averages import weekday_demand, saturday_demand

rng = np.random.default_rng(seed=42)

# true physical capacity (brief) — NOT the 14 buffer used during route generation
TRUCK_CAPACITY = 16

UNLOAD_SEC_PER_PALLET = 18 * 60
NORMAL_RATE_PER_HOUR = 220
OVERTIME_RATE_PER_HOUR = 310
OVERTIME_THRESHOLD_SEC = 4 * 3600

LEASE_COST_PER_2HR_BLOCK = 1400
LEASE_BLOCK_SEC = 2 * 3600

BAND_WIDTH = 0.07

SAMPLED_TIMES = {
    "AM": ["08:00", "09:00", "10:00", "11:00"],
    "PM": ["14:00", "15:00", "16:00", "17:00"],
}


# Load fixed routing plan
def load_chosen_routes(path):
    """Load a stored MILP route selection (list of dicts with
    'stops', 'total_pallets', 'total_time_sec', 'cost')."""
    with open(path) as f:
        return json.load(f)


def load_skipped_stores(path):
    """Load a stored list of skipped store names. PuLP sanitises variable
    names internally (spaces aren't valid), so skipped_stores_*.txt files
    written from v.name have underscores where every other file has
    spaces (e.g. 'New_World_Albany' vs 'New World Albany') — normalise
    here. Worth fixing at the source in lp_stuff.py too, since any other
    code relying on these names verbatim will hit the same mismatch."""
    with open(path) as f:
        raw = json.load(f)
    return [s.replace("_", " ") for s in raw]


def normalise_stops(route):
    """feasible_routes.py stores a single-stop route's 'stops' as a bare
    string, and a multi-stop route's 'stops' as a list — flatten both to
    a plain list of store names, in visit order."""
    stops = route["stops"]
    if isinstance(stops, str):
        return [stops]
    return list(stops)



# Demand resampling — bootstrap, independently per store

"""
independent per-store bootstrap (not whole-day resampling).
This does NOT preserve any store-to-store demand correlation on a given
real day (e.g. a network-wide busy Friday).
"""

def build_bootstrap_pools(demand_df, day_type):
    """
    Return {store: np.array of historical pallet values} for the
    given day_type ('weekday' or 'saturday').
    """
    if day_type == "weekday":
        df = weekday_demand(demand_df)
    elif day_type == "saturday":
        df = saturday_demand(demand_df)
    else:
        raise ValueError("day_type must be 'weekday' or 'saturday'")

    return {
        store: group["pallets"].to_numpy()
        for store, group in df.groupby("store")
    }


def sample_demand(bootstrap_pools, stores):
    """One bootstrap draw of demand for each store in `stores`."""
    return {
        store: rng.choice(bootstrap_pools[store])
        for store in stores
        if store in bootstrap_pools
    }


# Traffic multiplier
def load_multiples_lookup(path):
    """Build {frozenset(stops): {time_str: multiplier}} from a
    *_route_multiples.csv file."""
    df = pd.read_csv(path)
    times = SAMPLED_TIMES["AM"] + SAMPLED_TIMES["PM"]
    lookup = {}
    for _, row in df.iterrows():
        stops = parse_stops_string(row["Stops"])
        lookup[stops] = {t: row[t] for t in times}
    return lookup


def parse_stops_string(stops_str):
    """'Origin -> New World Birkenhead -> Origin' -> frozenset({'New World Birkenhead'})"""
    parts = [p.strip() for p in stops_str.split("->")]
    return frozenset(p for p in parts if p != "Origin")


def pooled_multiplier_distribution(multiples_lookup):
    """Fallback pool: every observed multiplier across every route/time,
    used only if a chosen route has no direct TomTom match."""
    return np.array([
        v for time_dict in multiples_lookup.values() for v in time_dict.values()
    ])


def nearest_sampled_time(shift_start_str, elapsed_seconds, shift_label):
    shift_start = datetime.strptime(shift_start_str, "%H:%M")
    leg_clock_time = shift_start + timedelta(seconds=elapsed_seconds)
    candidates = [datetime.strptime(t, "%H:%M") for t in SAMPLED_TIMES[shift_label]]
    closest = min(candidates, key=lambda t: abs((t - leg_clock_time).total_seconds()))
    return closest.strftime("%H:%M")


def sample_traffic_multiplier(anchor_multiplier, rng_=rng):
    low = max(0.5, anchor_multiplier - BAND_WIDTH)
    high = anchor_multiplier + BAND_WIDTH
    return rng_.uniform(low, high)


# ---------------------------------------------------------------------------
# 4. Leg-level driving times (needed to truncate a route mid-way on breach)
# ---------------------------------------------------------------------------
def build_leg_time_lookup():
    """{(from, to): seconds} for every store<->store and Warehouse<->store
    pair, symmetrised (see driving_time.py discussion)."""
    durations_df = load_durations()
    sym = (durations_df + durations_df.T) / 2
    return sym


LEG_TIMES = build_leg_time_lookup()


def route_leg_times(stops):
    """Ordered list of (from, to, seconds) for Origin -> stop1 -> ... -> Origin."""
    path = ["Warehouse"] + stops + ["Warehouse"]
    legs = []
    for a, b in zip(path[:-1], path[1:]):
        legs.append((a, b, LEG_TIMES.loc[a, b]))
    return legs


# 5. Cost of a realised (post-traffic) duration
def realised_cost(realised_time_sec, is_leased):
    if is_leased:
        blocks = int(np.ceil(realised_time_sec / LEASE_BLOCK_SEC))
        return blocks * LEASE_COST_PER_2HR_BLOCK

    hours = realised_time_sec / 3600
    if realised_time_sec <= OVERTIME_THRESHOLD_SEC:
        return hours * NORMAL_RATE_PER_HOUR
    normal_part = OVERTIME_THRESHOLD_SEC / 3600 * NORMAL_RATE_PER_HOUR
    overtime_hours = np.ceil((realised_time_sec - OVERTIME_THRESHOLD_SEC) / 3600)  # "or part thereof"
    return normal_part + overtime_hours * OVERTIME_RATE_PER_HOUR


# Simulate one route
def simulate_route(route, is_leased, demand_sample, multiples_lookup,
                    pooled_multipliers, shift_label, shift_start):
    stops = normalise_stops(route)
    legs = route_leg_times(stops)  # [(from, to, planned_sec), ...], len = len(stops)+1

    stop_key = frozenset(stops)
    time_multipliers = multiples_lookup.get(stop_key)

    total_demand = sum(demand_sample.get(s, 0) for s in stops)

    elapsed = 0.0
    cost_accrued = 0.0
    cumulative_pallets = 0.0
    delivered_stops = []
    breached = False

    def sampled_multiplier():
        if time_multipliers is not None:
            t_key = nearest_sampled_time(shift_start, elapsed, shift_label)
            anchor = time_multipliers[t_key]
        else:
            # fall back to the pooled
            # distribution of observed multipliers instead of a fixed anchor.
            anchor = rng.choice(pooled_multipliers)
        return sample_traffic_multiplier(anchor)

    for i, stop in enumerate(stops):
        # Capacity is checked BEFORE committing to the leg: a driver
        # already knows the remaining load before leaving the previous
        # stop, so a store that can't be serviced is never driven to in
        # the first place — the truck heads straight back to the depot
        # from the last successfully-delivered stop instead.
        stop_demand = demand_sample.get(stop, 0)
        if cumulative_pallets + stop_demand > TRUCK_CAPACITY:
            breached = True
            break

        leg_from, leg_to, planned_leg_sec = legs[i]
        elapsed += planned_leg_sec * sampled_multiplier()

        # unload at this stop
        elapsed += stop_demand * UNLOAD_SEC_PER_PALLET
        cumulative_pallets += stop_demand
        delivered_stops.append(stop)

    # final leg back to Warehouse — a DIRECT leg from wherever delivery
    # actually stopped, not the next leg in the original planned sequence
    # (that would point toward a store the truck never reached, if a
    # capacity breach cut the route short).
    last_location = delivered_stops[-1] if delivered_stops else "Warehouse"
    final_leg_sec = LEG_TIMES.loc[last_location, "Warehouse"]
    elapsed += final_leg_sec * sampled_multiplier()

    cost = realised_cost(elapsed, is_leased)
    pallets_delivered = cumulative_pallets
    pallets_not_delivered = total_demand - pallets_delivered

    return {
        "cost": cost,
        "pallets_total": total_demand,
        "pallets_delivered": pallets_delivered,
        "pallets_not_delivered": pallets_not_delivered,
        "breached": breached,
        "realised_time_sec": elapsed,
    }


# Simulate one day
def simulate_one_day(chosen_routes, leased_routes, skipped_stores,
                      bootstrap_pools, multiples_lookup, pooled_multipliers,
                      exclusion_cost_lookup, shift_label="AM", shift_start="08:00"):

    all_route_stops = set()
    for r in chosen_routes + leased_routes:
        all_route_stops.update(normalise_stops(r))

    demand_sample = sample_demand(bootstrap_pools, all_route_stops)

    route_results = []
    for r in chosen_routes:
        route_results.append(simulate_route(
            r, is_leased=False, demand_sample=demand_sample,
            multiples_lookup=multiples_lookup, pooled_multipliers=pooled_multipliers,
            shift_label=shift_label, shift_start=shift_start))
    for r in leased_routes:
        route_results.append(simulate_route(
            r, is_leased=True, demand_sample=demand_sample,
            multiples_lookup=multiples_lookup, pooled_multipliers=pooled_multipliers,
            shift_label=shift_label, shift_start=shift_start))

    total_cost = sum(r["cost"] for r in route_results)
    total_pallets = sum(r["pallets_total"] for r in route_results)
    total_delivered = sum(r["pallets_delivered"] for r in route_results)
    n_breached = sum(r["breached"] for r in route_results)

    # skipped stores (fuel-reduction plan): flat exclusion cost, 0 delivered
    skip_cost = sum(exclusion_cost_lookup[s] for s in skipped_stores)
    skip_demand = sum(rng.choice(bootstrap_pools[s]) for s in skipped_stores
                       if s in bootstrap_pools)
    total_cost += skip_cost
    total_pallets += skip_demand
    # skip_demand pallets are entirely "not delivered" by design

    pct_demand_met = total_delivered / total_pallets if total_pallets > 0 else np.nan

    return {
        "total_cost": total_cost,
        "total_pallets": total_pallets,
        "total_delivered": total_delivered,
        "pct_demand_met": pct_demand_met,
        "n_routes_breached": n_breached,
        "n_routes": len(route_results),
    }


# Run simulation n times
def run_simulation(chosen_routes, leased_routes, skipped_stores,
                    demand_df, multiples_path, day_type,
                    exclusion_cost_lookup, n_reps=1000,
                    shift_label="AM", shift_start="08:00"):
    bootstrap_pools = build_bootstrap_pools(demand_df, day_type)
    multiples_lookup = load_multiples_lookup(multiples_path)
    pooled_multipliers = pooled_multiplier_distribution(multiples_lookup)

    results = []
    for _ in range(n_reps):
        day_result = simulate_one_day(
            chosen_routes, leased_routes, skipped_stores,
            bootstrap_pools, multiples_lookup, pooled_multipliers,
            exclusion_cost_lookup, shift_label, shift_start)
        results.append(day_result)

    return pd.DataFrame(results)


# Output
def summarise(results_df, label=""):
    import statsmodels.stats.weightstats as sms

    cost_mean = results_df["total_cost"].mean()
    cost_ci = sms.DescrStatsW(results_df["total_cost"]).tconfint_mean(alpha=0.05)
    pct_met_mean = results_df["pct_demand_met"].mean()
    pct_days_with_breach = (results_df["n_routes_breached"] > 0).mean() * 100

    print(f"--- {label} ---")
    print(f"Mean daily cost:            ${cost_mean:,.2f}")
    print(f"95% CI for mean daily cost: (${cost_ci[0]:,.2f}, ${cost_ci[1]:,.2f})")
    print(f"Mean % of demand met:       {pct_met_mean * 100:.2f}%")
    print(f"% of days with >=1 breach:  {pct_days_with_breach:.1f}%")
    print()

    return {
        "cost_mean": float(cost_mean),
        "cost_ci": [float(cost_ci[0]), float(cost_ci[1])],
        "pct_met_mean": float(pct_met_mean),
        "pct_days_with_breach": float(pct_days_with_breach),
    }


def save_results_json(all_results, path="simulation_results.json"):
    """Write every scenario's summary (as returned by summarise()) to one
    JSON file, keyed by scenario label."""
    with open(path, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"Saved: {path}")



if __name__ == "__main__":
    demand_df = load_demand()

    stores_weekday = list(load_durations().drop(index="Warehouse", columns="Warehouse").index)
    exclusion_cost_lookup = {
        s: 1500 if s.startswith("Pak") else 800 for s in stores_weekday
    }

    all_results = {}

    # --- Baseline weekday plan ---
    chosen = load_chosen_routes("stored_routes/chosen_routes_weekdays.txt")
    leased = load_chosen_routes("stored_routes/leased_routes_weekdays.txt")
    results_baseline = run_simulation(
        chosen, leased, skipped_stores=[],
        demand_df=demand_df, multiples_path="weekday_route_multiples.csv",
        day_type="weekday", exclusion_cost_lookup=exclusion_cost_lookup,
        n_reps=1000,
    )
    all_results["weekday_baseline"] = summarise(results_baseline, "Weekday — baseline")

    # --- Fuel-reduction weekday plan ---
    chosen_fr = load_chosen_routes("stored_routes/chosen_routes_weekdays_fr.txt")
    leased_fr = load_chosen_routes("stored_routes/leased_routes_weekdays_fr.txt")
    skipped_fr = load_skipped_stores("stored_routes/skipped_stores_fr.txt")
    results_fr = run_simulation(
        chosen_fr, leased_fr, skipped_stores=skipped_fr,
        demand_df=demand_df, multiples_path="weekday_fr_route_multiples.csv",
        day_type="weekday", exclusion_cost_lookup=exclusion_cost_lookup,
        n_reps=1000,
    )
    all_results["weekday_fuel_reduction"] = summarise(results_fr, "Weekday — fuel reduction")

    # --- Baseline Saturday plan ---
    # TEMPORARY: reusing weekday_route_multiples.csv until the team
    # generates saturday_route_multiples.csv (real TomTom data for the
    # Saturday chosen routes). Since Saturday's route stop-combinations
    # differ from weekday's, most/all lookups here will miss the exact
    # match and fall back to the pooled multiplier distribution rather
    # than a route-specific anchor — coarser traffic modelling than
    # weekday gets. Swap the path below once saturday_route_multiples.csv
    # exists.
    chosen_sat = load_chosen_routes("stored_routes/chosen_routes_sat.txt")
    leased_sat = load_chosen_routes("stored_routes/leased_routes_sat.txt")
    results_sat_baseline = run_simulation(
        chosen_sat, leased_sat, skipped_stores=[],
        demand_df=demand_df, multiples_path="weekday_route_multiples.csv",
        day_type="saturday", exclusion_cost_lookup=exclusion_cost_lookup,
        n_reps=1000,
    )
    all_results["saturday_baseline"] = summarise(results_sat_baseline, "Saturday — baseline")

    # --- Fuel-reduction Saturday plan ---
    # TEMPORARY: same caveat as above — reusing weekday_fr_route_multiples.csv
    # until saturday_fr_route_multiples.csv exists.
    chosen_sat_fr = load_chosen_routes("stored_routes/chosen_routes_sat_fr.txt")
    leased_sat_fr = load_chosen_routes("stored_routes/leased_routes_sat_fr.txt")
    skipped_sat_fr = load_skipped_stores("stored_routes/skipped_stores_sat_fr.txt")
    results_sat_fr = run_simulation(
        chosen_sat_fr, leased_sat_fr, skipped_stores=skipped_sat_fr,
        demand_df=demand_df, multiples_path="weekday_fr_route_multiples.csv",
        day_type="saturday", exclusion_cost_lookup=exclusion_cost_lookup,
        n_reps=1000,
    )
    all_results["saturday_fuel_reduction"] = summarise(results_sat_fr, "Saturday — fuel reduction")

    save_results_json(all_results, "simulation_results.json")