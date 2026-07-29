import pandas as pd

def load_locations():
    return pd.read_csv("data/FoodstuffsLocations.csv")

def load_demand():
    return pd.read_csv("data/FoodstuffsDemand2026.csv")

def load_durations():
    return pd.read_csv("data/FoodstuffsDurations2026.csv")