"""Tests for config/segmentation.toml and its validator."""

import copy
from bisect import bisect_right

import pytest

from churn_analytics.config import ConfigError, load_config, validate_config


@pytest.fixture()
def config():
    return load_config()


def _label(config, name, value):
    """Look up which configured bin a value falls in (left-closed bins)."""
    seg = config["segmentation"][name]
    return seg["labels"][bisect_right(seg["lower_bounds"], value)]


def test_default_config_loads_and_validates(config):
    validate_config(config)  # should not raise


# --- the approved interval boundaries, tested at the edges -----------------------------
@pytest.mark.parametrize(
    "age, expected",
    [(18, "Under 30"), (29, "Under 30"), (30, "30-45"), (45, "30-45"),
     (46, "46-60"), (60, "46-60"), (61, "61+"), (92, "61+")],
)
def test_age_boundaries_do_not_overlap_or_leave_gaps(config, age, expected):
    assert _label(config, "age", age) == expected


@pytest.mark.parametrize(
    "score, expected",
    [(350, "Low"), (579, "Low"), (580, "Medium"), (739, "Medium"), (740, "High"), (850, "High")],
)
def test_credit_score_boundaries(config, score, expected):
    assert _label(config, "credit_score", score) == expected


@pytest.mark.parametrize(
    "years, expected",
    [(0, "New"), (2, "New"), (3, "Mid-term"), (7, "Mid-term"), (8, "Long-term"), (10, "Long-term")],
)
def test_tenure_boundaries(config, years, expected):
    assert _label(config, "tenure", years) == expected


def test_every_integer_age_maps_to_exactly_one_known_label(config):
    labels = set(config["segmentation"]["age"]["labels"])
    assert {_label(config, "age", a) for a in range(0, 121)} == labels


# --- the validator must reject bad edits -----------------------------------------------
def _broken(config, mutate):
    bad = copy.deepcopy(config)
    mutate(bad)
    return bad


def test_rejects_wrong_label_count(config):
    bad = _broken(config, lambda c: c["segmentation"]["age"]["labels"].pop())
    with pytest.raises(ConfigError, match="labels"):
        validate_config(bad)


def test_rejects_bounds_not_increasing(config):
    bad = _broken(config, lambda c: c["segmentation"]["age"].update(lower_bounds=[46, 30, 61]))
    with pytest.raises(ConfigError, match="strictly increasing"):
        validate_config(bad)


def test_rejects_duplicate_bounds(config):
    bad = _broken(config, lambda c: c["segmentation"]["tenure"].update(lower_bounds=[3, 3]))
    with pytest.raises(ConfigError, match="strictly increasing"):
        validate_config(bad)


def test_rejects_percentage_style_confidence_level(config):
    bad = _broken(config, lambda c: c["statistics"].update(confidence_level=95))
    with pytest.raises(ConfigError, match="confidence_level"):
        validate_config(bad)


def test_rejects_min_group_size_above_small_threshold(config):
    bad = _broken(config, lambda c: c["statistics"].update(min_reportable_group_size=500))
    with pytest.raises(ConfigError, match="min_reportable_group_size"):
        validate_config(bad)


def test_target_cannot_be_excluded_from_features(config):
    bad = _broken(config, lambda c: c["columns"]["excluded_from_features"].append("Exited"))
    with pytest.raises(ConfigError, match="target"):
        validate_config(bad)


def test_missing_config_file_gives_clear_error(tmp_path):
    with pytest.raises(ConfigError, match="not found"):
        load_config(tmp_path / "nope.toml")


# --- Phase 2 additions: schema, cross-references and plausibility bounds ---------------
def test_rejects_column_listed_in_two_dtype_groups(config):
    bad = _broken(config, lambda c: c["schema"]["float_columns"].append("Age"))
    with pytest.raises(ConfigError, match="more than one dtype group"):
        validate_config(bad)


def test_rejects_dtype_groups_that_do_not_cover_expected_columns(config):
    bad = _broken(config, lambda c: c["schema"]["string_columns"].remove("Surname"))
    with pytest.raises(ConfigError, match="cover exactly"):
        validate_config(bad)


def test_rejects_binary_column_that_is_not_an_integer_column(config):
    bad = _broken(config, lambda c: c["columns"]["binary_columns"].append("Balance"))
    with pytest.raises(ConfigError, match="binary_columns"):
        validate_config(bad)


def test_rejects_removing_the_identifier_from_processed_data(config):
    bad = _broken(config, lambda c: c["columns"]["remove_from_processed"].append("CustomerId"))
    with pytest.raises(ConfigError, match="remove_from_processed"):
        validate_config(bad)


def test_rejects_unknown_column_names(config):
    bad = _broken(config, lambda c: c["columns"]["excluded_from_features"].append("Nonexistent"))
    with pytest.raises(ConfigError, match="unknown columns"):
        validate_config(bad)


def test_rejects_inverted_plausibility_bounds(config):
    bad = _broken(config, lambda c: c["validation"].update(age_min=120))
    with pytest.raises(ConfigError, match="age_min"):
        validate_config(bad)


def test_rejects_non_numeric_bound(config):
    bad = _broken(config, lambda c: c["validation"].update(balance_min="zero"))
    with pytest.raises(ConfigError, match="balance_min"):
        validate_config(bad)


def test_reports_all_problems_at_once(config):
    def mutate(c):
        c["statistics"]["confidence_level"] = 95
        c["segmentation"]["age"]["labels"].pop()
    with pytest.raises(ConfigError) as error:
        validate_config(_broken(config, mutate))
    assert "confidence_level" in str(error.value) and "labels" in str(error.value)


# --- Phase 3 additions: the [kpi] section ----------------------------------------------
def test_rejects_kpi_column_that_does_not_exist(config):
    bad = _broken(config, lambda c: c["kpi"].update(geography_column="Country"))
    with pytest.raises(ConfigError, match="geography_column"):
        validate_config(bad)


def test_rejects_non_binary_engagement_column(config):
    bad = _broken(config, lambda c: c["kpi"].update(engagement_column="Age"))
    with pytest.raises(ConfigError, match="engagement_column"):
        validate_config(bad)


def test_rejects_blank_balance_segment_column(config):
    bad = _broken(config, lambda c: c["kpi"].update(balance_segment_column=" "))
    with pytest.raises(ConfigError, match="balance_segment_column"):
        validate_config(bad)


def test_missing_kpi_section_is_rejected(config):
    bad = _broken(config, lambda c: c.pop("kpi"))
    with pytest.raises(ConfigError, match=r"\[kpi\]"):
        validate_config(bad)


# --- Phase 4 additions: the [analysis] section -----------------------------------------
def test_rejects_unordered_effect_size_cutoffs(config):
    bad = _broken(config, lambda c: c["analysis"].update(effect_size_cutoffs=[0.3, 0.1, 0.5]))
    with pytest.raises(ConfigError, match="effect_size_cutoffs"):
        validate_config(bad)


def test_rejects_effect_size_label_count_mismatch(config):
    bad = _broken(config, lambda c: c["analysis"]["effect_size_labels"].pop())
    with pytest.raises(ConfigError, match="effect_size_labels"):
        validate_config(bad)


def test_rejects_smd_cutoffs_of_a_different_length(config):
    bad = _broken(config, lambda c: c["analysis"].update(smd_cutoffs=[0.2, 0.5]))
    with pytest.raises(ConfigError, match="smd_cutoffs"):
        validate_config(bad)


def test_rejects_same_interaction_row_and_column(config):
    bad = _broken(config, lambda c: c["analysis"].update(interaction_col="Geography"))
    with pytest.raises(ConfigError, match="interaction_row"):
        validate_config(bad)


def test_rejects_duplicate_segment_variables(config):
    bad = _broken(config, lambda c: c["analysis"]["segment_variables"].append("Gender"))
    with pytest.raises(ConfigError, match="duplicates"):
        validate_config(bad)


def test_rejects_non_text_display_labels(config):
    bad = _broken(config, lambda c: c["analysis"]["display_labels"].update(HasCrCard={"0": 5}))
    with pytest.raises(ConfigError, match="display_labels"):
        validate_config(bad)


def test_rejects_non_positive_top_gap_count(config):
    bad = _broken(config, lambda c: c["analysis"].update(top_contribution_gaps=0))
    with pytest.raises(ConfigError, match="top_contribution_gaps"):
        validate_config(bad)


def test_missing_analysis_section_is_rejected(config):
    bad = _broken(config, lambda c: c.pop("analysis"))
    with pytest.raises(ConfigError, match=r"\[analysis\]"):
        validate_config(bad)


# --- Phase 5 additions: the [balance_engagement] section -------------------------------
def test_rejects_wrong_number_of_salary_labels(config):
    bad = _broken(config, lambda c: c["balance_engagement"]["salary_labels"].pop())
    with pytest.raises(ConfigError, match="salary_labels"):
        validate_config(bad)


def test_rejects_duplicate_salary_labels(config):
    bad = _broken(config, lambda c: c["balance_engagement"].update(salary_labels=["Same", "Same", "Same"]))
    with pytest.raises(ConfigError, match="salary_labels"):
        validate_config(bad)


def test_rejects_too_few_balance_groups(config):
    bad = _broken(config, lambda c: c["balance_engagement"].update(balance_quantile_groups=1))
    with pytest.raises(ConfigError, match="balance_quantile_groups"):
        validate_config(bad)


def test_rejects_empty_standardisation_strata(config):
    bad = _broken(config, lambda c: c["balance_engagement"].update(standardise_high_vs_low_by=[[]]))
    with pytest.raises(ConfigError, match="standardise_high_vs_low_by"):
        validate_config(bad)


def test_rejects_concentration_shares_outside_zero_one(config):
    bad = _broken(config, lambda c: c["balance_engagement"].update(concentration_top_shares=[0.1, 1.5]))
    with pytest.raises(ConfigError, match="concentration_top_shares"):
        validate_config(bad)


def test_rejects_blank_tenure_column(config):
    bad = _broken(config, lambda c: c["balance_engagement"].update(tenure_column=""))
    with pytest.raises(ConfigError, match="tenure_column"):
        validate_config(bad)


def test_missing_balance_engagement_section_is_rejected(config):
    bad = _broken(config, lambda c: c.pop("balance_engagement"))
    with pytest.raises(ConfigError, match=r"\[balance_engagement\]"):
        validate_config(bad)
