"""Effect size calculations with bootstrap CIs and Cohen's interpretation guidelines."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np
import pandas as pd
from scipy import stats


@dataclass
class EffectSizeResult:
    cohens_d: Optional[float]
    risk_ratio: Optional[float]
    odds_ratio: Optional[float]
    absolute_risk_reduction: Optional[float]
    magnitude_label: str  # negligible / small / medium / large
    ci_lower: Optional[float]
    ci_upper: Optional[float]
    method: str


# ---------------------------------------------------------------------------
# Cohen's d
# ---------------------------------------------------------------------------

def cohens_d(
    pre_values: pd.Series,
    post_values: pd.Series,
    n_bootstrap: int = 1000,
    alpha: float = 0.05,
) -> EffectSizeResult:
    """Compute Cohen's d with bootstrap CI for continuous metrics."""
    pre = pre_values.dropna().values
    post = post_values.dropna().values

    if len(pre) < 2 or len(post) < 2:
        return EffectSizeResult(
            cohens_d=float("nan"), risk_ratio=None, odds_ratio=None,
            absolute_risk_reduction=None, magnitude_label="unknown",
            ci_lower=float("nan"), ci_upper=float("nan"), method="cohens_d",
        )

    pooled_std = np.sqrt(
        ((len(pre) - 1) * np.std(pre, ddof=1) ** 2 + (len(post) - 1) * np.std(post, ddof=1) ** 2)
        / (len(pre) + len(post) - 2)
    )
    d = (np.mean(post) - np.mean(pre)) / pooled_std if pooled_std > 0 else float("nan")

    # Bootstrap CI
    rng = np.random.default_rng(42)
    boot_d = []
    for _ in range(n_bootstrap):
        b_pre = rng.choice(pre, size=len(pre), replace=True)
        b_post = rng.choice(post, size=len(post), replace=True)
        ps = np.sqrt(
            ((len(b_pre) - 1) * np.std(b_pre, ddof=1) ** 2 + (len(b_post) - 1) * np.std(b_post, ddof=1) ** 2)
            / (len(b_pre) + len(b_post) - 2)
        )
        boot_d.append((np.mean(b_post) - np.mean(b_pre)) / ps if ps > 0 else 0.0)

    ci_lower = float(np.percentile(boot_d, 100 * alpha / 2))
    ci_upper = float(np.percentile(boot_d, 100 * (1 - alpha / 2)))

    return EffectSizeResult(
        cohens_d=float(d), risk_ratio=None, odds_ratio=None,
        absolute_risk_reduction=None,
        magnitude_label=_d_label(abs(d)),
        ci_lower=ci_lower, ci_upper=ci_upper, method="cohens_d",
    )


def _d_label(d: float) -> str:
    if d < 0.2:
        return "negligible"
    if d < 0.5:
        return "small"
    if d < 0.8:
        return "medium"
    return "large"


# ---------------------------------------------------------------------------
# Proportion effect sizes
# ---------------------------------------------------------------------------

def proportion_effect_sizes(
    pre_rate: float,
    post_rate: float,
    pre_n: int,
    post_n: int,
    n_bootstrap: int = 1000,
    alpha: float = 0.05,
) -> EffectSizeResult:
    """Compute risk ratio, odds ratio, and ARR with bootstrap CIs."""
    arr = post_rate - pre_rate
    rr = post_rate / pre_rate if pre_rate > 0 else float("nan")
    or_ = (
        (post_rate / (1 - post_rate)) / (pre_rate / (1 - pre_rate))
        if 0 < pre_rate < 1 and 0 < post_rate < 1
        else float("nan")
    )

    # Bootstrap CI on RR
    rng = np.random.default_rng(42)
    boot_rr = []
    for _ in range(n_bootstrap):
        b_pre = rng.binomial(pre_n, pre_rate) / pre_n
        b_post = rng.binomial(post_n, post_rate) / post_n
        boot_rr.append(b_post / b_pre if b_pre > 0 else float("nan"))

    clean_boot = [x for x in boot_rr if not np.isnan(x)]
    ci_lower = float(np.percentile(clean_boot, 100 * alpha / 2)) if clean_boot else float("nan")
    ci_upper = float(np.percentile(clean_boot, 100 * (1 - alpha / 2))) if clean_boot else float("nan")

    return EffectSizeResult(
        cohens_d=None, risk_ratio=rr, odds_ratio=or_,
        absolute_risk_reduction=arr,
        magnitude_label=_arr_label(abs(arr)),
        ci_lower=ci_lower, ci_upper=ci_upper, method="risk_ratio",
    )


def _arr_label(arr: float) -> str:
    if arr < 0.01:
        return "negligible"
    if arr < 0.05:
        return "small"
    if arr < 0.10:
        return "medium"
    return "large"
