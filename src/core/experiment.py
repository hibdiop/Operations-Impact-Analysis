"""Experiment context manager — loads and splits data into pre/treatment/post windows."""

from __future__ import annotations

import logging
from typing import Optional

import pandas as pd

from src.config.metrics import MetricConfig, registry as metric_registry
from src.config.schema import ExperimentConfig
from src.data.access import DataLoader, loader as default_loader

logger = logging.getLogger(__name__)


class Experiment:
    """Loads data for an ExperimentConfig and exposes pre/treatment/post DataFrames."""

    def __init__(
        self,
        config: ExperimentConfig,
        data_loader: Optional[DataLoader] = None,
    ) -> None:
        self.config = config
        self._loader = data_loader or default_loader
        self.metric: MetricConfig = metric_registry.get(config.metric_name)

        self._raw_df: Optional[pd.DataFrame] = None
        self._coverage: Optional[dict] = None

        self._load()

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def _load(self) -> None:
        full = self.config.full_date_range()
        logger.info(
            "Loading data for market=%s, metric=%s, range=%s→%s",
            self.config.market, self.config.metric_name,
            full.start, full.end,
        )

        all_markets = [self.config.market] + self.config.clean_comparison_markets()
        frames = []
        for market in all_markets:
            df = self._loader.load_metrics(
                market=market,
                start_date=full.start,
                end_date=full.end,
                segment_filters=self.config.segment_filters or {},
            )
            frames.append(df)

        if not frames or all(f.empty for f in frames):
            logger.warning("No data loaded for experiment.")
            self._raw_df = self._loader._empty_frame()
        else:
            self._raw_df = pd.concat(frames, ignore_index=True)

        # Aggregate to weekly if required
        if self.config.aggregation_grain == "weekly":
            self._raw_df = self._to_weekly(self._raw_df)

        # Coverage check for treatment market only
        treatment_df = self._raw_df[self._raw_df["market"] == self.config.market]
        self._coverage = self._loader.validate_data_coverage(
            treatment_df, full.start, full.end
        )

    def _to_weekly(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df
        df = df.copy()
        df["date"] = pd.to_datetime(df["date"])
        df["week"] = df["date"].dt.to_period("W").apply(lambda r: r.start_time.date())
        numeric_cols = [
            "orders", "sessions", "order_attempts", "cancellations",
            "gross_bookings", "net_revenue", "driver_hours", "active_delivery_hours",
        ]
        agg = df.groupby(["week", "market"])[numeric_cols].sum().reset_index()
        agg = agg.rename(columns={"week": "date"})
        agg["fulfillment_rate"] = agg["orders"] / agg["order_attempts"].replace(0, float("nan"))
        agg["segment"] = "all"
        return agg

    # ------------------------------------------------------------------
    # Period DataFrames
    # ------------------------------------------------------------------

    def _window(self, start, end, market: Optional[str] = None) -> pd.DataFrame:
        if self._raw_df is None or self._raw_df.empty:
            return self._loader._empty_frame()
        mkt = market or self.config.market
        mask = (
            (self._raw_df["market"] == mkt)
            & (self._raw_df["date"] >= start)
            & (self._raw_df["date"] <= end)
        )
        return self._raw_df[mask].copy().reset_index(drop=True)

    @property
    def pre_df(self) -> pd.DataFrame:
        w = self.config.pre_window()
        return self._window(w.start, w.end)

    @property
    def treatment_df(self) -> pd.DataFrame:
        w = self.config.treatment_window()
        return self._window(w.start, w.end)

    @property
    def post_df(self) -> pd.DataFrame:
        w = self.config.post_window()
        return self._window(w.start, w.end)

    @property
    def full_df(self) -> pd.DataFrame:
        """Full date range for the treatment market — used for charting."""
        full = self.config.full_date_range()
        return self._window(full.start, full.end)

    def comparison_df(self, market: str) -> pd.DataFrame:
        full = self.config.full_date_range()
        return self._window(full.start, full.end, market=market)

    # ------------------------------------------------------------------
    # Derived metric series
    # ------------------------------------------------------------------

    def metric_series(self, df: pd.DataFrame) -> pd.Series:
        """Compute the KPI value for each row based on metric type."""
        m = self.metric
        if m.metric_type == "rate":
            num = df[m.numerator_field]
            den = df[m.denominator_field].replace(0, float("nan"))
            return (num / den).rename(m.name)
        elif m.metric_type == "continuous":
            if m.denominator_field:
                den = df[m.denominator_field].replace(0, float("nan"))
                return (df[m.numerator_field] / den).rename(m.name)
            return df[m.numerator_field].rename(m.name)
        else:  # count
            return df[m.numerator_field].rename(m.name)

    # ------------------------------------------------------------------
    # Coverage diagnostics
    # ------------------------------------------------------------------

    @property
    def data_coverage(self) -> dict:
        return self._coverage or {}

    def has_sufficient_data(self) -> bool:
        cov = self.data_coverage
        return cov.get("coverage_pct", 0) >= 80

    def validation_warnings(self) -> list:
        warnings = list(self.config.configuration_warnings())
        cov = self.data_coverage
        if cov.get("coverage_pct", 100) < 100:
            missing = cov.get("missing_dates", [])
            warnings.append(
                f"Data coverage is {cov['coverage_pct']:.1f}% "
                f"({len(missing)} missing day(s)). Missing dates: "
                + (", ".join(str(d) for d in missing[:5]))
                + ("..." if len(missing) > 5 else "")
            )
        return warnings
