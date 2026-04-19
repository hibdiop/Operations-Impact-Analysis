"""Interpretation confidence scorer — produces a 0–100 trust score for each analysis run."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from src.stats.diagnostics import SeasonalityResult, TrendResult
from src.stats.tests import StatResult


@dataclass
class ConfidenceScore:
    score: int
    rating: str          # "Low" / "Medium" / "High"
    banner: str
    reasons: List[str] = field(default_factory=list)
    deductions: List[str] = field(default_factory=list)


def compute_confidence_score(
    stat_result: StatResult,
    trend: TrendResult,
    seasonality: SeasonalityResult,
    pre_period_days: int,
    min_sample_size: int,
) -> ConfidenceScore:
    """
    Score the trustworthiness of an analysis result.

    Scoring rubric (100 pts total):
      Sample size adequacy        0–30
      No pre-period trend         0–20
      No strong seasonality       0–20
      Sufficient pre-period len   0–15
      Effect size vs noise        0–15
    """
    score = 0
    reasons: List[str] = []
    deductions: List[str] = []

    # 1. Sample size adequacy (0–30 pts)
    n_min = min(stat_result.pre_n, stat_result.post_n)
    if n_min >= min_sample_size * 2:
        score += 30
        reasons.append("Strong sample size in both periods (+30)")
    elif n_min >= min_sample_size:
        score += 20
        reasons.append("Adequate sample size (+20)")
    elif n_min >= min_sample_size // 2:
        score += 10
        deductions.append(f"Sample size below recommended minimum ({n_min:,} < {min_sample_size:,}) (-20)")
    else:
        deductions.append(f"Very small sample size ({n_min:,}) — results are highly unstable (-30)")

    # 2. No trend in pre-period (0–20 pts)
    if not trend.trend_detected:
        score += 20
        reasons.append("No significant pre-period trend detected (+20)")
    else:
        deductions.append(f"Pre-period trend detected (p={trend.p_value:.3f}) — lift may partly reflect trend (-20)")

    # 3. No strong seasonality (0–20 pts)
    if not seasonality.strong_seasonality:
        score += 20
        reasons.append("No strong day-of-week seasonality detected (+20)")
    else:
        score += 5
        deductions.append(
            f"Day-of-week seasonality is strong (CV={seasonality.day_of_week_cv:.2f}) "
            "— results may be confounded by weekday mix (-15)"
        )

    # 4. Sufficient pre-period length (0–15 pts)
    if pre_period_days >= 28:
        score += 15
        reasons.append(f"Pre-period is {pre_period_days} days (≥ 4 weeks) (+15)")
    elif pre_period_days >= 14:
        score += 8
        deductions.append(f"Pre-period is only {pre_period_days} days (< 4 weeks) (-7)")
    else:
        deductions.append(f"Pre-period is very short ({pre_period_days} days) (-15)")

    # 5. Effect size vs noise — signal-to-noise ratio (0–15 pts)
    if stat_result.standard_error > 0 and stat_result.absolute_change == stat_result.absolute_change:
        snr = abs(stat_result.absolute_change) / stat_result.standard_error
        if snr >= 3:
            score += 15
            reasons.append(f"Strong signal-to-noise ratio ({snr:.1f}) (+15)")
        elif snr >= 1.5:
            score += 8
            reasons.append(f"Moderate signal-to-noise ratio ({snr:.1f}) (+8)")
        else:
            deductions.append(f"Weak signal-to-noise ratio ({snr:.1f}) — effect is small relative to variability (-7)")
    else:
        score += 5  # neutral when SE not available

    score = max(0, min(100, score))

    if score >= 75:
        rating = "High"
        banner = "High confidence: the data supports acting on this result, subject to business judgment."
    elif score >= 45:
        rating = "Medium"
        banner = "Medium confidence: directional signal is present but interpret with caution."
    else:
        rating = "Low"
        banner = "Low confidence: data quality or design limitations make this result unreliable for decision-making."

    return ConfidenceScore(
        score=score, rating=rating, banner=banner,
        reasons=reasons, deductions=deductions,
    )
