from src.feasible_routes import *
from pulp import *
import math
import json

routes_weekdays = all_feasible_routes(df_week_avg, durations_df, warehouse_df)

print("all routes found")

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

#This quadruple iterative variable nested loop is needed to access every route inside routes_weekdays and routes_sat
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
      route_cost[k] = 4*220 + (route_cost[k]-4*220)*310/220 #accounts for overtime if the route is >4 hours
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

flat_routes = [item for sublist in routes_weekdays for item in sublist] #flattens to one list, should've done earlier

print("constants set up")

#LP FOR WEEKDAYS
A_weekdays = makeDict([stores_weekday, routes_index], A_weekdays, 0)

vars_x = LpVariable.dicts("Route", routes_index, 0, None, LpBinary)
vars_y = LpVariable.dicts("Route_Lease", routes_index, 0, None, LpBinary)

prob = LpProblem("Weekdays", LpMinimize)
prob += lpSum([vars_x[routes_index[i]]*route_cost[i] + vars_y[routes_index[i]]*lease_route_cost[i] for i in range(len(routes_index))]), "Cost of Routes"

#each store is visited once
for i in stores_weekday:
  prob += lpSum(vars_x[j]*A_weekdays[i][j] + vars_y[j]*A_weekdays[i][j] for j in routes_index)==1, "%s is visited once" % i

prob += lpSum([vars_x[i] for i in routes_index])<=40, "Less than 40 trucks total are used"

prob.writeLP("Weekdays_routes.lp")

prob.solve()

chosen_routes = []
leased_routes = []
for v in prob.variables():
  if v.varValue != 0:
    print(v.name, "=", v.varValue)
    if v.name[0:7] == "Route_L":
      leased_routes.append(flat_routes[int(v.name[12:])])
      leased_routes[-1].update({"cost" : lease_route_cost[int(v.name[12:])]})
    elif v.name[0:6] == "Route_":
      chosen_routes.append(flat_routes[int(v.name[6:])])
      chosen_routes[-1].update({"cost" : route_cost[int(v.name[6:])]})

with open("../stored_routes/chosen_routes_weekdays.txt", "w") as file:
  json.dump(chosen_routes, file)
with open("../stored_routes/leased_routes_weekdays.txt", "w") as file:
  json.dump(leased_routes, file)

print("Total Cost = ", value(prob.objective))
Total_Cost = value(prob.objective)

flat_routes = [item for sublist in routes_weekdays for item in sublist]


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

#LP FOR WEEKDAYS with fuel reduction

vars_x = LpVariable.dicts("Route", routes_index, 0, None, LpBinary)
vars_y = LpVariable.dicts("Route_Lease", routes_index, 0, None, LpBinary)
vars_z = LpVariable.dicts("Skipped_Store", stores_weekday, 0, None, LpBinary)
prob_fr = LpProblem("Weekdays_Fuel_Reduction", LpMinimize)
prob_fr += lpSum([vars_x[routes_index[i]]*route_cost[i] +
               vars_y[routes_index[i]]*lease_route_cost[i]
               for i in range(len(routes_index))] +
                 [vars_z[stores_weekday[j]]*exclusion_cost[j] for j in range(len(stores_weekday))]), "Cost of Routes and Skipping"

#each store is either visited once or skipped
for i in stores_weekday:
  prob_fr += lpSum([vars_x[j]*A_weekdays[i][j] + vars_y[j]*A_weekdays[i][j] for j in routes_index] + [vars_z[i]])==1, "%s is visited once or skipped" % i

prob_fr += lpSum([vars_x[i] for i in routes_index])<=40, "Less than 40 trucks total are used"

#the logic might need to be different here for saturday since we are already skipping stores
prob_fr += lpSum([vars_z[i] for i in stores_weekday])<=0.2*len(stores_weekday), "Less than 20% of stores are skipped"

prob_fr.writeLP("Weekdays_Fuel_Reduction.lp")

prob_fr.solve()

for v in prob_fr.variables():
  if v.varValue != 0:
    print(v.name, "=", v.varValue)

print("Total Cost = ", value(prob_fr.objective))
Total_Cost_fr = value(prob_fr.objective)


chosen_routes = []
leased_routes = []
skipped_stores = []
for v in prob_fr.variables():
  if v.varValue != 0:
    print(v.name, "=", v.varValue)
    if v.name[0:7] == "Route_L":
      leased_routes.append(flat_routes[int(v.name[12:])])
      leased_routes[-1].update({"cost" : lease_route_cost[int(v.name[12:])]})
    elif v.name[0:6] == "Route_":
      chosen_routes.append(flat_routes[int(v.name[6:])])
      chosen_routes[-1].update({"cost" : route_cost[int(v.name[6:])]})
    elif v.name[0:7] == "Skipped":
      skipped_stores.append(v.name[14:])

with open("../stored_routes/chosen_routes_weekdays_fr.txt", "w") as file:
  json.dump(chosen_routes, file)
with open("../stored_routes/leased_routes_weekdays_fr.txt", "w") as file:
  json.dump(leased_routes, file) #should be empty
with open("../stored_routes/skipped_stores_fr.txt", "w") as file:
  json.dump(skipped_stores, file)


print(f"Cost without Fuel Reduction: {Total_Cost}\n"
      f"Cost with Fuel Reduction: {Total_Cost_fr}")