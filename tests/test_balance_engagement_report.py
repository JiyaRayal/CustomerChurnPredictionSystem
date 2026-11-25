"""Tests for the Phase 5 Markdown report, including that its wording follows the data (not fixed text)."""

import copy
import dataclasses
import re

import pandas as pd
import pytest

from churn_analytics.balance_engagement import run_balance_engagement_analysis
from churn_analytics.balance_engagement_report import (_ci_pp, _excludes_zero, _findings, _money, _tenure_note,
                                                       render_report)
from churn_analytics.segmentation import add_segments


@pytest.fixture(scope="module")
def parts(raw_df, config):
    segmented, _ = add_segments(raw_df.drop(columns=["Surname"]), config)
    analysis = run_balance_engagement_analysis(segmented, config)
    return analysis, render_report(analysis, config)


def test_helper_formats():
    assert _money(185_588_000) == "185.6M" and _money(float("nan")) == "n/a"
    assert _ci_pp(-1.84, 2.29) == "-1.8 to +2.3" and _ci_pp(float("nan"), 1.0) == "n/a"
    assert _excludes_zero(0.5, 2.0) and _excludes_zero(-3.0, -0.1) and not _excludes_zero(-1.0, 1.0) and not _excludes_zero(float("nan"), 1.0)


def test_tenure_note_is_computed_from_the_table():
    curve = pd.DataFrame({"tenure": [0, 1, 2, 3], "n": [400, 1000, 1020, 480]})
    text = _tenure_note(curve)
    assert "Tenure year 0 has 400 customers" in text and "year 3 has 480" in text and "median of 1,010" in text
    assert _tenure_note(curve.head(2)) == ""


def test_report_has_every_section(parts):
    text = parts[1]
    for heading in ("# High-Balance, Salary, Engagement and Tenure Analysis", "## Key findings", "## 1. Who are the High-balance customers?",
                    "## 2. Churn among High-balance customers", "## 3. High-balance vs Low-balance, like for like",
                    "### 3b. Directly standardised gap", "## 4. Does churn change with the size of the balance?",
                    "## 5. Salary and balance", "## 6. Engagement", "## 7. Tenure", "## 8. Balance exposure proxy",
                    "## 9. What this analysis cannot tell us"):
        assert heading in text


def test_report_has_no_nan_and_marks_empty_cells(parts):
    text = parts[1]
    assert not re.search(r"\bnan\b", text.lower())
    assert "n/a (n=0)" in text


def test_report_states_its_limits_and_never_calls_exposure_revenue(parts):
    text = parts[1]
    for phrase in ("**not lost revenue**", "**not** a measure of profitability or lifetime value", "associations, not causal effects", "Overlap."):
        assert phrase in text
    for banned in ("causes churn", "leads to churn", "drives churn", "lost revenue of", "revenue at risk", "is responsible for"):
        assert banned not in text.lower()


def test_report_findings_are_numbered_and_non_empty(parts, config):
    findings = _findings(parts[0], config)
    assert len(findings) >= 10 and all(len(f) > 40 for f in findings)


# ---- the verdict sentences must follow the numbers --------------------------------------
def _with_standardised(analysis, low, high):
    table = analysis.standardised_high_vs_low.copy()
    table["ci_low_pp"], table["ci_high_pp"] = low, high
    return dataclasses.replace(analysis, standardised_high_vs_low=table)


def test_verdict_says_no_difference_when_every_interval_includes_zero(parts, config):
    text = " ".join(_findings(_with_standardised(parts[0], -1.0, 1.0), config))
    assert "not distinguishable from comparable Low-balance customers" in text and "do differ" not in text


def test_verdict_says_difference_when_an_interval_excludes_zero(parts, config):
    text = " ".join(_findings(_with_standardised(parts[0], 1.0, 3.0), config))
    assert "do differ in this dataset" in text and "not distinguishable" not in text


def test_zero_balance_remark_is_omitted_when_every_country_has_zero_balances(parts, config):
    analysis = dataclasses.replace(parts[0], countries_without_zero_balance=[])
    assert "has a zero balance" not in render_report(analysis, config)
    assert "no customer in Germany has a zero balance" in render_report(parts[0], config)


def test_trend_wording_follows_the_correlation(parts, config):
    analysis = parts[0]
    steady = analysis.tenure_curve.copy()
    steady["churn_rate"] = [0.05 + 0.02 * i for i in range(len(steady))]       # a clear upward trend
    text = " ".join(_findings(dataclasses.replace(analysis, tenure_curve=steady), config))
    assert "a statistically detectable trend" in text and "no statistically detectable trend" not in text
    assert "no statistically detectable trend" in " ".join(_findings(analysis, config))  # the real data has none


def test_balance_group_shape_wording_follows_the_rates(parts, config):
    analysis = parts[0]
    rising = analysis.balance_group_churn.copy()
    rising["churn_rate"] = [0.10, 0.15, 0.20, 0.25, 0.30]
    assert "with a steady rise" in " ".join(_findings(dataclasses.replace(analysis, balance_group_churn=rising), config))
    assert "no steady rise or fall across the groups" in " ".join(_findings(analysis, config))


def test_small_sample_gap_is_not_presented_as_the_largest(parts, config):
    text = " ".join(_findings(parts[0], config))
    assert "rests on a small sample" in text           # the real +70.8 pp (n = 89 inactive) is mentioned only as a caveat
    assert "the largest among segments with at least 100 customers per group is" in text
