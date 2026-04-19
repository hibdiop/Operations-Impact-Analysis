"""Metric registry — centralizes all KPI definitions for the experimentation framework."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Literal, Optional


MetricType = Literal["count", "rate", "continuous"]
Direction = Literal["increase_is_good", "decrease_is_good"]
StatTest = Literal["proportion_z", "welch_t", "count_t"]


@dataclass(frozen=True)
class FormattingRules:
    decimal_places: int = 2
    is_percentage: bool = False
    prefix: str = ""
    suffix: str = ""
    multiplier: float = 1.0

    def format(self, value: float) -> str:
        if value is None or value != value:  # NaN check
            return "N/A"
        v = value * self.multiplier
        if self.is_percentage:
            return f"{self.prefix}{v:.{self.decimal_places}f}%{self.suffix}"
        return f"{self.prefix}{v:,.{self.decimal_places}f}{self.suffix}"


@dataclass(frozen=True)
class MetricConfig:
    """Complete specification for a single KPI."""

    name: str
    display_name: str
    description: str
    metric_type: MetricType
    numerator_field: str
    denominator_field: Optional[str]
    direction: Direction
    min_sample_size: int
    default_test: StatTest
    formatting: FormattingRules
    business_definition: str
    unit: str = ""
    warn_if_denominator_below: Optional[int] = None


METRIC_DEFINITIONS: List[MetricConfig] = [
    MetricConfig(
        name="orders",
        display_name="Completed Orders",
        description="Total number of successfully completed orders",
        metric_type="count",
        numerator_field="orders",
        denominator_field=None,
        direction="increase_is_good",
        min_sample_size=30,
        default_test="count_t",
        formatting=FormattingRules(decimal_places=0),
        business_definition="Count of orders that reached completed status within the period",
        unit="orders",
    ),
    MetricConfig(
        name="conversion_rate",
        display_name="Conversion Rate",
        description="Share of sessions that resulted in a completed order",
        metric_type="rate",
        numerator_field="orders",
        denominator_field="sessions",
        direction="increase_is_good",
        min_sample_size=200,
        default_test="proportion_z",
        formatting=FormattingRules(decimal_places=2, is_percentage=True, multiplier=100),
        business_definition="orders / sessions — captures demand-side funnel efficiency",
        unit="pp",
        warn_if_denominator_below=500,
    ),
    MetricConfig(
        name="cancellation_rate",
        display_name="Cancellation Rate",
        description="Share of orders that were cancelled before completion",
        metric_type="rate",
        numerator_field="cancellations",
        denominator_field="orders",
        direction="decrease_is_good",
        min_sample_size=200,
        default_test="proportion_z",
        formatting=FormattingRules(decimal_places=2, is_percentage=True, multiplier=100),
        business_definition="cancellations / orders — high values signal supply-demand mismatch or UX friction",
        unit="pp",
        warn_if_denominator_below=100,
    ),
    MetricConfig(
        name="fulfillment_rate",
        display_name="Fulfillment Rate",
        description="Share of requested orders successfully fulfilled by a courier",
        metric_type="rate",
        numerator_field="orders",
        denominator_field="order_attempts",
        direction="increase_is_good",
        min_sample_size=200,
        default_test="proportion_z",
        formatting=FormattingRules(decimal_places=2, is_percentage=True, multiplier=100),
        business_definition="fulfilled_orders / order_attempts — reflects supply availability and dispatch efficiency",
        unit="pp",
        warn_if_denominator_below=200,
    ),
    MetricConfig(
        name="avg_basket_size",
        display_name="Average Basket Size",
        description="Mean gross booking value per completed order",
        metric_type="continuous",
        numerator_field="gross_bookings",
        denominator_field="orders",
        direction="increase_is_good",
        min_sample_size=50,
        default_test="welch_t",
        formatting=FormattingRules(decimal_places=2, prefix="$"),
        business_definition="gross_bookings / orders — average spend per transaction",
        unit="USD",
    ),
    MetricConfig(
        name="gross_bookings",
        display_name="Gross Bookings",
        description="Total monetary value of all completed orders",
        metric_type="continuous",
        numerator_field="gross_bookings",
        denominator_field=None,
        direction="increase_is_good",
        min_sample_size=30,
        default_test="welch_t",
        formatting=FormattingRules(decimal_places=0, prefix="$"),
        business_definition="Sum of all order values including fees and taxes before any adjustments",
        unit="USD",
    ),
    MetricConfig(
        name="net_revenue",
        display_name="Net Revenue",
        description="Revenue after marketplace payouts and adjustments",
        metric_type="continuous",
        numerator_field="net_revenue",
        denominator_field=None,
        direction="increase_is_good",
        min_sample_size=30,
        default_test="welch_t",
        formatting=FormattingRules(decimal_places=0, prefix="$"),
        business_definition="Gross bookings minus courier payouts, refunds, and promotional costs",
        unit="USD",
    ),
    MetricConfig(
        name="driver_utilization",
        display_name="Driver Utilization",
        description="Share of active driver hours spent on deliveries",
        metric_type="rate",
        numerator_field="active_delivery_hours",
        denominator_field="driver_hours",
        direction="increase_is_good",
        min_sample_size=100,
        default_test="proportion_z",
        formatting=FormattingRules(decimal_places=1, is_percentage=True, multiplier=100),
        business_definition="active_delivery_hours / total_driver_hours — supply efficiency metric",
        unit="pp",
        warn_if_denominator_below=200,
    ),
]


class MetricRegistry:
    """Loads, validates, and provides lookup for all registered KPIs."""

    def __init__(self, definitions: List[MetricConfig] = METRIC_DEFINITIONS) -> None:
        self._metrics: Dict[str, MetricConfig] = {}
        for m in definitions:
            self._validate(m)
            self._metrics[m.name] = m

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def _validate(self, m: MetricConfig) -> None:
        if m.metric_type == "rate" and m.denominator_field is None:
            raise ValueError(f"Metric '{m.name}' is type 'rate' but has no denominator_field")
        if m.min_sample_size <= 0:
            raise ValueError(f"Metric '{m.name}' min_sample_size must be > 0")
        valid_tests: Dict[MetricType, StatTest] = {
            "count": "count_t",
            "rate": "proportion_z",
            "continuous": "welch_t",
        }
        if m.default_test != valid_tests[m.metric_type]:
            raise ValueError(
                f"Metric '{m.name}' default_test '{m.default_test}' is inconsistent "
                f"with metric_type '{m.metric_type}'"
            )

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    def get(self, name: str) -> MetricConfig:
        if name not in self._metrics:
            raise KeyError(f"Metric '{name}' not found. Available: {self.names()}")
        return self._metrics[name]

    def names(self) -> List[str]:
        return list(self._metrics.keys())

    def display_names(self) -> Dict[str, str]:
        return {m.name: m.display_name for m in self._metrics.values()}

    def by_type(self, metric_type: MetricType) -> List[MetricConfig]:
        return [m for m in self._metrics.values() if m.metric_type == metric_type]

    def all(self) -> List[MetricConfig]:
        return list(self._metrics.values())

    def __contains__(self, name: str) -> bool:
        return name in self._metrics


# Module-level singleton
registry = MetricRegistry()
