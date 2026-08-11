from feasible_routes import *
from pulp import *

routes_weekdays = all_feasible_routes(df_week_avg, durations_df, warehouse_df)
routes_sat = all_feasible_routes(df_sat_avg, durations_df_sat, warehouse_df_sat.squeeze())

print(routes_weekdays)
print(routes_sat)
print(routes_weekdays[0])
print(len(routes_weekdays), len(routes_sat))