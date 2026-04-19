"""Generate realistic synthetic marketplace data and save to CSV files."""

from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

# Allow running from repo root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "../data")
os.makedirs(OUTPUT_DIR, exist_ok=True)

MARKETS = [
    "new_york", "los_angeles", "chicago", "miami",
    "seattle", "denver", "boston", "austin",
]

START_DATE = "2023-01-01"
END_DATE   = "2024-03-31"

RNG = np.random.default_rng(42)

# Market-level base parameters
MARKET_PARAMS = {
    "new_york":    {"orders_base": 2800, "sessions_base": 34000, "gb_per_order": 38.5},
    "los_angeles": {"orders_base": 2100, "sessions_base": 26000, "gb_per_order": 42.0},
    "chicago":     {"orders_base": 1400, "sessions_base": 18000, "gb_per_order": 36.0},
    "miami":       {"orders_base": 900,  "sessions_base": 12000, "gb_per_order": 35.0},
    "seattle":     {"orders_base": 750,  "sessions_base": 10000, "gb_per_order": 44.0},
    "denver":      {"orders_base": 500,  "sessions_base": 7000,  "gb_per_order": 37.0},
    "boston":      {"orders_base": 620,  "sessions_base": 8500,  "gb_per_order": 40.0},
    "austin":      {"orders_base": 430,  "sessions_base": 6000,  "gb_per_order": 36.5},
}

DOW_MULTIPLIERS = {0: 0.90, 1: 0.92, 2: 0.94, 3: 1.0, 4: 1.08, 5: 1.20, 6: 1.10}


def build_market_df(market: str) -> pd.DataFrame:
    params = MARKET_PARAMS[market]
    dates = pd.date_range(START_DATE, END_DATE, freq="D")
    n = len(dates)

    # Slow growth trend + noise
    trend = np.linspace(1.0, 1.18, n)
    noise = RNG.normal(0, 0.04, n)
    dow_effect = np.array([DOW_MULTIPLIERS[d.weekday()] for d in dates])

    # Weekly seasonality in sessions
    base_sessions = params["sessions_base"]
    sessions = np.round(
        base_sessions * trend * dow_effect * (1 + noise) * RNG.uniform(0.97, 1.03, n)
    ).astype(int)
    sessions = np.clip(sessions, 10, None)

    # Conversion rate with slight day-of-week variation
    base_cvr = params["orders_base"] / params["sessions_base"]
    cvr = base_cvr * (1 + RNG.normal(0, 0.02, n)) * np.where(dow_effect > 1, 1.02, 0.99)
    cvr = np.clip(cvr, 0.01, 0.35)

    orders = np.round(sessions * cvr).astype(int)
    orders = np.clip(orders, 0, None)

    # Cancellations ~7–12% of orders
    cancel_rate = RNG.uniform(0.07, 0.12, n)
    cancellations = np.round(orders * cancel_rate).astype(int)

    # Order attempts (slightly more than orders — some unmatched)
    order_attempts = np.round(orders * RNG.uniform(1.03, 1.08, n)).astype(int)

    # Gross bookings
    gb_per_order = params["gb_per_order"]
    gb_noise = RNG.normal(1.0, 0.05, n)
    gross_bookings = np.round(orders * gb_per_order * gb_noise, 2)

    # Net revenue (~18% take rate)
    net_revenue = np.round(gross_bookings * RNG.uniform(0.17, 0.20, n), 2)

    # Driver hours
    driver_hours = np.round(orders * RNG.uniform(0.45, 0.55, n) + RNG.normal(0, 15, n), 1)
    driver_hours = np.clip(driver_hours, 0, None)

    active_delivery_hours = np.round(driver_hours * RNG.uniform(0.72, 0.82, n), 1)
    active_delivery_hours = np.clip(active_delivery_hours, 0, driver_hours)

    fulfillment_rate = np.where(order_attempts > 0, orders / order_attempts, np.nan)

    df = pd.DataFrame({
        "date": dates.date,
        "market": market,
        "segment": "all",
        "orders": orders,
        "sessions": sessions,
        "order_attempts": order_attempts,
        "cancellations": cancellations,
        "gross_bookings": gross_bookings,
        "net_revenue": net_revenue,
        "driver_hours": driver_hours,
        "active_delivery_hours": active_delivery_hours,
        "fulfillment_rate": np.round(fulfillment_rate, 4),
    })
    return df


def main():
    print(f"Generating synthetic data for {len(MARKETS)} markets...")
    frames = []
    for market in MARKETS:
        df = build_market_df(market)
        frames.append(df)
        print(f"  {market}: {len(df):,} rows")

    combined = pd.concat(frames, ignore_index=True)
    out_path = os.path.join(OUTPUT_DIR, "daily_market_metrics.csv")
    combined.to_csv(out_path, index=False)
    print(f"\nSaved {len(combined):,} rows → {out_path}")
    print("Done.")


if __name__ == "__main__":
    main()
