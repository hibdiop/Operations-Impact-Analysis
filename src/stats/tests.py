"""Statistical testing module — proportion z-test, Welch's t-test, and daily count t-test."""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np
import pandas as pd
from scipy import stats


@dataclass
class StatResult:
    """Unified result object returned by all test functions."""

    pre_value: float
    post_value: float
    absolute_change: float
    relative_lift_pct: float
    p_value: float
    ci_lower: float
    ci_upper: float
    test_statistic: float
    test_name: str
    pre_n: int
    post_n: int
    is_significant: bool
    alpha: float
    warnings: List[str] = field(default_factory=list)
    standard_error: float = float("nan")

    @property
    def direction(self) -> str:
        return "increase" if self.absolute_change > 0 else "decrease" if self.absolute_change < 0 else "no change"

    def significance_stars(self) -> str:
        if self.p_value < 0.001:
            return "***"
        if self.p_value < 0.01:
            return "**"
        if self.p_value < 0.05:
            return "*"
        return ""


# ---------------------------------------------------------------------------
# Proportion / Rate test (two-proportion z-test)
# ---------------------------------------------------------------------------

def proportion_test(
    pre_successes: int,
    pre_trials: int,
    post_successes: int,
    post_trials: int,
    alpha: float = 0.05,
) -> StatResult:
    """Two-proportion z-test for rate/proportion metrics."""
    test_warnings: List[str] = []

    if pre_trials == 0 or post_trials == 0:
        raise ValueError("Trials (denominator) cannot be zero for a proportion test")

    pre_rate = pre_successes / pre_trials
    post_rate = post_successes / post_trials

    # Pooled proportion under H0
    pooled = (pre_successes + post_successes) / (pre_trials + post_trials)
    se = np.sqrt(pooled * (1 - pooled) * (1 / pre_trials + 1 / post_trials))

    if se == 0:
        test_warnings.append("Standard error is zero — both groups have identical extreme proportions.")
        return StatResult(
            pre_value=pre_rate, post_value=post_rate,
            absolute_change=post_rate - pre_rate,
            relative_lift_pct=0.0, p_value=1.0,
            ci_lower=0.0, ci_upper=0.0,
            test_statistic=0.0, test_name="proportion_z",
            pre_n=pre_trials, post_n=post_trials,
            is_significant=False, alpha=alpha,
            warnings=test_warnings, standard_error=0.0,
        )

    z = (post_rate - pre_rate) / se
    p_value = 2 * (1 - stats.norm.cdf(abs(z)))

    # CI for difference in proportions (unpooled SE)
    se_diff = np.sqrt(
        pre_rate * (1 - pre_rate) / pre_trials + post_rate * (1 - post_rate) / post_trials
    )
    z_crit = stats.norm.ppf(1 - alpha / 2)
    diff = post_rate - pre_rate
    ci_lower = diff - z_crit * se_diff
    ci_upper = diff + z_crit * se_diff

    if pre_trials < 30 or post_trials < 30:
        test_warnings.append("Sample size is small; normal approximation may be unreliable.")
    if pooled < 0.05 or pooled > 0.95:
        test_warnings.append("Pooled proportion is near 0 or 1; z-test approximation is less accurate.")

    rel_lift = (diff / pre_rate * 100) if pre_rate != 0 else float("nan")

    return StatResult(
        pre_value=pre_rate, post_value=post_rate,
        absolute_change=diff, relative_lift_pct=rel_lift,
        p_value=p_value, ci_lower=ci_lower, ci_upper=ci_upper,
        test_statistic=z, test_name="proportion_z",
        pre_n=pre_trials, post_n=post_trials,
        is_significant=p_value < alpha,
        alpha=alpha, warnings=test_warnings, standard_error=se_diff,
    )


# ---------------------------------------------------------------------------
# Continuous metric test (Welch's t-test on daily series)
# ---------------------------------------------------------------------------

def t_test_continuous(
    pre_values: pd.Series,
    post_values: pd.Series,
    alpha: float = 0.05,
) -> StatResult:
    """Welch's t-test (unequal variance) for continuous metrics on daily time series."""
    test_warnings: List[str] = []

    pre_clean = pre_values.dropna()
    post_clean = post_values.dropna()

    if len(pre_clean) < 2 or len(post_clean) < 2:
        raise ValueError("Need at least 2 observations per period for t-test")

    pre_mean = float(pre_clean.mean())
    post_mean = float(post_clean.mean())

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        t_stat, p_value = stats.ttest_ind(post_clean, pre_clean, equal_var=False)

    diff = post_mean - pre_mean
    rel_lift = (diff / pre_mean * 100) if pre_mean != 0 else float("nan")

    # CI for difference using Welch approximation
    s1, s2 = float(pre_clean.std()), float(post_clean.std())
    n1, n2 = len(pre_clean), len(post_clean)
    se_diff = np.sqrt(s1 ** 2 / n1 + s2 ** 2 / n2)

    # Welch–Satterthwaite degrees of freedom
    if se_diff == 0:
        df_w = n1 + n2 - 2
    else:
        df_w = (s1 ** 2 / n1 + s2 ** 2 / n2) ** 2 / (
            (s1 ** 2 / n1) ** 2 / (n1 - 1) + (s2 ** 2 / n2) ** 2 / (n2 - 1)
        )

    t_crit = stats.t.ppf(1 - alpha / 2, df=df_w)
    ci_lower = diff - t_crit * se_diff
    ci_upper = diff + t_crit * se_diff

    if n1 < 7 or n2 < 7:
        test_warnings.append("Very few daily observations; t-test results are unreliable.")

    return StatResult(
        pre_value=pre_mean, post_value=post_mean,
        absolute_change=diff, relative_lift_pct=rel_lift,
        p_value=float(p_value), ci_lower=ci_lower, ci_upper=ci_upper,
        test_statistic=float(t_stat), test_name="welch_t",
        pre_n=n1, post_n=n2,
        is_significant=float(p_value) < alpha,
        alpha=alpha, warnings=test_warnings, standard_error=se_diff,
    )


# ---------------------------------------------------------------------------
# Count metric test (t-test on daily totals)
# ---------------------------------------------------------------------------

def count_test(
    pre_daily: pd.Series,
    post_daily: pd.Series,
    normalize_by: Optional[pd.Series] = None,
    alpha: float = 0.05,
) -> StatResult:
    """T-test on daily count aggregates, with optional normalization."""
    if normalize_by is not None:
        pre_daily = pre_daily / normalize_by.reindex(pre_daily.index).replace(0, float("nan"))
        post_daily = post_daily / normalize_by.reindex(post_daily.index).replace(0, float("nan"))

    result = t_test_continuous(pre_daily, post_daily, alpha=alpha)
    result = StatResult(
        **{
            **result.__dict__,
            "test_name": "count_t",
            "pre_value": float(pre_daily.dropna().sum()) if normalize_by is None else result.pre_value,
            "post_value": float(post_daily.dropna().sum()) if normalize_by is None else result.post_value,
        }
    )
    # Recalculate absolute_change and relative_lift for count totals
    if normalize_by is None:
        pre_total = float(pre_daily.dropna().sum())
        post_total = float(post_daily.dropna().sum())
        abs_change = post_total - pre_total
        rel_lift = (abs_change / pre_total * 100) if pre_total != 0 else float("nan")
        return StatResult(
            pre_value=pre_total, post_value=post_total,
            absolute_change=abs_change, relative_lift_pct=rel_lift,
            p_value=result.p_value, ci_lower=result.ci_lower, ci_upper=result.ci_upper,
            test_statistic=result.test_statistic, test_name="count_t",
            pre_n=result.pre_n, post_n=result.post_n,
            is_significant=result.is_significant, alpha=alpha,
            warnings=result.warnings, standard_error=result.standard_error,
        )
    return result


# ---------------------------------------------------------------------------
# Sample size checker
# ---------------------------------------------------------------------------

def sample_size_check(
    pre_n: int,
    post_n: int,
    min_sample_size: int,
    metric_name: str,
) -> List[str]:
    """Return warning strings if sample sizes fall below thresholds."""
    warnings_out: List[str] = []
    if pre_n < min_sample_size:
        warnings_out.append(
            f"Pre-period sample size ({pre_n:,}) is below the recommended minimum "
            f"({min_sample_size:,}) for '{metric_name}'. Results may be unstable."
        )
    if post_n < min_sample_size:
        warnings_out.append(
            f"Post-period sample size ({post_n:,}) is below the recommended minimum "
            f"({min_sample_size:,}) for '{metric_name}'. Results may be unstable."
        )
    return warnings_out


# ---------------------------------------------------------------------------
# Test selector
# ---------------------------------------------------------------------------

def choose_test(metric_type: str):
    """Return the appropriate test function for a given metric type."""
    mapping = {
        "rate": "proportion_z",
        "continuous": "welch_t",
        "count": "count_t",
    }
    if metric_type not in mapping:
        raise ValueError(f"Unknown metric_type '{metric_type}'. Choose from: {list(mapping)}")
    return mapping[metric_type]
