"""Load the sample CSV into a DuckDB database and validate it."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

CSV_PATH = os.path.join(os.path.dirname(__file__), "../data/daily_market_metrics.csv")
DB_PATH  = os.path.join(os.path.dirname(__file__), "../data/marketplace.duckdb")


def main():
    import duckdb
    import pandas as pd

    if not os.path.exists(CSV_PATH):
        print(f"CSV not found at {CSV_PATH}.")
        print("Run scripts/generate_sample_data.py first.")
        sys.exit(1)

    print(f"Reading CSV from {CSV_PATH} ...")
    df = pd.read_csv(CSV_PATH, parse_dates=["date"])
    df["date"] = df["date"].dt.date
    print(f"  Loaded {len(df):,} rows, {df['market'].nunique()} markets")

    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print(f"Removed existing DB at {DB_PATH}")

    print(f"Creating DuckDB database at {DB_PATH} ...")
    con = duckdb.connect(DB_PATH)

    con.execute("""
        CREATE TABLE daily_market_metrics (
            date                 DATE NOT NULL,
            market               VARCHAR NOT NULL,
            segment              VARCHAR,
            orders               INTEGER,
            sessions             INTEGER,
            order_attempts       INTEGER,
            cancellations        INTEGER,
            gross_bookings       DOUBLE,
            net_revenue          DOUBLE,
            driver_hours         DOUBLE,
            active_delivery_hours DOUBLE,
            fulfillment_rate     DOUBLE
        )
    """)

    con.register("df_view", df)
    con.execute("INSERT INTO daily_market_metrics SELECT * FROM df_view")

    # Create indexes for fast filtering
    con.execute("CREATE INDEX idx_market_date ON daily_market_metrics (market, date)")
    con.execute("CREATE INDEX idx_date ON daily_market_metrics (date)")

    row_count = con.execute("SELECT COUNT(*) FROM daily_market_metrics").fetchone()[0]
    print(f"  Inserted {row_count:,} rows into daily_market_metrics")

    # Validation queries
    print("\nValidation:")
    markets = con.execute(
        "SELECT market, COUNT(*) as days FROM daily_market_metrics GROUP BY market ORDER BY market"
    ).fetchall()
    for m, d in markets:
        print(f"  {m}: {d} days")

    sample = con.execute("""
        SELECT market, MIN(date) as min_dt, MAX(date) as max_dt,
               SUM(orders) as total_orders, ROUND(AVG(fulfillment_rate),3) as avg_fulfillment
        FROM daily_market_metrics
        GROUP BY market
        ORDER BY total_orders DESC
    """).df()
    print("\nSample aggregates:")
    print(sample.to_string(index=False))

    con.close()
    print(f"\nDatabase ready at {DB_PATH}")


if __name__ == "__main__":
    main()
