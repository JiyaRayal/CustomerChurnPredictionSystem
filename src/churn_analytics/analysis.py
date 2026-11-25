"""Segment-level churn analysis (descriptive only).

Beginner notes
--------------
This module answers: "which customer groups churn more or less, and by how much?"

* It builds on ``kpis.py``: every rate comes with its group size, a confidence interval,
  and the project's small-group flags. Empty groups are n/a, never 0.
* **Rate vs contribution.** The *rate* is the share of a group that churned. The
  *contribution* is the group's share of all churners. ``contribution - share`` shows
  whether a group has more (or fewer) churners than its size alone would suggest.
* **Association strength** uses Cramer's V (0 = no association, 1 = perfect). With
  thousands of customers almost anything is "statistically significant", so the effect
  size is what to read. This describes how variables go together; it does not say why.
* **Overlapping variables.** Age, products, balance, activity and country are related to
  each other, so each table below is a *single-variable* view. No table here controls for
  the others, and none shows that a characteristic causes churn.
"""

from __future__ import annotations

import math
from bisect import bisect_right
from dataclasses import dataclass
from typing import Any, Sequence

import numpy as np
import pandas as pd
from scipy import stats

from . import kpis
from .stats_utils import (STATUS_EMPTY, STATUS_OK, STATUS_SMALL, STATUS_WITHHELD, chi_square_independence,
                          newcombe_difference_interval, proportion_summary)

MISSING_LABEL = "(missing)"


class AnalysisError(ValueError):
    """Raised when the data cannot support a requested analysis."""


# --------------------------------------------------------------------------------------
# Preparation
# --------------------------------------------------------------------------------------
def prepare_for_analysis(df: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    """Return a COPY with readable labels for 0/1 columns and fixed category order everywhere.

    Values are never changed or dropped: only the *labels shown* in tables differ
    (e.g. IsActiveMember 0/1 becomes Inactive/Active).
    """
    analysis = config["analysis"]
    target = config["columns"]["target"]
    needed = list(dict.fromkeys(analysis["segment_variables"] + [analysis["sensitivity_variable"], target]))
    missing = [c for c in needed if c not in df.columns]
    if missing:
        raise AnalysisError(f"Missing column(s) {missing}. For derived segments, run the Phase 2 pipeline first.")

    out = df.copy()
    labelled = analysis["display_labels"]
    for column, mapping in labelled.items():
        if column not in out.columns:
            continue
        already = out[column].dtype
        if isinstance(already, pd.CategoricalDtype) and list(already.categories) == list(mapping.values()):
            continue  # already labelled: calling this function twice is harmless
        text = out[column].astype("Int64").astype(str)
        mapped = text.map(mapping)
        if mapped.isna().any():
            raise AnalysisError(f"{column} has values not covered by analysis.display_labels")
        out[column] = pd.Categorical(mapped, categories=list(mapping.values()), ordered=True)

    for column in analysis["segment_variables"]:
        if column not in labelled and not isinstance(out[column].dtype, pd.CategoricalDtype):
            out[column] = pd.Categorical(out[column], categories=sorted(out[column].dropna().unique()), ordered=True)
    return out


def _segment_label(value: Any) -> str:
    return MISSING_LABEL if pd.isna(value) else str(value)


# --------------------------------------------------------------------------------------
# 1. Segment overview: rate, contribution, share, ratio to overall
# --------------------------------------------------------------------------------------
def segment_overview(df: pd.DataFrame, config: dict[str, Any], variables: Sequence[str] | None = None) -> pd.DataFrame:
    """One row per segment of every variable.

    rate_ratio                 = segment churn rate / overall churn rate (1.00 = average)
    contribution_minus_share_pp = (churn contribution - customer share) x 100
    """
    variables = list(variables or config["analysis"]["segment_variables"])
    frame = df if all(isinstance(df[v].dtype, pd.CategoricalDtype) for v in variables if v in df) else \
        prepare_for_analysis(df, config)
    overall = kpis.overall_churn_rate(frame, config)["rate"]

    parts = []
    for variable in variables:
        table = kpis.segment_churn_table(frame, variable, config)
        table = table.rename(columns={variable: "segment"})
        table["segment"] = [_segment_label(v) for v in table["segment"]]
        table.insert(0, "variable", variable)
        table["overall_rate"] = overall
        if overall is None or overall == 0:
            table["rate_ratio"] = np.nan
        else:
            table["rate_ratio"] = table["churn_rate"] / overall
        table["contribution_minus_share_pp"] = (table["churn_contribution"] - table["share_of_customers"]) * 100
        parts.append(table)
    return pd.concat(parts, ignore_index=True)


# --------------------------------------------------------------------------------------
# 2. Association strength (Cramer's V) per variable
# --------------------------------------------------------------------------------------
def effect_label(value: float, cutoffs: Sequence[float], labels: Sequence[str]) -> str:
    """Plain-language label for an effect size. A value equal to a cut-off goes in the higher band."""
    return "n/a" if value is None or pd.isna(value) else labels[bisect_right(list(cutoffs), value)]


def association_table(df: pd.DataFrame, config: dict[str, Any], variables: Sequence[str] | None = None,
                      overview: pd.DataFrame | None = None) -> pd.DataFrame:
    """Chi-square test and Cramer's V between each variable and churn, ranked by V (largest first)."""
    analysis = config["analysis"]
    variables = list(variables or analysis["segment_variables"])
    frame = prepare_for_analysis(df, config)
    flags = kpis.churn_flags(frame, config)
    overview = overview if overview is not None else segment_overview(frame, config, variables)

    rows = []
    for variable in variables:
        segments = frame[variable].astype(object).where(frame[variable].notna(), MISSING_LABEL)
        counts = pd.crosstab(segments, flags.map({False: "retained", True: "churned"}))
        counts = counts.reindex(columns=["retained", "churned"], fill_value=0)
        counts = counts[counts.sum(axis=1) > 0]
        row: dict[str, Any] = {"variable": variable, "groups": int(len(counts))}
        try:
            test = chi_square_independence(counts)
        except ValueError:
            test = None
        if test is None:
            row.update(chi2=np.nan, dof=np.nan, p_value=np.nan, cramers_v=np.nan, min_expected_count=np.nan,
                       note="association not computable (fewer than 2 groups, or only one outcome present)")
        else:
            row.update(chi2=test["chi2"], dof=test["dof"], p_value=test["p_value"], cramers_v=test["cramers_v"],
                       min_expected_count=test["min_expected_count"],
                       note="some expected counts below 5; chi-square approximation is less reliable"
                       if test["min_expected_count"] < 5 else "")
        row["effect"] = effect_label(row["cramers_v"], analysis["effect_size_cutoffs"], analysis["effect_size_labels"])

        rated = overview[(overview["variable"] == variable) & overview["churn_rate"].notna()]
        if rated.empty:
            row.update(highest_segment=None, highest_rate=np.nan, highest_status=None, lowest_segment=None,
                       lowest_rate=np.nan, lowest_status=None, spread_pp=np.nan)
        else:
            high, low = rated.loc[rated["churn_rate"].idxmax()], rated.loc[rated["churn_rate"].idxmin()]
            row.update(highest_segment=high["segment"], highest_rate=high["churn_rate"], highest_status=high["status"],
                       lowest_segment=low["segment"], lowest_rate=low["churn_rate"], lowest_status=low["status"],
                       spread_pp=(high["churn_rate"] - low["churn_rate"]) * 100)
        rows.append(row)
    return pd.DataFrame(rows).sort_values("cramers_v", ascending=False, na_position="last").reset_index(drop=True)


# --------------------------------------------------------------------------------------
# 3. Difference between two groups (e.g. Female vs Male)
# --------------------------------------------------------------------------------------
def rate_difference(df: pd.DataFrame, config: dict[str, Any], column: str, group_a: Any, group_b: Any) -> dict[str, Any]:
    """Churn rate of group A minus group B, in percentage points, with a Newcombe interval."""
    if column not in df.columns:
        raise AnalysisError(f"Missing column {column}")
    flags = kpis.churn_flags(df, config)
    in_a, in_b = df[column] == group_a, df[column] == group_b
    sa = proportion_summary(int(flags[in_a].sum()), int(in_a.sum()), config)
    sb = proportion_summary(int(flags[in_b].sum()), int(in_b.sum()), config)
    result: dict[str, Any] = {"group_a": group_a, "group_b": group_b, "a": sa, "b": sb,
                              "diff_pp": None, "ci_low_pp": None, "ci_high_pp": None}
    if sa["n"] == 0 or sb["n"] == 0:
        result["status"] = STATUS_EMPTY
    elif sa["rate"] is None or sb["rate"] is None:
        result["status"] = STATUS_WITHHELD
    else:
        diff, low, high = newcombe_difference_interval(sa["events"], sa["n"], sb["events"], sb["n"],
                                                       config["statistics"]["confidence_level"])
        result.update(diff_pp=diff * 100, ci_low_pp=low * 100, ci_high_pp=high * 100)
        result["status"] = STATUS_SMALL if STATUS_SMALL in (sa["status"], sb["status"]) else STATUS_OK
    return result


def gender_comparison(df: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    """Gap between the first and second configured gender (Female - Male), overall and by country."""
    gender_col = config["analysis"]["gender_column"]
    geo_col = config["kpi"]["geography_column"]
    categories = list(config["columns"]["categorical_expected"][gender_col])
    if len(categories) != 2:
        raise AnalysisError("gender comparison needs exactly two configured gender categories")
    first, second = categories
    countries = list(config["columns"]["categorical_expected"][geo_col])

    scopes = [("All customers", df)] + [(c, df[df[geo_col].astype(str) == c]) for c in countries]
    rows = []
    for scope, subset in scopes:
        r = rate_difference(subset, config, gender_col, first, second)
        rows.append({"scope": scope, f"n {first}": r["a"]["n"], f"churn {first}": r["a"]["rate"],
                     f"n {second}": r["b"]["n"], f"churn {second}": r["b"]["rate"],
                     f"gap_pp ({first} - {second})": r["diff_pp"], "ci_low_pp": r["ci_low_pp"],
                     "ci_high_pp": r["ci_high_pp"], "status": r["status"]})
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------------------
# 4. Two-variable drill-downs (Geography x age, Geography x balance segment)
# --------------------------------------------------------------------------------------
def interaction_table(df: pd.DataFrame, config: dict[str, Any], row_var: str | None = None,
                      col_var: str | None = None) -> pd.DataFrame:
    """Churn rate in every row_var x col_var cell, with sizes, intervals and flags.

    Empty cells are kept (n = 0, rate n/a). Contributions and shares are relative to the rows passed in.
    """
    analysis = config["analysis"]
    row_var, col_var = row_var or analysis["interaction_row"], col_var or analysis["interaction_col"]
    frame = prepare_for_analysis(df, config) if any(
        not isinstance(df[v].dtype, pd.CategoricalDtype) for v in (row_var, col_var) if v in df) else df
    table = kpis.segment_churn_table(frame, [row_var, col_var], config)
    for column in (row_var, col_var):
        table[column] = [_segment_label(v) for v in table[column]]
    return table


# --------------------------------------------------------------------------------------
# 5. Churned vs retained profiles
# --------------------------------------------------------------------------------------
def _standardised_difference(churned: pd.Series, retained: pd.Series, z: float) -> tuple[float, float, float]:
    """Cohen's d (churned minus retained, pooled SD) with an approximate interval."""
    n1, n2 = len(churned), len(retained)
    if n1 < 2 or n2 < 2:
        return np.nan, np.nan, np.nan
    pooled_var = ((n1 - 1) * churned.var(ddof=1) + (n2 - 1) * retained.var(ddof=1)) / (n1 + n2 - 2)
    if pooled_var <= 0:
        return np.nan, np.nan, np.nan
    d = (churned.mean() - retained.mean()) / math.sqrt(pooled_var)
    se = math.sqrt((n1 + n2) / (n1 * n2) + d**2 / (2 * (n1 + n2)))
    return d, d - z * se, d + z * se


def profile_comparison(df: pd.DataFrame, config: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Compare churned and retained customers.

    Returns (numeric, categorical):
    * numeric: mean/median of each numeric column for both groups, plus Cohen's d (churned - retained).
    * categorical: each segment's share of retained customers vs share of churned customers.
    """
    analysis = config["analysis"]
    flags = kpis.churn_flags(df, config)
    z = stats.norm.ppf(1 - (1 - config["statistics"]["confidence_level"]) / 2)

    numeric_rows = []
    for column in analysis["numeric_profile_columns"]:
        if column not in df.columns:
            raise AnalysisError(f"Missing column {column}")
        churned, retained = df.loc[flags, column], df.loc[~flags, column]
        d, low, high = _standardised_difference(churned, retained, z)
        numeric_rows.append({
            "column": column, "mean_churned": churned.mean(), "mean_retained": retained.mean(),
            "median_churned": churned.median(), "median_retained": retained.median(),
            "cohens_d": d, "d_ci_low": low, "d_ci_high": high,
            "effect": effect_label(abs(d), analysis["smd_cutoffs"], analysis["effect_size_labels"])})

    frame = prepare_for_analysis(df, config)
    n_churned, n_retained = int(flags.sum()), int((~flags).sum())
    cat_rows = []
    for variable in analysis["segment_variables"]:
        for segment in frame[variable].cat.categories:
            in_seg = frame[variable] == segment
            c, r = int((in_seg & flags).sum()), int((in_seg & ~flags).sum())
            pc = c / n_churned if n_churned else np.nan
            pr = r / n_retained if n_retained else np.nan
            cat_rows.append({"variable": variable, "segment": str(segment), "n_retained": r, "n_churned": c,
                             "pct_of_retained": pr, "pct_of_churned": pc, "diff_pp": (pc - pr) * 100})
    return pd.DataFrame(numeric_rows), pd.DataFrame(cat_rows)


# --------------------------------------------------------------------------------------
# 6. Everything together
# --------------------------------------------------------------------------------------
@dataclass
class SegmentAnalysis:
    overview: pd.DataFrame
    association: pd.DataFrame
    gender: pd.DataFrame
    geography_age_all: pd.DataFrame
    geography_age_non_zero: pd.DataFrame
    geography_balance: pd.DataFrame
    credit_sensitivity_overview: pd.DataFrame
    credit_sensitivity_association: pd.DataFrame
    profile_numeric: pd.DataFrame
    profile_categorical: pd.DataFrame


def run_segment_analysis(df: pd.DataFrame, config: dict[str, Any]) -> SegmentAnalysis:
    """Run every Phase 4 analysis on the processed customers table."""
    analysis = config["analysis"]
    balance_col = config["kpi"]["balance_column"]
    segment_col = config["kpi"]["balance_segment_column"]
    frame = prepare_for_analysis(df, config)

    overview = segment_overview(frame, config)
    association = association_table(frame, config, overview=overview)

    credit_vars = [v for v in ("CreditScoreBand", analysis["sensitivity_variable"]) if v in frame.columns]
    credit_overview = segment_overview(frame, config, credit_vars)
    credit_assoc = association_table(frame, config, credit_vars, overview=credit_overview)

    numeric, categorical = profile_comparison(df, config)
    return SegmentAnalysis(
        overview=overview, association=association, gender=gender_comparison(frame, config),
        geography_age_all=interaction_table(frame, config),
        geography_age_non_zero=interaction_table(frame[frame[balance_col] > 0], config),
        geography_balance=interaction_table(frame, config, analysis["interaction_row"], segment_col),
        credit_sensitivity_overview=credit_overview, credit_sensitivity_association=credit_assoc,
        profile_numeric=numeric, profile_categorical=categorical)
