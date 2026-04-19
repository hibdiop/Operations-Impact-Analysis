"""Pydantic schema for experiment configuration with full validation."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from src.config.metrics import registry as metric_registry

InterventionType = Literal[
    "fee_waiver",
    "incentive",
    "pricing_change",
    "supply_campaign",
    "policy_change",
    "other",
]

AggregationGrain = Literal["daily", "weekly"]

MIN_PRE_PERIOD_DAYS = 14
MIN_TREATMENT_DAYS = 1
RECOMMENDED_PRE_PERIOD_DAYS = 28


class DateWindow:
    """A resolved date range."""

    def __init__(self, start: date, end: date) -> None:
        if end < start:
            raise ValueError(f"Window end {end} is before start {start}")
        self.start = start
        self.end = end

    @property
    def days(self) -> int:
        return (self.end - self.start).days + 1

    def date_list(self) -> List[date]:
        return [self.start + timedelta(days=i) for i in range(self.days)]

    def __repr__(self) -> str:
        return f"DateWindow({self.start} → {self.end}, {self.days}d)"


class ExperimentConfig(BaseModel):
    market: str = Field(..., description="Market / city identifier (e.g. 'new_york')")
    intervention_name: str = Field(..., description="Short descriptive name for this intervention")
    intervention_type: InterventionType = Field(..., description="Category of operational intervention")
    treatment_start: date = Field(..., description="First day of the intervention period")
    treatment_end: date = Field(..., description="Last day of the intervention period (inclusive)")
    pre_period_days: int = Field(
        default=RECOMMENDED_PRE_PERIOD_DAYS,
        ge=MIN_PRE_PERIOD_DAYS,
        description="Number of days before treatment_start used as baseline",
    )
    post_period_days: Optional[int] = Field(
        default=None,
        description="Days after treatment_end to include as post-window; defaults to treatment length",
    )
    metric_name: str = Field(..., description="KPI to evaluate (must exist in metric registry)")
    aggregation_grain: AggregationGrain = Field(default="daily")
    segment_filters: Dict[str, List[str]] = Field(
        default_factory=dict,
        description="Optional segment filters, e.g. {'customer_segment': ['new']}",
    )
    comparison_markets: List[str] = Field(
        default_factory=list,
        description="Optional control markets for DiD-style analysis",
    )
    significance_level: float = Field(
        default=0.05, gt=0.0, lt=1.0, description="Alpha threshold for hypothesis testing"
    )
    advanced_mode: bool = Field(default=False)

    # ------------------------------------------------------------------
    # Field-level validators
    # ------------------------------------------------------------------

    @field_validator("market")
    @classmethod
    def market_not_empty(cls, v: str) -> str:
        v = v.strip().lower().replace(" ", "_")
        if not v:
            raise ValueError("Market cannot be empty")
        return v

    @field_validator("metric_name")
    @classmethod
    def metric_must_exist(cls, v: str) -> str:
        if v not in metric_registry:
            raise ValueError(
                f"Metric '{v}' not found in registry. "
                f"Available metrics: {metric_registry.names()}"
            )
        return v

    @field_validator("comparison_markets")
    @classmethod
    def normalise_comparison_markets(cls, v: List[str]) -> List[str]:
        return [m.strip().lower().replace(" ", "_") for m in v]

    # ------------------------------------------------------------------
    # Cross-field validators
    # ------------------------------------------------------------------

    @model_validator(mode="after")
    def validate_dates(self) -> "ExperimentConfig":
        if self.treatment_end < self.treatment_start:
            raise ValueError("treatment_end must be on or after treatment_start")
        if (self.treatment_end - self.treatment_start).days + 1 < MIN_TREATMENT_DAYS:
            raise ValueError(f"Treatment period must be at least {MIN_TREATMENT_DAYS} day(s)")
        pre_start = self.pre_period_start
        if pre_start >= self.treatment_start:
            raise ValueError(
                f"Pre-period start {pre_start} overlaps with treatment start {self.treatment_start}"
            )
        return self

    @model_validator(mode="after")
    def treatment_not_in_future(self) -> "ExperimentConfig":
        if self.treatment_start > date.today():
            raise ValueError("treatment_start cannot be in the future")
        return self

    # ------------------------------------------------------------------
    # Derived properties
    # ------------------------------------------------------------------

    @property
    def pre_period_start(self) -> date:
        return self.treatment_start - timedelta(days=self.pre_period_days)

    @property
    def pre_period_end(self) -> date:
        return self.treatment_start - timedelta(days=1)

    @property
    def effective_post_period_days(self) -> int:
        if self.post_period_days is not None:
            return self.post_period_days
        return (self.treatment_end - self.treatment_start).days + 1

    @property
    def post_period_start(self) -> date:
        return self.treatment_end + timedelta(days=1)

    @property
    def post_period_end(self) -> date:
        return self.post_period_start + timedelta(days=self.effective_post_period_days - 1)

    @property
    def treatment_days(self) -> int:
        return (self.treatment_end - self.treatment_start).days + 1

    def pre_window(self) -> DateWindow:
        return DateWindow(self.pre_period_start, self.pre_period_end)

    def treatment_window(self) -> DateWindow:
        return DateWindow(self.treatment_start, self.treatment_end)

    def post_window(self) -> DateWindow:
        return DateWindow(self.post_period_start, self.post_period_end)

    def full_date_range(self) -> DateWindow:
        return DateWindow(self.pre_period_start, self.post_period_end)

    # ------------------------------------------------------------------
    # Warnings (non-blocking)
    # ------------------------------------------------------------------

    def configuration_warnings(self) -> List[str]:
        warnings: List[str] = []
        if self.pre_period_days < RECOMMENDED_PRE_PERIOD_DAYS:
            warnings.append(
                f"Pre-period is only {self.pre_period_days} days. "
                f"At least {RECOMMENDED_PRE_PERIOD_DAYS} days recommended for stable baseline estimates."
            )
        if self.treatment_days < 7:
            warnings.append(
                "Treatment period is shorter than 7 days. "
                "Results may be driven by day-of-week effects rather than the intervention."
            )
        if self.aggregation_grain == "weekly" and self.pre_period_days < 28:
            warnings.append(
                "Weekly aggregation with fewer than 4 pre-period weeks yields very few data points."
            )
        if self.comparison_markets and self.market in self.comparison_markets:
            warnings.append("Treatment market appears in comparison_markets list — removing it.")
        return warnings

    def clean_comparison_markets(self) -> List[str]:
        return [m for m in self.comparison_markets if m != self.market]

    class Config:
        frozen = True
