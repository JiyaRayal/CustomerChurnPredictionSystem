"""Tests for the 'no silent changes' cleaning rules."""

import pandas as pd
import pytest

from churn_analytics.cleaning import ValidationFailedError, prepare_dataset
from churn_analytics.segmentation import DERIVED_COLUMNS
from churn_analytics.validation import validate_dataset


def prepare(df, config):
    return prepare_dataset(df, config, validate_dataset(df, config))


def test_no_records_are_removed(valid_df, config):
    result = prepare(valid_df, config)
    assert len(result.data) == len(valid_df)
    assert result.data["CustomerId"].tolist() == valid_df["CustomerId"].tolist()  # same rows, same order


def test_surname_removed_but_identifier_and_metadata_kept(valid_df, config):
    data = prepare(valid_df, config).data
    assert "Surname" not in data.columns
    assert {"CustomerId", "Year", "Exited"} <= set(data.columns)


def test_original_values_are_unchanged(valid_df, config):
    result = prepare(valid_df, config)
    for column in result.data.columns:
        if column in valid_df.columns:
            assert (result.data[column].astype(object) == valid_df[column].astype(object)).all(), column
    proof = next(d for d in result.decisions if d.id == "C9")
    assert proof.rows_affected == 0


def test_input_dataframe_is_not_mutated(valid_df, config):
    before = valid_df.copy()
    prepare(valid_df, config)
    pd.testing.assert_frame_equal(valid_df, before)


def test_derived_columns_are_added_and_complete(valid_df, config):
    data = prepare(valid_df, config).data
    assert set(DERIVED_COLUMNS) <= set(data.columns)
    assert data[list(DERIVED_COLUMNS)].notna().all().all()


def test_geography_and_gender_become_fixed_order_categories(valid_df, config):
    data = prepare(valid_df, config).data
    assert list(data["Geography"].cat.categories) == ["France", "Germany", "Spain"]
    assert list(data["Gender"].cat.categories) == ["Female", "Male"]


def test_refuses_to_clean_data_that_failed_validation(valid_df, config):
    valid_df.loc[5, "CustomerId"] = valid_df.loc[4, "CustomerId"]
    report = validate_dataset(valid_df, config)
    assert report.has_failures
    with pytest.raises(ValidationFailedError, match="Duplicates: CustomerId"):
        prepare_dataset(valid_df, config, report)


def test_missing_values_block_cleaning_instead_of_being_imputed(valid_df, config):
    valid_df.loc[0, "Balance"] = float("nan")
    with pytest.raises(ValidationFailedError):
        prepare(valid_df, config)


def test_records_with_plausibility_warnings_are_kept(valid_df, config):
    valid_df.loc[0, "Age"] = 5
    report = validate_dataset(valid_df, config)
    assert report.warnings and not report.has_failures
    data = prepare_dataset(valid_df, config, report).data
    row = data.loc[data["CustomerId"] == valid_df.loc[0, "CustomerId"]].iloc[0]
    assert row["Age"] == 5 and row["AgeBand"] == "Under 30"


def test_cleaning_is_deterministic(valid_df, config):
    pd.testing.assert_frame_equal(prepare(valid_df, config).data, prepare(valid_df, config).data)


def test_decision_log_is_complete_and_markdown_renders(valid_df, config):
    result = prepare(valid_df, config)
    assert [d.id for d in result.decisions] == [f"C{i}" for i in range(1, 10)]
    text = result.to_markdown("abc123")
    assert "Balance threshold" in text and "Proof: original values unchanged" in text and "abc123" in text
