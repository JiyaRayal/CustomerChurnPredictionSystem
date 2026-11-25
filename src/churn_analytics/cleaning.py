"""Prepare the analysis dataset and document every cleaning decision.

Beginner notes
--------------
The guiding rule is **"no silent changes"**:

1. If validation found FAIL-level problems, ``prepare_dataset`` refuses to run. A person must
   decide how to handle bad data; the code never guesses.
2. Records are never deleted and values are never imputed or edited. Records flagged WARN
   during validation are kept.
3. Only *columns* are changed: Surname is removed from the processed copy (personal,
   non-analytical); text columns become fixed-order categories; segment columns are added.
4. Every decision is written to a log **with counts computed from the data** (not typed in),
   including a check that no original value changed.
5. The raw CSV is never touched: everything happens on an in-memory copy.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from .md_utils import fmt_int, fmt_pct, markdown_table
from .segmentation import DERIVED_COLUMNS, add_segments, segment_category_orders
from .validation import ValidationReport


class ValidationFailedError(RuntimeError):
    """Raised when cleaning is attempted on data that failed validation."""


@dataclass
class CleaningDecision:
    id: str
    action: str
    rationale: str
    rows_affected: int
    columns: str


@dataclass
class CleaningResult:
    data: pd.DataFrame
    decisions: list[CleaningDecision]
    segmentation_metadata: dict[str, Any]

    def to_markdown(self, raw_sha256: str | None = None) -> str:
        meta = self.segmentation_metadata
        lines = ["# Cleaning and Segmentation Log", "",
                 "Every decision below was applied by code, with counts computed from the data. "
                 "The raw CSV was not modified.", ""]
        if raw_sha256:
            lines += [f"* Raw file SHA-256: `{raw_sha256}`", ""]

        lines += ["## Cleaning decisions", "",
                  markdown_table(["ID", "Action", "Rationale", "Rows affected", "Columns"],
                                 [[d.id, d.action, d.rationale, fmt_int(d.rows_affected), d.columns]
                                  for d in self.decisions]), ""]

        thr = meta["balance_threshold_median_of_nonzero"]
        cuts = ", ".join(f"{c:,.2f}" for c in meta["credit_score_tercile_cutpoints"])
        lines += ["## Values computed from the data", "",
                  f"* **Balance threshold** (median of the {meta['balance_nonzero_count']:,} non-zero "
                  f"balances): **{thr:,.2f}**. Low-balance: 0 < balance <= {thr:,.2f}; "
                  f"High-balance: balance > {thr:,.2f}.",
                  f"* **Credit-score tercile cut points** (sensitivity grouping, right-closed): {cuts}.", ""]

        rows = [[s["segment_variable"], s["segment"], fmt_int(s["n"]), fmt_pct(s["share"]),
                 "yes" if s["small_sample"] else "no"] for s in meta["segment_sizes"]]
        lines += ["## Segment sizes", "",
                  markdown_table(["Segment variable", "Segment", "Customers", "Share", "Small sample?"], rows), "",
                  "Small sample = fewer customers than `small_group_threshold` in the config. Shares "
                  "within one variable sum to 100%.", ""]
        return "\n".join(lines)


def _count_changed_cells(original: pd.DataFrame, processed: pd.DataFrame) -> int:
    """Count cells whose value differs between the raw and processed frames (shared columns)."""
    changed = 0
    for column in processed.columns:
        if column in original.columns:
            changed += int((processed[column].astype(object) != original[column].astype(object)).sum())
    return changed


def prepare_dataset(raw: pd.DataFrame, config: dict[str, Any], report: ValidationReport) -> CleaningResult:
    """Build the processed dataset from validated raw data. Does not modify ``raw``."""
    if report.has_failures:
        names = ", ".join(c.name for c in report.failures)
        raise ValidationFailedError(
            f"Validation failed ({names}). Review the validation report and decide how to handle the "
            "problem; no automatic cleaning is performed on data that fails validation."
        )

    columns = config["columns"]
    n_rows = len(raw)
    df = raw.copy()
    decisions: list[CleaningDecision] = []

    # C1 - records are retained (counted again at the end to prove it)
    # C2 - no imputation needed (validation guarantees no missing values)
    n_missing = int(raw.isna().sum().sum())
    flagged = sum(c.status == "WARN" for c in report.checks if c.name == "Plausibility bounds")

    # C3 - remove non-analytical personal columns from the processed copy
    removed = [c for c in columns["remove_from_processed"] if c in df.columns]
    df = df.drop(columns=removed)

    # C4 - fixed-order categories for Geography / Gender (labels unchanged)
    orders = segment_category_orders(config)
    for name in columns["categorical_expected"]:
        df[name] = pd.Categorical(df[name], categories=orders[name], ordered=False)

    # C5 - derived segments (thresholds from the config; balance cut computed from the data)
    df, metadata = add_segments(df, config)

    changed = _count_changed_cells(raw, df)
    n_out = len(df)

    decisions += [
        CleaningDecision("C1", "Keep every customer record; none deleted",
                         "Deleting records needs a justified reason; validation found no FAIL-level problems",
                         0, "(all)"),
        CleaningDecision("C2", "No imputation performed",
                         f"Raw data contains {n_missing} missing values, so there is nothing to fill in",
                         0, "(all)"),
        CleaningDecision("C3", "Keep records flagged by plausibility checks",
                         "Flagged records are reviewed by a person, never auto-removed. "
                         f"Plausibility check status: {'WARN' if flagged else 'PASS (no records flagged)'}",
                         0, "Age, CreditScore, Tenure, Balance, EstimatedSalary, NumOfProducts"),
        CleaningDecision("C4", "Remove column(s) from the processed copy: " + (", ".join(removed) or "none"),
                         "Personal and non-analytical; the raw file still contains them. Columns only, no rows",
                         0, ", ".join(removed) or "-"),
        CleaningDecision("C5", "Keep CustomerId as identifier only; keep Year as metadata",
                         "Neither is used for segmentation or as a feature (config: excluded_from_features). "
                         "Year has a single value", 0, "CustomerId, Year"),
        CleaningDecision("C6", "Convert Geography and Gender to fixed-order categories",
                         "Reliable grouping and consistent chart order; labels unchanged", 0,
                         ", ".join(columns["categorical_expected"])),
        CleaningDecision("C7", "Keep binary fields as 0/1 integers",
                         "Validated to contain only 0 and 1", 0, ", ".join(columns["binary_columns"])),
        CleaningDecision("C8", "Add derived segment columns: " + ", ".join(DERIVED_COLUMNS),
                         "Thresholds read from config/segmentation.toml; every row receives exactly one "
                         "label per variable", n_rows, ", ".join(DERIVED_COLUMNS)),
        CleaningDecision("C9", "Proof: original values unchanged",
                         f"Cells whose value differs from the raw file in retained columns: {changed}. "
                         f"Rows in: {n_rows:,}; rows out: {n_out:,}", changed, "(all retained)"),
    ]
    return CleaningResult(data=df, decisions=decisions, segmentation_metadata=metadata)
