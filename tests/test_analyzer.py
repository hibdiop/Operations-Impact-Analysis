"""End-to-end analyzer tests using synthetic in-memory data."""

from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from src.config.metrics import registry as metric_registry
from src.config.schema import ExperimentConfig
from src.core.analyzer import AnalysisResult, Analyzer
from src.core.experiment import Experiment


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_config(metric="conversion_rate", treatment_days=14, pre_period_days=30):
    t_start = date(2023, 9, 1)
    t_end = t_start + timedelta(days=treatment_days - 1)
    return ExperimentConfig(
        market="new_york",
        intervention_name="Test Waiver",
        intervention_type="fee_waiver",
        treatment_start=t_start,
        treatment_end=t_end,
        pre_period_days=pre_period_days,
        metric_name=metric,
    )


def _make_synthetic_df(
    market: str,
    start: date,
    end: date,
    orders_mean: float = 1000,
    sessions_mean: float = 12000,
    seed: int = 42,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = []
    d = start
    while d <= end:
        dates.append(d)
        d += timedelta(days=1)
    n = len(dates)
    orders = rng.poisson(orders_mean, n)
    sessions = rng.poisson(sessions_mean, n)
    cancellations = (orders * rng.uniform(0.07, 0.09, n)).astype(int)
    order_attempts = (orders * rng.uniform(1.03, 1.06, n)).astype(int)
    gb = orders * rng.normal(38.0, 2.0, n)
    nr = gb * rng.uniform(0.17, 0.20, n)
    dh = orders * rng.uniform(0.48, 0.52, n)
    adh = dh * rng.uniform(0.74, 0.80, n)
    return pd.DataFrame({
        "date": dates,
        "market": market,
        "segment": "all",
        "orders": orders,
        "sessions": sessions,
        "order_attempts": order_attempts,
        "cancellations": cancellations,
        "gross_bookings": gb,
        "net_revenue": nr,
        "driver_hours": dh,
        "active_delivery_hours": adh,
        "fulfillment_rate": orders / order_attempts,
    })


def _make_experiment_with_mock_data(
    config: ExperimentConfig,
    pre_orders_mean=1000,
    post_orders_mean=1100,
    pre_sessions_mean=12000,
    post_sessions_mean=12000,
) -> Experiment:
    """Build an Experiment with a mocked DataLoader."""
    full = config.full_date_range()
    pre_end = config.pre_period_end
    t_start = config.treatment_start
    t_end = config.treatment_end
    post_end = config.post_period_end

    pre_df = _make_synthetic_df("new_york", full.start, pre_end, pre_orders_mean, pre_sessions_mean, seed=1)
    post_df = _make_synthetic_df("new_york", t_start, post_end, post_orders_mean, post_sessions_mean, seed=2)
    combined = pd.concat([pre_df, post_df], ignore_index=True)

    mock_loader = MagicMock()
    mock_loader.load_metrics.return_value = combined
    mock_loader.validate_data_coverage.return_value = {
        "expected_days": len(combined),
        "actual_days": len(combined),
        "missing_dates": [],
        "coverage_pct": 100.0,
        "is_complete": True,
    }
    mock_loader._empty_frame.return_value = pd.DataFrame(
        columns=["date", "market", "segment", "orders", "sessions",
                 "order_attempts", "cancellations", "gross_bookings",
                 "net_revenue", "driver_hours", "active_delivery_hours",
                 "fulfillment_rate"]
    )

    exp = Experiment.__new__(Experiment)
    exp.config = config
    exp._loader = mock_loader
    exp.metric = metric_registry.get(config.metric_name)
    exp._raw_df = combined
    exp._coverage = mock_loader.validate_data_coverage.return_value
    return exp


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestAnalyzer:
    def test_returns_analysis_result(self):
        config = _make_config("conversion_rate")
        exp = _make_experiment_with_mock_data(config)
        analyzer = Analyzer(exp)
        result = analyzer.run()
        assert isinstance(result, AnalysisResult)

    def test_detects_significant_lift_conversion_rate(self):
        config = _make_config("conversion_rate")
        # Increase sessions-to-orders ratio significantly in treatment
        exp = _make_experiment_with_mock_data(
            config,
            pre_orders_mean=800,
            post_orders_mean=1100,
            pre_sessions_mean=12000,
            post_sessions_mean=12000,
        )
        analyzer = Analyzer(exp)
        result = analyzer.run()
        assert result.absolute_change > 0
        assert result.pre_value < result.post_value

    def test_no_effect_produces_high_p_value(self):
        config = _make_config("conversion_rate")
        exp = _make_experiment_with_mock_data(
            config,
            pre_orders_mean=1000,
            post_orders_mean=1002,  # Tiny difference
        )
        analyzer = Analyzer(exp)
        result = analyzer.run()
        # With near-identical means, p-value should be high
        assert result.p_value > 0.05

    def test_analysis_result_has_required_fields(self):
        config = _make_config("orders")
        exp = _make_experiment_with_mock_data(config)
        analyzer = Analyzer(exp)
        result = analyzer.run()
        assert result.pre_value >= 0
        assert result.post_value >= 0
        assert isinstance(result.all_warnings, list)
        assert result.confidence.score >= 0
        assert result.confidence.score <= 100
        assert result.trend is not None
        assert result.seasonality is not None

    def test_chart_series_has_date_and_value_cols(self):
        config = _make_config("gross_bookings")
        exp = _make_experiment_with_mock_data(config)
        result = Analyzer(exp).run()
        assert result.full_series is not None
        assert "date" in result.full_series.columns
        assert "value" in result.full_series.columns
        assert "period" in result.full_series.columns

    def test_period_labels_are_correct(self):
        config = _make_config("orders")
        exp = _make_experiment_with_mock_data(config)
        result = Analyzer(exp).run()
        periods = result.full_series["period"].unique().tolist()
        assert "Pre-period" in periods
        assert "Treatment" in periods

    def test_confidence_rating_is_valid(self):
        config = _make_config("conversion_rate")
        exp = _make_experiment_with_mock_data(config)
        result = Analyzer(exp).run()
        assert result.confidence.rating in ("Low", "Medium", "High")

    def test_count_metric_uses_count_t(self):
        config = _make_config("orders")
        exp = _make_experiment_with_mock_data(config)
        result = Analyzer(exp).run()
        assert result.test_used == "count_t"

    def test_rate_metric_uses_proportion_z(self):
        config = _make_config("conversion_rate")
        exp = _make_experiment_with_mock_data(config)
        result = Analyzer(exp).run()
        assert result.test_used == "proportion_z"

    def test_continuous_metric_uses_welch_t(self):
        config = _make_config("avg_basket_size")
        exp = _make_experiment_with_mock_data(config)
        result = Analyzer(exp).run()
        assert result.test_used == "welch_t"
