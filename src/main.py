from src.load_data import load_locations, load_demand, load_durations

# Load the data into DataFrames
locations_df = load_locations()
demand_df = load_demand()
durations_df = load_durations()

# View the first few rows
print(locations_df.head())
print(demand_df.head())
print(durations_df.head())