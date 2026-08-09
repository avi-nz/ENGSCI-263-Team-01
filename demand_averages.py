from load_data import load_demand
import pandas as pd
import numpy as np
import statsmodels.api as sm

df = load_demand()

def weekday_demand(df):
    """Create a new dataframe containing demand only on weekdays"""
    dates = pd.to_datetime(df["date"])
    weekdays_df = df[dates.dt.weekday < 5]
    return weekdays_df

def saturday_demand(df):
    """Create a new dataframe containing demand only on saturdays"""
    dates = pd.to_datetime(df["date"])
    saturday_df = df[dates.dt.weekday == 5]
    return saturday_df

def huber_mean(series, t=1.345):
    """Calculates Huber's M-estimator robust average for a series of values."""
    if len(series) < 3 or series.nunique() == 1:
        return series.median()

    try:
        y = series.values
        X = np.ones(len(y))  # Intercept-only matrix
        # HuberT(t=1.345) gives 95% efficiency for normal distributions
        model = sm.RLM(y, X, M=sm.robust.norms.HuberT(t=t))
        results = model.fit()
        return results.params[0]
    except (ValueError, np.linalg.LinAlgError):
        # Fallback for small or zero-variance groups
        return series.median()

def weekday_average(df):
    """Calculates the weekday average demand"""
    weekday_df = weekday_demand(df)
    weekday_average = (
        weekday_df.groupby("store")["pallets"]
        .apply(huber_mean)
        .reset_index(name="huber_mean_pallets")
    )
    return weekday_average

def saturday_average(df):
    """Calculates the saturday average demand"""
    saturday_df = saturday_demand(df)
    saturday_average = (
        saturday_df.groupby("store")["pallets"]
        .apply(huber_mean)
        .reset_index(name="huber_mean_pallets")
    )
    return saturday_average


