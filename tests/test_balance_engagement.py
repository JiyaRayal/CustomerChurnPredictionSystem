"""Tests for the Phase 5 analysis: high-balance, salary, engagement, tenure, balance exposure proxy.

Small hand-computable datasets check each formula; real-data tests re-derive the key numbers with plain
pandas / numpy / scipy (a separate code path) as an independent check.
"""

import copy
import math

import numpy as np
import pandas as pd
import pytest
from scipy import stats

from churn_analytics.analysis import AnalysisError, rate_difference
from churn_analytics.balance_engagement import (balance_engagement_matrix, churn_by_balance_group,
                                                churn_within_high_balance, churned_balance_concentration,
                                                engagement_by_segment, exposure_by_variable, high_balance_profile,
                                                high_vs_low_by_stratum, inactive_share,
                                                run_balance_engagement_analysis, salary_groups, salary_vs_balance,
                                                standardised_high_vs_low, tenure_curve, _prepare)
from churn_analytics.segmentation import add_segments
from churn_analytics.stats_utils import newcombe_difference_interval, wilson_interval

HIGH, LOW, ZERO = "High-balance", "Low-balance", "Zero-balance"


def be_cfg(config, **overrides):
    """A config that analyses only the columns the toy datasets contain."""
    cfg = copy.deepcopy(config)
    cfg["analysis"]["segment_variables"] = ["Geography", "AgeBand"]
    cfg["analysis"]["sensitivity_variable"] = "Geography"
    be = cfg["balance_engagement"]
    be.update(within_high_balance_variables=["Geography"], stratify_high_vs_low_by=["Geography"],
              standardise_high_vs_low_by=[["Geography"]], engagement_segment_variables=["Geography"],
              exposure_variables=["Geography", "BalanceSegment"])
    be.update(overrides)
    return cfg


def build(cells, **defaults):
    """cells: (geography, balance segment, active 0/1, customers, churned, balance)."""
    rows = []
    for geo, seg, active, n, churned, balance in cells:
        for i in range(n):
            rows.append({"Geography": geo, "BalanceSegment": seg, "IsActiveMember": active, "Balance": float(balance),
                         "Gender": "Female", "AgeBand": "30-45", "TenureGroup": "Mid-term", "NumOfProducts": 1,
                         "EstimatedSalary": 50000.0, "Tenure": 3, "Exited": int(i < churned), **defaults})
    return pd.DataFrame(rows)


# Germany: High 60 (30 churned = 50%), Low 60 (20 = 33.3%); France: High 100 (20 = 20%), Low 100 (10 = 10%); France zero-balance 40 (4).
FIXTURE_A = [("Germany", HIGH, 1, 60, 30, 100000), ("Germany", LOW, 1, 60, 20, 50000),
             ("France", HIGH, 1, 100, 20, 100000), ("France", LOW, 1, 100, 10, 50000), ("France", ZERO, 1, 40, 4, 0)]

# Simpson-style: Germany High 90 (45 = 50%) / Low 30 (10 = 33.3%); France High 30 (6 = 20%) / Low 90 (9 = 10%).
# High-balance customers are concentrated in the high-churn country, so the raw gap is inflated.
FIXTURE_B = [("Germany", HIGH, 1, 90, 45, 100000), ("Germany", LOW, 1, 30, 10, 50000),
             ("France", HIGH, 1, 30, 6, 100000), ("France", LOW, 1, 90, 9, 50000)]


# ------------------------------------------------------------------ high vs low, like for like
def test_high_vs_low_gap_inside_each_stratum(config):
    table = high_vs_low_by_stratum(_prepare(build(FIXTURE_A), be_cfg(config)), be_cfg(config)).set_index("stratum")
    assert table.loc["Germany", "gap_pp"] == pytest.approx((0.5 - 1 / 3) * 100)
    assert table.loc["France", "gap_pp"] == pytest.approx(10.0)
    assert table.loc["All customers", "gap_pp"] == pytest.approx(12.5)       # High 50/160 = 31.25%, Low 30/160 = 18.75%
    assert table.loc["All customers", ["n_high", "n_low"]].tolist() == [160, 160]    # zero-balance customers are excluded


def test_high_vs_low_interval_is_newcombe(config):
    cfg = be_cfg(config)
    row = high_vs_low_by_stratum(_prepare(build(FIXTURE_A), cfg), cfg).set_index("stratum").loc["Germany"]
    _, low, high = newcombe_difference_interval(30, 60, 20, 60)
    assert (row["ci_low_pp"], row["ci_high_pp"]) == pytest.approx((low * 100, high * 100))


def test_high_vs_low_stratum_without_one_group_is_undefined(config):
    cfg = be_cfg(config)
    df = build([("Germany", HIGH, 1, 60, 30, 100000), ("France", HIGH, 1, 60, 20, 100000), ("France", LOW, 1, 60, 10, 50000)])
    row = high_vs_low_by_stratum(_prepare(df, cfg), cfg).set_index("stratum").loc["Germany"]
    assert pd.isna(row["gap_pp"]) and row["status"].startswith("n/a")


# ------------------------------------------------------------------ standardisation
def test_standardised_gap_differs_from_the_raw_gap_when_group_mixes_differ(config):
    cfg = be_cfg(config)
    row = standardised_high_vs_low(_prepare(build(FIXTURE_B), cfg), cfg).iloc[0]
    assert row["unadjusted_gap_pp"] == pytest.approx((51 / 120 - 19 / 120) * 100)           # 26.67 pp: inflated by the mix
    assert row["rate_high_std"] == pytest.approx(0.5 * 0.5 + 0.5 * 0.2)                      # equal weights: 120 customers per country
    assert row["rate_low_std"] == pytest.approx(0.5 * (10 / 30) + 0.5 * 0.1)
    assert row["standardised_gap_pp"] == pytest.approx(((0.35) - (0.5 / 3 + 0.05)) * 100)    # 13.33 pp
    assert row["coverage"] == pytest.approx(1.0) and (row["cells"], row["cells_used"]) == (2, 2)


def test_standardised_interval_uses_the_stratified_variance(config):
    cfg = be_cfg(config)
    row = standardised_high_vs_low(_prepare(build(FIXTURE_B), cfg), cfg).iloc[0]
    w = 0.5
    var = (w**2 * (0.5 * 0.5 / 90 + (1 / 3) * (2 / 3) / 30)) + (w**2 * (0.2 * 0.8 / 30 + 0.1 * 0.9 / 90))
    z = stats.norm.ppf(0.975)
    gap = row["standardised_gap_pp"] / 100
    assert row["ci_low_pp"] == pytest.approx((gap - z * math.sqrt(var)) * 100)
    assert row["ci_high_pp"] == pytest.approx((gap + z * math.sqrt(var)) * 100)


def test_standardisation_leaves_out_strata_with_a_tiny_group_and_reports_coverage(config):
    cfg = be_cfg(config)
    cells = FIXTURE_B + [("Spain", HIGH, 1, 10, 5, 100000), ("Spain", LOW, 1, 50, 10, 50000)]   # Spain High has only 10 customers
    row = standardised_high_vs_low(_prepare(build(cells), cfg), cfg).iloc[0]
    assert (row["cells"], row["cells_used"]) == (3, 2)
    assert row["coverage"] == pytest.approx(240 / 300)
    assert row["standardised_gap_pp"] == pytest.approx(13.3333, abs=1e-3)      # same as without Spain


def test_standardisation_ignores_zero_balance_customers_when_computing_coverage(config):
    cfg = be_cfg(config)
    cells = FIXTURE_B + [("France", ZERO, 1, 60, 6, 0), ("Germany", ZERO, 1, 20, 2, 0)]     # 80 zero-balance customers
    row = standardised_high_vs_low(_prepare(build(cells), cfg), cfg).iloc[0]
    assert row["coverage"] == pytest.approx(1.0)               # all 240 NON-ZERO customers are represented; zeros are not in the base
    assert row["standardised_gap_pp"] == pytest.approx(13.3333, abs=1e-3)


def test_standardisation_without_usable_strata_is_undefined(config):
    cfg = be_cfg(config)
    df = build([("Germany", HIGH, 1, 10, 5, 100000), ("Germany", LOW, 1, 10, 2, 50000)])
    row = standardised_high_vs_low(_prepare(df, cfg), cfg).iloc[0]
    assert row["cells_used"] == 0 and pd.isna(row["standardised_gap_pp"]) and pd.isna(row["coverage"])


# ------------------------------------------------------------------ who they are, churn inside the group
def test_high_balance_profile_composition(config):
    cfg = be_cfg(config)
    table = high_balance_profile(_prepare(build(FIXTURE_A), cfg), cfg).set_index("segment")
    assert table.loc["Germany", "n_high_balance"] == 60 and table.loc["France", "n_high_balance"] == 100
    assert table.loc["Germany", "pct_of_high_balance"] == pytest.approx(60 / 160)
    assert table.loc["Germany", "pct_of_all"] == pytest.approx(120 / 360)
    assert table.loc["Germany", "high_share_of_segment"] == pytest.approx(0.5)          # 60 of Germany's 120
    assert table["pct_of_high_balance"].sum() == pytest.approx(1.0)


def test_churn_within_high_balance_only_looks_at_high_balance_customers(config):
    cfg = be_cfg(config)
    table = churn_within_high_balance(_prepare(build(FIXTURE_A), cfg), cfg).set_index("segment")
    assert table["n"].sum() == 160 and table["churned"].sum() == 50
    assert table.loc["Germany", "churn_rate"] == pytest.approx(0.5)
    assert table["churn_contribution"].sum() == pytest.approx(1.0)


# ------------------------------------------------------------------ balance level and salary
def test_balance_groups_are_equal_sized_and_exclude_zero_balances(config):
    cfg = be_cfg(config)
    cells = []
    rows = [{"Geography": "France", "BalanceSegment": LOW, "IsActiveMember": 1, "Balance": float(b), "Gender": "Female",
             "AgeBand": "30-45", "TenureGroup": "Mid-term", "NumOfProducts": 1, "EstimatedSalary": 1.0, "Tenure": 1,
             "Exited": int(b > 120)} for b in range(1, 151)]          # 150 balances -> 5 groups of 30 (the minimum for a rate)
    rows += [{**rows[0], "Balance": 0.0, "BalanceSegment": ZERO, "Exited": 0} for _ in range(20)]
    table, cuts = churn_by_balance_group(_prepare(pd.DataFrame(rows), cfg), cfg)
    assert table["n"].tolist() == [30] * 5 and len(cuts) == 4
    assert table["churn_rate"].tolist() == pytest.approx([0, 0, 0, 0, 1.0])
    assert table["group"].tolist()[0] == "Q1 (lowest)" and table["group"].tolist()[-1] == "Q5 (highest)"
    assert (table.loc[0, "balance_min"], table.loc[4, "balance_max"]) == (1.0, 150.0)


def test_small_balance_groups_have_their_rate_withheld_not_guessed(config):
    cfg = be_cfg(config)
    rows = [{"Geography": "France", "BalanceSegment": LOW, "IsActiveMember": 1, "Balance": float(b), "Gender": "Female",
             "AgeBand": "30-45", "TenureGroup": "Mid-term", "NumOfProducts": 1, "EstimatedSalary": 1.0, "Tenure": 1,
             "Exited": int(b > 80)} for b in range(1, 101)]          # 5 groups of 20: below the 30-customer minimum
    table, _ = churn_by_balance_group(_prepare(pd.DataFrame(rows), cfg), cfg)
    assert table["churn_rate"].isna().all() and table["status"].str.startswith("withheld").all() and table["churned"].sum() == 20


def test_salary_groups_and_overview(config):
    cfg = be_cfg(config)
    rows = [{"Geography": "France", "BalanceSegment": LOW, "IsActiveMember": 1, "Balance": 1000.0, "Gender": "Female",
             "AgeBand": "30-45", "TenureGroup": "Mid-term", "NumOfProducts": 1, "EstimatedSalary": float(s), "Tenure": 1,
             "Exited": int(s > 200)} for s in range(1, 301)]
    frame = _prepare(pd.DataFrame(rows), cfg)
    labels, cuts = salary_groups(frame, cfg)
    assert labels.value_counts().tolist() == [100, 100, 100] and len(cuts) == 2
    out = salary_vs_balance(frame, cfg)
    assert out["overview"]["churn_rate"].tolist() == pytest.approx([0, 0, 1.0])
    assert list(out["overview"]["group"]) == cfg["balance_engagement"]["salary_labels"]


@pytest.mark.parametrize("sign, expected", [(1, 1.0), (-1, -1.0)])
def test_spearman_correlation_of_salary_and_balance(config, sign, expected):
    cfg = be_cfg(config)
    n = 60
    rows = [{"Geography": "France", "BalanceSegment": LOW, "IsActiveMember": 1, "Balance": float(1000 + sign * i), "Gender": "Female",
             "AgeBand": "30-45", "TenureGroup": "Mid-term", "NumOfProducts": 1, "EstimatedSalary": float(i), "Tenure": 1,
             "Exited": 0} for i in range(n)]
    rows += [{**rows[0], "Balance": 0.0, "BalanceSegment": ZERO} for _ in range(5)]
    out = salary_vs_balance(_prepare(pd.DataFrame(rows), cfg), cfg)
    assert out["rho_non_zero"] == pytest.approx(expected) and out["n_non_zero"] == n and out["n_all"] == n + 5


# ------------------------------------------------------------------ engagement and tenure
FIXTURE_E = [("Germany", HIGH, 0, 50, 25, 1000), ("Germany", HIGH, 1, 50, 10, 1000),
             ("France", HIGH, 0, 100, 30, 1000), ("France", HIGH, 1, 100, 10, 1000)]


def test_engagement_gap_inside_each_segment(config):
    cfg = be_cfg(config)
    table = engagement_by_segment(_prepare(build(FIXTURE_E), cfg), cfg).set_index("segment")
    assert table.loc["Germany", "edi_pp"] == pytest.approx(30.0) and table.loc["France", "edi_pp"] == pytest.approx(20.0)
    assert table.loc["All customers", "edi_pp"] == pytest.approx((55 / 150 - 20 / 150) * 100)
    _, low, high = newcombe_difference_interval(25, 50, 10, 50)
    assert (table.loc["Germany", "ci_low_pp"], table.loc["Germany", "ci_high_pp"]) == pytest.approx((low * 100, high * 100))


def test_engagement_gap_withheld_when_a_group_is_tiny(config):
    cfg = be_cfg(config)
    cells = [("Germany", HIGH, 0, 10, 5, 1000), ("Germany", HIGH, 1, 60, 6, 1000)]
    row = engagement_by_segment(_prepare(build(cells), cfg), cfg).set_index("segment").loc["Germany"]
    assert pd.isna(row["edi_pp"]) and row["status"].startswith("withheld")


def test_inactive_share(config):
    cfg = be_cfg(config)
    row = inactive_share(_prepare(build(FIXTURE_E), cfg), cfg).set_index("segment").loc["Germany"]
    assert (row["n"], row["inactive"]) == (100, 50) and row["share_inactive"] == pytest.approx(0.5)
    assert (row["ci_low"], row["ci_high"]) == pytest.approx(wilson_interval(50, 100))


def test_tenure_curve_rates_and_order(config):
    cfg = be_cfg(config)
    df = pd.concat([build([("France", HIGH, 1, 40, 4, 1000)], Tenure=2), build([("France", HIGH, 1, 50, 25, 1000)], Tenure=0),
                    build([("France", HIGH, 1, 60, 6, 1000)], Tenure=1)], ignore_index=True)
    table = tenure_curve(_prepare(df, cfg), cfg)
    assert table["tenure"].tolist() == [0, 1, 2] and table["n"].tolist() == [50, 60, 40]
    assert table["churn_rate"].tolist() == pytest.approx([0.5, 0.1, 0.1])


# ------------------------------------------------------------------ balance exposure proxy
FIXTURE_X = [("France", HIGH, 1, 2, 2, 100), ("France", HIGH, 1, 2, 0, 100), ("Germany", LOW, 1, 4, 4, 50), ("Spain", ZERO, 1, 2, 2, 0)]


def test_exposure_by_variable(config):
    cfg = be_cfg(config)
    table = exposure_by_variable(_prepare(build(FIXTURE_X), cfg), cfg)
    geo = table[table["variable"] == "Geography"].set_index("segment")
    assert geo.loc["France", "churned_balance"] == pytest.approx(200) and geo.loc["Germany", "churned_balance"] == pytest.approx(200)
    assert geo["share_of_all_churned_balance"].to_dict() == pytest.approx({"France": 0.5, "Germany": 0.5, "Spain": 0.0})
    assert geo["share_of_all_balance"].to_dict() == pytest.approx({"France": 400 / 600, "Germany": 200 / 600, "Spain": 0.0})
    assert geo.loc["France", "churned_share_of_segment_balance"] == pytest.approx(0.5)
    assert geo.loc["Germany", "churned_share_of_segment_balance"] == pytest.approx(1.0)
    assert pd.isna(geo.loc["Spain", "churned_share_of_segment_balance"])           # 0 / 0 is undefined, not 0%
    for variable, part in table.groupby("variable"):
        assert part["share_of_all_churned_balance"].sum() == pytest.approx(1.0)
        assert part["share_of_all_balance"].sum() == pytest.approx(1.0)


def test_churned_balance_concentration(config):
    cfg = be_cfg(config)
    cells = [("France", HIGH, 1, 1, 1, b) for b in range(100, 0, -10)] + [("Spain", ZERO, 1, 2, 2, 0)]   # churned balances 100..10 plus two zeros
    table = churned_balance_concentration(_prepare(build(cells), cfg), cfg)
    assert table.attrs == {"churned_customers": 12, "churned_with_zero_balance": 2}
    # top 10% of 12 churned customers = ceil(1.2) = 2 customers (100 + 90 of 550); top 20% = 3; top 50% = 6
    assert table["customers"].tolist() == [2, 3, 6]
    assert table["share_of_churned_balance"].tolist() == pytest.approx([190 / 550, 270 / 550, 450 / 550])
    assert table["smallest_balance_in_group"].tolist() == [90.0, 80.0, 50.0]


def test_balance_engagement_matrix(config):
    cfg = be_cfg(config)
    m = balance_engagement_matrix(_prepare(build(FIXTURE_E), cfg), cfg)
    assert m["n"].sum() == 300 and m["churn_contribution"].sum() == pytest.approx(1.0)
    assert m["share_of_all_churned_balance"].sum() == pytest.approx(1.0)
    inactive = m[m["IsActiveMember"] == "Inactive"].iloc[0]
    assert (inactive["n"], inactive["churned"]) == (150, 55) and inactive["churned_balance"] == pytest.approx(55000)


# ------------------------------------------------------------------ preconditions
def test_missing_column_is_refused(config):
    cfg = be_cfg(config)
    with pytest.raises(AnalysisError, match="Missing column"):
        _prepare(build(FIXTURE_A).drop(columns=["EstimatedSalary"]), cfg)


# ------------------------------------------------------------------ real data, checked independently
@pytest.fixture(scope="module")
def real(raw_df, config):
    segmented, _ = add_segments(raw_df.drop(columns=["Surname"]), config)
    return segmented, raw_df, run_balance_engagement_analysis(segmented, config)


def test_real_analysis_does_not_mutate_its_input(raw_df, config):
    segmented, _ = add_segments(raw_df.drop(columns=["Surname"]), config)
    before = segmented.copy()
    run_balance_engagement_analysis(segmented, config)
    pd.testing.assert_frame_equal(segmented, before)


def test_real_high_vs_low_matches_manual_counts(real):
    _, raw, result = real
    t = raw[raw.Balance > 0].Balance.median()
    nz = raw[raw.Balance > 0]
    high, low = nz[nz.Balance > t], nz[nz.Balance <= t]
    row = result.high_vs_low_by_stratum.iloc[0]
    assert (row["n_high"], row["n_low"]) == (len(high), len(low))
    assert row["gap_pp"] == pytest.approx((high.Exited.mean() - low.Exited.mean()) * 100)
    germany = result.high_vs_low_by_stratum.set_index(["variable", "stratum"]).loc[("Geography", "Germany")]
    gh, gl = high[high.Geography == "Germany"], low[low.Geography == "Germany"]
    assert (germany["n_high"], germany["n_low"]) == (len(gh), len(gl))
    assert germany["gap_pp"] == pytest.approx((gh.Exited.mean() - gl.Exited.mean()) * 100)


def test_real_standardised_gap_by_geography_matches_an_independent_calculation(real):
    _, raw, result = real
    t = raw[raw.Balance > 0].Balance.median()
    nz = raw[raw.Balance > 0].assign(high=lambda d: d.Balance > t)
    gaps, weights = [], []
    for _, g in nz.groupby("Geography"):
        gaps.append(g[g.high].Exited.mean() - g[~g.high].Exited.mean())
        weights.append(len(g))
    expected = float(np.average(gaps, weights=weights)) * 100
    row = result.standardised_high_vs_low.set_index("strata").loc["Geography"]
    assert row["standardised_gap_pp"] == pytest.approx(expected) and row["coverage"] == pytest.approx(1.0)


def test_real_balance_groups_match_pandas_qcut(real, config):
    _, raw, result = real
    nz = raw[raw.Balance > 0]
    expected = nz.groupby(pd.qcut(nz.Balance, config["balance_engagement"]["balance_quantile_groups"]), observed=True).Exited.agg(["size", "sum"])
    table = result.balance_group_churn
    assert table["n"].tolist() == expected["size"].tolist() and table["churned"].tolist() == expected["sum"].tolist()
    assert table["n"].sum() == len(nz)


def test_real_salary_balance_correlation_matches_scipy(real):
    _, raw, result = real
    nz = raw[raw.Balance > 0]
    expected = stats.spearmanr(nz.EstimatedSalary, nz.Balance)
    assert result.salary["rho_non_zero"] == pytest.approx(expected.statistic) and result.salary["p_non_zero"] == pytest.approx(expected.pvalue)
    assert result.salary["overview"]["n"].sum() == 10000


def test_real_engagement_gap_for_germany_matches_manual(real):
    _, raw, result = real
    g = raw[raw.Geography == "Germany"]
    expected = (g[g.IsActiveMember == 0].Exited.mean() - g[g.IsActiveMember == 1].Exited.mean()) * 100
    row = result.engagement_by_segment.set_index(["variable", "segment"]).loc[("Geography", "Germany")]
    assert row["edi_pp"] == pytest.approx(expected) and expected > 0


def test_real_tenure_curve_matches_groupby(real):
    _, raw, result = real
    expected = raw.groupby("Tenure").Exited.agg(["size", "mean"])
    table = result.tenure_curve.set_index("tenure")
    assert table["n"].tolist() == expected["size"].tolist() and table["churn_rate"].tolist() == pytest.approx(expected["mean"].tolist())


def test_real_exposure_reconciles_with_the_raw_data(real):
    _, raw, result = real
    churned_total = raw.loc[raw.Exited == 1, "Balance"].sum()
    for variable, part in result.exposure_by_variable.groupby("variable"):
        assert part["churned_balance"].sum() == pytest.approx(churned_total)
        assert part["share_of_all_churned_balance"].sum() == pytest.approx(1.0)
        assert part["segment_balance"].sum() == pytest.approx(raw.Balance.sum())
    assert result.balance_engagement_matrix["churned_balance"].sum() == pytest.approx(churned_total)


def test_real_concentration_matches_manual(real):
    _, raw, result = real
    balances = raw.loc[raw.Exited == 1, "Balance"].sort_values(ascending=False).to_numpy()
    k = math.ceil(0.10 * len(balances))
    row = result.concentration.iloc[0]
    assert row["customers"] == k and row["share_of_churned_balance"] == pytest.approx(balances[:k].sum() / balances.sum())
    assert result.concentration.attrs["churned_with_zero_balance"] == int((balances == 0).sum())


def test_real_country_without_zero_balances_is_detected(real):
    assert real[2].countries_without_zero_balance == ["Germany"]


def test_real_high_balance_profile_matches_manual(real):
    _, raw, result = real
    t = raw[raw.Balance > 0].Balance.median()
    high = raw[raw.Balance > t]
    row = result.high_balance_profile.set_index(["variable", "segment"]).loc[("Geography", "Germany")]
    assert row["n_high_balance"] == int((high.Geography == "Germany").sum())
    assert row["high_share_of_segment"] == pytest.approx((high.Geography == "Germany").sum() / (raw.Geography == "Germany").sum())


def test_real_analysis_is_deterministic(raw_df, config):
    segmented, _ = add_segments(raw_df.drop(columns=["Surname"]), config)
    a, b = run_balance_engagement_analysis(segmented, config), run_balance_engagement_analysis(segmented, config)
    pd.testing.assert_frame_equal(a.high_vs_low_by_stratum, b.high_vs_low_by_stratum)
    pd.testing.assert_frame_equal(a.exposure_by_variable, b.exposure_by_variable)


def test_correlation_is_undefined_without_variation_and_raises_no_warning(config):
    import warnings
    cfg = be_cfg(config)
    rows = [{"Geography": "France", "BalanceSegment": LOW, "IsActiveMember": 1, "Balance": 1000.0, "Gender": "Female",
             "AgeBand": "30-45", "TenureGroup": "Mid-term", "NumOfProducts": 1, "EstimatedSalary": float(i), "Tenure": 1,
             "Exited": 0} for i in range(40)]                       # every balance identical
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        out = salary_vs_balance(_prepare(pd.DataFrame(rows), cfg), cfg)
    assert pd.isna(out["rho_non_zero"]) and pd.isna(out["p_non_zero"])
