"""Automated data-quality checks that produce a written validation report.

Beginner notes
--------------
Every check returns a ``CheckResult`` with one of four statuses:

* **PASS** - nothing wrong found.
* **INFO** - an observation worth knowing (e.g. a small category). Not a problem by itself.
* **WARN** - suspicious records or values. They are REPORTED and KEPT, never deleted.
* **FAIL** - the data breaks a structural rule (missing values, wrong types, duplicate IDs,
  non-binary target...). The pipeline stops: a human must decide what to do.

Important limits (also printed in the report): validation can confirm that ``Exited`` is
complete and binary, but it cannot prove that 1 truly means "left the bank". That meaning
comes from the project brief and is an assumption.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from .md_utils import fmt_int, fmt_pct, markdown_table

PASS, INFO, WARN, FAIL = "PASS", "INFO", "WARN", "FAIL"
SAMPLE_IDS = 5  # how many example CustomerIds to show for flagged records


@dataclass
class CheckResult:
    name: str
    status: str
    summary: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationReport:
    checks: list[CheckResult]
    n_rows: int
    n_columns: int
    skipped_note: str | None = None

    @property
    def failures(self) -> list[CheckResult]:
        return [c for c in self.checks if c.status == FAIL]

    @property
    def warnings(self) -> list[CheckResult]:
        return [c for c in self.checks if c.status == WARN]

    @property
    def has_failures(self) -> bool:
        return bool(self.failures)

    def get(self, name: str) -> CheckResult:
        for check in self.checks:
            if check.name == name:
                return check
        raise KeyError(name)

    def status_counts(self) -> dict[str, int]:
        return {s: sum(c.status == s for c in self.checks) for s in (PASS, INFO, WARN, FAIL)}

    def to_dataframe(self) -> pd.DataFrame:
        return pd.DataFrame([{"check": c.name, "status": c.status, "summary": c.summary}
                             for c in self.checks])

    def to_markdown(self, context: dict[str, Any] | None = None) -> str:
        counts = self.status_counts()
        verdict = "FAILED - pipeline stopped" if self.has_failures else "PASSED (no FAIL-level problems)"
        lines = ["# Data Validation Report", "",
                 f"* Rows: **{self.n_rows:,}**, columns: **{self.n_columns}**"]
        for key, value in (context or {}).items():
            lines.append(f"* {key}: `{value}`")
        lines += [f"* Overall result: **{verdict}**",
                  f"* Check results: {counts[PASS]} PASS, {counts[INFO]} INFO, "
                  f"{counts[WARN]} WARN, {counts[FAIL]} FAIL", ""]
        if self.skipped_note:
            lines += [f"> **Note:** {self.skipped_note}", ""]

        lines += ["## Summary of checks", "",
                  markdown_table(["Check", "Status", "Result"],
                                 [[c.name, f"**{c.status}**", c.summary] for c in self.checks]), ""]

        lines += ["## Details", ""]
        for check in self.checks:
            if not check.details:
                continue
            lines.append(f"### {check.name} ({check.status})")
            lines += [f"* {key}: {_format_detail(value)}" for key, value in check.details.items()]
            lines.append("")

        lines += [
            "## What this validation can and cannot confirm", "",
            "* **Can confirm:** structure, data types, completeness, uniqueness of CustomerId, "
            "binary coding, allowed categories, and that the target has both classes.",
            "* **Cannot confirm:** that `Exited = 1` really means the customer left, over what time "
            "window, or where the data came from. These are assumptions taken from the project brief "
            "(see docs/decisions_log.md D6 and docs/data_provenance.md).",
            "* **WARN-level records are kept.** They are listed so a person can review them; "
            "nothing is deleted or corrected automatically.", ""]
        return "\n".join(lines)


def _format_detail(value: Any) -> str:
    if isinstance(value, dict):
        return "; ".join(f"{k}: {_format_detail(v)}" for k, v in value.items()) or "none"
    if isinstance(value, (list, tuple)):
        return ", ".join(str(v) for v in value) or "none"
    if isinstance(value, float):
        return f"{value:,.2f}"
    return str(value)


def _sample_ids(df: pd.DataFrame, mask: pd.Series, id_col: str) -> list[Any]:
    return df.loc[mask, id_col].head(SAMPLE_IDS).tolist() if id_col in df else []


# --------------------------------------------------------------------------------------
# Individual checks
# --------------------------------------------------------------------------------------
def _check_schema(df: pd.DataFrame, config: dict[str, Any]) -> CheckResult:
    expected = config["schema"]["expected_columns"]
    missing = [c for c in expected if c not in df.columns]
    extra = [c for c in df.columns if c not in expected]
    details = {"expected_columns": len(expected), "found_columns": len(df.columns)}
    if missing:
        return CheckResult("Schema: columns", FAIL, f"{len(missing)} expected column(s) missing",
                           {**details, "missing": missing, "extra": extra})
    if extra:
        return CheckResult("Schema: columns", WARN, f"{len(extra)} unexpected extra column(s)",
                           {**details, "extra": extra})
    order_note = {} if list(df.columns) == expected else {"note": "column order differs from config"}
    return CheckResult("Schema: columns", PASS, "all expected columns present, no extras",
                       {**details, **order_note})


def _check_dtypes(df: pd.DataFrame, config: dict[str, Any]) -> CheckResult:
    schema = config["schema"]
    checks = {"integer": (schema["integer_columns"], pd.api.types.is_integer_dtype),
              "float": (schema["float_columns"], pd.api.types.is_float_dtype),
              "string": (schema["string_columns"], pd.api.types.is_string_dtype)}
    wrong = {}
    for kind, (columns, test) in checks.items():
        for column in columns:
            if not test(df[column]):
                wrong[column] = f"expected {kind}, found {df[column].dtype}"
    if wrong:
        return CheckResult("Data types", FAIL, f"{len(wrong)} column(s) have unexpected types", wrong)
    return CheckResult("Data types", PASS, "all columns have the expected types")


def _check_missing(df: pd.DataFrame, config: dict[str, Any]) -> CheckResult:
    missing = {c: int(n) for c, n in df.isna().sum().items() if n}
    blanks = {}
    for column in config["schema"]["string_columns"]:
        n = int(df[column].astype("string").str.strip().eq("").sum())
        if n:
            blanks[column] = n
    if missing or blanks:
        return CheckResult("Missing values", FAIL, "missing or blank values found - none imputed",
                           {"missing_by_column": missing, "blank_strings_by_column": blanks})
    return CheckResult("Missing values", PASS, "no missing or blank values in any column")


def _check_duplicates(df: pd.DataFrame, config: dict[str, Any]) -> list[CheckResult]:
    id_col = config["columns"]["identifier"]
    results = []

    n_dup_rows = int(df.duplicated().sum())
    results.append(CheckResult(
        "Duplicates: full rows", FAIL if n_dup_rows else PASS,
        f"{n_dup_rows} fully duplicated row(s)" if n_dup_rows else "no fully duplicated rows"))

    dup_ids = df[id_col].duplicated(keep=False)
    n_dup_ids = int(df[id_col].duplicated().sum())
    results.append(CheckResult(
        "Duplicates: CustomerId", FAIL if n_dup_ids else PASS,
        f"{n_dup_ids} repeated CustomerId value(s)" if n_dup_ids else
        f"all {df[id_col].nunique():,} CustomerId values are unique",
        {"example_ids": _sample_ids(df, dup_ids, id_col)} if n_dup_ids else {}))

    others = [c for c in df.columns if c != id_col]
    n_same = int(df.duplicated(subset=others).sum())
    results.append(CheckResult(
        "Duplicates: identical except CustomerId", WARN if n_same else PASS,
        f"{n_same} record(s) identical to another in every column except CustomerId; kept, "
        "may be coincidence" if n_same else "no records identical except for CustomerId"))
    return results


def _check_binary(df: pd.DataFrame, config: dict[str, Any]) -> CheckResult:
    id_col = config["columns"]["identifier"]
    bad = {}
    for column in config["columns"]["binary_columns"]:
        mask = ~df[column].isin([0, 1])
        if mask.any():
            bad[column] = {"invalid_count": int(mask.sum()),
                           "invalid_values": sorted(df.loc[mask, column].unique().tolist())[:10],
                           "example_ids": _sample_ids(df, mask, id_col)}
    if bad:
        return CheckResult("Binary fields (0/1)", FAIL, f"{len(bad)} binary column(s) contain other values", bad)
    return CheckResult("Binary fields (0/1)", PASS,
                       "all binary columns contain only 0 and 1: " + ", ".join(config["columns"]["binary_columns"]))


def _check_categories(df: pd.DataFrame, config: dict[str, Any]) -> CheckResult:
    problems, absent, counts = {}, {}, {}
    for column, allowed in config["columns"]["categorical_expected"].items():
        found = df[column].value_counts()
        counts[column] = {str(k): int(v) for k, v in found.items()}
        unexpected = [str(v) for v in found.index if v not in allowed]
        missing_categories = [a for a in allowed if a not in found.index]
        if unexpected:
            problems[column] = unexpected
        if missing_categories:
            absent[column] = missing_categories
    details = {"counts": counts}
    if problems:
        return CheckResult("Categories: allowed values", FAIL, "unexpected category values found",
                           {**details, "unexpected_values": problems})
    if absent:
        return CheckResult("Categories: allowed values", WARN, "an expected category has no customers",
                           {**details, "absent_categories": absent})
    return CheckResult("Categories: allowed values", PASS,
                       "all categorical columns contain only the expected values", details)


def _check_target(df: pd.DataFrame, config: dict[str, Any]) -> list[CheckResult]:
    target, churn_value = config["columns"]["target"], config["columns"]["churn_value"]
    values = df[target]
    if not values.isin([0, 1]).all():
        return [CheckResult("Target: Exited coding", FAIL, "target contains values other than 0 and 1",
                            {"values_found": sorted(values.dropna().unique().tolist())[:10]})]
    churned = int((values == churn_value).sum())
    retained = len(df) - churned
    results = [CheckResult("Target: Exited coding", PASS, "target contains only 0 and 1")]
    if churned == 0 or retained == 0:
        results.append(CheckResult("Target: both classes present", FAIL,
                                   "only one class present; churn analysis is impossible",
                                   {"churned": churned, "retained": retained}))
    else:
        results.append(CheckResult(
            "Target: both classes present", PASS,
            f"{churned:,} churned ({fmt_pct(churned / len(df), 2)}) and {retained:,} retained",
            {"churned": churned, "retained": retained,
             "assumption": f"{target} = {churn_value} means churned (from the project brief; not verifiable from data)"}))
    return results


def _check_plausibility(df: pd.DataFrame, config: dict[str, Any]) -> CheckResult:
    v, id_col = config["validation"], config["columns"]["identifier"]
    rules = {
        f"Age outside {v['age_min']}-{v['age_max']}": (df["Age"] < v["age_min"]) | (df["Age"] > v["age_max"]),
        f"CreditScore outside {v['credit_score_min']}-{v['credit_score_max']}":
            (df["CreditScore"] < v["credit_score_min"]) | (df["CreditScore"] > v["credit_score_max"]),
        f"Tenure below {v['tenure_min']}": df["Tenure"] < v["tenure_min"],
        f"Balance below {v['balance_min']}": df["Balance"] < v["balance_min"],
        f"EstimatedSalary not above {v['estimated_salary_min_exclusive']}":
            df["EstimatedSalary"] <= v["estimated_salary_min_exclusive"],
        f"NumOfProducts below {v['num_products_min']}": df["NumOfProducts"] < v["num_products_min"],
    }
    flagged = {rule: int(mask.sum()) for rule, mask in rules.items()}
    total = sum(flagged.values())
    details = {"records_per_rule": flagged}
    if total:
        any_mask = pd.concat(rules.values(), axis=1).any(axis=1)
        details["example_ids"] = _sample_ids(df, any_mask, id_col)
        return CheckResult("Plausibility bounds", WARN,
                           f"{int(any_mask.sum())} record(s) outside plausibility bounds; kept and flagged",
                           details)
    return CheckResult("Plausibility bounds", PASS,
                       "all values inside the configured plausibility bounds (age, credit score, tenure, "
                       "balance, salary, products)", details)


def _check_constant_columns(df: pd.DataFrame, config: dict[str, Any]) -> CheckResult:
    metadata = set(config["columns"]["metadata_columns"])
    constant = {c: df[c].iloc[0] for c in df.columns if df[c].nunique(dropna=False) == 1} if len(df) else {}
    unexpected = {c: v for c, v in constant.items() if c not in metadata}
    if unexpected:
        return CheckResult("Constant columns", WARN, "unexpected constant column(s) carry no information",
                           {"constant": constant})
    if constant:
        return CheckResult("Constant columns", INFO,
                           "constant metadata column(s): " + ", ".join(f"{c} = {v}" for c, v in constant.items())
                           + "; no time dimension, excluded from segmentation", {"constant": constant})
    return CheckResult("Constant columns", PASS, "no constant columns")


def _check_numeric_ranges(df: pd.DataFrame, config: dict[str, Any]) -> CheckResult:
    columns = ["CreditScore", "Age", "Tenure", "Balance", "NumOfProducts", "EstimatedSalary"]
    ranges = {c: f"{df[c].min():,.2f} to {df[c].max():,.2f}" for c in columns}
    return CheckResult("Numeric ranges", INFO, "observed minimum and maximum of numeric fields", ranges)


def _check_surname_encoding(df: pd.DataFrame) -> CheckResult:
    n = int(df["Surname"].astype("string").str.contains("?", regex=False).sum())
    if n:
        examples = df.loc[df["Surname"].astype("string").str.contains("?", regex=False), "Surname"].head(5).tolist()
        return CheckResult("Surname characters", WARN,
                           f"{n} surname(s) contain a literal '?' (possible character loss in the source "
                           "file; cause not verified). Surname is excluded from analysis, so results are "
                           "unaffected; values were not altered", {"examples": examples})
    return CheckResult("Surname characters", PASS, "no surnames contain '?'")


def _check_small_groups(df: pd.DataFrame, config: dict[str, Any]) -> CheckResult:
    small = config["statistics"]["small_group_threshold"]
    found = {}
    for column in config["validation"]["small_group_check_columns"]:
        for value, n in df[column].value_counts().items():
            if n < small:
                found[f"{column} = {value}"] = int(n)
    if found:
        return CheckResult("Small categories", INFO,
                           f"{len(found)} raw category value(s) have fewer than {small} customers: rates "
                           "for them need extra caution", found)
    return CheckResult("Small categories", PASS, f"no raw category has fewer than {small} customers")


def _check_tenure_edges(df: pd.DataFrame) -> CheckResult:
    counts = df["Tenure"].value_counts().sort_index()
    if len(counts) < 3:
        return CheckResult("Tenure distribution edges", INFO, "too few tenure values to compare")
    low, high = counts.index.min(), counts.index.max()
    interior = counts.iloc[1:-1]
    return CheckResult(
        "Tenure distribution edges", INFO,
        f"tenure {low}: {fmt_int(counts[low])} customers, tenure {high}: {fmt_int(counts[high])}; "
        f"interior years median {fmt_int(interior.median())}. The cause of the difference is NOT known "
        "and is not assumed", {"counts_by_tenure": {int(k): int(v) for k, v in counts.items()}})


# --------------------------------------------------------------------------------------
# Public entry point
# --------------------------------------------------------------------------------------
def validate_dataset(df: pd.DataFrame, config: dict[str, Any]) -> ValidationReport:
    """Run every check and return a ValidationReport. Never modifies ``df``."""
    n_rows, n_cols = df.shape
    checks = [_check_schema(df, config)]
    if checks[0].status == FAIL:
        return ValidationReport(checks, n_rows, n_cols,
                                "Remaining checks were skipped because expected columns are missing.")

    checks.append(_check_dtypes(df, config))
    if checks[-1].status == FAIL:
        return ValidationReport(checks, n_rows, n_cols,
                                "Remaining checks were skipped because column types are invalid.")

    checks.append(_check_missing(df, config))
    checks += _check_duplicates(df, config)
    checks.append(_check_binary(df, config))
    checks.append(_check_categories(df, config))
    checks += _check_target(df, config)
    checks.append(_check_plausibility(df, config))
    checks.append(_check_constant_columns(df, config))
    checks.append(_check_numeric_ranges(df, config))
    checks.append(_check_surname_encoding(df))
    checks.append(_check_small_groups(df, config))
    checks.append(_check_tenure_edges(df))
    return ValidationReport(checks, n_rows, n_cols)
