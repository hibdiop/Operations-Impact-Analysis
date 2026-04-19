# Developer Guide — Marketplace Experimentation Framework

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         src/app.py                              │
│                    (Streamlit UI layer)                          │
│   Sidebar inputs → ExperimentConfig → Experiment → Analyzer     │
│   → AnalysisResult → insights.py → Rendered charts + narrative  │
└───────────────────┬─────────────────────────────────────────────┘
                    │
        ┌───────────┼───────────────────────┐
        ▼           ▼                       ▼
 src/config/   src/core/             src/stats/
 metrics.py    experiment.py         tests.py
 schema.py     analyzer.py           effect_size.py
               (orchestration)       diagnostics.py
                    │                confidence_score.py
                    ▼
             src/data/access.py
             (DuckDB / SQLAlchemy)
                    │
                    ▼
             data/marketplace.duckdb
             (daily_market_metrics table)
```

**Data flow**:
1. User inputs → `ExperimentConfig` (validated Pydantic model)
2. `Experiment` loads data from DuckDB, splits into pre/treatment/post windows
3. `Analyzer` runs appropriate statistical test, diagnostics, effect size, confidence score
4. `AnalysisResult` returned to Streamlit for rendering
5. `insights.py` generates plain-English narrative
6. `audit_logger.py` persists run metadata to SQLite

---

## Setup from Scratch

```bash
# 1. Clone / navigate to project
cd marketplace-experimentation-framework

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Generate sample data
python scripts/generate_sample_data.py

# 5. Load into DuckDB
python scripts/load_sample_data_to_duckdb.py

# 6. Run the app
streamlit run src/app.py

# 7. Run tests
pytest tests/ -v
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MARKETPLACE_DB_PATH` | `data/marketplace.duckdb` | Path to DuckDB database |
| `AUDIT_DB_PATH` | `data/audit_log.db` | Path to SQLite audit log |

---

## How to Add a New Metric

1. Open [src/config/metrics.py](../src/config/metrics.py).
2. Add a new `MetricConfig` entry to `METRIC_DEFINITIONS`:

```python
MetricConfig(
    name="new_user_rate",
    display_name="New User Rate",
    description="Share of orders placed by first-time users",
    metric_type="rate",
    numerator_field="new_user_orders",
    denominator_field="orders",
    direction="increase_is_good",
    min_sample_size=200,
    default_test="proportion_z",
    formatting=FormattingRules(decimal_places=2, is_percentage=True, multiplier=100),
    business_definition="new_user_orders / orders",
    unit="pp",
)
```

3. Ensure the corresponding column exists in `daily_market_metrics`.
4. Add a test in [tests/test_metric_registry.py](../tests/test_metric_registry.py).
5. Run `pytest tests/test_metric_registry.py`.

---

## How to Add a New Statistical Test

1. Add your function to [src/stats/tests.py](../src/stats/tests.py). It must:
   - Accept the appropriate pandas Series or aggregate counts
   - Return a `StatResult` dataclass
   - Handle edge cases (zeros, NaN, small N) gracefully
   - Include docstring explaining statistical assumptions

2. Update `choose_test()` in the same file to map the new metric type.

3. Update `Analyzer._run_test()` in [src/core/analyzer.py](../src/core/analyzer.py) to dispatch to the new function.

4. Add unit tests in [tests/test_statistical_tests.py](../tests/test_statistical_tests.py) verifying:
   - Known inputs produce correct outputs
   - Edge cases are handled
   - Type and shape of return value

---

## Database Schema

```sql
CREATE TABLE daily_market_metrics (
    date                  DATE NOT NULL,
    market                VARCHAR NOT NULL,
    segment               VARCHAR,
    orders                INTEGER,
    sessions              INTEGER,
    order_attempts        INTEGER,
    cancellations         INTEGER,
    gross_bookings        DOUBLE,
    net_revenue           DOUBLE,
    driver_hours          DOUBLE,
    active_delivery_hours DOUBLE,
    fulfillment_rate      DOUBLE
);

CREATE INDEX idx_market_date ON daily_market_metrics (market, date);
```

**To connect to a production warehouse**, set `MARKETPLACE_DB_PATH` to a SQLAlchemy connection string and adapt `src/data/access.py` to use `sqlalchemy.create_engine()`.

---

## Caching Strategy

- All data loads in `DataLoader.load_metrics()` are candidates for caching via `@st.cache_data(ttl=300)` (5 min TTL). Add this decorator if query latency becomes a bottleneck.
- DuckDB queries on the local file database complete in < 100ms for single-market requests.
- For production deployments with a remote warehouse, wrap `load_metrics` with `@st.cache_data(ttl=3600)`.

---

## Testing Strategy

```
tests/
├── test_statistical_tests.py   # Pure stat functions — no I/O
├── test_metric_registry.py     # Config validation — no I/O
└── test_analyzer.py            # Integration tests using mocked DataLoader
```

Run all tests:
```bash
pytest tests/ -v --tb=short
```

Run with coverage:
```bash
pytest tests/ --cov=src --cov-report=term-missing
```

The analyzer tests use `unittest.mock.MagicMock` to replace `DataLoader` with in-memory synthetic DataFrames. This keeps tests fast and deterministic without requiring a database.

---

## Deployment

### Streamlit Cloud
1. Push to GitHub.
2. Connect repo at [streamlit.io/cloud](https://streamlit.io/cloud).
3. Set main file to `src/app.py`.
4. Add `MARKETPLACE_DB_PATH` as a secret (pointing to a mounted volume or S3-backed path).

### Docker
```bash
docker build -t marketplace-exp .
docker run -p 8501:8501 marketplace-exp
```

### Local (production-like)
```bash
streamlit run src/app.py --server.port 8501 --server.headless true
```

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| "Cannot connect to DuckDB" | DB file missing | Run `python scripts/load_sample_data_to_duckdb.py` |
| "Metric not found in registry" | Typo or missing metric | Check `src/config/metrics.py` |
| "Insufficient data" | Date range has no rows | Check that market + dates exist in DB |
| App crashes on analysis | Edge case in stat engine | Check `all_warnings` for low-sample alerts |
| Tests fail with import errors | Running pytest from wrong dir | Run from repo root: `pytest tests/` |
