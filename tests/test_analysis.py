"""Tests for the Phase 4 segment analysis.

Small hand-computable datasets check each formula; real-data tests re-derive the key numbers with
plain pandas / scipy (a separate code path) as an independent check.
"""

import copy

import numpy as np
import pandas as pd
import pytest
from scipy import stats

from churn_analytics.analysis import (MISSING_LABEL, AnalysisError, association_table, effect_label,
                                      gender_comparison, interaction_table, prepare_for_analysis,
                                      profile_comparison, rate_difference, run_segment_analysis,
                                      segment_overview)
from churn_analytics.segmentation import add_segments
from churn_analytics.stats_utils import newcombe_difference_interval, wilson_interval


def mini_config(config, variables, sensitivity=None, numeric=("Age",)):
    """A copy of the config that analyses only the listed variables (keeps toy datasets small)."""
    cfg = copy.deepcopy(config)
    cfg["analysis"]["segment_variables"] = list(variables)
    cfg["analysis"]["sensitivity_variable"] = sensitivity or variables[0]
    cfg["analysis"]["numeric_profile_columns"] = list(numeric)
    return cfg


def geo_df():
    """France 100 (20 churned), Germany 60 (30), Spain 40 (10): overall 60/200 = 30%."""
    geo = ["France"] * 100 + ["Germany"] * 60 + ["Spain"] * 40
    exited = [1] * 20 + [0] * 80 + [1] * 30 + [0] * 30 + [1] * 10 + [0] * 30
    return pd.DataFrame({"Geography": geo, "Exited": exited})


def two_group_df(n_a, churn_a, n_b, churn_b, column="Gender", a="Female", b="Male"):
    rows = [(a, int(i < churn_a)) for i in range(n_a)] + [(b, int(i < churn_b)) for i in range(n_b)]
    return pd.DataFrame(rows, columns=[column, "Exited"])


# ------------------------------------------------------------------ preparation
def test_display_labels_replace_0_and_1_without_losing_or_changing_customers(valid_df, config):
    segmented, _ = add_segments(valid_df.drop(columns=["Surname"]), config)
    prepared = prepare_for_analysis(segmented, config)
    assert list(prepared["HasCrCard"].cat.categories) == ["No credit card", "Has credit card"]
    assert list(prepared["IsActiveMember"].cat.categories) == ["Inactive", "Active"]
    assert (prepared["IsActiveMember"].astype(str) == segmented["IsActiveMember"].map({0: "Inactive", 1: "Active"})).all()
    assert len(prepared) == len(segmented) and prepared["Exited"].equals(segmented["Exited"])


def test_prepare_is_idempotent_and_does_not_mutate_input(valid_df, config):
    segmented, _ = add_segments(valid_df.drop(columns=["Surname"]), config)
    before = segmented.copy()
    once = prepare_for_analysis(segmented, config)
    twice = prepare_for_analysis(once, config)
    pd.testing.assert_frame_equal(once, twice)
    pd.testing.assert_frame_equal(segmented, before)


def test_prepare_refuses_unmapped_values(valid_df, config):
    segmented, _ = add_segments(valid_df.drop(columns=["Surname"]), config)
    segmented.loc[0, "HasCrCard"] = 5
    with pytest.raises(AnalysisError, match="display_labels"):
        prepare_for_analysis(segmented, config)


def test_prepare_refuses_missing_columns(valid_df, config):
    with pytest.raises(AnalysisError, match="Phase 2 pipeline"):
        prepare_for_analysis(valid_df, config)      # raw frame: derived segments are not there yet


# ------------------------------------------------------------------ segment overview
def test_overview_ratio_and_contribution_gap_values(config):
    cfg = mini_config(config, ["Geography"])
    table = segment_overview(geo_df(), cfg, ["Geography"]).set_index("segment")
    assert table["rate_ratio"].to_dict() == pytest.approx({"France": 0.20 / 0.30, "Germany": 0.50 / 0.30, "Spain": 0.25 / 0.30})
    # contribution - share: France 20/60 - 0.5, Germany 30/60 - 0.3, Spain 10/60 - 0.2   (x100, percentage points)
    assert table["contribution_minus_share_pp"].to_dict() == pytest.approx(
        {"France": (20 / 60 - 0.5) * 100, "Germany": (0.5 - 0.3) * 100, "Spain": (10 / 60 - 0.2) * 100})
    assert table["contribution_minus_share_pp"].sum() == pytest.approx(0.0, abs=1e-9)
    assert table["overall_rate"].to_numpy() == pytest.approx([0.30, 0.30, 0.30])


def test_ratio_equals_contribution_divided_by_share(config):
    cfg = mini_config(config, ["Geography"])
    table = segment_overview(geo_df(), cfg, ["Geography"])
    assert (table["churn_contribution"] / table["share_of_customers"]).to_numpy() == pytest.approx(table["rate_ratio"].to_numpy())


def test_overview_keeps_every_customer(config):
    cfg = mini_config(config, ["Geography"])
    table = segment_overview(geo_df(), cfg, ["Geography"])
    assert table["n"].sum() == 200 and table["churned"].sum() == 60 and table["churn_contribution"].sum() == pytest.approx(1.0)


def test_missing_segment_value_gets_its_own_row(config):
    cfg = mini_config(config, ["Geography"])
    df = geo_df()
    df["Geography"] = df["Geography"].astype(object)
    df.loc[0, "Geography"] = np.nan
    table = segment_overview(df, cfg, ["Geography"])
    assert MISSING_LABEL in set(table["segment"]) and table["n"].sum() == 200


def test_no_churners_gives_undefined_ratio_not_a_crash(config):
    cfg = mini_config(config, ["Geography"])
    df = geo_df().assign(Exited=0)
    table = segment_overview(df, cfg, ["Geography"])
    assert table["rate_ratio"].isna().all() and (table["churn_rate"] == 0).all()


# ------------------------------------------------------------------ association strength
def test_association_matches_hand_computed_table(config):
    cfg = mini_config(config, ["Gender"])
    df = two_group_df(30, 10, 30, 20)           # 33.3% vs 66.7%: chi2 = 6.667, V = 1/3
    row = association_table(df, cfg, ["Gender"]).iloc[0]
    assert row["chi2"] == pytest.approx(6.667, abs=1e-3) and row["cramers_v"] == pytest.approx(1 / 3, abs=1e-4)
    assert row["effect"] == "medium" and row["groups"] == 2
    assert (row["highest_segment"], row["lowest_segment"]) == ("Male", "Female")
    assert row["spread_pp"] == pytest.approx(100 / 3)
    assert row["highest_status"] == "small sample"       # n = 30 is below the small-sample threshold


@pytest.mark.parametrize("value, expected", [(0.0, "negligible"), (0.0999, "negligible"), (0.10, "small"),
                                              (0.2999, "small"), (0.30, "medium"), (0.4999, "medium"),
                                              (0.50, "large"), (0.9, "large")])
def test_effect_label_boundaries(config, value, expected):
    a = config["analysis"]
    assert effect_label(value, a["effect_size_cutoffs"], a["effect_size_labels"]) == expected


def test_effect_label_for_missing_value(config):
    a = config["analysis"]
    assert effect_label(float("nan"), a["effect_size_cutoffs"], a["effect_size_labels"]) == "n/a"


def test_association_is_ranked_strongest_first(config):
    cfg = mini_config(config, ["Gender", "Geography"])
    strong = two_group_df(200, 20, 200, 120)
    strong["Geography"] = ["France", "Germany"] * 200      # unrelated to churn on purpose
    ranked = association_table(strong, cfg, ["Gender", "Geography"])
    assert list(ranked["variable"]) == ["Gender", "Geography"]
    assert ranked.loc[0, "cramers_v"] > ranked.loc[1, "cramers_v"]


def test_association_not_computable_with_a_single_group(config):
    cfg = mini_config(config, ["Gender"])
    df = two_group_df(50, 10, 0, 0)
    row = association_table(df, cfg, ["Gender"]).iloc[0]
    assert pd.isna(row["cramers_v"]) and "not computable" in row["note"] and row["effect"] == "n/a"


def test_association_with_nobody_churned_is_not_computable(config):
    cfg = mini_config(config, ["Gender"])
    row = association_table(two_group_df(50, 0, 50, 0), cfg, ["Gender"]).iloc[0]
    assert pd.isna(row["cramers_v"])


# ------------------------------------------------------------------ differences between two groups
def test_rate_difference_value_and_interval(config):
    df = two_group_df(100, 30, 100, 20)
    r = rate_difference(df, config, "Gender", "Female", "Male")
    assert r["diff_pp"] == pytest.approx(10.0)
    _, low, high = newcombe_difference_interval(30, 100, 20, 100)
    assert (r["ci_low_pp"], r["ci_high_pp"]) == pytest.approx((low * 100, high * 100)) and r["status"] == "ok"


def test_rate_difference_sign_flips_when_groups_are_swapped(config):
    df = two_group_df(100, 30, 100, 20)
    assert rate_difference(df, config, "Gender", "Male", "Female")["diff_pp"] == pytest.approx(-10.0)


def test_rate_difference_empty_and_tiny_groups(config):
    assert rate_difference(two_group_df(100, 30, 0, 0), config, "Gender", "Female", "Male")["status"].startswith("n/a")
    tiny = rate_difference(two_group_df(100, 30, 10, 2), config, "Gender", "Female", "Male")
    assert tiny["diff_pp"] is None and tiny["status"].startswith("withheld")


def test_gender_comparison_by_country(config):
    rows = []
    for country, (nf, cf, nm, cm) in {"France": (100, 30, 100, 20), "Germany": (60, 30, 60, 20), "Spain": (40, 10, 40, 10)}.items():
        part = two_group_df(nf, cf, nm, cm)
        part["Geography"] = country
        rows.append(part)
    df = pd.concat(rows, ignore_index=True)
    table = gender_comparison(df, config).set_index("scope")
    gap = "gap_pp (Female - Male)"
    assert table.loc["France", gap] == pytest.approx(10.0)
    assert table.loc["Germany", gap] == pytest.approx((30 / 60 - 20 / 60) * 100)
    assert table.loc["Spain", gap] == pytest.approx(0.0)
    assert list(table.index) == ["All customers", "France", "Germany", "Spain"]


# ------------------------------------------------------------------ two-variable drill-down
def test_interaction_table_cells_and_empty_combinations(config):
    cells = [("France", "Under 30", 40, 4), ("France", "30-45", 60, 30), ("Germany", "30-45", 50, 25),
             ("Spain", "Under 30", 20, 5), ("Spain", "30-45", 40, 8)]
    rows = [(g, a, int(i < c)) for g, a, n, c in cells for i in range(n)]
    df = pd.DataFrame(rows, columns=["Geography", "AgeBand", "Exited"])
    df["Geography"] = pd.Categorical(df["Geography"], categories=["France", "Germany", "Spain"])
    df["AgeBand"] = pd.Categorical(df["AgeBand"], categories=["Under 30", "30-45"], ordered=True)
    table = interaction_table(df, config, "Geography", "AgeBand").set_index(["Geography", "AgeBand"])
    assert table["n"].sum() == len(df) == 210
    assert table.loc[("France", "30-45"), "churn_rate"] == pytest.approx(0.5)
    germany_young = table.loc[("Germany", "Under 30")]
    assert germany_young["n"] == 0 and pd.isna(germany_young["churn_rate"]) and germany_young["status"].startswith("n/a")
    spain_young = table.loc[("Spain", "Under 30")]
    assert spain_young["n"] == 20 and pd.isna(spain_young["churn_rate"]) and "withheld" in spain_young["status"]
    assert table["churn_contribution"].sum() == pytest.approx(1.0)


# ------------------------------------------------------------------ churned vs retained profiles
def profile_df():
    return pd.DataFrame({"Gender": ["Female", "Female", "Male", "Female", "Male", "Male"],
                         "Age": [10, 12, 14, 8, 10, 12], "Exited": [1, 1, 1, 0, 0, 0]})


def test_profile_numeric_cohens_d(config):
    cfg = mini_config(config, ["Gender"], numeric=["Age"])
    numeric, _ = profile_comparison(profile_df(), cfg)
    row = numeric.iloc[0]
    assert (row["mean_churned"], row["mean_retained"]) == (12.0, 10.0)
    assert (row["median_churned"], row["median_retained"]) == (12.0, 10.0)
    assert row["cohens_d"] == pytest.approx(1.0)                 # (12 - 10) / pooled SD of 2
    assert row["d_ci_low"] < 1.0 < row["d_ci_high"] and row["effect"] == "large"


def test_profile_numeric_d_is_undefined_without_variation(config):
    cfg = mini_config(config, ["Gender"], numeric=["Age"])
    df = profile_df().assign(Age=7)
    assert pd.isna(profile_comparison(df, cfg)[0].iloc[0]["cohens_d"])


def test_profile_composition(config):
    cfg = mini_config(config, ["Gender"], numeric=["Age"])
    _, cat = profile_comparison(profile_df(), cfg)
    cat = cat.set_index("segment")
    assert cat.loc["Female", "pct_of_churned"] == pytest.approx(2 / 3) and cat.loc["Female", "pct_of_retained"] == pytest.approx(1 / 3)
    assert cat.loc["Female", "diff_pp"] == pytest.approx(100 / 3)
    assert cat["pct_of_churned"].sum() == pytest.approx(1.0) and cat["pct_of_retained"].sum() == pytest.approx(1.0)


# ------------------------------------------------------------------ everything together, on real data
@pytest.fixture(scope="module")
def real(raw_df, config):
    segmented, _ = add_segments(raw_df.drop(columns=["Surname"]), config)
    return segmented, raw_df, run_segment_analysis(segmented, config)


def test_run_analysis_does_not_modify_its_input(raw_df, config):
    segmented, _ = add_segments(raw_df.drop(columns=["Surname"]), config)
    before = segmented.copy()
    run_segment_analysis(segmented, config)
    pd.testing.assert_frame_equal(segmented, before)


def test_every_variable_accounts_for_every_customer(real, config):
    _, raw, result = real
    for variable in config["analysis"]["segment_variables"]:
        part = result.overview[result.overview["variable"] == variable]
        assert part["n"].sum() == 10000 and part["churned"].sum() == int(raw.Exited.sum())
        assert part["churn_contribution"].sum() == pytest.approx(1.0)
        assert part["share_of_customers"].sum() == pytest.approx(1.0)
        assert part["contribution_minus_share_pp"].sum() == pytest.approx(0.0, abs=1e-9)


def test_real_gender_rates_match_manual_calculation(real):
    _, raw, result = real
    table = result.overview[result.overview["variable"] == "Gender"].set_index("segment")
    for gender in ("Female", "Male"):
        assert table.loc[gender, "churn_rate"] == pytest.approx(raw[raw.Gender == gender].Exited.mean())
    gap = result.gender.iloc[0]["gap_pp (Female - Male)"]
    assert gap == pytest.approx((raw[raw.Gender == "Female"].Exited.mean() - raw[raw.Gender == "Male"].Exited.mean()) * 100)


def test_real_number_of_products_extremes_are_flagged(real):
    _, raw, result = real
    table = result.overview[result.overview["variable"] == "NumOfProducts"].set_index("segment")
    four = raw[raw.NumOfProducts == 4]
    assert (table.loc["4", "n"], table.loc["4", "churned"]) == (len(four), int(four.Exited.sum()))
    assert table.loc["4", "status"] == "small sample"            # fewer than 100 customers
    assert table.loc["4", "ci_low"] == pytest.approx(wilson_interval(len(four), len(four))[0])


@pytest.mark.parametrize("variable, column", [("AgeBand", None), ("NumOfProducts", "NumOfProducts"),
                                              ("IsActiveMember", "IsActiveMember"), ("Gender", "Gender")])
def test_real_cramers_v_matches_scipy_on_a_plain_crosstab(real, variable, column):
    segmented, raw, result = real
    if variable == "AgeBand":
        groups = pd.cut(raw.Age, [-np.inf, 30, 46, 61, np.inf], right=False)
    else:
        groups = raw[column]
    table = pd.crosstab(groups, raw.Exited)
    chi2, _, _, _ = stats.chi2_contingency(table, correction=False)
    expected_v = np.sqrt(chi2 / table.to_numpy().sum())
    got = result.association.set_index("variable").loc[variable, "cramers_v"]
    assert got == pytest.approx(expected_v)


def test_real_association_is_ranked_and_bounded(real):
    result = real[2].association
    v = result["cramers_v"].dropna()
    assert (v.between(0, 1)).all() and v.is_monotonic_decreasing
    assert set(result["variable"]) == set(real[2].overview["variable"])


def test_real_credit_score_sensitivity_has_both_groupings(real, config):
    result = real[2]
    assert set(result.credit_sensitivity_association["variable"]) == {"CreditScoreBand", config["analysis"]["sensitivity_variable"]}
    assert set(result.credit_sensitivity_overview["variable"]) == {"CreditScoreBand", "CreditScoreTercile"}


def test_real_geography_age_cells_match_manual_counts(real):
    _, raw, result = real
    cell = result.geography_age_all.set_index(["Geography", "AgeBand"]).loc[("Germany", "46-60")]
    manual = raw[(raw.Geography == "Germany") & (raw.Age.between(46, 60))]
    assert (cell["n"], cell["churned"]) == (len(manual), int(manual.Exited.sum()))
    assert result.geography_age_all["n"].sum() == 10000


def test_real_non_zero_balance_view_excludes_zero_balance_customers(real):
    _, raw, result = real
    assert result.geography_age_non_zero["n"].sum() == int((raw.Balance > 0).sum())


def test_real_geography_by_balance_shows_germany_zero_balance_as_empty(real):
    cells = real[2].geography_balance.set_index(["Geography", "BalanceSegment"])
    germany_zero = cells.loc[("Germany", "Zero-balance")]
    assert germany_zero["n"] == 0 and pd.isna(germany_zero["churn_rate"]) and germany_zero["status"].startswith("n/a")


def test_real_age_effect_size_matches_independent_formula(real):
    _, raw, result = real
    churned, retained = raw[raw.Exited == 1].Age.to_numpy(float), raw[raw.Exited == 0].Age.to_numpy(float)
    n1, n2 = len(churned), len(retained)
    pooled = np.sqrt(((n1 - 1) * churned.var(ddof=1) + (n2 - 1) * retained.var(ddof=1)) / (n1 + n2 - 2))
    expected = (churned.mean() - retained.mean()) / pooled
    row = result.profile_numeric.set_index("column").loc["Age"]
    assert row["cohens_d"] == pytest.approx(expected) and expected > 0


def test_analysis_is_deterministic(raw_df, config):
    segmented, _ = add_segments(raw_df.drop(columns=["Surname"]), config)
    a, b = run_segment_analysis(segmented, config), run_segment_analysis(segmented, config)
    pd.testing.assert_frame_equal(a.overview, b.overview)
    pd.testing.assert_frame_equal(a.association, b.association)
