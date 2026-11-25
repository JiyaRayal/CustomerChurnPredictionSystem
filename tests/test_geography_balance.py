"""Tests for the Geography x zero-balance investigation.

The synthetic dataset below is built so every answer can be checked by hand:

    cell                      n    churned   rate
    France  zero-balance      40   10        25.0%
    France  non-zero          60   30        50.0%
    Germany zero-balance       0    0        undefined (n/a)
    Germany non-zero          50   40        80.0%
    Spain   zero-balance      40    4        10.0%
    Spain   non-zero          40   20        50.0%
"""

import re

import pandas as pd
import pytest

from churn_analytics.geography_balance import NONZERO, ZERO, investigate_geography_zero_balance


def build(cells):
    rows = []
    for country, is_zero, n, churned in cells:
        for i in range(n):
            rows.append({"Geography": country, "Balance": 0.0 if is_zero else 100.0 + i,
                         "Exited": int(i < churned)})
    return pd.DataFrame(rows)


CELLS = [("France", True, 40, 10), ("France", False, 60, 30), ("Germany", False, 50, 40),
         ("Spain", True, 40, 4), ("Spain", False, 40, 20)]


@pytest.fixture()
def result(config):
    return investigate_geography_zero_balance(build(CELLS), config)


def test_counts_table_is_correct(result):
    c = result.counts
    assert c.loc["France", [ZERO, NONZERO]].tolist() == [40, 60]
    assert c.loc["Germany", [ZERO, NONZERO]].tolist() == [0, 50]
    assert c.loc["Spain", [ZERO, NONZERO]].tolist() == [40, 40]
    assert c.loc["Germany", "Share zero-balance"] == 0.0


def test_country_without_zero_balance_customers_is_detected(result):
    assert result.structural_zero_countries == ["Germany"]
    assert result.pairwise_countries == ["France", "Spain"]


def test_association_between_country_and_zero_balance_is_detected(result):
    assert result.independence_test["p_value"] < 0.001
    assert result.independence_test["cramers_v"] > 0.3


def test_empty_cell_is_undefined_not_zero(result):
    cell = result.churn_cells.query("Country == 'Germany' and `Balance status` == @ZERO").iloc[0]
    assert cell["n"] == 0 and pd.isna(cell["churn rate"]) and cell["status"].startswith("n/a")


def test_cell_churn_rates(result):
    rates = result.churn_cells.set_index(["Country", "Balance status"])["churn rate"]
    assert rates[("France", ZERO)] == pytest.approx(0.25)
    assert rates[("France", NONZERO)] == pytest.approx(0.50)
    assert rates[("Germany", NONZERO)] == pytest.approx(0.80)
    assert rates[("Spain", ZERO)] == pytest.approx(0.10)


def test_like_for_like_pools_the_other_countries(result):
    pooled = result.like_for_like[result.like_for_like["Group"].str.startswith("Other countries")].iloc[0]
    assert pooled["n"] == 100 and pooled["churned"] == 50 and pooled["churn rate"] == pytest.approx(0.5)


def test_pooled_gap_differs_from_gap_within_countries_that_have_both_groups(result):
    gap = result.balance_gap.set_index("Scope")["gap (pp)"]
    assert gap["Pooled: France + Spain"] == pytest.approx(32.5)   # 50% - 17.5%
    assert gap["Pooled: all countries"] == pytest.approx(42.5)    # 60% - 17.5%  (Germany inflates it)
    assert gap["France"] == pytest.approx(25.0) and gap["Spain"] == pytest.approx(40.0)


def test_findings_name_the_country_and_stay_descriptive(result):
    text = " ".join(result.findings)
    assert "No customer in Germany has a zero balance" in text
    assert "does not explain why" in text
    assert "cause" not in text.lower().replace("because", "")


def test_markdown_has_no_nan_and_shows_na(result):
    text = result.to_markdown()
    assert not re.search(r"\bnan\b", text.lower())
    assert "n/a" in text and "What this does NOT tell us" in text


def test_when_every_country_has_zero_balances_no_structural_zero_is_reported(config):
    cells = [("France", True, 40, 10), ("France", False, 40, 20), ("Germany", True, 40, 8),
             ("Germany", False, 40, 25), ("Spain", True, 40, 4), ("Spain", False, 40, 20)]
    res = investigate_geography_zero_balance(build(cells), config)
    assert res.structural_zero_countries == []
    assert "No customer in" not in " ".join(res.findings)


# ------------------------------------------------ real data, cross-checked with plain pandas
def test_real_data_zero_balance_by_country(raw_df, config):
    res = investigate_geography_zero_balance(raw_df, config)
    zero = raw_df[raw_df.Balance == 0].Geography.value_counts()
    assert res.counts.loc["France", ZERO] == zero["France"] == 2418
    assert res.counts.loc["Spain", ZERO] == zero["Spain"] == 1199
    assert res.counts.loc["Germany", ZERO] == 0
    assert res.structural_zero_countries == ["Germany"]


def test_real_data_churn_numbers_match_independent_calculation(raw_df, config):
    res = investigate_geography_zero_balance(raw_df, config)
    nz = raw_df[raw_df.Balance > 0]
    germany = nz[nz.Geography == "Germany"].Exited
    row = res.like_for_like.set_index("Group").loc["Germany"]
    assert (row["n"], row["churned"]) == (len(germany), germany.sum()) == (2509, 814)
    gap = res.balance_gap.set_index("Scope")["gap (pp)"]
    assert gap["Pooled: all countries"] == pytest.approx(10.3, abs=0.05)
    assert gap["Pooled: France + Spain"] == pytest.approx(4.8, abs=0.05)
    assert res.independence_test["cramers_v"] == pytest.approx(0.44, abs=0.01)
