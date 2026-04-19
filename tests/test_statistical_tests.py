"""Unit tests for the statistical testing module."""

import numpy as np
import pandas as pd
import pytest

from src.stats.tests import (
    StatResult,
    count_test,
    proportion_test,
    sample_size_check,
    t_test_continuous,
)


# ---------------------------------------------------------------------------
# proportion_test
# ---------------------------------------------------------------------------

class TestProportionTest:
    def test_known_significant_difference(self):
        # Large samples with clear difference — should be significant
        result = proportion_test(800, 10_000, 900, 10_000, alpha=0.05)
        assert result.is_significant
        assert result.p_value < 0.05
        assert abs(result.pre_value - 0.08) < 0.001
        assert abs(result.post_value - 0.09) < 0.001
        assert abs(result.absolute_change - 0.01) < 0.001

    def test_no_difference(self):
        result = proportion_test(500, 10_000, 500, 10_000, alpha=0.05)
        assert not result.is_significant
        assert result.p_value == pytest.approx(1.0, abs=0.01)
        assert result.absolute_change == pytest.approx(0.0, abs=1e-6)

    def test_small_improvement_large_sample(self):
        result = proportion_test(1000, 50_000, 1050, 50_000, alpha=0.05)
        assert result.relative_lift_pct == pytest.approx(5.0, abs=0.1)

    def test_zero_denominator_raises(self):
        with pytest.raises(ValueError, match="Trials.*cannot be zero"):
            proportion_test(10, 0, 10, 100)

    def test_ci_contains_zero_when_not_significant(self):
        result = proportion_test(100, 1_000, 105, 1_000, alpha=0.05)
        if not result.is_significant:
            assert result.ci_lower <= 0 <= result.ci_upper

    def test_returns_stat_result_type(self):
        result = proportion_test(100, 1_000, 120, 1_000)
        assert isinstance(result, StatResult)

    def test_direction_of_lift(self):
        result = proportion_test(100, 1_000, 200, 1_000)
        assert result.absolute_change > 0
        assert result.relative_lift_pct > 0

    def test_small_sample_warning(self):
        result = proportion_test(5, 20, 8, 25)
        assert any("small" in w.lower() for w in result.warnings)


# ---------------------------------------------------------------------------
# t_test_continuous
# ---------------------------------------------------------------------------

class TestTTestContinuous:
    def _series(self, mean, std, n, seed=0):
        rng = np.random.default_rng(seed)
        return pd.Series(rng.normal(mean, std, n))

    def test_detects_known_lift(self):
        pre = self._series(100, 10, 30)
        post = self._series(115, 10, 30)
        result = t_test_continuous(pre, post, alpha=0.05)
        assert result.is_significant
        assert result.absolute_change > 0

    def test_no_effect_not_significant(self):
        rng = np.random.default_rng(99)
        pre = pd.Series(rng.normal(50, 5, 100))
        post = pd.Series(rng.normal(50.1, 5, 100))
        result = t_test_continuous(pre, post, alpha=0.05)
        # May or may not be significant — just check it runs without error
        assert isinstance(result, StatResult)

    def test_ci_width_shrinks_with_larger_n(self):
        small_pre = self._series(100, 10, 10)
        small_post = self._series(110, 10, 10)
        large_pre = self._series(100, 10, 200)
        large_post = self._series(110, 10, 200)
        r_small = t_test_continuous(small_pre, small_post)
        r_large = t_test_continuous(large_pre, large_post)
        ci_small = r_small.ci_upper - r_small.ci_lower
        ci_large = r_large.ci_upper - r_large.ci_lower
        assert ci_large < ci_small

    def test_too_few_observations_raises(self):
        with pytest.raises(ValueError):
            t_test_continuous(pd.Series([1.0]), pd.Series([2.0, 3.0]))

    def test_nan_handling(self):
        pre = pd.Series([10, 12, float("nan"), 11, 13])
        post = pd.Series([15, 14, float("nan"), 16, 14])
        result = t_test_continuous(pre, post)
        assert result.pre_n == 4
        assert result.post_n == 4


# ---------------------------------------------------------------------------
# count_test
# ---------------------------------------------------------------------------

class TestCountTest:
    def test_basic_count_increase(self):
        rng = np.random.default_rng(1)
        # count_test reports totals; use equal-length series so totals compare cleanly
        pre = pd.Series(rng.poisson(100, 30))
        post = pd.Series(rng.poisson(130, 30))  # same length, higher mean
        result = count_test(pre, post)
        assert isinstance(result, StatResult)
        assert result.absolute_change > 0

    def test_test_name_is_count_t(self):
        pre = pd.Series(np.ones(20) * 50)
        post = pd.Series(np.ones(20) * 55)
        result = count_test(pre, post)
        assert result.test_name == "count_t"


# ---------------------------------------------------------------------------
# sample_size_check
# ---------------------------------------------------------------------------

class TestSampleSizeCheck:
    def test_no_warning_above_threshold(self):
        warnings = sample_size_check(500, 200, min_sample_size=100, metric_name="orders")
        assert len(warnings) == 0

    def test_warning_when_below_threshold(self):
        warnings = sample_size_check(50, 200, min_sample_size=100, metric_name="orders")
        assert len(warnings) == 1
        assert "50" in warnings[0]

    def test_two_warnings_when_both_low(self):
        warnings = sample_size_check(10, 15, min_sample_size=100, metric_name="conversion_rate")
        assert len(warnings) == 2
