"""Pre-period diagnostics — trend detection, seasonality, stationarity."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd
from scipy import stats


@dataclass
class TrendResult:
    slope: float
    p_value: float
    r_squared: float
    trend_detected: bool
    direction: str
    warning: Optional[str]


@dataclass
class SeasonalityResult:
    day_of_week_cv: float
    strong_seasonality: bool
    dow_averages: dict
    warning: Optional[str]


@dataclass
class StationarityResult:
    adf_statistic: float
    p_value: float
    is_stationary: bool
    warning: Optional[str]


# ---------------------------------------------------------------------------
# Trend detection via OLS on pre-period
# ---------------------------------------------------------------------------

def detect_trend(series: pd.Series, alpha: float = 0.05) -> TrendResult:
    """Run linear regression on a time series; flag significant trends."""
    clean = series.dropna()
    if len(clean) < 4:
        return TrendResult(
            slope=float("nan"), p_value=float("nan"), r_squared=float("nan"),
            trend_detected=False, direction="unknown",
            warning="Too few observations to assess trend.",
        )

    x = np.arange(len(clean))
    slope, intercept, r, p_value, _ = stats.linregress(x, clean.values)
    r_squared = r ** 2
    trend_detected = p_value < alpha
    direction = "upward" if slope > 0 else "downward"

    warning = None
    if trend_detected:
        warning = (
            f"Significant {direction} trend detected in the pre-period "
            f"(p={p_value:.3f}, slope={slope:.4f}/day). "
            "Observed post-period change may partially reflect this pre-existing trend."
        )

    return TrendResult(
        slope=float(slope), p_value=float(p_value), r_squared=float(r_squared),
        trend_detected=trend_detected, direction=direction, warning=warning,
    )


# ---------------------------------------------------------------------------
# Seasonality detection via day-of-week variance
# ---------------------------------------------------------------------------

def detect_seasonality(
    dates: pd.Series,
    values: pd.Series,
    cv_threshold: float = 0.15,
) -> SeasonalityResult:
    """Detect day-of-week seasonality using coefficient of variation."""
    df = pd.DataFrame({"date": pd.to_datetime(dates), "value": values}).dropna()
    if len(df) < 7:
        return SeasonalityResult(
            day_of_week_cv=float("nan"), strong_seasonality=False,
            dow_averages={},
            warning="Insufficient data to assess day-of-week seasonality.",
        )

    df["dow"] = df["date"].dt.day_name()
    dow_means = df.groupby("dow")["value"].mean()
    cv = float(dow_means.std() / dow_means.mean()) if dow_means.mean() != 0 else 0.0
    strong = cv > cv_threshold

    warning = None
    if strong:
        warning = (
            f"Strong day-of-week seasonality detected (CV={cv:.2f}). "
            "If treatment and pre-periods cover different weekday mixes, "
            "results may be confounded by day-of-week patterns."
        )

    return SeasonalityResult(
        day_of_week_cv=cv,
        strong_seasonality=strong,
        dow_averages=dow_means.to_dict(),
        warning=warning,
    )


# ---------------------------------------------------------------------------
# Stationarity — augmented Dickey-Fuller
# ---------------------------------------------------------------------------

def check_stationarity(series: pd.Series, alpha: float = 0.05) -> StationarityResult:
    """ADF test for unit root (non-stationarity)."""
    clean = series.dropna()
    if len(clean) < 10:
        return StationarityResult(
            adf_statistic=float("nan"), p_value=float("nan"),
            is_stationary=False,
            warning="Too few observations for stationarity test.",
        )

    try:
        from statsmodels.tsa.stattools import adfuller
        adf_stat, p_value, *_ = adfuller(clean.values, autolag="AIC")
        is_stationary = p_value < alpha
        warning = None
        if not is_stationary:
            warning = (
                f"Pre-period series may be non-stationary (ADF p={p_value:.3f}). "
                "Mean and variance may be shifting over time, which can affect inference."
            )
        return StationarityResult(
            adf_statistic=float(adf_stat), p_value=float(p_value),
            is_stationary=is_stationary, warning=warning,
        )
    except ImportError:
        return StationarityResult(
            adf_statistic=float("nan"), p_value=float("nan"),
            is_stationary=True,
            warning="statsmodels not available; stationarity not checked.",
        )
