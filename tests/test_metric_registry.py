"""Unit tests for the metric registry."""

import pytest

from src.config.metrics import (
    METRIC_DEFINITIONS,
    MetricConfig,
    MetricRegistry,
    registry,
)


class TestMetricRegistry:
    def test_all_required_metrics_present(self):
        required = ["orders", "conversion_rate", "cancellation_rate",
                    "fulfillment_rate", "avg_basket_size", "gross_bookings"]
        for name in required:
            assert name in registry, f"Metric '{name}' missing from registry"

    def test_get_returns_correct_metric(self):
        m = registry.get("conversion_rate")
        assert m.display_name == "Conversion Rate"
        assert m.metric_type == "rate"
        assert m.denominator_field == "sessions"

    def test_get_unknown_raises_key_error(self):
        with pytest.raises(KeyError, match="not found"):
            registry.get("nonexistent_metric_xyz")

    def test_names_returns_list(self):
        names = registry.names()
        assert isinstance(names, list)
        assert len(names) >= 6

    def test_display_names_maps_correctly(self):
        display = registry.display_names()
        assert display["orders"] == "Completed Orders"
        assert display["conversion_rate"] == "Conversion Rate"

    def test_by_type_rate(self):
        rates = registry.by_type("rate")
        names = [m.name for m in rates]
        assert "conversion_rate" in names
        assert "orders" not in names

    def test_by_type_count(self):
        counts = registry.by_type("count")
        names = [m.name for m in counts]
        assert "orders" in names

    def test_by_type_continuous(self):
        conts = registry.by_type("continuous")
        names = [m.name for m in conts]
        assert "gross_bookings" in names

    def test_contains_operator(self):
        assert "orders" in registry
        assert "fake_metric" not in registry

    def test_all_returns_all_metrics(self):
        all_metrics = registry.all()
        assert len(all_metrics) == len(METRIC_DEFINITIONS)

    def test_rate_metrics_have_denominator(self):
        for m in registry.by_type("rate"):
            assert m.denominator_field is not None, f"{m.name} is rate but has no denominator"

    def test_count_metrics_have_no_denominator(self):
        for m in registry.by_type("count"):
            assert m.denominator_field is None, f"{m.name} is count but has a denominator"

    def test_formatting_rate_is_percentage(self):
        m = registry.get("conversion_rate")
        assert m.formatting.is_percentage

    def test_formatting_count_not_percentage(self):
        m = registry.get("orders")
        assert not m.formatting.is_percentage

    def test_invalid_registry_rate_without_denominator(self):
        bad = MetricConfig(
            name="bad_metric",
            display_name="Bad",
            description="X",
            metric_type="rate",
            numerator_field="orders",
            denominator_field=None,  # Missing!
            direction="increase_is_good",
            min_sample_size=100,
            default_test="proportion_z",
            formatting=__import__("src.config.metrics", fromlist=["FormattingRules"]).FormattingRules(),
            business_definition="test",
        )
        with pytest.raises(ValueError, match="no denominator_field"):
            MetricRegistry([bad])

    def test_direction_values_are_valid(self):
        for m in registry.all():
            assert m.direction in ("increase_is_good", "decrease_is_good")

    def test_cancellation_rate_direction_is_decrease(self):
        m = registry.get("cancellation_rate")
        assert m.direction == "decrease_is_good"
