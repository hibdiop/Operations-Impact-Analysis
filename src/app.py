"""Main Streamlit application — Marketplace Experimentation Framework."""

from __future__ import annotations

import json
import os
import sys
import time
import uuid
from datetime import date, timedelta

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.config.metrics import registry as metric_registry
from src.config.schema import ExperimentConfig
from src.core.analyzer import Analyzer
from src.core.experiment import Experiment
from src.data.access import loader
from src.ui.insights import generate_action_recommendation, generate_narrative
from src.utils.audit_logger import log_run

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Marketplace Experimentation Framework",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# CSS — professional card-based look
# ---------------------------------------------------------------------------

st.markdown("""
<style>
/* ── Global ── */
html, body, [class*="css"] { font-family: "Inter", "Segoe UI", sans-serif; }
.main { background-color: #f5f7f9; }

/* ── Hide default footer, inject custom one ── */
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }
footer:after {
    content: "Strategy & Operations · Marketplace Experimentation Framework v1.0 · Internal Use Only";
    visibility: visible;
    display: block;
    text-align: center;
    font-size: 0.72rem;
    color: #9ca3af;
    padding: 12px 0 8px 0;
}

/* ── Metric tiles (results row) ── */
[data-testid="stMetric"] {
    background: #ffffff;
    border: 1px solid #e6e9ef;
    border-radius: 10px;
    padding: 18px 20px 14px 20px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    transition: box-shadow 0.15s ease;
}
[data-testid="stMetric"]:hover { box-shadow: 0 4px 12px rgba(0,0,0,0.10); }
[data-testid="stMetricLabel"] { font-size: 0.75rem; color: #6b7280; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; }
[data-testid="stMetricValue"] { font-size: 1.7rem; font-weight: 800; color: #111827; }
[data-testid="stMetricDelta"] svg { display: none; }

/* ── Primary button ── */
button[kind="primary"] {
    background-color: #FF3008 !important;
    border: none !important;
    color: white !important;
    font-weight: 700 !important;
    letter-spacing: 0.03em !important;
    border-radius: 8px !important;
    transition: background-color 0.15s ease, transform 0.1s ease !important;
}
button[kind="primary"]:hover {
    background-color: #d4260a !important;
    transform: translateY(-1px) !important;
}

/* ── Hide sidebar entirely ── */
[data-testid="stSidebar"]       { display: none !important; }
[data-testid="collapsedControl"]{ display: none !important; }

/* ── Content area: full width ── */
section.main .block-container {
    max-width: 100% !important;
    padding-left: 3rem !important;
    padding-right: 3rem !important;
    padding-bottom: 1rem !important;
}

/* ── Sticky bottom control bar ── */
/* Form is rendered LAST in Python (after content), so sticky:bottom:0 pins it to viewport */
[data-testid="stForm"] {
    position: sticky !important;
    bottom: 0 !important;
    z-index: 999 !important;
    background: #1a1d2e !important;
    border-top: 2px solid #FF3008 !important;
    padding: 14px 3rem 10px 3rem !important;
    margin: 0 -3rem !important;
    box-shadow: 0 -8px 40px rgba(0,0,0,0.40) !important;
    border-radius: 0 !important;
}

/* ── Bar labels and inputs ── */
[data-testid="stForm"] label,
[data-testid="stForm"] .stSelectbox label,
[data-testid="stForm"] .stTextInput label,
[data-testid="stForm"] .stDateInput label,
[data-testid="stForm"] .stNumberInput label {
    color: #9ca3af !important;
    font-size: 0.65rem !important;
    font-weight: 700 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.08em !important;
    margin-bottom: 2px !important;
}
[data-testid="stForm"] input {
    background: #252a3d !important;
    border-color: #374151 !important;
    color: #f0f6fc !important;
    font-size: 0.85rem !important;
}
[data-testid="stForm"] [data-baseweb="select"] > div {
    background: #252a3d !important;
    border-color: #374151 !important;
    color: #f0f6fc !important;
}
[data-testid="stForm"] [data-baseweb="select"] > div > div,
[data-testid="stForm"] [data-baseweb="select"] > div > div > div,
[data-testid="stForm"] [data-baseweb="select"] span {
    color: #f0f6fc !important;
    font-size: 0.85rem !important;
    background: transparent !important;
}

/* ── Section divider inside bar ── */
.bar-divider {
    width: 1px;
    background: #374151;
    align-self: stretch;
    margin: 0 4px;
}
.bar-section {
    font-size: 0.6rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: #4b5563;
    margin: 0 0 6px 0;
    padding: 0;
}

/* ── Run Analysis button — bigger in the bar ── */
[data-testid="stForm"] button[kind="primary"] {
    font-size: 1rem !important;
    font-weight: 800 !important;
    letter-spacing: 0.06em !important;
    height: 46px !important;
    border-radius: 10px !important;
    box-shadow: 0 4px 14px rgba(255,48,8,0.40) !important;
}
[data-testid="stForm"] button[kind="primary"]:hover {
    box-shadow: 0 6px 20px rgba(255,48,8,0.55) !important;
    transform: translateY(-2px) !important;
}

/* ── Section label (legacy) ── */
.section-label {
    font-size: 0.68rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: #6b7280;
    margin: 10px 0 4px 0;
}

/* ── Bento stat cards (idle hero row) ── */
.bento-card {
    background: #ffffff;
    border: 1px solid #e5e7eb;
    border-radius: 14px;
    padding: 24px 28px;
    text-align: center;
    box-shadow: 0 2px 8px rgba(0,0,0,0.06);
    transition: transform 0.15s ease, box-shadow 0.15s ease;
    height: 100%;
}
.bento-card:hover {
    transform: translateY(-3px);
    box-shadow: 0 8px 24px rgba(0,0,0,0.10);
}
.bento-card-eyebrow {
    font-size: 0.7rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: #9ca3af;
    margin-bottom: 8px;
}
.bento-card-number {
    font-size: 2.8rem;
    font-weight: 900;
    line-height: 1;
    color: #111827;
    margin-bottom: 6px;
}
.bento-card-number.red  { color: #FF3008; }
.bento-card-number.green { color: #16a34a; }
.bento-card-number.blue  { color: #2563eb; }
.bento-card-sub {
    font-size: 0.8rem;
    color: #6b7280;
    margin-top: 4px;
}

/* ── Metric pill cards ── */
.metric-pill {
    display: flex;
    align-items: flex-start;
    gap: 12px;
    background: #ffffff;
    border: 1px solid #e6e9ef;
    border-radius: 10px;
    padding: 14px 16px;
    margin-bottom: 10px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    transition: box-shadow 0.12s ease;
}
.metric-pill:hover { box-shadow: 0 4px 12px rgba(0,0,0,0.09); }
.metric-pill-icon { font-size: 1.5rem; line-height: 1; }
.metric-pill-body { flex: 1; }
.metric-pill-name { font-weight: 600; font-size: 0.92rem; color: #111827; }
.metric-pill-desc { font-size: 0.78rem; color: #6b7280; margin-top: 2px; }
.metric-pill-badge {
    font-size: 0.68rem; font-weight: 700;
    padding: 2px 8px; border-radius: 20px;
    margin-top: 6px; display: inline-block;
}
.badge-rate       { background: #dbeafe; color: #1d4ed8; }
.badge-count      { background: #d1fae5; color: #065f46; }
.badge-continuous { background: #fef3c7; color: #92400e; }

/* ── Caution banner ── */
.caution-banner {
    background: #fff7ed;
    border: 1px solid #fed7aa;
    border-left: 4px solid #f97316;
    border-radius: 8px;
    padding: 12px 16px;
    font-size: 0.88rem;
    color: #7c2d12;
    margin-top: 16px;
}

/* ── Confidence banners ── */
.confidence-high   { background: #d1fae5; border: 1px solid #6ee7b7; border-radius: 8px; padding: 12px 16px; }
.confidence-medium { background: #fef3c7; border: 1px solid #fcd34d; border-radius: 8px; padding: 12px 16px; }
.confidence-low    { background: #fee2e2; border: 1px solid #fca5a5; border-radius: 8px; padding: 12px 16px; }

/* ── Divider ── */
hr { margin: 1.2rem 0 !important; border-color: #e5e7eb !important; }

/* ── Tab strip ── */
[data-testid="stTabs"] [data-baseweb="tab"] { font-weight: 600; font-size: 0.9rem; }

/* ── Placeholder chart overlay ── */
.placeholder-label {
    font-size: 0.78rem;
    color: #9ca3af;
    text-align: center;
    margin-top: -12px;
    font-style: italic;
}
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

METRIC_META = {
    "orders":           ("🛒", "count"),
    "conversion_rate":  ("📈", "rate"),
    "cancellation_rate":("❌", "rate"),
    "fulfillment_rate": ("✅", "rate"),
    "avg_basket_size":  ("🧺", "continuous"),
    "gross_bookings":   ("💰", "continuous"),
    "net_revenue":      ("💵", "continuous"),
    "driver_utilization":("🚗", "rate"),
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_markets():
    try:
        return loader.get_available_markets()
    except Exception:
        return ["new_york", "los_angeles", "chicago", "miami", "seattle", "denver", "boston", "austin"]


def _get_date_range(market: str):
    try:
        return loader.get_date_range_for_market(market)
    except Exception:
        return {"min_date": date(2023, 1, 1), "max_date": date(2024, 3, 31)}


def _delta_color(absolute_change: float, direction: str) -> str:
    """Return Streamlit delta_color string based on metric direction."""
    if direction == "decrease_is_good":
        return "inverse"
    return "normal"


# ---------------------------------------------------------------------------
# Bottom control bar  (replaces sidebar)
# ---------------------------------------------------------------------------

def render_control_bar() -> dict:
    """
    Fixed horizontal bar at the bottom of the viewport.
    Uses st.form so the whole config submits atomically.
    CSS targets [data-testid="stForm"] to pin it to bottom: 0.
    """
    markets       = _get_markets()
    display_names = metric_registry.display_names()
    metric_options = metric_registry.names()

    # Default dates use the last market's range (static — validated on submit)
    max_dt = date(2024, 3, 31)
    default_start = max_dt - timedelta(days=20)
    default_end   = max_dt - timedelta(days=7)

    with st.form("experiment_config", clear_on_submit=False):

        # ── Row 1: section headers ─────────────────────────────────────
        h1, h2, h3, h4 = st.columns([5, 4, 2, 3])
        h1.markdown('<p class="bar-section">MARKET & INTERVENTION</p>', unsafe_allow_html=True)
        h2.markdown('<p class="bar-section">TREATMENT WINDOW</p>',      unsafe_allow_html=True)
        h3.markdown('<p class="bar-section">BASELINE</p>',              unsafe_allow_html=True)
        h4.markdown('<p class="bar-section">KPI</p>',                   unsafe_allow_html=True)

        # ── Row 2: inputs ──────────────────────────────────────────────
        c1, c2, c3, c4, c5, c6, c7 = st.columns([2, 2.2, 1.6, 1.4, 1.4, 1.1, 2.5])

        market = c1.selectbox(
            "Market",
            markets,
            format_func=lambda m: m.replace("_", " ").title(),
            help="City or region where the intervention was deployed.",
        )
        intervention_name = c2.text_input(
            "Intervention Name",
            value="Fee Waiver Campaign",
            help="Short label for this experiment — appears in the audit log and exports.",
        )
        intervention_type = c3.selectbox(
            "Type",
            ["fee_waiver", "incentive", "pricing_change", "supply_campaign", "policy_change", "other"],
            format_func=lambda x: x.replace("_", " ").title(),
        )
        treatment_start = c4.date_input(
            "Start Date",
            value=default_start,
            help="First day the intervention was live.",
        )
        treatment_end = c5.date_input(
            "End Date",
            value=default_end,
            help="Last day of the intervention (inclusive).",
        )
        pre_period_days = c6.number_input(
            "Pre (days)",
            min_value=14, max_value=90, value=30, step=7,
            help=(
                "Baseline lookback window. Default 30 = 4 weekly cycles, "
                "enough to capture Mon–Sun seasonality. Minimum 14."
            ),
        )
        metric_name = c7.selectbox(
            "KPI to Analyze",
            metric_options,
            format_func=lambda n: f"{METRIC_META.get(n,('',''))[0]}  {display_names[n]}",
            help="The business metric to evaluate.",
        )

        # ── Row 3: big centered Run Analysis button ────────────────────
        _, btn_col, _ = st.columns([2, 6, 2])
        submitted = btn_col.form_submit_button(
            "▶   RUN ANALYSIS",
            type="primary",
            use_container_width=True,
        )

    return {
        "market": market,
        "intervention_name": intervention_name,
        "intervention_type": intervention_type,
        "treatment_start": treatment_start,
        "treatment_end": treatment_end,
        "pre_period_days": int(pre_period_days),
        "metric_name": metric_name,
        "significance_level": 0.05,
        "aggregation_grain": "daily",
        "segment_filters": {},
        "comparison_markets": [],
        "run": submitted,
        "advanced": False,
    }


# ---------------------------------------------------------------------------
# Idle screen helpers
# ---------------------------------------------------------------------------

def _placeholder_chart() -> go.Figure:
    """Dummy pre-post area chart shown before any analysis runs."""
    import numpy as np
    rng = np.random.default_rng(7)
    n_pre, n_post = 30, 14
    dates_pre  = pd.date_range("2024-01-01", periods=n_pre,  freq="D")
    dates_post = pd.date_range("2024-01-31", periods=n_post, freq="D")

    pre_vals  = 100 + np.cumsum(rng.normal(0, 1.2, n_pre))
    post_vals = pre_vals[-1] + 8 + np.cumsum(rng.normal(0.4, 1.2, n_post))

    fig = go.Figure()

    # Pre-period area
    fig.add_trace(go.Scatter(
        x=dates_pre, y=pre_vals,
        fill="tozeroy", fillcolor="rgba(99,102,241,0.10)",
        line=dict(color="rgba(99,102,241,0.6)", width=2),
        mode="lines", name="Pre-period",
    ))
    # Treatment area — green lift shading
    fig.add_trace(go.Scatter(
        x=dates_post, y=post_vals,
        fill="tozeroy", fillcolor="rgba(22,163,74,0.12)",
        line=dict(color="#16a34a", width=2.5),
        mode="lines", name="Treatment period",
    ))
    # Intervention line — use add_shape to avoid Plotly 5.17 annotation bug on date axes
    fig.add_shape(
        type="line",
        x0="2024-01-31", x1="2024-01-31",
        y0=0, y1=1, yref="paper",
        line=dict(dash="dash", color="#FF3008", width=1.5),
    )
    fig.add_annotation(
        x="2024-01-31", y=1, yref="paper",
        text="Intervention start", showarrow=False,
        font=dict(color="#FF3008", size=11),
        xanchor="left", yanchor="top", xshift=6,
    )
    # Pre-avg reference
    pre_avg = float(pre_vals.mean())
    fig.add_shape(
        type="line",
        x0=dates_pre[0].isoformat(), x1=dates_pre[-1].isoformat(),
        y0=pre_avg, y1=pre_avg,
        line=dict(dash="dot", color="#9ca3af", width=1),
    )

    fig.update_layout(
        title=dict(text="Your results will appear here", font=dict(size=13, color="#9ca3af")),
        xaxis=dict(showgrid=False, linecolor="#e5e7eb", tickfont=dict(color="#9ca3af")),
        yaxis=dict(gridcolor="#f3f4f6", linecolor="#e5e7eb", tickfont=dict(color="#9ca3af")),
        plot_bgcolor="#ffffff", paper_bgcolor="#ffffff",
        legend=dict(orientation="h", y=-0.22, font=dict(size=11, color="#6b7280")),
        height=280,
        margin=dict(l=40, r=20, t=40, b=50),
    )
    return fig


# ---------------------------------------------------------------------------
# Idle screen
# ---------------------------------------------------------------------------

def render_idle_screen():
    # ── Hero bento row — three big-number outcome cards ──────────────────
    st.markdown(
        "<p style='font-size:0.85rem;color:#6b7280;font-weight:600;"
        "text-transform:uppercase;letter-spacing:0.08em;margin-bottom:14px'>"
        "Three questions answered every run</p>",
        unsafe_allow_html=True,
    )

    c1, c2, c3 = st.columns(3, gap="medium")
    with c1:
        st.markdown("""
<div class="bento-card">
  <div class="bento-card-eyebrow">Did it change?</div>
  <div class="bento-card-number red">p-value</div>
  <div class="bento-card-sub">Tested against your α threshold (default 0.05).<br>
  Values below α = statistically significant.</div>
</div>""", unsafe_allow_html=True)

    with c2:
        st.markdown("""
<div class="bento-card">
  <div class="bento-card-eyebrow">By how much?</div>
  <div class="bento-card-number green">Lift %</div>
  <div class="bento-card-sub">Relative change from baseline + absolute difference
  with 95% confidence interval.</div>
</div>""", unsafe_allow_html=True)

    with c3:
        st.markdown("""
<div class="bento-card">
  <div class="bento-card-eyebrow">Can I trust it?</div>
  <div class="bento-card-number blue">0 – 100</div>
  <div class="bento-card-sub">Confidence score based on sample size, baseline
  stability, seasonality, and signal-to-noise ratio.</div>
</div>""", unsafe_allow_html=True)

    st.markdown("<div style='margin-top:20px'></div>", unsafe_allow_html=True)

    # ── Two-column bento: placeholder chart + KPI catalog ─────────────────
    col_chart, col_kpis = st.columns([3, 2], gap="large")

    with col_chart:
        st.markdown("##### Pre-post trend visualization")
        st.plotly_chart(_placeholder_chart(), use_container_width=True, config={"displayModeBar": False})
        st.markdown(
            '<p class="placeholder-label">Configure an experiment in the sidebar and click ▶ Run Analysis to populate this chart with real data.</p>',
            unsafe_allow_html=True,
        )

    with col_kpis:
        st.markdown("##### Available KPIs")
        metrics_list = metric_registry.all()
        for m in metrics_list:
            icon, badge_type = METRIC_META.get(m.name, ("📊", "count"))
            direction_arrow = "↑ good" if m.direction == "increase_is_good" else "↓ good"
            st.markdown(f"""
<div class="metric-pill">
  <div class="metric-pill-icon">{icon}</div>
  <div class="metric-pill-body">
    <div class="metric-pill-name">{m.display_name}</div>
    <div class="metric-pill-desc">{m.description}</div>
    <span class="metric-pill-badge badge-{badge_type}">{m.metric_type}</span>
    &nbsp;<span class="metric-pill-badge badge-{badge_type}">{direction_arrow}</span>
  </div>
</div>""", unsafe_allow_html=True)

    # ── Methodology expander ───────────────────────────────────────────────
    with st.expander("⚙️ How the analysis works", expanded=False):
        col_a, col_b = st.columns(2, gap="large")
        with col_a:
            st.markdown("""
**Analysis pipeline**
```
Market + Dates + KPI
        ↓
ExperimentConfig (Pydantic validation)
        ↓
Data loaded from DuckDB warehouse
        ↓
Pre / Treatment windows split
        ↓
Statistical test auto-selected:
 • Rate metric     → two-proportion z-test
 • Continuous      → Welch's t-test
 • Count / volume  → daily count t-test
        ↓
Effect size + Diagnostics
 (trend, seasonality, stationarity)
        ↓
Confidence score (0–100)
        ↓
Plain-English summary + Export
```
""")
        with col_b:
            st.markdown("""
**Supported test types**

| Metric type | Statistical test | Effect size |
|------------|-----------------|-------------|
| Rate / proportion | Two-proportion z-test | Risk ratio, ARR |
| Continuous | Welch's t-test | Cohen's d |
| Count / volume | t-test on daily aggregates | Cohen's d |

**Validated against Monte Carlo simulation:**
- False positive rate ≤ 5.6% (within α tolerance)
- Lift estimation bias < 0.6% for adequate samples
- 92% detection power at 25% true lift
""")

    # ── Causality warning ──────────────────────────────────────────────────
    st.markdown(
        '<div class="caution-banner">'
        "<strong>⚠️ Pre-post analysis ≠ causal proof.</strong> "
        "This tool quantifies whether the observed change is statistically unlikely under the null hypothesis. "
        "It cannot rule out seasonality, concurrent campaigns, holiday effects, or other market dynamics. "
        "Use results as <em>directional evidence</em>, not definitive attribution."
        "</div>",
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Results components
# ---------------------------------------------------------------------------

def render_hero_metrics(result, config):
    """Five-wide top-line KPI cards — the TL;DR row."""
    m   = result.metric
    sr  = result.stat_result
    sig = "✅ Yes" if sr.is_significant else "❌ No"

    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.metric(
            label=f"{METRIC_META.get(m.name,('',''))[0]}  Pre-period",
            value=m.formatting.format(sr.pre_value),
            help="Average value during the baseline window.",
        )
    with col2:
        st.metric(
            label=f"{METRIC_META.get(m.name,('',''))[0]}  Treatment",
            value=m.formatting.format(sr.post_value),
            delta=f"{sr.relative_lift_pct:+.1f}%" if sr.relative_lift_pct == sr.relative_lift_pct else None,
            delta_color=_delta_color(sr.absolute_change, m.direction),
            help="Average value during the treatment window.",
        )
    with col3:
        abs_label = m.formatting.format(abs(sr.absolute_change))
        sign = "+" if sr.absolute_change > 0 else "−" if sr.absolute_change < 0 else ""
        st.metric(
            label="Absolute Change",
            value=f"{sign}{abs_label}",
            delta=f"{sr.relative_lift_pct:+.1f}% relative" if sr.relative_lift_pct == sr.relative_lift_pct else None,
            delta_color=_delta_color(sr.absolute_change, m.direction),
        )
    with col4:
        p_fmt = f"{sr.p_value:.3f}" if sr.p_value >= 0.001 else "< 0.001"
        st.metric(
            label="p-value",
            value=p_fmt,
            delta=sig,
            delta_color="off",
            help=f"Tested at α = {config.significance_level}. Stars: {sr.significance_stars() or 'none'}",
        )
    with col5:
        conf = result.confidence
        rating_emoji = {"High": "🟢", "Medium": "🟡", "Low": "🔴"}.get(conf.rating, "🟡")
        st.metric(
            label="Confidence Score",
            value=f"{conf.score} / 100",
            delta=f"{rating_emoji} {conf.rating}",
            delta_color="off",
            help=conf.banner,
        )


def render_stats_table(result, config):
    m   = result.metric
    sr  = result.stat_result
    alpha_pct = int((1 - config.significance_level) * 100)

    rows = {
        "Metric":          m.display_name,
        "Pre-period":      m.formatting.format(sr.pre_value),
        "Treatment period":m.formatting.format(sr.post_value),
        "Absolute change": (
            m.formatting.format(sr.absolute_change)
            if sr.absolute_change >= 0
            else f"−{m.formatting.format(abs(sr.absolute_change))}"
        ),
        "Relative lift":   f"{sr.relative_lift_pct:+.1f}%" if sr.relative_lift_pct == sr.relative_lift_pct else "N/A",
        "p-value":         f"{sr.p_value:.4f}{sr.significance_stars()}",
        f"{alpha_pct}% CI": f"[{m.formatting.format(sr.ci_lower)}, {m.formatting.format(sr.ci_upper)}]",
        "Effect size":     result.effect_size.magnitude_label,
        "Test used":       sr.test_name.replace("_", " "),
        "Pre N":           f"{sr.pre_n:,}",
        "Post N":          f"{sr.post_n:,}",
    }
    df = pd.DataFrame.from_dict(rows, orient="index", columns=["Value"])
    st.dataframe(df, use_container_width=True, height=420)


def render_trend_chart(result, config):
    chart_df = result.full_series
    if chart_df is None or chart_df.empty:
        st.warning("No chart data available.")
        return

    m        = result.metric
    chart_df = chart_df.copy()
    chart_df["date"] = pd.to_datetime(chart_df["date"])

    pre_mask  = chart_df["period"] == "Pre-period"
    post_mask = chart_df["period"] == "Treatment"
    pre_avg   = chart_df.loc[pre_mask,  "value"].mean()
    post_avg  = chart_df.loc[post_mask, "value"].mean()

    fig = go.Figure()

    # Faint area fill for readability
    fig.add_trace(go.Scatter(
        x=chart_df["date"], y=chart_df["value"],
        fill="tozeroy",
        fillcolor="rgba(76,120,168,0.06)",
        line=dict(color="#4c78a8", width=2),
        mode="lines",
        name=m.display_name,
    ))

    # Treatment shading
    fig.add_vrect(
        x0=pd.Timestamp(config.treatment_start),
        x1=pd.Timestamp(config.treatment_end),
        fillcolor="rgba(230,57,70,0.10)",
        layer="below", line_width=0,
        annotation_text="Treatment window",
        annotation_position="top left",
        annotation_font_color="#e63946",
    )

    # Pre average
    pre_dates = chart_df.loc[pre_mask, "date"]
    if not pre_dates.empty:
        fig.add_trace(go.Scatter(
            x=[pre_dates.min(), pre_dates.max()],
            y=[pre_avg, pre_avg],
            mode="lines",
            name=f"Pre avg: {m.formatting.format(pre_avg)}",
            line=dict(color="#6b7280", width=1.5, dash="dot"),
        ))

    # Treatment average
    post_dates = chart_df.loc[post_mask, "date"]
    if not post_dates.empty:
        fig.add_trace(go.Scatter(
            x=[post_dates.min(), post_dates.max()],
            y=[post_avg, post_avg],
            mode="lines",
            name=f"Treatment avg: {m.formatting.format(post_avg)}",
            line=dict(color="#e63946", width=1.5, dash="dash"),
        ))

    fig.update_layout(
        title=dict(
            text=f"{m.display_name} — {config.market.replace('_',' ').title()}",
            font=dict(size=15),
        ),
        xaxis_title=None,
        yaxis_title=m.display_name,
        legend=dict(orientation="h", y=-0.18, font=dict(size=11)),
        height=400,
        margin=dict(l=50, r=20, t=50, b=60),
        plot_bgcolor="#ffffff",
        paper_bgcolor="#ffffff",
        xaxis=dict(showgrid=False, linecolor="#e5e7eb"),
        yaxis=dict(gridcolor="#f3f4f6", linecolor="#e5e7eb"),
    )
    st.plotly_chart(fig, use_container_width=True)


def render_ci_plot(result, config):
    m  = result.metric
    sr = result.stat_result

    is_positive  = sr.absolute_change > 0
    point_color  = "#16a34a" if (is_positive and m.direction == "increase_is_good") or \
                               (not is_positive and m.direction == "decrease_is_good") else "#dc2626"

    fig = go.Figure()
    # CI bar
    fig.add_trace(go.Scatter(
        x=[sr.ci_lower, sr.ci_upper], y=["Effect"],
        mode="lines",
        line=dict(color="#9ca3af", width=6),
        name=f"{int((1-config.significance_level)*100)}% CI",
    ))
    # Point estimate
    fig.add_trace(go.Scatter(
        x=[sr.absolute_change], y=["Effect"],
        mode="markers",
        marker=dict(color=point_color, size=16, symbol="diamond"),
        name=f"Estimate: {m.formatting.format(sr.absolute_change)}",
    ))
    fig.add_vline(x=0, line_dash="dash", line_color="#6b7280", line_width=1)

    fig.update_layout(
        title=dict(text=f"{int((1-config.significance_level)*100)}% Confidence Interval", font=dict(size=13)),
        xaxis_title=f"Change ({m.unit or m.display_name})",
        height=190,
        margin=dict(l=30, r=20, t=45, b=40),
        plot_bgcolor="#ffffff",
        paper_bgcolor="#ffffff",
        xaxis=dict(gridcolor="#f3f4f6"),
        yaxis=dict(showticklabels=False),
        legend=dict(orientation="h", y=-0.35, font=dict(size=10)),
    )
    st.plotly_chart(fig, use_container_width=True)


def render_confidence_banner(result):
    conf = result.confidence
    css_class = {"High": "confidence-high", "Medium": "confidence-medium", "Low": "confidence-low"}.get(
        conf.rating, "confidence-medium"
    )
    emoji = {"High": "🟢", "Medium": "🟡", "Low": "🔴"}.get(conf.rating, "🟡")

    st.markdown(
        f'<div class="{css_class}">'
        f"{emoji} <strong>Confidence Score: {conf.score}/100 — {conf.rating}</strong><br>"
        f"<span style='font-size:0.9rem'>{conf.banner}</span>"
        f"</div>",
        unsafe_allow_html=True,
    )
    st.caption("")

    with st.expander("Score breakdown", expanded=False):
        for r in conf.reasons:
            st.markdown(f"✅ {r}")
        for d in conf.deductions:
            st.markdown(f"⚠️ {d}")


def render_diagnostics(result, config):
    with st.expander("🔬 Pre-period Diagnostics", expanded=False):
        col1, col2, col3 = st.columns(3)

        with col1:
            t = result.trend
            if t.trend_detected:
                st.warning(f"**Trend detected**\n\np={t.p_value:.3f}, slope={t.slope:+.4f}/day")
            else:
                st.success(f"**No trend**\n\np={t.p_value:.3f}, slope≈{t.slope:.4f}/day")

        with col2:
            s = result.seasonality
            if s.strong_seasonality:
                st.warning(f"**Strong seasonality**\n\nCV={s.day_of_week_cv:.2f}")
            else:
                st.success(f"**Mild seasonality**\n\nCV={s.day_of_week_cv:.2f}")

        with col3:
            st.info(
                f"**Coverage**\n\n"
                f"Pre: {config.pre_period_days}d  |  "
                f"Treatment: {config.treatment_days}d\n\n"
                f"Effect magnitude: **{result.effect_size.magnitude_label}**"
            )

        if s.dow_averages:
            st.markdown("**Day-of-week averages (pre-period)**")
            dow_df = pd.DataFrame.from_dict(s.dow_averages, orient="index", columns=["avg_value"])
            day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
            dow_df = dow_df.reindex([d for d in day_order if d in dow_df.index])
            st.bar_chart(dow_df, height=200)


def render_warnings(warnings):
    if not warnings:
        return
    with st.expander(f"⚠️ Warnings ({len(warnings)})", expanded=True):
        for w in warnings:
            st.warning(w)


def render_export(result, config):
    st.markdown("---")
    st.markdown("#### Export Results")
    c1, c2, c3 = st.columns(3)

    with c1:
        if result.full_series is not None:
            csv = result.full_series.to_csv(index=False)
            st.download_button(
                "📥 Time Series CSV", csv, "time_series.csv", "text/csv",
                use_container_width=True,
            )
    with c2:
        sr = result.stat_result
        summary = {
            "market": config.market,
            "metric": config.metric_name,
            "treatment_start": str(config.treatment_start),
            "treatment_end": str(config.treatment_end),
            "pre_value": sr.pre_value,
            "post_value": sr.post_value,
            "absolute_change": sr.absolute_change,
            "relative_lift_pct": sr.relative_lift_pct,
            "p_value": sr.p_value,
            "ci_lower": sr.ci_lower,
            "ci_upper": sr.ci_upper,
            "is_significant": sr.is_significant,
            "confidence_score": result.confidence.score,
            "confidence_rating": result.confidence.rating,
        }
        st.download_button(
            "📥 JSON Summary", json.dumps(summary, indent=2, default=str),
            "result_summary.json", "application/json",
            use_container_width=True,
        )
    with c3:
        narrative = generate_narrative(result, config)
        st.download_button(
            "📥 Narrative (.txt)", narrative, "narrative.txt", "text/plain",
            use_container_width=True,
        )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    # Header row — branding left, metadata right
    head_l, head_r = st.columns([3, 1])
    head_l.markdown(
        "<h2 style='margin:0;font-weight:900;color:#111827'>📊 Marketplace Experimentation Framework</h2>"
        "<p style='margin:2px 0 0 0;color:#6b7280;font-size:0.85rem'>"
        "Strategy & Operations · Self-service pre-post impact analysis</p>",
        unsafe_allow_html=True,
    )
    head_r.markdown(
        "<p style='text-align:right;color:#9ca3af;font-size:0.75rem;margin-top:10px'>"
        "v1.0 · Internal Use Only</p>",
        unsafe_allow_html=True,
    )
    st.markdown('<hr style="margin:10px 0 20px 0">', unsafe_allow_html=True)

    # Reserve a slot for all page content — filled AFTER the form so the form
    # renders last in the DOM, which makes position:sticky;bottom:0 work correctly.
    content_slot = st.empty()

    # Form renders last → sits at natural document bottom → sticky pins it to viewport
    inputs = render_control_bar()

    # ── Idle screen ────────────────────────────────────────────────────────
    if not inputs["run"]:
        with content_slot.container():
            render_idle_screen()
        return

    # ── Step-by-step progress tracker ──────────────────────────────────────
    run_id     = str(uuid.uuid4())[:8]
    start_time = time.time()
    config     = None
    result     = None

    with content_slot.container():
        with st.status("Running analysis…", expanded=True) as status:
            # Step 1 — validate
            st.write("🔎  Validating configuration…")
            try:
                config = ExperimentConfig(
                    market=inputs["market"],
                    intervention_name=inputs["intervention_name"],
                    intervention_type=inputs["intervention_type"],
                    treatment_start=inputs["treatment_start"],
                    treatment_end=inputs["treatment_end"],
                    pre_period_days=inputs["pre_period_days"],
                    metric_name=inputs["metric_name"],
                    significance_level=inputs["significance_level"],
                    aggregation_grain=inputs["aggregation_grain"],
                    segment_filters=inputs["segment_filters"],
                    comparison_markets=inputs["comparison_markets"],
                    advanced_mode=inputs["advanced"],
                )
            except Exception as e:
                status.update(label="Configuration error", state="error")
                st.error(f"**Configuration Error:** {e}")
                return

            # Step 2 — load data
            st.write("📦  Loading data from warehouse…")
            try:
                experiment = Experiment(config)
            except Exception as e:
                status.update(label="Data load failed", state="error")
                st.error(f"**Data load failed:** {e}")
                st.caption("Run `python scripts/generate_sample_data.py` then `python scripts/load_sample_data_to_duckdb.py`")
                return

            # Step 3 — statistical analysis
            st.write("📐  Running statistical tests…")
            try:
                analyzer = Analyzer(experiment)
                result   = analyzer.run()
            except Exception as e:
                status.update(label="Analysis failed", state="error")
                runtime_ms = (time.time() - start_time) * 1000
                log_run(run_id, config, None, runtime_ms, success=False, error_message=str(e))
                st.error(f"**Analysis failed:** {e}")
                return

            # Step 4 — finalise
            st.write("✨  Building visualisations…")
            runtime_ms = (time.time() - start_time) * 1000
            log_run(run_id, config, result, runtime_ms, success=True)

            status.update(
                label=f"Analysis complete — {runtime_ms:.0f} ms  |  Run ID: `{run_id}`",
                state="complete",
                expanded=False,
            )

        st.balloons()

        # ── Config warnings ────────────────────────────────────────────────
        render_warnings(result.all_warnings + config.configuration_warnings())

        # ── Hero KPI row ───────────────────────────────────────────────────
        st.markdown("---")
        render_hero_metrics(result, config)

        # ── Tabs: Analysis / Interpretation / Diagnostics ──────────────────
        st.markdown("---")
        tab_analysis, tab_interpret, tab_diag, tab_glossary = st.tabs([
            "📊 Analysis",
            "🧠 Interpretation",
            "🔬 Diagnostics",
            "📖 Glossary",
        ])

        with tab_analysis:
            st.markdown(f"#### {result.metric.display_name} over time — {config.market.replace('_',' ').title()}")
            render_trend_chart(result, config)

            col_left, col_right = st.columns([3, 2], gap="large")
            with col_left:
                st.markdown("**Statistical Results**")
                render_stats_table(result, config)
            with col_right:
                st.markdown("**Confidence Interval**")
                render_ci_plot(result, config)

        with tab_interpret:
            render_confidence_banner(result)
            st.markdown("")
            st.markdown(generate_narrative(result, config))
            st.markdown("")
            st.info(generate_action_recommendation(result, config))

        with tab_diag:
            render_diagnostics(result, config)

        with tab_glossary:
            st.markdown("""
**p-value**
: Probability of seeing a change this large (or larger) purely by chance when the intervention has zero effect.
A value below your α threshold → statistically significant.

**Confidence Interval (CI)**
: The range that would contain the true effect in ~95% of repeated experiments.
Wide = uncertain; narrow = precise.

**Statistical Significance ≠ Causality**
: This is a pre-post design. Significance means the change is unlikely to be noise —
it does not rule out seasonality, concurrent events, or other confounders.

**Relative Lift**
: Absolute change expressed as a percentage of the pre-period baseline.

**Effect Size**
: Practical magnitude — negligible / small / medium / large — independent of sample size.
A significant but negligible effect may not justify action.

**Confidence Score**
: A 0–100 trust index based on sample size, pre-period stability, seasonality strength,
and signal-to-noise ratio. High (75+), Medium (45–74), Low (< 45).

**Welch's t-test**
: Used for continuous metrics (basket size, revenue). Does not assume equal variance between periods.

**Two-proportion z-test**
: Used for rate metrics (conversion, cancellation). Tests whether two population proportions are equal.
            """)

        render_export(result, config)


if __name__ == "__main__":
    main()
