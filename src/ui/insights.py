"""Natural language insight generator — translates AnalysisResult into business narrative."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.config.schema import ExperimentConfig
    from src.core.analyzer import AnalysisResult


def generate_narrative(result: "AnalysisResult", config: "ExperimentConfig") -> str:
    """
    Produce a plain-English summary paragraph for a completed analysis.
    Includes observed change, statistical significance, CI, and caveats.
    """
    m = result.metric
    sr = result.stat_result

    market_label = config.market.replace("_", " ").title()
    intervention_label = config.intervention_name
    treatment_days = config.treatment_days

    # Format values using metric formatting rules
    pre_fmt = m.formatting.format(sr.pre_value)
    post_fmt = m.formatting.format(sr.post_value)
    abs_fmt = _format_change(sr.absolute_change, m)
    rel_fmt = f"{sr.relative_lift_pct:+.1f}%" if sr.relative_lift_pct == sr.relative_lift_pct else "N/A"
    ci_lower_fmt = _format_change(sr.ci_lower, m)
    ci_upper_fmt = _format_change(sr.ci_upper, m)
    alpha_pct = int((1 - config.significance_level) * 100)

    direction_word = "increased" if sr.absolute_change > 0 else "decreased"

    # Core finding
    narrative = (
        f"During the {treatment_days}-day {intervention_label} period in {market_label}, "
        f"{m.display_name} {direction_word} from {pre_fmt} to {post_fmt} "
        f"({abs_fmt}, {rel_fmt}). "
    )

    # Statistical significance
    p_fmt = f"{sr.p_value:.3f}" if sr.p_value >= 0.001 else "< 0.001"
    if sr.is_significant:
        narrative += (
            f"The p-value was {p_fmt}, and the {alpha_pct}% confidence interval "
            f"for the change was [{ci_lower_fmt}, {ci_upper_fmt}]. "
            f"This result is **statistically significant** at the {int(config.significance_level * 100)}% level. "
        )
    else:
        narrative += (
            f"The p-value was {p_fmt}, and the {alpha_pct}% confidence interval "
            f"for the change was [{ci_lower_fmt}, {ci_upper_fmt}]. "
            f"This result is **not statistically significant** at the {int(config.significance_level * 100)}% level — "
            f"the observed change could plausibly be due to random variation. "
        )

    # Direction check vs metric expectation
    if sr.is_significant:
        improvement = (
            (sr.absolute_change > 0 and m.direction == "increase_is_good")
            or (sr.absolute_change < 0 and m.direction == "decrease_is_good")
        )
        if improvement:
            narrative += f"The direction of change is **favorable** for {m.display_name}. "
        else:
            narrative += f"⚠️ The direction of change is **unfavorable** for {m.display_name}. "

    # Pre-post caveat (always included — critical for rigor)
    narrative += (
        "\n\n_Note: This is a pre-post analysis, not a randomized experiment. "
        "Statistical significance indicates the observed change is unlikely under the null hypothesis, "
        "but does not establish that the intervention alone caused the effect. "
        "Seasonality, concurrent events, and other market dynamics may contribute._"
    )

    return narrative


def generate_action_recommendation(result: "AnalysisResult", config: "ExperimentConfig") -> str:
    """Generate a short action-oriented recommendation based on the result."""
    sr = result.stat_result
    m = result.metric
    conf = result.confidence

    improvement = (
        (sr.absolute_change > 0 and m.direction == "increase_is_good")
        or (sr.absolute_change < 0 and m.direction == "decrease_is_good")
    )

    if conf.rating == "Low":
        return (
            "**Recommendation: Do not act yet.** "
            "The confidence score is low, suggesting data or design limitations. "
            "Consider extending the measurement window or consulting an analyst."
        )

    if sr.is_significant and improvement:
        if conf.rating == "High":
            return (
                "**Recommendation: Consider scaling this intervention.** "
                "The result is statistically significant, in the right direction, "
                "and the data quality is strong. Validate with a controlled experiment before full rollout."
            )
        return (
            "**Recommendation: Promising — but validate further.** "
            "The result is significant and directionally positive, "
            "but confidence in the data is moderate. A controlled A/B test is advisable before scaling."
        )

    if sr.is_significant and not improvement:
        return (
            "**Recommendation: Investigate and pause.** "
            "The result is statistically significant but in an unfavorable direction. "
            "Review whether the intervention may have had unintended negative effects."
        )

    return (
        "**Recommendation: Inconclusive.** "
        "The result is not statistically significant. "
        "This may mean the intervention had no effect, or the test lacked sufficient power. "
        "Consider a longer measurement window or larger market before concluding."
    )


def _format_change(value: float, metric) -> str:
    """Format an absolute change value with sign and metric unit."""
    if value != value:  # NaN
        return "N/A"
    fmt = metric.formatting
    if fmt.is_percentage:
        v = value * fmt.multiplier
        return f"{v:+.{fmt.decimal_places}f} {metric.unit}"
    return f"{fmt.prefix}{value:+,.{fmt.decimal_places}f}{fmt.suffix}"
