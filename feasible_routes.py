from load_data import load_demand, load_durations
from demand_averages import weekday_average, saturday_average
import pandas as pd

# organizing data such that we have a data frame for demand, durations, and warehouse all aligned
demand_df = load_demand()



