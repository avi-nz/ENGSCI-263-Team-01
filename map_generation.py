import json
import folium
import pandas as pd
from load_data import load_locations

# Load data
locations = load_locations()

def map_generation(df_loc, chosen, leased, name):
    coords = {
        row["Supermarket"]: (row["Lat"], row["Long"]) for _, row in df_loc.iterrows()
    }
    wh = df_loc[df_loc["Supermarket"] == "Warehouse"].iloc[0]
    coords["Origin"] = (wh["Lat"], wh["Long"])

    with open(chosen) as f:
        chosen_routes = json.load(f)

    with open(leased) as f:
        leased_routes = json.load(f)

    # Initialize Folium Map centered on Auckland Warehouse
    m = folium.Map(location=coords["Origin"], zoom_start=11)

    # Origin Marker
    folium.Marker(
        location=coords["Origin"],
        popup="Origin Warehouse",
        icon=folium.Icon(color="black", icon="home"),
    ).add_to(m)

    # Plot Chosen Routes (Blue group)
    for idx, r in enumerate(chosen_routes):
        route_coords = [
            coords[s]
            for s in (["Origin"] + r["stops"] + ["Origin"])
            if s in coords
        ]
        folium.PolyLine(
            route_coords,
            color="#1D70B8",
            weight=3.5,
            opacity=0.8,
            tooltip=f"Chosen Route {idx+1}",
        ).add_to(m)
        for stop in r["stops"]:
            if stop in coords:
                folium.CircleMarker(
                    location=coords[stop],
                    radius=5,
                    color="#003078",
                    fill=True,
                    popup=stop,
                ).add_to(m)

    # Plot Leased Routes (Red group)
    for idx, r in enumerate(leased_routes):
        route_coords = [
            coords[s]
            for s in (["Origin"] + r["stops"] + ["Origin"])
            if s in coords
        ]
        folium.PolyLine(
            route_coords,
            color="#D4351C",
            weight=3.5,
            opacity=0.8,
            dash_array="5, 10",
            tooltip=f"Leased Route {idx+1}",
        ).add_to(m)
        for stop in r["stops"]:
            if stop in coords:
                folium.CircleMarker(
                    location=coords[stop],
                    radius=5,
                    color="#850018",
                    fill=True,
                    popup=stop,
                ).add_to(m)

    m.save(name)

#map_generation(locations, "stored_routes/chosen_routes_sat.txt", "stored_routes/leased_routes_sat.txt", "sat_map.html")
map_generation(locations, "stored_routes/chosen_routes_sat_fr.txt", "stored_routes/leased_routes_sat_fr.txt", "sat_map_fr.html")
map_generation(locations, "stored_routes/chosen_routes_weekdays.txt", "stored_routes/leased_routes_weekdays.txt", "weekdays_map.html")
map_generation(locations, "stored_routes/chosen_routes_weekdays_fr.txt", "stored_routes/leased_routes_weekdays_fr.txt", "weekdays_map_fr.html")