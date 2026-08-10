from demand_averages import weekday_average, saturday_average
from load_data import load_durations, load_demand
from typing import List, Dict, Any
import pandas as pd

# loading data
durations_df = load_durations()
demand_df = load_demand()
week_avg = weekday_average(demand_df)
sat_avg = saturday_average(demand_df)

# setting store to index and pulling only the averages we want to use
week_avg = week_avg[['store', 'huber_pallets_ceil']].set_index('store')
sat_avg = sat_avg[['store', 'huber_pallets_round']].set_index('store')

# creating a separate warehouse df then removing it from original df
warehouse_df = durations_df.iloc[55]
warehouse_df = warehouse_df.drop('Warehouse')
durations_df =  durations_df.drop(columns = ['Warehouse'])
durations_df = durations_df.drop('Warehouse')

# ordering the dataframes such that they all follow the same order
order = warehouse_df.index.tolist()
df_week_avg = week_avg.loc[order]
df_sat_avg = sat_avg.loc[order]

# normalizing to series
df_week_avg = df_week_avg.squeeze()
df_sat_avg = df_sat_avg.squeeze()
warehouse_df = warehouse_df.squeeze()

def generate_feasible_routes(
        start_node: int | str,
        df_origin : pd.DataFrame,
        df_start : pd.DataFrame,
        df_demand : pd.DataFrame,
        max_capacity: float = 14.0,
        max_time: float = 12600.0,
        time_per_pallet: float = 1080.0
) -> List[Dict[str, Any]]:
    """"""
    # making start node into a series
    s_start = df_start[start_node]
    all_nodes = list(df_demand.index)

    # initialising starting values
    start_demand = float(df_demand.loc[start_node])
    travel_from_origin = float(df_origin.loc[start_node])
    service_time_start = start_demand * time_per_pallet
    initial_accumulated_time = travel_from_origin + service_time_start
    base_route_time = initial_accumulated_time + travel_from_origin

    # adding base one store route: [Origin -> start_node -> Origin]
    feasible_routes = [{
        "route": ["Origin", start_node, "Origin"],
        "stops": [start_node],
        "total_pallets": start_demand,
        "total_time_sec": base_route_time
    }]

    def dfs(current_path: List[int | str], current_load: float, accumulated_time: float):
        for next_node in all_nodes:
            if next_node in current_path:
                continue

            # calculating potential load
            next_demand = float(df_demand.loc[next_node])
            new_load = current_load + next_demand

            # checking capacity constraint
            if new_load > max_capacity:
                continue

            # calculating new travel time with introduction of new node
            leg_travel_time = float(df_start.loc[next_node])
            next_service_time = next_demand * time_per_pallet
            new_accumulated_time = accumulated_time + leg_travel_time + next_service_time
            total_route_time = new_accumulated_time + float(df_origin.loc[next_node])

            # checking it is within time constraint
            if total_route_time <= max_time:
                new_path = current_path + [next_node]
                feasible_routes.append({
                    "route": ["Origin", new_path, "Origin"],
                    "stops": new_path,
                    "total_pallets": new_load,
                    "total_time_sec": total_route_time
                })

                dfs(new_path, new_load, new_accumulated_time)

    dfs(current_path=[start_node], current_load=start_demand, accumulated_time =initial_accumulated_time)

    return feasible_routes

def all_feasible_routes(df_demand, df_durations, df_origin):
    """"""
    feasible_routes = []

    for col_name, col_data in df_durations.items():
        temp = generate_feasible_routes(col_name, df_origin, col_data, df_demand)
        feasible_routes.append(temp)

    return feasible_routes

routes_weekdays = all_feasible_routes(df_week_avg, durations_df, warehouse_df)