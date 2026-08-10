from demand_averages import weekday_average, saturday_average
from load_data import load_durations, load_demand
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


