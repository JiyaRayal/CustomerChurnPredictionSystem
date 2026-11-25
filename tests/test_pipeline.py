"""End-to-end tests: run the whole pipeline in a throw-away copy of the project folders."""

import re

import hashlib
import json
import shutil

import pandas as pd
import pytest

from churn_analytics.cleaning import ValidationFailedError
from churn_analytics.config import project_root
from churn_analytics.data_loader import DataIntegrityError, sha256_of_file
from churn_analytics.pipeline import (CLEANING_LOG, GEOGRAPHY_REPORT, METADATA_FILE, PROCESSED_FILE,
                                      VALIDATION_REPORT, run)


@pytest.fixture()
def sandbox(tmp_path, config, raw_path):
    """A temporary project root holding a copy of the real raw CSV and its checksum."""
    raw = tmp_path / config["paths"]["raw_data"]
    raw.parent.mkdir(parents=True)
    shutil.copy(raw_path, raw)
    shutil.copy(project_root() / config["paths"]["raw_checksums"], tmp_path / config["paths"]["raw_checksums"])
    return tmp_path


def rerecord_checksum(root, config):
    raw = root / config["paths"]["raw_data"]
    (root / config["paths"]["raw_checksums"]).write_text(f"{sha256_of_file(raw)}  {raw.name}\n")


def test_pipeline_writes_every_expected_output(sandbox, config):
    result = run(config, sandbox)
    processed = sandbox / config["paths"]["processed_dir"]
    reports = sandbox / "reports"
    for path in (processed / PROCESSED_FILE, processed / METADATA_FILE, reports / VALIDATION_REPORT,
                 reports / CLEANING_LOG, reports / GEOGRAPHY_REPORT):
        assert path.is_file(), path
    assert not result.report.has_failures


def test_processed_data_has_all_rows_no_surname_and_no_missing_values(sandbox, config):
    run(config, sandbox)
    df = pd.read_csv(sandbox / config["paths"]["processed_dir"] / PROCESSED_FILE)
    assert len(df) == 10000 and "Surname" not in df.columns and df.isna().sum().sum() == 0


def test_pipeline_never_modifies_the_raw_file(sandbox, config):
    raw = sandbox / config["paths"]["raw_data"]
    before = sha256_of_file(raw)
    run(config, sandbox)
    assert sha256_of_file(raw) == before


def test_pipeline_is_reproducible_byte_for_byte(sandbox, config):
    run(config, sandbox)
    first = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in
             list((sandbox / "reports").glob("*.md")) + list((sandbox / "data/processed").glob("*"))}
    run(config, sandbox)
    second = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in
              list((sandbox / "reports").glob("*.md")) + list((sandbox / "data/processed").glob("*"))}
    assert first == second and len(first) >= 5


def test_metadata_threshold_matches_independent_calculation(sandbox, config, raw_df):
    run(config, sandbox)
    meta = json.loads((sandbox / config["paths"]["processed_dir"] / METADATA_FILE).read_text())
    assert meta["balance_threshold_median_of_nonzero"] == pytest.approx(raw_df.loc[raw_df.Balance > 0, "Balance"].median())
    assert meta["raw_sha256"] == sha256_of_file(sandbox / config["paths"]["raw_data"])


def test_pipeline_stops_on_a_modified_raw_file(sandbox, config):
    raw = sandbox / config["paths"]["raw_data"]
    raw.write_bytes(raw.read_bytes().replace(b"Hargrave", b"Hargrove", 1))
    with pytest.raises(DataIntegrityError):
        run(config, sandbox)
    assert not (sandbox / config["paths"]["processed_dir"] / PROCESSED_FILE).exists()


def test_pipeline_stops_on_validation_failure_but_still_writes_the_report(sandbox, config):
    raw = sandbox / config["paths"]["raw_data"]
    df = pd.read_csv(raw)
    df.loc[1, "CustomerId"] = df.loc[0, "CustomerId"]          # introduce a duplicate ID
    df.to_csv(raw, index=False)
    rerecord_checksum(sandbox, config)                          # so the checksum itself still passes
    with pytest.raises(ValidationFailedError):
        run(config, sandbox)
    assert "FAILED" in (sandbox / "reports" / VALIDATION_REPORT).read_text()
    assert not (sandbox / config["paths"]["processed_dir"] / PROCESSED_FILE).exists()


# --- Phase 3 additions: KPI outputs -----------------------------------------------------
from churn_analytics.data_loader import load_processed_data  # noqa: E402
from churn_analytics.kpi_report import build_kpi_summary  # noqa: E402
from churn_analytics.pipeline import KPI_REPORT  # noqa: E402


def test_pipeline_writes_the_kpi_report_and_tables(sandbox, config):
    run(config, sandbox)
    assert (sandbox / "reports" / KPI_REPORT).is_file()
    for name in ("geographic_risk_index_all_customers", "geographic_risk_index_non_zero_balance",
                 "engagement_drop_by_country", "high_balance_churn_by_country", "balance_exposure_by_segment"):
        assert (sandbox / config["paths"]["tables_dir"] / f"{name}.csv").is_file(), name


def test_kpi_report_is_descriptive_and_has_no_nan(sandbox, config):
    run(config, sandbox)
    text = (sandbox / "reports" / KPI_REPORT).read_text()
    assert not re.search(r"\bnan\b", text.lower())
    for phrase in ("NOT lost revenue", "descriptive associations", "like-for-like", "symptom"):
        assert phrase in text


def test_kpis_are_identical_from_memory_and_from_the_saved_processed_file(sandbox, config):
    result = run(config, sandbox)
    reloaded = load_processed_data(sandbox / config["paths"]["processed_dir"] / PROCESSED_FILE, config)
    again = build_kpi_summary(reloaded, config)
    assert again.overall["events"] == result.kpis.overall["events"]
    cols = ["n", "churned", "risk_index"]
    pd.testing.assert_frame_equal(again.geographic_risk_all[cols], result.kpis.geographic_risk_all[cols])
    assert again.engagement["edi_pp"] == pytest.approx(result.kpis.engagement["edi_pp"])
    assert again.high_balance["events"] == result.kpis.high_balance["events"]


# --- Phase 4 additions: segment analysis outputs ----------------------------------------
from churn_analytics.pipeline import SEGMENT_REPORT  # noqa: E402


def test_pipeline_writes_the_segment_report_and_tables(sandbox, config):
    result = run(config, sandbox)
    assert (sandbox / "reports" / SEGMENT_REPORT).is_file()
    for name in ("segment_overview", "association_ranking", "gender_comparison", "geography_age_all_customers",
                 "geography_age_non_zero_balance", "geography_balance_segment", "credit_score_sensitivity_overview",
                 "credit_score_sensitivity_association", "profile_numeric", "profile_categorical"):
        assert (sandbox / config["paths"]["tables_dir"] / f"{name}.csv").is_file(), name
    assert result.segments.overview["n"].sum() > 0


def test_segment_report_in_pipeline_has_no_nan_and_keeps_its_caveats(sandbox, config):
    run(config, sandbox)
    text = (sandbox / "reports" / SEGMENT_REPORT).read_text()
    assert not re.search(r"\bnan\b", text.lower())
    assert "not causal effects" in text and "What this analysis cannot tell us" in text


# --- Phase 5 additions: balance / engagement outputs -----------------------------------
from churn_analytics.pipeline import BALANCE_ENGAGEMENT_REPORT  # noqa: E402


def test_pipeline_writes_the_balance_engagement_report_and_tables(sandbox, config):
    result = run(config, sandbox)
    assert (sandbox / "reports" / BALANCE_ENGAGEMENT_REPORT).is_file()
    for name in ("high_balance_profile", "churn_within_high_balance", "high_vs_low_balance_by_stratum",
                 "standardised_high_vs_low_balance", "churn_by_balance_group", "salary_group_churn",
                 "salary_balance_grid_all_customers", "salary_balance_grid_non_zero_balance", "engagement_by_segment",
                 "inactive_share", "engagement_tenure_grid", "engagement_products_grid", "tenure_curve",
                 "balance_exposure_by_variable", "churned_balance_concentration", "balance_engagement_matrix"):
        assert (sandbox / config["paths"]["tables_dir"] / f"{name}.csv").is_file(), name
    assert result.balance_engagement.countries_without_zero_balance == ["Germany"]


def test_balance_engagement_report_in_pipeline_is_clean(sandbox, config):
    run(config, sandbox)
    text = (sandbox / "reports" / BALANCE_ENGAGEMENT_REPORT).read_text()
    assert not re.search(r"\bnan\b", text.lower())
    assert "not lost revenue" in text and "What this analysis cannot tell us" in text
