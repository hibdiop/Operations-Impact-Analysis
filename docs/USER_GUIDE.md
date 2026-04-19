# User Guide — Marketplace Experimentation Framework

## Quick Start (2 minutes)

1. Open the app in your browser (ask your admin for the URL, or run `streamlit run src/app.py` locally).
2. In the **sidebar**, select your **Market**, enter an **Intervention Name**, and pick the **Intervention Type**.
3. Set the **Treatment Start** and **End** dates to match when your intervention ran.
4. Choose the **KPI to Analyze** (e.g., Conversion Rate).
5. Click **▶️ Run Analysis**.
6. Read the summary cards, the trend chart, and the plain-English interpretation.

---

## Step-by-Step Tutorial

### 1. Select your market
Choose the city or region where the intervention was deployed. Only markets with data in the warehouse will appear.

### 2. Name your intervention
Use a short, descriptive name like "NYC Fee Waiver — Jan 2024". This label appears in the audit log and exported files.

### 3. Set the treatment window
- **Treatment Start**: The first day the intervention was live.
- **Treatment End**: The last day (inclusive).
- A minimum of 7 days is recommended. Very short treatment windows are prone to day-of-week noise.

### 4. Set the pre-period length
This is the baseline lookback. Defaults to **30 days**. Minimum is 14 days. 28+ days (4 weeks) is recommended to capture weekly patterns.

### 5. Choose a KPI
| KPI | What it measures | Good direction |
|-----|-----------------|----------------|
| Completed Orders | Total order volume | ↑ |
| Conversion Rate | % of sessions converting to orders | ↑ |
| Cancellation Rate | % of orders cancelled | ↓ |
| Fulfillment Rate | % of demand met by supply | ↑ |
| Average Basket Size | Revenue per order | ↑ |
| Gross Bookings | Total GMV | ↑ |
| Net Revenue | Revenue after payouts | ↑ |
| Driver Utilization | Supply efficiency | ↑ |

### 6. Run the analysis
Click **▶️ Run Analysis**. Results appear in seconds.

---

## Understanding Your Results

### Summary Cards
Four cards show: **pre-period value**, **treatment-period value**, **absolute change**, and **p-value with significance flag**.

### Trend Chart
The time series shows the KPI daily with the treatment window shaded in orange. Dashed horizontal lines show the pre-period and treatment-period averages.

### Statistical Results Table
Contains the full set of numbers: change, lift %, p-value, confidence interval, and the statistical test used.

### What is statistical significance?
The p-value measures how likely the observed change would be if the intervention had no effect whatsoever. A p-value below your α threshold (default 5%) means the result is "statistically significant" — it's unlikely to be pure noise.

**Important**: Statistical significance does **not** mean causality. It means the effect is real relative to random variation. Other concurrent factors may also explain the change.

### What is a confidence interval?
A 95% confidence interval means: if you repeated this experiment 100 times, the interval would contain the true effect about 95 times. A wide interval means high uncertainty; a narrow interval means low uncertainty.

### The Confidence Score
Ranges from 0–100. Based on:
- Sample size adequacy
- Absence of pre-period trends
- Low day-of-week seasonality
- Sufficient pre-period length
- Signal strength relative to noise

**High (75–100)**: Data supports acting on the result.
**Medium (45–74)**: Directional signal, but interpret cautiously.
**Low (0–44)**: Unreliable; consult an analyst before acting.

---

## Common Use Cases

### Fee Waiver Analysis
- **KPI**: Conversion Rate or Completed Orders
- **Pre-period**: 28 days before waiver launch
- **Treatment**: Duration of the waiver
- **Watch for**: Seasonality if the waiver ran over a holiday weekend

### Incentive Program Evaluation
- **KPI**: Gross Bookings or Net Revenue
- **Pre-period**: Matching period from prior week/month
- **Treatment**: Duration of the incentive program
- **Watch for**: If the incentive attracted lower-value orders, basket size may drop

### Pricing Change Impact
- **KPI**: Conversion Rate (demand-side) and Gross Bookings (revenue-side)
- Run two analyses — one per KPI
- **Watch for**: Price elasticity effects showing up 1–2 days after announcement

### Supply-Side Campaign
- **KPI**: Driver Utilization or Fulfillment Rate
- **Pre-period**: 14–28 days
- **Watch for**: Lagged effects — supply response may take a few days

---

## Interpreting Warnings

### "Pre-period too short"
You have fewer than 28 days of baseline. Weekly seasonality patterns may not be fully captured. Consider extending the pre-period lookback.

### "Seasonality detected"
Day-of-week variation is strong. If your treatment window covers a different weekday mix than the pre-period (e.g., treatment ran Mon–Fri but pre-period included weekends), the difference may reflect the weekday mix, not the intervention.
**Action**: Verify the weekday composition of each window matches, or use weekly aggregation.

### "Trend in pre-period"
The metric was already moving before the intervention. The observed post-period change may continue that existing trajectory.
**Action**: Consider whether the trend has a separate business explanation. The lift estimate may overstate the intervention's contribution.

### "Small sample size"
The denominator or number of daily observations is below the recommended minimum. Results are statistically unstable.
**Action**: Extend the measurement period, or consult an analyst for a properly powered experiment.

---

## FAQ

**Q: Why is my p-value > 0.05 even though the metric clearly moved?**
A: A p-value measures whether the observed change is unlikely *given random variation*. If your market is small or noisy, the same absolute change may not be statistically distinguishable from noise.

**Q: My p-value is 0.03 but the confidence interval includes 0. How?**
A: This shouldn't happen consistently — if the CI includes 0, the p-value should exceed α. If you see this, check for rounding in the display.

**Q: Can I use this for A/B tests?**
A: No. This tool is designed for pre-post analysis, not randomized experiments. For A/B tests with treatment and control groups, a different analysis methodology is required.

**Q: What if my treatment period spans a holiday?**
A: Flag it manually. Holidays often cause large one-time shifts unrelated to the intervention. The tool does not currently auto-detect holidays, but the diagnostics section will show unusual spikes in the trend chart.

**Q: How do I know the tool is calculating correctly?**
A: The statistical engine is validated via Monte Carlo simulations (see `scripts/validate_analysis.py`). It reproduces known false positive rates (~5%) and detects known effects with expected power.

**Q: The result says "significant" but I don't believe it. What should I do?**
A: That's healthy skepticism. Check the confidence score — if it's "Low" or "Medium", treat the result as directional only. Look at the trend chart for anomalies. Consider requesting a formal analyst review.

**Q: Why does the chart look different from what I expected?**
A: The chart shows the raw daily metric. If you're seeing volatility, that's real noise in the data. The statistical test accounts for this volatility.

**Q: Can I compare two interventions side by side?**
A: Not in v1. This is planned for a future release.

**Q: Where are my results saved?**
A: Every run is logged to the audit database automatically. Use the Download buttons to export CSV, JSON, or a text summary.

**Q: How do I add a new market?**
A: New markets need to be added to the data warehouse. Ask your data engineering team to populate the `daily_market_metrics` table for the new market.

---

## Decision Flowchart: Should I Act on This Result?

```
Is the result statistically significant?
├── No  → Insufficient evidence. Extend period or run a formal experiment.
└── Yes
    ├── Is the direction favorable?
    │   ├── No  → Investigate. The intervention may have caused harm.
    │   └── Yes
    │       ├── Is the Confidence Score "High"?
    │       │   ├── Yes → Consider scaling. Validate with a controlled test first.
    │       │   └── No  → Use as directional signal only. More data needed.
    └── Are there active warnings (trend / seasonality)?
        ├── Yes → Interpret cautiously. Consult an analyst.
        └── No  → Proceed with above logic.
```

---

## Glossary

| Term | Plain-English Definition |
|------|------------------------|
| p-value | Probability the observed change happened by chance if the intervention had zero effect |
| Confidence Interval | Range of plausible values for the true effect |
| Statistical Significance | The result clears the noise threshold; unlikely to be random variation |
| Absolute Change | The raw difference between post and pre values |
| Relative Lift | Absolute change as a percentage of the pre-period value |
| Effect Size | How large the change is in practical terms (small/medium/large) |
| Pre-period | The baseline window before the intervention |
| Treatment Period | The window when the intervention was active |
| Proportion Test | Statistical test for rate metrics (e.g., conversion rate) |
| Welch's t-test | Statistical test for continuous metrics (e.g., basket size) |
| Causality | Whether the intervention *caused* the change — this tool cannot establish causality |
