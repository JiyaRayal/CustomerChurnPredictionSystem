"""Tests for the KPI functions.

HAND-COMPUTED FIXTURE (200 customers) - every expected value below can be checked on paper:

    Geography   customers  churned  churn rate   contribution (of 60 churners)
    France      100        20       20%          20/60
    Germany      60        30       50%          30/60
    Spain        40        10       25%          10/60            overall churn = 60/200 = 30%

    Engagement  inactive: 100 customers, 40 churned (40%)   active: 100 customers, 20 churned (20%)  -> +20 pp
    Balance     High-balance: 80 customers, 32 churned (40%)   balances: High 100,000 / Low 10,000 / Zero 0
"""

import copy

import numpy as np
import pandas as pd
import pytest

from churn_analytics import kpis
from churn_analytics.kpis import KPIError
from churn_analytics.segmentation import add_segments
from churn_analytics.stats_utils import newcombe_difference_interval, wilson_interval


def build_fixture():
    geo = ["France"] * 100 + ["Germany"] * 60 + ["Spain"] * 40
    exited = np.array([1] * 20 + [0] * 80 + [1] * 30 + [0] * 30 + [1] * 10 + [0] * 30)
    active = np.zeros(200, dtype=int)
    segment = np.empty(200, dtype=object)
    churned_idx, kept_idx = np.where(exited == 1)[0], np.where(exited == 0)[0]
    active[churned_idx[40:]] = 1                       # 20 of 60 churners are active
    active[kept_idx[60:]] = 1                          # 80 of 140 non-churners are active
    for idx, labels in ((churned_idx, [("High-balance", 32), ("Low-balance", 18), ("Zero-balance", 10)]),
                        (kept_idx, [("High-balance", 48), ("Low-balance", 52), ("Zero-balance", 40)])):
        start = 0
        for label, count in labels:
            segment[idx[start:start + count]] = label
            start += count
    balance = pd.Series(segment).map({"High-balance": 100000.0, "Low-balance": 10000.0, "Zero-balance": 0.0})
    return pd.DataFrame({"Geography": geo, "IsActiveMember": active, "BalanceSegment": segment,
                         "Balance": balance.to_numpy(), "Exited": exited})


@pytest.fixture()
def df():
    return build_fixture()


# ------------------------------------------------------------------ fixture sanity
def test_fixture_matches_the_documented_hand_numbers(df):
    assert df.groupby("Geography").Exited.sum().to_dict() == {"France": 20, "Germany": 30, "Spain": 10}
    assert df.groupby("IsActiveMember").Exited.agg(["sum", "size"]).values.tolist() == [[40, 100], [20, 100]]
    high = df[df.BalanceSegment == "High-balance"]
    assert (len(high), high.Exited.sum()) == (80, 32)


# ------------------------------------------------------------------ input checks
def test_invalid_target_values_are_refused(df):
    df.loc[0, "Exited"] = 2
    with pytest.raises(KPIError, match="only 0 and 1"):
        kpis.overall_churn_rate(df, load())


def test_missing_target_values_are_refused(df):
    df["Exited"] = df["Exited"].astype(float)
    df.loc[0, "Exited"] = np.nan
    with pytest.raises(KPIError, match="missing"):
        kpis.overall_churn_rate(df, load())


def test_missing_target_column_is_refused(df):
    with pytest.raises(KPIError, match="Missing column"):
        kpis.overall_churn_rate(df.drop(columns=["Exited"]), load())


def load():
    from churn_analytics.config import load_config
    return load_config()


@pytest.fixture()
def cfg(config):
    return config


# ------------------------------------------------------------------ 1. overall churn rate
def test_overall_churn_rate(df, cfg):
    result = kpis.overall_churn_rate(df, cfg)
    assert (result["n"], result["events"]) == (200, 60)
    assert result["rate"] == pytest.approx(0.30)
    assert (result["ci_low"], result["ci_high"]) == pytest.approx(wilson_interval(60, 200))
    assert result["status"] == "ok"


def test_overall_churn_rate_of_no_customers_is_undefined_not_zero(df, cfg):
    result = kpis.overall_churn_rate(df.iloc[0:0], cfg)
    assert result["rate"] is None and result["status"].startswith("n/a") and result["n"] == 0


def test_overall_rate_is_withheld_for_a_tiny_selection(df, cfg):
    result = kpis.overall_churn_rate(df.iloc[:10], cfg)
    assert result["rate"] is None and result["n"] == 10 and result["status"].startswith("withheld")


def test_zero_percent_overall_is_a_real_rate(df, cfg):
    df["Exited"] = 0
    result = kpis.overall_churn_rate(df, cfg)
    assert result["rate"] == 0.0 and result["status"] == "ok"


# ------------------------------------------------------------------ 2+3. segment rate and contribution
def test_segment_churn_rates_and_contributions(df, cfg):
    table = kpis.segment_churn_table(df, "Geography", cfg).set_index("Geography")
    assert table["n"].to_dict() == {"France": 100, "Germany": 60, "Spain": 40}
    assert table["churn_rate"].to_dict() == pytest.approx({"France": 0.20, "Germany": 0.50, "Spain": 0.25})
    assert table["churn_contribution"].to_dict() == pytest.approx(
        {"France": 20 / 60, "Germany": 30 / 60, "Spain": 10 / 60})
    assert table["share_of_customers"].to_dict() == pytest.approx({"France": 0.5, "Germany": 0.3, "Spain": 0.2})


def test_contributions_and_shares_add_up_to_100_percent(df, cfg):
    for column in ("Geography", "IsActiveMember", "BalanceSegment"):
        table = kpis.segment_churn_table(df, column, cfg)
        assert table["churn_contribution"].sum() == pytest.approx(1.0)
        assert table["share_of_customers"].sum() == pytest.approx(1.0)
        assert table["n"].sum() == 200


def test_drill_down_on_two_columns_keeps_every_customer(df, cfg):
    table = kpis.segment_churn_table(df, ["Geography", "IsActiveMember"], cfg)
    assert table["n"].sum() == 200 and table["churned"].sum() == 60
    assert table["churn_contribution"].sum() == pytest.approx(1.0)


def test_empty_category_is_kept_with_undefined_rate(df, cfg):
    df["Geography"] = pd.Categorical(df["Geography"], categories=["France", "Germany", "Spain", "Italy"])
    table = kpis.segment_churn_table(df, "Geography", cfg).set_index("Geography")
    assert table.loc["Italy", "n"] == 0
    assert pd.isna(table.loc["Italy", "churn_rate"]) and table.loc["Italy", "status"].startswith("n/a")


def test_customers_with_missing_segment_are_not_silently_dropped(df, cfg):
    df.loc[0, "Geography"] = np.nan
    table = kpis.segment_churn_table(df, "Geography", cfg)
    assert table["n"].sum() == 200 and table["Geography"].isna().sum() == 1


def test_no_churners_means_contribution_is_undefined(df, cfg):
    df["Exited"] = 0
    table = kpis.segment_churn_table(df, "Geography", cfg)
    assert table["churn_contribution"].isna().all() and (table["churn_rate"] == 0).all()


def test_segment_table_does_not_modify_input(df, cfg):
    before = df.copy()
    kpis.segment_churn_table(df, ["Geography", "BalanceSegment"], cfg)
    pd.testing.assert_frame_equal(df, before)


def test_contributions_are_relative_to_the_rows_passed_in(df, cfg):
    germany = df[df.Geography == "Germany"]
    table = kpis.segment_churn_table(germany, "IsActiveMember", cfg)
    assert table["churn_contribution"].sum() == pytest.approx(1.0)
    assert table["n"].sum() == 60


# ------------------------------------------------------------------ 4. geographic risk index
def test_geographic_risk_index_values(df, cfg):
    table = kpis.geographic_risk_index(df, cfg).set_index("Geography")
    assert table["risk_index"].to_dict() == pytest.approx(
        {"France": 0.20 / 0.30, "Germany": 0.50 / 0.30, "Spain": 0.25 / 0.30})
    assert (table["overall_rate"] == 0.30).all()


def test_risk_index_interval_is_country_interval_divided_by_overall_rate(df, cfg):
    row = kpis.geographic_risk_index(df, cfg).set_index("Geography").loc["Germany"]
    low, high = wilson_interval(30, 60)
    assert row["index_ci_low"] == pytest.approx(low / 0.30) and row["index_ci_high"] == pytest.approx(high / 0.30)


def test_risk_index_is_undefined_when_overall_churn_is_zero(df, cfg):
    df["Exited"] = 0
    table = kpis.geographic_risk_index(df, cfg)
    assert table["risk_index"].isna().all()
    assert (table["index_note"] == "n/a (overall churn rate is 0)").all()


def test_country_without_customers_gets_an_undefined_index(df, cfg):
    table = kpis.geographic_risk_index(df[df.Geography != "Spain"], cfg).set_index("Geography")
    assert table.loc["Spain", "n"] == 0 and pd.isna(table.loc["Spain", "risk_index"])
    assert "empty" in table.loc["Spain", "index_note"]
    assert table.loc["France", "risk_index"] > 0       # the others are unaffected
    assert list(table.index) == ["France", "Germany", "Spain"]   # all configured countries stay in the table


def test_country_below_minimum_size_has_no_index(df, cfg):
    small_spain = pd.concat([df[df.Geography != "Spain"], df[df.Geography == "Spain"].head(20)])
    row = kpis.geographic_risk_index(small_spain, cfg).set_index("Geography").loc["Spain"]
    assert row["n"] == 20 and pd.isna(row["risk_index"]) and "withheld" in row["index_note"]


def test_risk_index_unavailable_when_overall_rate_is_withheld(df, cfg):
    table = kpis.geographic_risk_index(df.head(10), cfg)
    assert table["risk_index"].isna().all()
    assert (table["index_note"] == "n/a (overall rate unavailable)").all()


def test_risk_index_on_a_subset_uses_the_subsets_own_overall_rate(df, cfg):
    subset = df[df.IsActiveMember == 0]   # 100 customers, 40 churned -> overall 40%; France 80, Germany 20, Spain 0
    table = kpis.geographic_risk_index(subset, cfg).set_index("Geography")
    assert table["overall_rate"].to_numpy() == pytest.approx([0.40, 0.40, 0.40])
    assert table.loc["France", "n"] == 80 and table.loc["France", "risk_index"] == pytest.approx(0.25 / 0.40)
    assert pd.isna(table.loc["Germany", "risk_index"]) and "withheld" in table.loc["Germany", "index_note"]  # n = 20
    assert pd.isna(table.loc["Spain", "risk_index"]) and "empty" in table.loc["Spain", "index_note"]        # n = 0


def test_customer_weighted_average_of_the_risk_index_is_exactly_one(df, cfg):
    # sum(rate_g / overall * n_g / N) = (total churned / N) / overall = 1 whenever every group has an index
    table = kpis.geographic_risk_index(df, cfg)
    assert (table["risk_index"] * table["share_of_customers"]).sum() == pytest.approx(1.0)


# ------------------------------------------------------------------ 5. engagement drop indicator
def test_engagement_drop_indicator_value_and_interval(df, cfg):
    result = kpis.engagement_drop_indicator(df, cfg)
    assert result["edi_pp"] == pytest.approx(20.0)
    assert result["inactive"]["rate"] == pytest.approx(0.40) and result["active"]["rate"] == pytest.approx(0.20)
    _, low, high = newcombe_difference_interval(40, 100, 20, 100)
    assert (result["ci_low_pp"], result["ci_high_pp"]) == pytest.approx((low * 100, high * 100))
    assert result["ci_low_pp"] < 20.0 < result["ci_high_pp"] and result["status"] == "ok"


def test_engagement_drop_sign_follows_inactive_minus_active(df, cfg):
    flipped = df.assign(IsActiveMember=1 - df["IsActiveMember"])
    assert kpis.engagement_drop_indicator(flipped, cfg)["edi_pp"] == pytest.approx(-20.0)


def test_engagement_drop_is_undefined_without_inactive_members(df, cfg):
    result = kpis.engagement_drop_indicator(df.assign(IsActiveMember=1), cfg)
    assert result["edi_pp"] is None and result["status"].startswith("n/a")


def test_engagement_drop_withheld_when_a_group_is_tiny(df, cfg):
    tiny = pd.concat([df[df.IsActiveMember == 1], df[df.IsActiveMember == 0].head(10)])
    result = kpis.engagement_drop_indicator(tiny, cfg)
    assert result["edi_pp"] is None and result["status"].startswith("withheld")


def test_engagement_drop_flags_small_samples(df, cfg):
    small = pd.concat([df[df.IsActiveMember == 1], df[df.IsActiveMember == 0].head(50)])
    result = kpis.engagement_drop_indicator(small, cfg)
    assert result["edi_pp"] is not None and result["status"] == "small sample"


def test_engagement_column_must_be_binary(df, cfg):
    df.loc[0, "IsActiveMember"] = 3
    with pytest.raises(KPIError, match="0/1"):
        kpis.engagement_drop_indicator(df, cfg)


def test_engagement_column_comes_from_the_config(df, cfg):
    cfg2 = copy.deepcopy(cfg)
    cfg2["kpi"]["engagement_column"] = "HasCrCard"
    df["HasCrCard"] = [0, 1] * 100
    result = kpis.engagement_drop_indicator(df, cfg2)
    assert result["inactive"]["n"] == 100 and result["edi_pp"] != pytest.approx(20.0)


# ------------------------------------------------------------------ 6. high-balance churn rate + exposure
def test_high_balance_churn_rate(df, cfg):
    result = kpis.high_balance_churn_rate(df, cfg)
    assert (result["n"], result["events"]) == (80, 32)
    assert result["rate"] == pytest.approx(0.40)
    assert result["share_of_customers"] == pytest.approx(0.40)
    assert result["churn_contribution"] == pytest.approx(32 / 60)
    assert result["churned_balance"] == pytest.approx(3_200_000) and result["segment_balance"] == pytest.approx(8_000_000)


def test_high_balance_label_comes_from_the_config(df, cfg):
    cfg2 = copy.deepcopy(cfg)
    cfg2["segmentation"]["balance"]["high_label"] = "Low-balance"
    assert kpis.high_balance_churn_rate(df, cfg2)["n"] == 70


def test_no_high_balance_customers_gives_an_undefined_rate(df, cfg):
    result = kpis.high_balance_churn_rate(df[df.BalanceSegment != "High-balance"], cfg)
    assert result["n"] == 0 and result["rate"] is None and result["status"].startswith("n/a")


def test_high_balance_needs_the_derived_segment_column(df, cfg):
    with pytest.raises(KPIError, match="Phase 2 pipeline"):
        kpis.high_balance_churn_rate(df.drop(columns=["BalanceSegment"]), cfg)


def test_balance_exposure_overall(df, cfg):
    row = kpis.balance_exposure(df, cfg).iloc[0]
    assert row["churned_balance"] == pytest.approx(3_380_000) and row["segment_balance"] == pytest.approx(8_700_000)
    assert row["churned_share_of_segment_balance"] == pytest.approx(3_380_000 / 8_700_000)
    assert row["share_of_all_churned_balance"] == pytest.approx(1.0)


def test_balance_exposure_by_segment(df, cfg):
    table = kpis.balance_exposure(df, cfg, by="BalanceSegment").set_index("BalanceSegment")
    assert table.loc["High-balance", "churned_balance"] == pytest.approx(3_200_000)
    assert table.loc["High-balance", "churned_share_of_segment_balance"] == pytest.approx(0.40)
    assert table.loc["High-balance", "share_of_all_churned_balance"] == pytest.approx(3_200_000 / 3_380_000)
    assert pd.isna(table.loc["Zero-balance", "churned_share_of_segment_balance"])   # 0 / 0 is undefined
    assert table["share_of_all_churned_balance"].sum() == pytest.approx(1.0)


def test_balance_exposure_refuses_missing_balances(df, cfg):
    df.loc[0, "Balance"] = np.nan
    with pytest.raises(KPIError, match="missing"):
        kpis.balance_exposure(df, cfg)


# ------------------------------------------------------------------ real data, cross-checked with plain pandas
@pytest.fixture(scope="module")
def real(raw_df, config):
    segmented, meta = add_segments(raw_df.drop(columns=["Surname"]), config)
    return segmented, raw_df


def test_real_overall_churn_rate(real, config):
    segmented, raw = real
    result = kpis.overall_churn_rate(segmented, config)
    assert (result["events"], result["n"]) == (int(raw.Exited.sum()), 10000) == (2037, 10000)


def test_real_geographic_risk_index_matches_manual_division(real, config):
    segmented, raw = real
    table = kpis.geographic_risk_index(segmented, config).set_index("Geography")
    overall = raw.Exited.mean()
    for country in ("France", "Germany", "Spain"):
        assert table.loc[country, "risk_index"] == pytest.approx(raw[raw.Geography == country].Exited.mean() / overall)
    assert table["churn_contribution"].sum() == pytest.approx(1.0)


def test_real_non_zero_balance_risk_index_recomputes_overall(real, config):
    segmented, raw = real
    nz = raw[raw.Balance > 0]
    table = kpis.geographic_risk_index(segmented[segmented.Balance > 0], config).set_index("Geography")
    assert table.loc["Germany", "overall_rate"] == pytest.approx(nz.Exited.mean())
    assert table.loc["Germany", "risk_index"] == pytest.approx(
        nz[nz.Geography == "Germany"].Exited.mean() / nz.Exited.mean())


def test_real_engagement_drop_matches_manual_difference(real, config):
    segmented, raw = real
    manual = (raw[raw.IsActiveMember == 0].Exited.mean() - raw[raw.IsActiveMember == 1].Exited.mean()) * 100
    result = kpis.engagement_drop_indicator(segmented, config)
    assert result["edi_pp"] == pytest.approx(manual) and manual > 0
    assert result["ci_low_pp"] < result["edi_pp"] < result["ci_high_pp"]


def test_real_high_balance_churn_matches_independent_threshold(real, config):
    segmented, raw = real
    threshold = raw.loc[raw.Balance > 0, "Balance"].median()
    high = raw[raw.Balance > threshold]
    result = kpis.high_balance_churn_rate(segmented, config)
    assert (result["n"], result["events"]) == (len(high), int(high.Exited.sum()))
    assert result["churned_balance"] == pytest.approx(high.loc[high.Exited == 1, "Balance"].sum())
    assert result["churn_contribution"] == pytest.approx(high.Exited.sum() / raw.Exited.sum())


def test_real_total_churned_balance_matches_manual_sum(real, config):
    segmented, raw = real
    row = kpis.balance_exposure(segmented, config).iloc[0]
    assert row["churned_balance"] == pytest.approx(raw.loc[raw.Exited == 1, "Balance"].sum())
    assert row["segment_balance"] == pytest.approx(raw.Balance.sum())
