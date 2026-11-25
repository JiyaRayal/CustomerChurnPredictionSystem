"""Pipeline: verify -> load -> validate -> clean/segment -> investigate -> KPIs -> segment analysis -> balance/engagement analysis -> write outputs.

Beginner note: running this module is the one command that reproduces every Phase 2
output from the raw CSV. It stops immediately if the checksum does not match or if
validation finds FAIL-level problems (the validation report is still written first so
you can see what went wrong).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from .cleaning import CleaningResult, ValidationFailedError, prepare_dataset
from .analysis import SegmentAnalysis, run_segment_analysis
from .analysis_report import render_report
from .balance_engagement import BalanceEngagementAnalysis, run_balance_engagement_analysis
from .balance_engagement_report import render_report as render_balance_engagement_report
from .config import load_config, project_root
from .data_loader import load_raw_data, resolve_path, verify_raw_checksum
from .geography_balance import GeographyBalanceResult, investigate_geography_zero_balance
from .kpi_report import KpiSummary, build_kpi_summary
from .validation import ValidationReport, validate_dataset

PROCESSED_FILE = "customers_segmented.csv"
METADATA_FILE = "segmentation_metadata.json"
VALIDATION_REPORT = "validation_report.md"
CLEANING_LOG = "cleaning_log.md"
GEOGRAPHY_REPORT = "geography_zero_balance_investigation.md"
KPI_REPORT = "kpi_summary.md"
SEGMENT_REPORT = "segment_churn_analysis.md"
BALANCE_ENGAGEMENT_REPORT = "high_balance_engagement_analysis.md"


@dataclass
class PipelineResult:
    raw_sha256: str
    report: ValidationReport
    cleaning: CleaningResult
    investigation: GeographyBalanceResult
    kpis: KpiSummary
    segments: SegmentAnalysis
    balance_engagement: BalanceEngagementAnalysis
    outputs: dict[str, Path]


def run(config: dict[str, Any] | None = None, root: Path | None = None) -> PipelineResult:
    """Run the whole Phase 2 pipeline and write its outputs under ``root``."""
    config = config or load_config()
    root = root or project_root()
    processed_dir = root / config["paths"]["processed_dir"]
    reports_dir = root / "reports"
    tables_dir = root / config["paths"]["tables_dir"]
    for folder in (processed_dir, reports_dir, tables_dir):
        folder.mkdir(parents=True, exist_ok=True)

    sha = verify_raw_checksum(config, root)
    raw = load_raw_data(config, root, verify=False)  # already verified one line above

    report = validate_dataset(raw, config)
    context = {"Source file": config["paths"]["raw_data"], "SHA-256": sha}
    (reports_dir / VALIDATION_REPORT).write_text(report.to_markdown(context), encoding="utf-8")
    if report.has_failures:
        raise ValidationFailedError(
            "Validation failed; see reports/" + VALIDATION_REPORT + ". No processed data was written.")

    cleaning = prepare_dataset(raw, config, report)
    outputs = {"validation_report": reports_dir / VALIDATION_REPORT}

    processed_path = processed_dir / PROCESSED_FILE
    cleaning.data.to_csv(processed_path, index=False, lineterminator="\n")
    metadata = {"raw_file": config["paths"]["raw_data"], "raw_sha256": sha,
                "rows": len(cleaning.data), "columns": list(cleaning.data.columns),
                **cleaning.segmentation_metadata}
    metadata_path = processed_dir / METADATA_FILE
    metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")
    log_path = reports_dir / CLEANING_LOG
    log_path.write_text(cleaning.to_markdown(sha), encoding="utf-8")

    investigation = investigate_geography_zero_balance(cleaning.data, config)
    geo_path = reports_dir / GEOGRAPHY_REPORT
    geo_path.write_text(investigation.to_markdown(), encoding="utf-8")
    investigation.counts.to_csv(tables_dir / "geography_zero_balance_counts.csv", lineterminator="\n")
    investigation.churn_cells.to_csv(tables_dir / "geography_zero_balance_churn_cells.csv",
                                     index=False, lineterminator="\n")
    investigation.like_for_like.to_csv(tables_dir / "non_zero_balance_churn_by_geography.csv",
                                       index=False, lineterminator="\n")
    pd.DataFrame(cleaning.segmentation_metadata["segment_sizes"]).to_csv(
        tables_dir / "segment_sizes.csv", index=False, lineterminator="\n")

    kpi_summary = build_kpi_summary(cleaning.data, config)
    kpi_path = reports_dir / KPI_REPORT
    kpi_path.write_text(kpi_summary.to_markdown(config), encoding="utf-8")
    for name, table in (("geographic_risk_index_all_customers", kpi_summary.geographic_risk_all),
                        ("geographic_risk_index_non_zero_balance", kpi_summary.geographic_risk_nonzero),
                        ("engagement_drop_by_country", kpi_summary.engagement_by_country),
                        ("high_balance_churn_by_country", kpi_summary.high_balance_by_country),
                        ("balance_exposure_by_segment", kpi_summary.exposure_by_balance_segment)):
        table.to_csv(tables_dir / f"{name}.csv", index=False, lineterminator="\n")

    segments = run_segment_analysis(cleaning.data, config)
    overall = kpi_summary.overall
    segment_path = reports_dir / SEGMENT_REPORT
    segment_path.write_text(render_report(segments, config, overall["rate"], overall["n"]), encoding="utf-8")
    for name, table in (("segment_overview", segments.overview), ("association_ranking", segments.association),
                        ("gender_comparison", segments.gender), ("geography_age_all_customers", segments.geography_age_all),
                        ("geography_age_non_zero_balance", segments.geography_age_non_zero),
                        ("geography_balance_segment", segments.geography_balance),
                        ("credit_score_sensitivity_overview", segments.credit_sensitivity_overview),
                        ("credit_score_sensitivity_association", segments.credit_sensitivity_association),
                        ("profile_numeric", segments.profile_numeric), ("profile_categorical", segments.profile_categorical)):
        table.to_csv(tables_dir / f"{name}.csv", index=False, lineterminator="\n")

    be = run_balance_engagement_analysis(cleaning.data, config)
    be_path = reports_dir / BALANCE_ENGAGEMENT_REPORT
    be_path.write_text(render_balance_engagement_report(be, config), encoding="utf-8")
    for name, table in (("high_balance_profile", be.high_balance_profile),
                        ("churn_within_high_balance", be.churn_within_high_balance),
                        ("high_vs_low_balance_by_stratum", be.high_vs_low_by_stratum),
                        ("standardised_high_vs_low_balance", be.standardised_high_vs_low),
                        ("churn_by_balance_group", be.balance_group_churn),
                        ("salary_group_churn", be.salary["overview"]),
                        ("salary_balance_grid_all_customers", be.salary["grid_all"]),
                        ("salary_balance_grid_non_zero_balance", be.salary["grid_non_zero"]),
                        ("engagement_by_segment", be.engagement_by_segment), ("inactive_share", be.inactive_share),
                        ("engagement_tenure_grid", be.engagement_tenure_grid),
                        ("engagement_products_grid", be.engagement_products_grid), ("tenure_curve", be.tenure_curve),
                        ("balance_exposure_by_variable", be.exposure_by_variable),
                        ("churned_balance_concentration", be.concentration),
                        ("balance_engagement_matrix", be.balance_engagement_matrix)):
        table.to_csv(tables_dir / f"{name}.csv", index=False, lineterminator="\n")

    outputs.update(processed_data=processed_path, segmentation_metadata=metadata_path,
                   cleaning_log=log_path, geography_report=geo_path, kpi_summary=kpi_path,
                   segment_analysis=segment_path, balance_engagement_analysis=be_path, tables=tables_dir)
    return PipelineResult(sha, report, cleaning, investigation, kpi_summary, segments, be, outputs)


def main() -> None:
    result = run()
    counts = result.report.status_counts()
    print(f"Raw checksum verified: {result.raw_sha256[:16]}...")
    print(f"Validation: {counts['PASS']} PASS, {counts['INFO']} INFO, {counts['WARN']} WARN, {counts['FAIL']} FAIL")
    print(f"Processed rows: {len(result.cleaning.data):,}  columns: {result.cleaning.data.shape[1]}")
    print("Outputs written:")
    for name, path in result.outputs.items():
        print(f"  {name}: {path}")


if __name__ == "__main__":
    main()
