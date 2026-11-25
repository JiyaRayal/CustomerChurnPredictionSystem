"""Tests for the Phase 4 Markdown report."""

import re

import pandas as pd
import pytest

from churn_analytics.analysis import run_segment_analysis
from churn_analytics.analysis_report import _band_text, _cell, _fmt_p, render_report
from churn_analytics.segmentation import add_segments


@pytest.fixture(scope="module")
def report(raw_df, config):
    segmented, _ = add_segments(raw_df.drop(columns=["Surname"]), config)
    analysis = run_segment_analysis(segmented, config)
    return render_report(analysis, config, float(segmented["Exited"].mean()), len(segmented))


def test_band_text_comes_from_the_config_bounds():
    assert _band_text([580, 740]) == "<580, 580-739, >=740"
    assert _band_text([30, 46, 61]) == "<30, 30-45, 46-60, >=61"


def test_p_value_formatting():
    assert _fmt_p(0.0000001) == "<0.001" and _fmt_p(0.0421) == "0.042" and _fmt_p(float("nan")) == "n/a"


def test_matrix_cell_formats():
    ok = pd.Series({"n": 1500, "churn_rate": 0.1234, "status": "ok"})
    small = pd.Series({"n": 64, "churn_rate": 0.234, "status": "small sample"})
    withheld = pd.Series({"n": 20, "churn_rate": float("nan"), "status": "withheld (too small)"})
    empty = pd.Series({"n": 0, "churn_rate": float("nan"), "status": "n/a (empty group)"})
    assert _cell(ok) == "12.3% (n=1,500)" and _cell(small) == "23.4% (n=64)*"
    assert _cell(withheld) == "n/a (n=20)" and _cell(empty) == "n/a (n=0)" and _cell(None) == "n/a"


def test_report_has_every_section(report):
    for heading in ("# Segment Churn Analysis", "## Key findings", "## 1. Strength of association", "## 2. Churn by segment",
                    "## 3. Churn rate vs churn contribution", "## 4. Gender comparison", "## 5. Two-variable views",
                    "## 6. Credit score: sensitivity", "## 7. Churned vs retained", "## 8. What this analysis cannot tell us"):
        assert heading in report


def test_report_has_a_table_for_every_configured_variable(report, config):
    for variable in config["analysis"]["segment_variables"]:
        assert f"### {variable}" in report


def test_report_has_no_nan_and_shows_na_for_empty_cells(report):
    assert not re.search(r"\bnan\b", report.lower())
    assert "n/a (n=0)" in report                  # Germany x zero-balance is an empty cell


def test_report_states_its_limits_and_makes_no_causal_claim(report):
    for phrase in ("associations in one snapshot, not causal effects", "Overlap between variables", "Multiple comparisons",
                   "No German customer has a zero balance"):
        assert phrase in report
    for banned in ("causes churn", "leads to churn", "drives churn", "is responsible for"):
        assert banned not in report.lower()


def test_report_flags_extreme_rates_for_the_data_owner(report):
    assert "Worth confirming with the data owner" in report
    assert "NumOfProducts = 4 has a churn rate of exactly 100%" in report


def test_report_marks_small_samples_with_a_star(report):
    assert "4 (100.0%)*" in report


def test_report_credit_bands_are_described_from_config(report):
    assert "(<580, 580-739, >=740)" in report
