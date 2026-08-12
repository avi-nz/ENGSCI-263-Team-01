import json

print("For Weekdays:")
with open("stored_routes/chosen_routes_weekdays.txt") as fp:
    trucks = len(json.load(fp))
with open("stored_routes/leased_routes_weekdays.txt") as fp:
    leased = len(json.load(fp))

print(f"{trucks} trucks were sent and {leased} were leased (without fuel reduction)")

with open("stored_routes/chosen_routes_weekdays_fr.txt") as fp:
    trucks = len(json.load(fp))
with open("stored_routes/leased_routes_weekdays_fr.txt") as fp:
    leased = len(json.load(fp))
with open("stored_routes/skipped_stores_fr.txt") as fp:
    skipped_stores = json.load(fp)

print(f"{trucks} trucks were sent, {leased} were leased, and {len(skipped_stores)} stores were skipped with fuel reduction")
print(f"{skipped_stores} were skipped\n")


print("For Saturdays:")
with open("stored_routes/chosen_routes_sat.txt") as fp:
    trucks = len(json.load(fp))
with open("stored_routes/leased_routes_sat.txt") as fp:
    leased = len(json.load(fp))

print(f"{trucks} trucks were sent and {leased} were leased (without fuel reduction)")

with open("stored_routes/chosen_routes_sat_fr.txt") as fp:
    trucks = len(json.load(fp))
with open("stored_routes/leased_routes_sat_fr.txt") as fp:
    leased = len(json.load(fp))
with open("stored_routes/skipped_stores_sat_fr.txt") as fp:
    skipped_stores = json.load(fp)

print(f"{trucks} trucks were sent, {leased} were leased, and {len(skipped_stores)} stores were skipped with fuel reduction")
print(f"{skipped_stores} were skipped\n")
