from feasible_routes import *
from pulp import *
import math

routes_weekdays = all_feasible_routes(df_week_avg, durations_df, warehouse_df)
routes_sat = all_feasible_routes(df_sat_avg, durations_df_sat, warehouse_df_sat.squeeze())

"""
for store in df_week_avg.loc['store']:
    print(store)
    #stores_weekday[store] = i
    i+=1
print(stores_weekday)
"""
"""
Instructions for future me/other teammates:
For each of the weekday/sat:
    1. Index each store (Done)
    2. Index each feasible route (Done)
    3. create cost vector for each route (220/3600*duration) (Done)
    4. create cost vector for using wet-lease truck for each route (ceilng(duration/7200)*1400)
    5. create cost vector for skipping stores (1500 for PaknSave, 800 for every other entry) (this is for fuel reduction)
    6. create a matrix A where a_ij = 1 if route i contains store j, 0 otherwise (Done)

This needs to be done separately for weekdays and for saturdays
"""
#calculating the number of routes because the formatting is list: list: dict
num_routes = 0
for i in range(len(routes_weekdays)):
  temp = routes_weekdays[i]
  for j in range(len(temp)):
    num_routes += 1

print(num_routes)

stores_weekday = durations_df.index.tolist()
routes_index = [str(i) for i in range(num_routes)]

#ok building the matrix, wish me luck
A_weekdays = [[0 for j in range(num_routes)] for i in range(len(stores_weekday))]
#A[i][j] = 1 if store

#This triple nested loop is needed to access every route inside routes_weekdays and routes_sat
#there is probably more efficient notation, but I can't be bothered
for i in range(len(routes_weekdays)):
  temp = routes_weekdays[i]
  for j in range(len(temp)):
    temp2 = temp[j]
    for k in temp2["stops"]:
      A_weekdays[stores_weekday.index(k)][i] = 1

print(routes_weekdays)

#Base cost vector for each route
route_cost = [0 for i in range(num_routes)]
k = 0
for i in range(len(routes_weekdays)):
  temp = routes_weekdays[i]
  for j in range(len(temp)):
    temp2 = temp[j]
    route_cost[k] += temp2["total_time_sec"]*220/3600
    k+=1

print(route_cost)
