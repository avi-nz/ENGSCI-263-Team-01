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
    4. create cost vector for using wet-lease truck for each route (ceilng(duration/7200)*1400) (done)
    5. create cost vector for skipping stores (1500 for PaknSave, 800 for every other entry) (this is for fuel reduction) (done)
    6. create a matrix A where a_ij = 1 if route i contains store j, 0 otherwise (Done)

This needs to be done separately for weekdays and for saturdays
"""
#calculating the number of routes because the formatting is list: list: dict
num_routes = 0
for i in range(len(routes_weekdays)):
  temp = routes_weekdays[i]
  for j in range(len(temp)):
    num_routes += 1

stores_weekday = durations_df.index.tolist()
routes_index = [str(i) for i in range(num_routes)]

#ok building the matrix, wish me luck
A_weekdays = [[0 for j in range(num_routes)] for i in range(len(stores_weekday))]
#A[i][j] = 1 if store i is contained within route j

#This triple nested loop is needed to access every route inside routes_weekdays and routes_sat
#there is probably more efficient notation, but I can't be bothered
l = 0
for i in range(len(routes_weekdays)):
  temp = routes_weekdays[i]
  for j in range(len(temp)):
    temp2 = temp[j]
    for k in temp2["stops"]:
      A_weekdays[stores_weekday.index(k)][l] = 1
    l+=1

#Base cost vector for each route
#ok guys do I calculate the cost by the second or do I round up the hour or something
route_cost = [0 for i in range(num_routes)]
k = 0
for i in range(len(routes_weekdays)):
  for j in range(len(routes_weekdays[i])):
    route_cost[k] += routes_weekdays[i][j]["total_time_sec"]*220/3600
    if route_cost[k] > 4*220:
      route_cost[k] = 10**10 #sets the price VERY HIGH if the duration is over 4 hours
    k+=1

lease_route_cost = [0 for i in range(num_routes)]
k = 0
for i in range(len(routes_weekdays)):
  for j in range(len(routes_weekdays[i])):
    lease_route_cost[k] += 1400*math.ceil(routes_weekdays[i][j]["total_time_sec"]/7200)
    k+=1

exclusion_cost = [0 for i in range(len(stores_weekday))]
for i in range(len(stores_weekday)):
  if stores_weekday[i][0] == "P":
    exclusion_cost[i] = 1500
  else:
    exclusion_cost[i] = 800



#LP FOR WEEKDAYS
A_weekdays = makeDict([stores_weekday, routes_index], A_weekdays, 0)
#route_cost = makeDict()
vars_x = LpVariable.dicts("Route", routes_index, 0, None, LpBinary)
vars_y = LpVariable.dicts("Route_Lease", routes_index, 0, None, LpBinary)
prob = LpProblem("Weekdays", LpMinimize)
prob += lpSum([vars_x[routes_index[i]]*route_cost[i] + vars_y[routes_index[i]]*lease_route_cost[i] for i in range(len(routes_index))]), "Cost of Routes"

#each store is visited once
for i in stores_weekday:
  prob += lpSum(vars_x[j]*A_weekdays[i][j] + vars_y[j]*A_weekdays[i][j] for j in routes_index)==1, "%s is visited once" % i

prob += lpSum([vars_x[i]-vars_y[i] for i in routes_index])<=40, "Less than 40 trucks total are used"
print(prob)

prob.writeLP("Weekdays_routes.lp")

prob.solve()
print("Status: ", LpStatus[prob.status])

for v in prob.variables():
  if v.varValue != 0:
    print(v.name, "=", v.varValue)

print("Total Cost = ", value(prob.objective))

"""
#THESE ARE ALL MY ATTEMPTS AT DEBUGGING THE CODE, WILL DELETE LATER

for name, constraint in prob.constraints.items():
  lhs_value = constraint.value()
  print(f"{name}: {lhs_value}")



print(result)
for i in range(len(routes_weekdays)):
  print(routes_weekdays[i][0])
  print(stores_weekday[i])

flat_list = [item for sublist in routes_weekdays for item in sublist]
print(flat_list)
print(len(flat_list))
"""
