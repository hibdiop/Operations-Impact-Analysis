# Marketplace Experimentation Framework

A self-service pre-post impact analysis platform for marketplace operations teams. Enables Operations Managers to independently evaluate the statistical significance of localized interventions — fee waivers, incentive programs, pricing changes, supply campaigns — without requiring dedicated analyst support.

Built with Python, Streamlit, DuckDB, and SciPy. 



---

## Demo

![App Screenshot](docs/assets/screenshot_placeholder.png)

> Configure a market, set treatment dates, pick a KPI, and get a statistically grounded result in seconds.

---

## Features

- **Self-serve UI** — Simple and Advanced modes; no SQL or code required for end users
- **Metric registry** — 8 pre-configured KPIs (conversion rate, orders, cancellation rate, fulfillment rate, gross bookings, net revenue, avg basket size, driver utilization); extensible via config
- **Automatic test selection** — Two-proportion z-test for rates, Welch's t-test for continuous metrics, daily count t-test for volume metrics
- **Effect size estimation** — Cohen's d, risk ratio, odds ratio, absolute risk reduction with bootstrap confidence intervals
- **Pre-period diagnostics** — Trend detection (OLS), day-of-week seasonality (CV), ADF stationarity test
- **Confidence scoring** — 0–100 trust score based on sample size, baseline stability, and signal-to-noise ratio
- **Plain-English interpretation** — Auto-generated narrative with statistical results and business caveats
- **Audit logging** — Every run persisted to SQLite with full config and result metadata
- **Export** — CSV time series, JSON summary, narrative text download
- **Validated** — Monte Carlo simulation confirms <6% false positive rate and unbiased lift estimation

---

## Quickstart

### Prerequisites

- Python 3.9+
- pip

### Installation

```bash
git clone (https://github.com/hibdiop/Operations-Impact-Analysis.git)
cd Operations-Impact-Analysis

python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

### Load sample data

```bash
python scripts/generate_sample_data.py
python scripts/load_sample_data_to_duckdb.py
```

This creates a DuckDB database at `data/marketplace.duckdb` with 3,648 rows of synthetic daily metrics across 8 markets (New York, Los Angeles, Chicago, Miami, Seattle, Denver, Boston, Austin) from 2023-01-01 through 2024-03-31.

### Run the app

```bash
streamlit run src/app.py
```

Open [http://localhost:8501](http://localhost:8501) in your browser.

### Run tests

```bash
pytest tests/ -v
```

### Run statistical validation

```bash
python scripts/validate_analysis.py
```

---

## Project Structure

```
marketplace-experimentation-framework/
├── src/
│   ├── app.py                    # Streamlit application
│   ├── config/
│   │   ├── metrics.py            # KPI registry (MetricConfig, MetricRegistry)
│   │   └── schema.py             # Pydantic experiment configuration schema
│   ├── data/
│   │   └── access.py             # DuckDB data loader with coverage validation
│   ├── stats/
│   │   ├── tests.py              # Proportion z-test, Welch t-test, count t-test
│   │   ├── effect_size.py        # Cohen's d, risk ratio, bootstrap CIs
│   │   ├── diagnostics.py        # Trend, seasonality, stationarity checks
│   │   └── confidence_score.py   # 0–100 result trust score
│   ├── core/
│   │   ├── experiment.py         # Data loading and window splitting
│   │   └── analyzer.py           # Analysis orchestration → AnalysisResult
│   ├── ui/
│   │   └── insights.py           # Natural language narrative generator
│   └── utils/
│       └── audit_logger.py       # SQLite run audit log
├── scripts/
│   ├── generate_sample_data.py   # Synthetic data generation
│   ├── load_sample_data_to_duckdb.py
│   └── validate_analysis.py      # Monte Carlo statistical validation
├── tests/
│   ├── test_statistical_tests.py
│   ├── test_metric_registry.py
│   └── test_analyzer.py
├── data/                         # DuckDB + audit SQLite (git-ignored)
├── outputs/                      # Validation reports
├── docs/
│   ├── USER_GUIDE.md
│   └── DEVELOPER_GUIDE.md
├── .streamlit/config.toml
├── Dockerfile
├── requirements.txt
└── .env.example
```

---

## How It Works

### Analysis pipeline

```
User inputs (market, dates, KPI)
        │
        ▼
ExperimentConfig (Pydantic validation)
        │
        ▼
Experiment (loads DuckDB, splits pre/treatment/post windows)
        │
        ▼
Analyzer
  ├── Statistical test (proportion z / Welch t / count t)
  ├── Effect size (Cohen's d / risk ratio + bootstrap CI)
  ├── Diagnostics (trend, seasonality, stationarity)
  └── Confidence score (0–100)
        │
        ▼
AnalysisResult → Streamlit UI + plain-English narrative
        │
        ▼
Audit log (SQLite)
```

### Statistical methods

| Metric type | Test | Effect size |
|-------------|------|-------------|
| Rate / proportion | Two-proportion z-test | Risk ratio, ARR, odds ratio |
| Continuous (basket size, revenue) | Welch's t-test (unequal variance) | Cohen's d |
| Count (orders, cancellations) | t-test on daily aggregates | Cohen's d |

All tests report: absolute change, relative lift %, p-value, confidence interval, test statistic, sample sizes, and a significance decision at the user-selected α threshold (default 5%).

> **Important**: This framework implements pre-post analysis, not randomized experimentation. Statistical significance indicates the observed change is unlikely under the null hypothesis — it does not establish causality. The app communicates this explicitly in every result.

---

## Supported KPIs

| Metric | Type | Favorable Direction |
|--------|------|---------------------|
| Completed Orders | Count | ↑ |
| Conversion Rate | Rate | ↑ |
| Cancellation Rate | Rate | ↓ |
| Fulfillment Rate | Rate | ↑ |
| Average Basket Size | Continuous | ↑ |
| Gross Bookings | Continuous | ↑ |
| Net Revenue | Continuous | ↑ |
| Driver Utilization | Rate | ↑ |

Adding a new metric requires a single entry in `src/config/metrics.py` and a matching column in the data table. See the [Developer Guide](docs/DEVELOPER_GUIDE.md).

---

## Configuration

Copy `.env.example` to `.env` and set:

```bash
MARKETPLACE_DB_PATH=data/marketplace.duckdb   # path to DuckDB file
AUDIT_DB_PATH=data/audit_log.db               # path to audit SQLite
```

---

## Docker

```bash
docker build -t marketplace-exp .
docker run -p 8501:8501 marketplace-exp
```

The image generates and loads sample data at build time.

---

## Validation Results

Monte Carlo simulation across 500 runs per scenario confirms:

| Scenario | True Lift | Detection Rate |
|----------|-----------|----------------|
| No effect (null) — proportion | 0% | 5.6% ✅ |
| No effect (null) — continuous | 0% | 4.0% ✅ |
| Medium lift (+25%) — proportion | 25% | 92.4% |
| Large lift (+50%) — proportion | 50% | 100% |
| Medium lift (+25%) — continuous | 25% | 100% |

False positive rate is within the 5% α tolerance. Lift bias is < 0.6% for adequately sized samples.

---

## Documentation

- [User Guide](docs/USER_GUIDE.md) — How to run analyses, interpret results, and act on findings
- [Developer Guide](docs/DEVELOPER_GUIDE.md) — Architecture, setup, adding metrics/tests, deployment

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| UI | Streamlit |
| Statistical engine | SciPy, statsmodels |
| Data transformation | pandas, NumPy |
| Data warehouse (dev) | DuckDB |
| Schema validation | Pydantic v2 |
| Visualization | Plotly |
| Audit logging | SQLite |
| Testing | pytest |

---

## Roadmap

- [ ] Difference-in-differences with control market support
- [ ] Automatic control market recommendation
- [ ] Seasonality-adjusted lift estimation (CUPED-style)
- [ ] Power analysis / minimum detectable effect calculator before launch
- [ ] Intervention history browser and side-by-side comparison
- [ ] Holiday/event flagging layer
- [ ] Role-based access and saved analyses
- [ ] Integration with internal campaign management systems

---

## License

MIT
