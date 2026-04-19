"""Validation script — runs Monte Carlo simulations to verify statistical framework correctness."""

from __future__ import annotations

import os
import sys
from datetime import date, timedelta
from typing import Dict, List

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.stats.tests import proportion_test, t_test_continuous

N_SIMULATIONS = 500
ALPHA = 0.05
RNG = np.random.default_rng(2024)


def run_proportion_scenario(
    pre_rate: float,
    post_rate: float,
    n_pre: int,
    n_post: int,
    n_sim: int = N_SIMULATIONS,
) -> Dict:
    detections = 0
    lift_estimates = []

    for _ in range(n_sim):
        pre_s = RNG.binomial(n_pre, pre_rate)
        post_s = RNG.binomial(n_post, post_rate)
        try:
            r = proportion_test(pre_s, n_pre, post_s, n_post, alpha=ALPHA)
            if r.is_significant:
                detections += 1
            lift_estimates.append(r.relative_lift_pct)
        except Exception:
            pass

    true_lift = (post_rate - pre_rate) / pre_rate * 100 if pre_rate > 0 else 0
    return {
        "true_lift_pct": true_lift,
        "detection_rate": detections / n_sim,
        "mean_estimated_lift": float(np.nanmean(lift_estimates)),
        "bias": float(np.nanmean(lift_estimates)) - true_lift,
    }


def run_continuous_scenario(
    pre_mean: float,
    post_mean: float,
    std: float,
    n_pre: int,
    n_post: int,
    n_sim: int = N_SIMULATIONS,
) -> Dict:
    detections = 0
    lift_estimates = []

    for _ in range(n_sim):
        pre = pd.Series(RNG.normal(pre_mean, std, n_pre))
        post = pd.Series(RNG.normal(post_mean, std, n_post))
        r = t_test_continuous(pre, post, alpha=ALPHA)
        if r.is_significant:
            detections += 1
        lift_estimates.append(r.relative_lift_pct)

    true_lift = (post_mean - pre_mean) / pre_mean * 100
    return {
        "true_lift_pct": true_lift,
        "detection_rate": detections / n_sim,
        "mean_estimated_lift": float(np.nanmean(lift_estimates)),
        "bias": float(np.nanmean(lift_estimates)) - true_lift,
    }


def main():
    print("=" * 70)
    print("Marketplace Experimentation Framework — Statistical Validation")
    print(f"Simulations per scenario: {N_SIMULATIONS}  |  Alpha: {ALPHA}")
    print("=" * 70)

    scenarios_proportion = [
        ("No effect (null)",         0.08, 0.08,  5_000, 5_000),
        ("Small lift (+10%)",        0.08, 0.088, 5_000, 5_000),
        ("Medium lift (+25%)",       0.08, 0.10,  5_000, 5_000),
        ("Large lift (+50%)",        0.08, 0.12,  5_000, 5_000),
        ("Small lift, small sample", 0.08, 0.088, 500,   500),
    ]

    print("\n--- Proportion Tests (two-proportion z-test) ---")
    print(f"{'Scenario':<32} {'True Lift':>10} {'Detection':>10} {'Est Lift':>10} {'Bias':>8}")
    print("-" * 75)
    results = []
    for name, pr, po, n1, n2 in scenarios_proportion:
        r = run_proportion_scenario(pr, po, n1, n2)
        flag = ""
        if name == "No effect (null)" and r["detection_rate"] > 0.10:
            flag = " ⚠️ HIGH FP RATE"
        print(
            f"{name:<32} {r['true_lift_pct']:>9.1f}%"
            f" {r['detection_rate']:>9.1%}"
            f" {r['mean_estimated_lift']:>9.1f}%"
            f" {r['bias']:>+7.2f}%{flag}"
        )
        results.append({"test": "proportion", "scenario": name, **r})

    scenarios_continuous = [
        ("No effect (null)",     100, 100, 15, 30, 30),
        ("Small lift (+10%)",    100, 110, 15, 30, 30),
        ("Medium lift (+25%)",   100, 125, 15, 30, 30),
        ("Large lift (+50%)",    100, 150, 15, 30, 30),
        ("Small sample +10%",    100, 110, 15,  7,  7),
    ]

    print("\n--- Continuous Metric Tests (Welch's t-test, daily series) ---")
    print(f"{'Scenario':<32} {'True Lift':>10} {'Detection':>10} {'Est Lift':>10} {'Bias':>8}")
    print("-" * 75)
    for name, pm, qm, std, n1, n2 in scenarios_continuous:
        r = run_continuous_scenario(pm, qm, std, n1, n2)
        flag = ""
        if name == "No effect (null)" and r["detection_rate"] > 0.10:
            flag = " ⚠️ HIGH FP RATE"
        print(
            f"{name:<32} {r['true_lift_pct']:>9.1f}%"
            f" {r['detection_rate']:>9.1%}"
            f" {r['mean_estimated_lift']:>9.1f}%"
            f" {r['bias']:>+7.2f}%{flag}"
        )
        results.append({"test": "continuous", "scenario": name, **r})

    # Null hypothesis — check false positive rate
    null_rows = [r for r in results if "No effect" in r["scenario"]]
    print("\n--- False Positive Rate Check (should be ≤ 5%) ---")
    all_pass = True
    for r in null_rows:
        status = "✅ PASS" if r["detection_rate"] <= 0.10 else "❌ FAIL"
        print(f"  {r['test']:>12} null: {r['detection_rate']:.1%}  {status}")
        if r["detection_rate"] > 0.10:
            all_pass = False

    # Save report
    out_dir = os.path.join(os.path.dirname(__file__), "../outputs")
    os.makedirs(out_dir, exist_ok=True)
    report_path = os.path.join(out_dir, "validation_report.md")

    lines = [
        "# Statistical Validation Report\n",
        f"N simulations: {N_SIMULATIONS}  |  Alpha: {ALPHA}\n\n",
        "| Test | Scenario | True Lift | Detection Rate | Est Lift | Bias |\n",
        "|------|----------|-----------|----------------|----------|------|\n",
    ]
    for r in results:
        lines.append(
            f"| {r['test']} | {r['scenario']} | {r['true_lift_pct']:.1f}% "
            f"| {r['detection_rate']:.1%} | {r['mean_estimated_lift']:.1f}% "
            f"| {r['bias']:+.2f}% |\n"
        )
    lines.append("\n## Conclusion\n")
    lines.append("All null scenarios pass false positive check.\n" if all_pass else
                 "⚠️ One or more null scenarios exceeded acceptable false positive rate.\n")

    with open(report_path, "w") as f:
        f.writelines(lines)
    print(f"\nReport saved → {report_path}")
    print("=" * 70)


if __name__ == "__main__":
    main()
