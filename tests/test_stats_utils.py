"""Tests for the Wilson interval, group-size rules and chi-square helper."""

import copy

import pandas as pd
import pytest

from churn_analytics.stats_utils import (STATUS_EMPTY, STATUS_OK, STATUS_SMALL, STATUS_WITHHELD,
                                         chi_square_independence, proportion_summary, wilson_interval)


def test_wilson_matches_known_values():
    low, high = wilson_interval(50, 100)
    assert low == pytest.approx(0.4038, abs=1e-3)
    assert high == pytest.approx(0.5962, abs=1e-3)


def test_wilson_zero_events_has_zero_lower_bound():
    low, high = wilson_interval(0, 10)
    assert low == 0.0
    assert high == pytest.approx(0.2775, abs=1e-3)


def test_wilson_all_events_has_upper_bound_one():
    # Mathematically exactly 1; computers return 0.9999999999999999, so compare with a tolerance.
    assert wilson_interval(10, 10)[1] == pytest.approx(1.0, abs=1e-12)


@pytest.mark.parametrize("events, n", [(1, 10), (20, 100), (205, 1000), (2037, 10000)])
def test_wilson_interval_contains_the_observed_rate(events, n):
    low, high = wilson_interval(events, n)
    assert 0 <= low <= events / n <= high <= 1


def test_smaller_groups_have_wider_intervals():
    small = wilson_interval(10, 50)
    large = wilson_interval(200, 1000)
    assert (small[1] - small[0]) > (large[1] - large[0])


def test_wilson_rejects_invalid_input():
    with pytest.raises(ValueError):
        wilson_interval(0, 0)
    with pytest.raises(ValueError):
        wilson_interval(11, 10)
    with pytest.raises(ValueError):
        wilson_interval(5, 10, confidence_level=95)


def test_empty_group_is_undefined_not_zero(config):
    s = proportion_summary(0, 0, config)
    assert s["rate"] is None and s["status"] == STATUS_EMPTY and s["n"] == 0


def test_tiny_group_rate_is_withheld_but_counts_are_kept(config):
    s = proportion_summary(3, 10, config)
    assert s["rate"] is None and s["status"] == STATUS_WITHHELD
    assert (s["n"], s["events"]) == (10, 3)


def test_small_group_is_flagged_but_reported(config):
    s = proportion_summary(10, 50, config)
    assert s["status"] == STATUS_SMALL and s["rate"] == pytest.approx(0.2)
    assert s["ci_low"] is not None


def test_large_group_is_ok(config):
    assert proportion_summary(200, 1000, config)["status"] == STATUS_OK


def test_zero_percent_is_a_real_rate_not_undefined(config):
    s = proportion_summary(0, 500, config)
    assert s["rate"] == 0.0 and s["status"] == STATUS_OK


def test_group_size_rules_come_from_config(config):
    cfg = copy.deepcopy(config)
    cfg["statistics"]["min_reportable_group_size"] = 5
    assert proportion_summary(3, 10, cfg)["rate"] == pytest.approx(0.3)


def test_chi_square_known_table():
    result = chi_square_independence(pd.DataFrame([[10, 20], [20, 10]]))
    assert result["chi2"] == pytest.approx(6.667, abs=1e-3)
    assert result["cramers_v"] == pytest.approx(1 / 3, abs=1e-3)
    assert result["n"] == 60 and result["dof"] == 1


def test_chi_square_independent_variables_have_zero_effect_size():
    result = chi_square_independence(pd.DataFrame([[25, 25], [25, 25]]))
    assert result["cramers_v"] == pytest.approx(0.0, abs=1e-9)
    assert result["p_value"] == pytest.approx(1.0)


def test_chi_square_perfect_association():
    assert chi_square_independence(pd.DataFrame([[50, 0], [0, 50]]))["cramers_v"] == pytest.approx(1.0)


def test_chi_square_rejects_bad_tables():
    with pytest.raises(ValueError):
        chi_square_independence(pd.DataFrame([[1, 2, 3]]))
    with pytest.raises(ValueError):
        chi_square_independence(pd.DataFrame([[0, 0], [0, 0]]))


# --- Newcombe interval for the difference of two proportions (Phase 3) ------------------
from churn_analytics.stats_utils import newcombe_difference_interval  # noqa: E402


def test_newcombe_matches_published_example():
    # Newcombe (1998), Statistics in Medicine: 56/70 vs 48/80, hybrid score method.
    # Published values as I recall them from the paper (not re-checked against it): 0.2000, 0.0524 to 0.3339.
    diff, low, high = newcombe_difference_interval(56, 70, 48, 80)
    assert diff == pytest.approx(0.2000, abs=1e-4)
    assert low == pytest.approx(0.0524, abs=1e-4)
    assert high == pytest.approx(0.3339, abs=1e-4)


def test_newcombe_swapping_groups_flips_the_sign_and_the_interval():
    d1, l1, h1 = newcombe_difference_interval(56, 70, 48, 80)
    d2, l2, h2 = newcombe_difference_interval(48, 80, 56, 70)
    assert (d2, l2, h2) == pytest.approx((-d1, -h1, -l1))


def test_newcombe_identical_groups_give_an_interval_around_zero():
    diff, low, high = newcombe_difference_interval(20, 100, 20, 100)
    assert diff == 0 and low < 0 < high and low == pytest.approx(-high)


def test_newcombe_stays_within_minus_one_and_plus_one_at_extremes():
    diff, low, high = newcombe_difference_interval(100, 100, 0, 100)
    assert diff == 1.0 and -1 <= low <= high <= 1.0 + 1e-12


def test_newcombe_is_wider_for_smaller_groups():
    _, l_small, h_small = newcombe_difference_interval(8, 20, 4, 20)
    _, l_big, h_big = newcombe_difference_interval(400, 1000, 200, 1000)
    assert (h_small - l_small) > (h_big - l_big)


def test_newcombe_rejects_empty_groups():
    with pytest.raises(ValueError):
        newcombe_difference_interval(0, 0, 5, 10)
