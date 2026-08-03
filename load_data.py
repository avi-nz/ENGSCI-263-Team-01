import pandas as pd

# FUNCTIONS TO LOAD IN THE DEMAND DATA

def load_demand_raw():
    """Wide format, exactly as it is on disk."""
    return pd.read_csv("data/FoodstuffsDemand2026.csv")


def melt_demand(df):
    """Wide (store x date columns) -> long (store, date, pallets)."""
    long_df = df.melt(id_vars=df.columns[0], var_name="date", value_name="pallets")
    long_df = long_df.rename(columns={df.columns[0]: "store"})
    long_df["date"] = pd.to_datetime(long_df["date"], format="%d/%m/%Y")
    return long_df


def find_outliers(long_df, z_thresh=4):
    """Flag rows where a store's demand is an extreme number of
    std-deviations from that store's own mean."""
    stats = long_df.groupby("store")["pallets"].transform(lambda s: (s - s.mean()) / s.std())
    return long_df[stats.abs() > z_thresh]


def clean_demand(long_df):
    """Apply known data-entry fixes (misplaced decimal -> divide by 10)."""
    df = long_df.copy()
    outliers = find_outliers(df)
    df.loc[outliers.index, "pallets"] = df.loc[outliers.index, "pallets"] / 10
    return df


def load_demand():
    """Cleaned, tidy demand data — this is what you'll use everywhere else."""
    return clean_demand(melt_demand(load_demand_raw()))




def load_locations():
    return pd.read_csv("data/FoodstuffsLocations.csv")

def load_durations():
    return pd.read_csv("data/FoodstuffsDurations2026.csv")