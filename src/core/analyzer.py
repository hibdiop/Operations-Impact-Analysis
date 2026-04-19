"""Analysis orchestrator — selects the right test, runs it, and produces a unified AnalysisResult."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np
import pandas as pd

from src.config.metrics import MetricConfig
from src.core.experiment import Experiment
from src.stats.confidence_score import ConfidenceScore, compute_confidence_score
from src.stats.diagnostics import (
    SeasonalityResult,
    StationarityResult,
    TrendResult,
    check_stationarity,
    detect_seasonality,
    detect_trend,
)
from src.stats.effect_size import EffectSizeResult, cohens_d, proportion_effect_sizes
from src.stats.tests import (
    StatResult,
    count_test,
    proportion_test,
    sample_size_check,
    t_test_continuous,
)

logger = logging.getLogger(__name__)


@dataclass
class AnalysisResult:
    # Core statistics
    stat_result: StatResult
    effect_size: EffectSizeResult
    # Diagnostics
    trend: TrendResult
    seasonality: SeasonalityResult
    stationarity: StationarityResult
    # Confidence
    confidence: ConfidenceScore
    # Meta
    metric: MetricConfig
    test_used: str
    all_warnings: List[str] = field(default_factory=list)
    # Time series for charting
    full_series: Optional[pd.DataFrame] = None

    # Convenience pass-throughs
    @property
    def pre_value(self) -> float:
        return self.stat_result.pre_value

    @property
    def post_value(self) -> float:
        return self.stat_result.post_value

    @property
    def absolute_change(self) -> float:
        return self.stat_result.absolute_change

    @property
    def relative_lift_pct(self) -> float:
        return self.stat_result.relative_lift_pct

    @property
    def p_value(self) -> float:
        return self.stat_result.p_value

    @property
    def ci_lower(self) -> float:
        return self.stat_result.ci_lower

    @property
    def ci_upper(self) -> float:
        return self.stat_result.ci_upper

    @property
    def is_significant(self) -> bool:
        return self.stat_result.is_significant

    @property
    def pre_n(self) -> int:
        return self.stat_result.pre_n

    @property
    def post_n(self) -> int:
        return self.stat_result.post_n


class Analyzer:
    """Runs the full statistical analysis pipeline for an Experiment."""

    def __init__(self, experiment: Experiment) -> None:
        self.exp = experiment
        self.metric = experiment.metric
        self.config = experiment.config

    def run(self) -> AnalysisResult:
        logger.info("Running analysis for metric=%s, market=%s", self.metric.name, self.config.market)

        pre_df = self.exp.pre_df
        post_df = self.exp.treatment_df  # We compare pre vs treatment period
        full_df = self.exp.full_df

        if pre_df.empty or post_df.empty:
            raise ValueError(
                "Insufficient data to run analysis. "
                "Check that the selected market and date range have data in the database."
            )

        pre_series = self.exp.metric_series(pre_df)
        post_series = self.exp.metric_series(post_df)

        # --- Statistical test ---
        stat_result = self._run_test(pre_df, post_df, pre_series, post_series)

        # --- Sample size warnings ---
        size_warnings = sample_size_check(
            pre_n=stat_result.pre_n,
            post_n=stat_result.post_n,
            min_sample_size=self.metric.min_sample_size,
            metric_name=self.metric.display_name,
        )

        # --- Effect size ---
        effect = self._compute_effect_size(pre_series, post_series, stat_result)

        # --- Diagnostics ---
        pre_dates = pd.Series(pre_df["date"].values)
        trend = detect_trend(pre_series)
        seasonality = detect_seasonality(pre_dates, pre_series)
        stationarity = check_stationarity(pre_series)

        # --- Confidence score ---
        confidence = compute_confidence_score(
            stat_result=stat_result,
            trend=trend,
            seasonality=seasonality,
            pre_period_days=self.config.pre_period_days,
            min_sample_size=self.metric.min_sample_size,
        )

        # --- Aggregate all warnings ---
        all_warnings: List[str] = list(self.exp.validation_warnings())
        all_warnings.extend(size_warnings)
        all_warnings.extend(stat_result.warnings)
        if trend.warning:
            all_warnings.append(trend.warning)
        if seasonality.warning:
            all_warnings.append(seasonality.warning)
        if stationarity.warning:
            all_warnings.append(stationarity.warning)

        # --- Build chart series ---
        chart_df = self._build_chart_series(full_df)

        return AnalysisResult(
            stat_result=stat_result,
            effect_size=effect,
            trend=trend,
            seasonality=seasonality,
            stationarity=stationarity,
            confidence=confidence,
            metric=self.metric,
            test_used=stat_result.test_name,
            all_warnings=all_warnings,
            full_series=chart_df,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _run_test(
        self,
        pre_df: pd.DataFrame,
        post_df: pd.DataFrame,
        pre_series: pd.Series,
        post_series: pd.Series,
    ) -> StatResult:
        alpha = self.config.significance_level
        mt = self.metric.metric_type

        if mt == "rate":
            num_col = self.metric.numerator_field
            den_col = self.metric.denominator_field
            pre_num = int(pre_df[num_col].sum())
            pre_den = int(pre_df[den_col].sum())
            post_num = int(post_df[num_col].sum())
            post_den = int(post_df[den_col].sum())
            return proportion_test(pre_num, pre_den, post_num, post_den, alpha=alpha)

        elif mt == "continuous":
            return t_test_continuous(pre_series, post_series, alpha=alpha)

        else:  # count
            return count_test(pre_series, post_series, alpha=alpha)

    def _compute_effect_size(
        self,
        pre_series: pd.Series,
        post_series: pd.Series,
        stat_result: StatResult,
    ) -> EffectSizeResult:
        mt = self.metric.metric_type
        if mt == "rate":
            return proportion_effect_sizes(
                pre_rate=stat_result.pre_value,
                post_rate=stat_result.post_value,
                pre_n=stat_result.pre_n,
                post_n=stat_result.post_n,
            )
        else:
            return cohens_d(pre_series, post_series)

    def _build_chart_series(self, full_df: pd.DataFrame) -> pd.DataFrame:
        if full_df.empty:
            return pd.DataFrame()
        series = self.exp.metric_series(full_df)
        chart = pd.DataFrame({
            "date": full_df["date"].values,
            "value": series.values,
        })
        # Label each row by period
        pre_end = self.config.pre_period_end
        t_start = self.config.treatment_start
        t_end = self.config.treatment_end

        def label(d):
            if d <= pre_end:
                return "Pre-period"
            if d <= t_end:
                return "Treatment"
            return "Post-period"

        chart["period"] = chart["date"].apply(label)
        return chart
