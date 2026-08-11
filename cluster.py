from demand_averages import weekday_average, saturday_average
from load_data import load_durations, load_demand
import pandas as pd
import matplotlib.pyplot as plt

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

def budget_table(avg_pallets_per_store, label, n_range=range(0, 9)):
    rows = []
    for n in n_range:
        budget, per_leg = driving_budget_per_leg(avg_pallets_per_store, n)
        rows.append({"day_type": label, "num_stores": n,
                      "driving_budget_min": budget, "per_leg_min": per_leg})
    return pd.DataFrame(rows)

weekday_table = budget_table(weekday_avg_df["huber_mean_pallets"].mean(), "Weekday")
saturday_table = budget_table(saturday_avg_df["huber_mean_pallets"].mean(), "Saturday")
budget_df = pd.concat([weekday_table, saturday_table], ignore_index=True)

fig, ax = plt.subplots(figsize=(7, 4.5))
for label, group in budget_df.groupby("day_type"):
    ax.plot(group["num_stores"], group["driving_budget_min"], marker="o", label=label)
ax.axhline(0, color="black", linewidth=1, linestyle="--")
ax.set_xlabel("Stores on route")
ax.set_ylabel("Remaining budget after unloading (min)")
ax.set_title("Trip budget consumed by unloading, by route size")
ax.legend()
plt.savefig('driving_budget_graph.png')
plt.show()