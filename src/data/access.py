"""Data access layer — connects to DuckDB (dev) or SQLAlchemy (prod) and loads metric data."""

from __future__ import annotations

import logging
import os
from datetime import date, timedelta
from typing import Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)

# Default DB path (overridable via env var)
DEFAULT_DB_PATH = os.path.join(os.path.dirname(__file__), "../../data/marketplace.duckdb")
DB_PATH = os.environ.get("MARKETPLACE_DB_PATH", DEFAULT_DB_PATH)


def _get_connection():
    """Return a DuckDB connection. Falls back gracefully with a clear error."""
    try:
        import duckdb
        return duckdb.connect(DB_PATH, read_only=True)
    except Exception as e:
        raise ConnectionError(
            f"Cannot connect to DuckDB at '{DB_PATH}'. "
            f"Run scripts/load_sample_data_to_duckdb.py first.\nOriginal error: {e}"
        )


# ---------------------------------------------------------------------------
# Query templates
# ---------------------------------------------------------------------------

_BASE_QUERY = """
SELECT
    date,
    market,
    segment,
    orders,
    sessions,
    order_attempts,
    cancellations,
    gross_bookings,
    net_revenue,
    driver_hours,
    active_delivery_hours,
    fulfillment_rate
FROM daily_market_metrics
WHERE market = '{market}'
  AND date >= '{start_date}'
  AND date <= '{end_date}'
{segment_clause}
ORDER BY date
"""

_MARKETS_QUERY = "SELECT DISTINCT market FROM daily_market_metrics ORDER BY market"

_DATE_RANGE_QUERY = """
SELECT MIN(date) AS min_date, MAX(date) AS max_date
FROM daily_market_metrics
WHERE market = '{market}'
"""


def _build_segment_clause(segment_filters: Dict[str, List[str]]) -> str:
    if not segment_filters:
        return ""
    clauses = []
    for col, values in segment_filters.items():
        quoted = ", ".join(f"'{v}'" for v in values)
        clauses.append(f"AND {col} IN ({quoted})")
    return "\n  ".join(clauses)


# ---------------------------------------------------------------------------
# DataLoader
# ---------------------------------------------------------------------------

class DataLoader:
    """Loads and validates marketplace metric data from the warehouse."""

    def load_metrics(
        self,
        market: str,
        start_date: date,
        end_date: date,
        segment_filters: Optional[Dict[str, List[str]]] = None,
    ) -> pd.DataFrame:
        """Load all metric columns for a market over a date range."""
        segment_filters = segment_filters or {}
        segment_clause = _build_segment_clause(segment_filters)

        query = _BASE_QUERY.format(
            market=market,
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            segment_clause=segment_clause,
        )
        logger.debug("Executing query:\n%s", query)

        con = _get_connection()
        try:
            df = con.execute(query).df()
        finally:
            con.close()

        if df.empty:
            logger.warning("No data returned for market=%s %s→%s", market, start_date, end_date)
            return self._empty_frame()

        df["date"] = pd.to_datetime(df["date"]).dt.date
        df = df.sort_values("date").reset_index(drop=True)

        # If segment filters applied, aggregate across segments
        if segment_filters:
            df = self._aggregate_segments(df)

        return df

    def _aggregate_segments(self, df: pd.DataFrame) -> pd.DataFrame:
        agg = {
            "orders": "sum",
            "sessions": "sum",
            "order_attempts": "sum",
            "cancellations": "sum",
            "gross_bookings": "sum",
            "net_revenue": "sum",
            "driver_hours": "sum",
            "active_delivery_hours": "sum",
        }
        group_cols = ["date", "market"]
        df_agg = df.groupby(group_cols).agg(agg).reset_index()
        # Recompute derived rate
        df_agg["fulfillment_rate"] = (
            df_agg["orders"] / df_agg["order_attempts"].replace(0, float("nan"))
        )
        df_agg["segment"] = "all"
        return df_agg

    def validate_data_coverage(
        self, df: pd.DataFrame, start_date: date, end_date: date
    ) -> Dict:
        """Check completeness of data between start and end dates."""
        expected_dates = set()
        d = start_date
        while d <= end_date:
            expected_dates.add(d)
            d += timedelta(days=1)

        actual_dates = set(df["date"].tolist()) if not df.empty else set()
        missing = sorted(expected_dates - actual_dates)
        coverage_pct = (
            100.0 * len(actual_dates) / len(expected_dates) if expected_dates else 0.0
        )

        return {
            "expected_days": len(expected_dates),
            "actual_days": len(actual_dates),
            "missing_dates": missing,
            "coverage_pct": coverage_pct,
            "is_complete": len(missing) == 0,
        }

    def get_available_markets(self) -> List[str]:
        con = _get_connection()
        try:
            result = con.execute(_MARKETS_QUERY).fetchall()
        finally:
            con.close()
        return [row[0] for row in result]

    def get_date_range_for_market(self, market: str) -> Optional[Dict[str, date]]:
        query = _DATE_RANGE_QUERY.format(market=market)
        con = _get_connection()
        try:
            row = con.execute(query).fetchone()
        finally:
            con.close()
        if row is None or row[0] is None:
            return None
        return {"min_date": row[0], "max_date": row[1]}

    @staticmethod
    def _empty_frame() -> pd.DataFrame:
        return pd.DataFrame(
            columns=[
                "date", "market", "segment", "orders", "sessions",
                "order_attempts", "cancellations", "gross_bookings",
                "net_revenue", "driver_hours", "active_delivery_hours",
                "fulfillment_rate",
            ]
        )


# Module-level singleton
loader = DataLoader()
