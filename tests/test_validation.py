"""Tests for the validation checks. Each test breaks a valid dataset in ONE way."""

import pandas as pd
import pytest

from churn_analytics.validation import FAIL, INFO, PASS, WARN, validate_dataset


def status(report, name):
    return report.get(name).status


# ---------------------------------------------------------------- baseline
def test_valid_dataset_has_no_failures_or_warnings(valid_df, config):
    report = validate_dataset(valid_df, config)
    assert not report.has_failures
    assert report.warnings == []
    assert report.skipped_note is None


def test_validation_does_not_modify_the_data(valid_df, config):
    before = valid_df.copy()
    validate_dataset(valid_df, config)
    pd.testing.assert_frame_equal(valid_df, before)


# ---------------------------------------------------------------- structure
def test_missing_column_fails_and_skips_remaining_checks(valid_df, config):
    report = validate_dataset(valid_df.drop(columns=["Balance"]), config)
    assert status(report, "Schema: columns") == FAIL
    assert len(report.checks) == 1 and report.skipped_note


def test_extra_column_is_a_warning(valid_df, config):
    valid_df["Mystery"] = 1
    assert status(validate_dataset(valid_df, config), "Schema: columns") == WARN


def test_wrong_dtype_fails(valid_df, config):
    valid_df["Balance"] = valid_df["Balance"].astype(str)
    report = validate_dataset(valid_df, config)
    assert status(report, "Data types") == FAIL
    assert "Balance" in report.get("Data types").details


# ---------------------------------------------------------------- completeness
def test_missing_value_fails_and_is_not_imputed(valid_df, config):
    valid_df.loc[3, "Balance"] = float("nan")
    report = validate_dataset(valid_df, config)
    assert status(report, "Missing values") == FAIL
    assert report.get("Missing values").details["missing_by_column"] == {"Balance": 1}
    assert valid_df["Balance"].isna().sum() == 1  # still missing: nothing was filled in


def test_blank_string_counts_as_missing(valid_df, config):
    valid_df.loc[2, "Surname"] = "   "
    assert status(validate_dataset(valid_df, config), "Missing values") == FAIL


# ---------------------------------------------------------------- duplicates
def test_duplicate_customer_id_fails_with_example(valid_df, config):
    valid_df.loc[5, "CustomerId"] = valid_df.loc[4, "CustomerId"]
    check = validate_dataset(valid_df, config).get("Duplicates: CustomerId")
    assert check.status == FAIL
    assert valid_df.loc[4, "CustomerId"] in check.details["example_ids"]


def test_fully_duplicated_row_fails(valid_df, config):
    dup = pd.concat([valid_df, valid_df.iloc[[0]]], ignore_index=True)
    assert status(validate_dataset(dup, config), "Duplicates: full rows") == FAIL


def test_record_identical_except_id_is_only_a_warning(valid_df, config):
    twin = valid_df.iloc[[0]].copy()
    twin["CustomerId"] = 99999999
    report = validate_dataset(pd.concat([valid_df, twin], ignore_index=True), config)
    assert status(report, "Duplicates: identical except CustomerId") == WARN
    assert not report.has_failures


# ---------------------------------------------------------------- coding
def test_non_binary_flag_fails(valid_df, config):
    valid_df.loc[0, "HasCrCard"] = 2
    report = validate_dataset(valid_df, config)
    assert status(report, "Binary fields (0/1)") == FAIL
    assert report.get("Binary fields (0/1)").details["HasCrCard"]["invalid_values"] == [2]


def test_invalid_target_value_fails(valid_df, config):
    valid_df.loc[0, "Exited"] = 2
    assert status(validate_dataset(valid_df, config), "Target: Exited coding") == FAIL


def test_single_class_target_fails(valid_df, config):
    valid_df["Exited"] = 0
    assert status(validate_dataset(valid_df, config), "Target: both classes present") == FAIL


def test_target_check_reports_the_assumption(valid_df, config):
    details = validate_dataset(valid_df, config).get("Target: both classes present").details
    assert "not verifiable" in details["assumption"]


@pytest.mark.parametrize("bad_value", ["Italy", "france", "France "])
def test_unexpected_or_inexact_category_fails(valid_df, config, bad_value):
    valid_df.loc[0, "Geography"] = bad_value
    assert status(validate_dataset(valid_df, config), "Categories: allowed values") == FAIL


def test_expected_category_with_no_customers_is_a_warning(valid_df, config):
    valid_df = valid_df[valid_df["Geography"] != "Spain"].copy()
    assert status(validate_dataset(valid_df, config), "Categories: allowed values") == WARN


# ---------------------------------------------------------------- plausibility: flag, never delete
def test_implausible_values_are_flagged_but_records_are_kept(valid_df, config):
    n_before = len(valid_df)
    valid_df.loc[0, "Age"] = 5
    valid_df.loc[1, "Balance"] = -50.0
    valid_df.loc[2, "EstimatedSalary"] = 0.0
    valid_df.loc[3, "CreditScore"] = 900
    report = validate_dataset(valid_df, config)
    check = report.get("Plausibility bounds")
    assert check.status == WARN and "4 record(s)" in check.summary
    assert not report.has_failures          # warnings do not stop the pipeline
    assert len(valid_df) == n_before        # and nothing is removed
    assert check.details["example_ids"]


# ---------------------------------------------------------------- observations
def test_year_constant_is_info_not_a_problem(valid_df, config):
    check = validate_dataset(valid_df, config).get("Constant columns")
    assert check.status == INFO and "Year = 2025" in check.summary


def test_unexpected_constant_column_is_a_warning(valid_df, config):
    valid_df["Tenure"] = 4
    assert status(validate_dataset(valid_df, config), "Constant columns") == WARN


def test_question_mark_in_surname_is_counted(valid_df, config):
    valid_df.loc[[0, 1], "Surname"] = ["Y?an", "Sm?th"]
    check = validate_dataset(valid_df, config).get("Surname characters")
    assert check.status == WARN and "2 surname(s)" in check.summary


def test_small_categories_are_reported(valid_df, config):
    check = validate_dataset(valid_df, config).get("Small categories")
    assert check.status == INFO  # synthetic frame has only 60 rows, so categories are all small


def test_tenure_edge_check_makes_no_causal_claim(valid_df, config):
    summary = validate_dataset(valid_df, config).get("Tenure distribution edges").summary
    assert "NOT known" in summary


# ---------------------------------------------------------------- report rendering
def test_markdown_report_contents(valid_df, config):
    text = validate_dataset(valid_df, config).to_markdown({"SHA-256": "abc"})
    assert "# Data Validation Report" in text
    assert "PASSED" in text and "abc" in text
    assert "cannot confirm" in text.lower()


def test_markdown_report_says_failed_when_failing(valid_df, config):
    valid_df.loc[0, "Exited"] = 7
    assert "FAILED" in validate_dataset(valid_df, config).to_markdown()


# ---------------------------------------------------------------- the real dataset
def test_real_dataset_validation_matches_manual_inspection(raw_df, config):
    report = validate_dataset(raw_df, config)
    assert not report.has_failures
    assert status(report, "Missing values") == PASS
    assert status(report, "Duplicates: CustomerId") == PASS
    target = report.get("Target: both classes present").details
    assert (target["churned"], target["retained"]) == (2037, 7963)
    assert report.get("Surname characters").summary.startswith("92 surname(s)")
    assert "NumOfProducts = 4" in report.get("Small categories").details
    assert report.get("Constant columns").details["constant"] == {"Year": 2025}
