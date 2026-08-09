from demand_averages import weekday_average, saturday_average
from load_data import load_durations, load_demand

durations_df = load_durations()

demand_df = load_demand()

weekday_avg_df = weekday_average(demand_df)   # one huber_mean_pallets value per store
saturday_avg_df = saturday_average(demand_df)

def symmetrize_durations(durations_df):
    """Average forward/reverse travel time between each pair of locations."""
    return (durations_df + durations_df.T) / 2



def driving_budget_per_leg(avg_pallets_per_store, num_stores_on_route,
                            trip_cap_minutes=210, unload_min_per_pallet=18):
    """
    Given an assumed route size (num_stores_on_route) and average pallets
    per store, work out how much of the 3.5hr trip cap is left for driving
    after unloading, and split that evenly across the legs of the route
    (depot -> store1 -> ... -> storeN -> depot = N+1 legs).
    """
    total_unload_min = num_stores_on_route * avg_pallets_per_store * unload_min_per_pallet
    driving_budget_min = trip_cap_minutes - total_unload_min
    num_legs = num_stores_on_route + 1
    return driving_budget_min, driving_budget_min / num_legs


for n in range(1, 9):
    budget, per_leg = driving_budget_per_leg(weekday_avg_df["huber_mean_pallets"].mean(), n)
    print(f"{n} stores: total driving budget = {budget:.1f} min, per leg = {per_leg:.1f} min")

print("-"*50)

for n in range(1, 9):
    budget, per_leg = driving_budget_per_leg(saturday_avg_df["huber_mean_pallets"].mean(), n)
    print(f"{n} stores: total driving budget = {budget:.1f} min, per leg = {per_leg:.1f} min")