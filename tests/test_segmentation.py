"""Tests for segment assignment: boundaries, balance rule, config-driven thresholds."""

import copy

import numpy as np
import pandas as pd
import pytest

from churn_analytics.segmentation import (AGE_BAND, BALANCE_SEGMENT, CREDIT_BAND, CREDIT_TERCILE,
                                          DERIVED_COLUMNS, TENURE_GROUP, SegmentationError,
                                          add_segments, assign_balance_segment, assign_binned_segment,
                                          assign_quantile_segment, compute_balance_threshold,
                                          compute_quantile_cutpoints, segment_category_orders)


def labels_for(config, name, values):
    seg = config["segmentation"][name]
    series = pd.Series(values, name=name)
    return assign_binned_segment(series, seg["lower_bounds"], seg["labels"]).astype(str).tolist()


# ------------------------------------------------ approved intervals, tested at every edge
def test_age_bands_at_every_boundary(config):
    ages = [18, 29, 30, 45, 46, 60, 61, 92]
    expected = ["Under 30", "Under 30", "30-45", "30-45", "46-60", "46-60", "61+", "61+"]
    assert labels_for(config, "age", ages) == expected


def test_credit_bands_at_every_boundary(config):
    scores = [350, 579, 580, 739, 740, 850]
    assert labels_for(config, "credit_score", scores) == ["Low", "Low", "Medium", "Medium", "High", "High"]


def test_tenure_groups_at_every_boundary(config):
    years = [0, 2, 3, 7, 8, 10]
    assert labels_for(config, "tenure", years) == ["New", "New", "Mid-term", "Mid-term", "Long-term", "Long-term"]


def test_age_60_belongs_only_to_46_60(config):
    assert labels_for(config, "age", [60]) == ["46-60"]  # the overlap in the brief is fixed


def test_extreme_values_still_get_a_label_validation_flags_them_instead(config):
    assert labels_for(config, "age", [5, 150]) == ["Under 30", "61+"]


def test_every_integer_age_gets_exactly_one_label(config):
    result = assign_binned_segment(pd.Series(range(0, 121), name="Age"),
                                   config["segmentation"]["age"]["lower_bounds"],
                                   config["segmentation"]["age"]["labels"])
    assert result.notna().all()
    assert result.dtype.name == "category" and result.cat.ordered


def test_missing_value_raises_instead_of_silent_label(config):
    seg = config["segmentation"]["age"]
    with pytest.raises(SegmentationError, match="missing"):
        assign_binned_segment(pd.Series([30.0, np.nan], name="Age"), seg["lower_bounds"], seg["labels"])


def test_thresholds_come_from_config_not_code(config):
    cfg = copy.deepcopy(config)
    cfg["segmentation"]["age"]["lower_bounds"] = [25, 50, 70]
    assert labels_for(cfg, "age", [24, 25, 49, 50, 69, 70]) == \
        ["Under 30", "30-45", "30-45", "46-60", "46-60", "61+"]  # labels unchanged, boundaries moved


# ------------------------------------------------ balance rule
def test_threshold_is_median_of_nonzero_balances_only():
    balance = pd.Series([0, 0, 0, 10, 20, 30], name="Balance", dtype=float)
    assert compute_balance_threshold(balance) == 20.0  # including zeros the median would be 5


def test_balance_segments_zero_low_high_and_tie_goes_to_low():
    balance = pd.Series([0.0, 5.0, 20.0, 20.01, 100.0], name="Balance")
    out = assign_balance_segment(balance, 20.0, "Zero", "Low", "High").astype(str).tolist()
    assert out == ["Zero", "Low", "Low", "High", "High"]  # exactly the threshold -> Low (<=)


def test_negative_balance_raises_because_the_rule_does_not_cover_it():
    with pytest.raises(SegmentationError, match="negative"):
        compute_balance_threshold(pd.Series([-1.0, 5.0], name="Balance"))
    with pytest.raises(SegmentationError, match="negative"):
        assign_balance_segment(pd.Series([-1.0, 5.0], name="Balance"), 3.0, "Z", "L", "H")


def test_all_zero_balances_cannot_define_a_threshold():
    with pytest.raises(SegmentationError, match="no non-zero"):
        compute_balance_threshold(pd.Series([0.0, 0.0], name="Balance"))


def test_missing_balance_raises():
    with pytest.raises(SegmentationError, match="missing"):
        compute_balance_threshold(pd.Series([np.nan, 5.0], name="Balance"))


# ------------------------------------------------ tercile sensitivity grouping
def test_tercile_groups_are_roughly_equal():
    scores = pd.Series(range(1, 301), name="CreditScore")
    cuts = compute_quantile_cutpoints(scores, 3)
    groups = assign_quantile_segment(scores, cuts, ["a", "b", "c"]).value_counts()
    assert groups.max() - groups.min() <= 2


def test_non_distinct_cutpoints_raise():
    with pytest.raises(SegmentationError, match="not distinct"):
        compute_quantile_cutpoints(pd.Series([5] * 50, name="CreditScore"), 3)


# ------------------------------------------------ add_segments on a whole frame
def test_add_segments_adds_all_columns_without_touching_input(valid_df, config):
    before = valid_df.copy()
    out, meta = add_segments(valid_df, config)
    pd.testing.assert_frame_equal(valid_df, before)           # input untouched
    assert set(DERIVED_COLUMNS) <= set(out.columns)
    assert len(out) == len(valid_df)
    assert out[list(DERIVED_COLUMNS)].notna().all().all()      # every row has every label


def test_metadata_records_what_was_used(valid_df, config):
    out, meta = add_segments(valid_df, config)
    expected = valid_df.loc[valid_df["Balance"] > 0, "Balance"].median()
    assert meta["balance_threshold_median_of_nonzero"] == pytest.approx(expected)
    assert len(meta["credit_score_tercile_cutpoints"]) == 2


def test_segment_sizes_sum_to_total_for_each_variable(valid_df, config):
    _, meta = add_segments(valid_df, config)
    sizes = pd.DataFrame(meta["segment_sizes"])
    assert (sizes.groupby("segment_variable")["n"].sum() == len(valid_df)).all()


def test_category_orders_cover_every_categorical_column(config):
    orders = segment_category_orders(config)
    assert set(DERIVED_COLUMNS) | {"Geography", "Gender"} == set(orders)
    assert orders[AGE_BAND] == ["Under 30", "30-45", "46-60", "61+"]


# ------------------------------------------------ real data, checked independently with plain pandas
def test_real_segments_agree_with_independent_counts(raw_df, config):
    out, meta = add_segments(raw_df.drop(columns=["Surname"]), config)
    assert (out[AGE_BAND] == "Under 30").sum() == (raw_df.Age < 30).sum()
    assert (out[AGE_BAND] == "61+").sum() == (raw_df.Age >= 61).sum()
    assert (out[CREDIT_BAND] == "Low").sum() == (raw_df.CreditScore < 580).sum()
    assert (out[CREDIT_BAND] == "High").sum() == (raw_df.CreditScore >= 740).sum()
    assert (out[TENURE_GROUP] == "New").sum() == (raw_df.Tenure <= 2).sum()
    assert (out[TENURE_GROUP] == "Long-term").sum() == (raw_df.Tenure >= 8).sum()
    assert (out[BALANCE_SEGMENT] == "Zero-balance").sum() == (raw_df.Balance == 0).sum()
    t = raw_df.loc[raw_df.Balance > 0, "Balance"].median()
    assert meta["balance_threshold_median_of_nonzero"] == pytest.approx(t)
    assert (out[BALANCE_SEGMENT] == "High-balance").sum() == (raw_df.Balance > t).sum()
    assert out[CREDIT_TERCILE].notna().all()
