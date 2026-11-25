"""High-balance, salary, engagement and tenure analysis (descriptive only).

Beginner notes
--------------
Questions this module answers, in plain language:

* **Who are the high-balance customers, and do they churn more than comparable customers?**
  The fair comparison is High-balance vs Low-balance *among customers with a non-zero balance*
  (zero-balance customers are a different group), and *within* the same country / age band, so the
  groups being compared are alike in other ways. A **directly standardised** gap goes one step further:
  it averages the within-group gaps using the same customer mix for both groups.
* **Does churn change with the size of the balance, or with salary?** Equal-sized groups of balance
  and of salary show the shape without choosing arbitrary cut-offs.
* **Does the engagement pattern (inactive vs active) hold across segments, and across tenure?**
* **Where is the churned balance?** The *balance exposure proxy* is the balance held by customers
  who left. It is **not** lost revenue, profit or lifetime value: the dataset has no revenue data.
  Salary and balance are never equated with profitability.

Everything is a single- or two-variable view of one snapshot. Nothing here shows that a characteristic
causes churn, and no table controls for every other variable.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Sequence

import numpy as np
import pandas as pd
from scipy import stats

from . import kpis
from .analysis import AnalysisError, interaction_table, prepare_for_analysis, rate_difference
from .segmentation import assign_quantile_segment, compute_quantile_cutpoints
from .stats_utils import proportion_summary

SALARY_BAND = "SalaryBand"
BALANCE_QUANTILE = "BalanceQuantile"
ALL_LABEL = "All customers"


# --------------------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------------------
def _balance_labels(config: dict[str, Any]) -> tuple[str, str, str]:
    bal = config["segmentation"]["balance"]
    return bal["zero_label"], bal["low_label"], bal["high_label"]


def _engagement_labels(config: dict[str, Any]) -> tuple[str, str]:
    """(inactive label, active label) as shown after display labelling."""
    mapping = config["analysis"]["display_labels"][config["kpi"]["engagement_column"]]
    return mapping["0"], mapping["1"]


def _require(df: pd.DataFrame, columns: Sequence[str]) -> None:
    missing = [c for c in dict.fromkeys(columns) if c not in df.columns]
    if missing:
        raise AnalysisError(f"Missing column(s) {missing}. For derived segments, run the Phase 2 pipeline first.")


def _prepare(df: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    """Labelled copy of the data; also checks that every column used in this module exists."""
    be = config["balance_engagement"]
    needed = [config["kpi"]["balance_column"], config["kpi"]["balance_segment_column"], config["kpi"]["engagement_column"],
              be["salary_column"], be["tenure_column"]]
    for key in ("within_high_balance_variables", "stratify_high_vs_low_by", "engagement_segment_variables",
                "exposure_variables"):
        needed += be[key]
    for group in be["standardise_high_vs_low_by"]:
        needed += group
    _require(df, needed)
    return prepare_for_analysis(df, config)


def _label(value: Any) -> str:
    return "(missing)" if pd.isna(value) else str(value)


def _categorical(series: pd.Series) -> pd.Series:
    """Ordered categorical with the observed values sorted (keeps tables in a natural order)."""
    if isinstance(series.dtype, pd.CategoricalDtype):
        return series
    return pd.Series(pd.Categorical(series, categories=sorted(series.dropna().unique()), ordered=True),
                     index=series.index, name=series.name)


# --------------------------------------------------------------------------------------
# 1. Who are the high-balance customers?
# --------------------------------------------------------------------------------------
def high_balance_profile(frame: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    """Composition of High-balance customers compared with all customers, per variable and segment.

    high_share_of_segment = share of the segment's customers who are High-balance.
    """
    seg_col = config["kpi"]["balance_segment_column"]
    high = _balance_labels(config)[2]
    is_high = frame[seg_col] == high
    n_high_total, n_all_total = int(is_high.sum()), len(frame)

    rows = []
    for variable in config["balance_engagement"]["within_high_balance_variables"]:
        column = _categorical(frame[variable])
        for category in column.cat.categories:
            in_seg = column == category
            n_all, n_high = int(in_seg.sum()), int((in_seg & is_high).sum())
            pct_high = n_high / n_high_total if n_high_total else np.nan
            pct_all = n_all / n_all_total if n_all_total else np.nan
            rows.append({"variable": variable, "segment": str(category), "n_high_balance": n_high, "pct_of_high_balance": pct_high,
                         "n_all": n_all, "pct_of_all": pct_all, "diff_pp": (pct_high - pct_all) * 100,
                         "high_share_of_segment": n_high / n_all if n_all else np.nan})
    return pd.DataFrame(rows)


def churn_within_high_balance(frame: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    """Churn rate inside the High-balance group, by variable. Contributions are relative to High-balance churners."""
    seg_col = config["kpi"]["balance_segment_column"]
    high = _balance_labels(config)[2]
    subset = frame[frame[seg_col] == high]
    parts = []
    for variable in config["balance_engagement"]["within_high_balance_variables"]:
        table = kpis.segment_churn_table(subset.assign(**{variable: _categorical(subset[variable])}), variable, config)
        table = table.rename(columns={variable: "segment"})
        table["segment"] = [_label(v) for v in table["segment"]]
        table.insert(0, "variable", variable)
        parts.append(table)
    return pd.concat(parts, ignore_index=True)


# --------------------------------------------------------------------------------------
# 2. High-balance vs Low-balance, like for like
# --------------------------------------------------------------------------------------
def high_vs_low_by_stratum(frame: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    """Churn rate of High-balance minus Low-balance customers (non-zero balances only), per stratum.

    Zero-balance customers are excluded because they are a different group (and Germany has none).
    The gap is in percentage points with a Newcombe interval.
    """
    balance_col, seg_col = config["kpi"]["balance_column"], config["kpi"]["balance_segment_column"]
    _, low, high = _balance_labels(config)
    nonzero = frame[frame[balance_col] > 0]

    def row(variable: str, stratum: str, subset: pd.DataFrame) -> dict[str, Any]:
        r = rate_difference(subset, config, seg_col, high, low)
        return {"variable": variable, "stratum": stratum, "n_high": r["a"]["n"], "churn_high": r["a"]["rate"],
                "n_low": r["b"]["n"], "churn_low": r["b"]["rate"], "gap_pp": r["diff_pp"],
                "ci_low_pp": r["ci_low_pp"], "ci_high_pp": r["ci_high_pp"], "status": r["status"]}

    rows = [row("(all non-zero customers)", ALL_LABEL, nonzero)]
    for variable in config["balance_engagement"]["stratify_high_vs_low_by"]:
        column = _categorical(nonzero[variable])
        for category in column.cat.categories:
            rows.append(row(variable, str(category), nonzero[column == category]))
    return pd.DataFrame(rows)


def standardised_high_vs_low(frame: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    """Directly standardised High-balance minus Low-balance gap, for each configured set of strata.

    Idea: inside each stratum (e.g. each country) compute both churn rates; then average them with the
    SAME weights for High and Low (weight = the stratum's share of non-zero customers). Differences in
    customer mix between the two groups can no longer produce a gap by themselves.
    Strata where either group has fewer than ``min_reportable_group_size`` customers are left out and the
    weights re-scaled; ``coverage`` says what share of non-zero customers the used strata represent.
    The interval is a normal approximation (approximate).
    """
    stats_cfg = config["statistics"]
    minimum = stats_cfg["min_reportable_group_size"]
    z = stats.norm.ppf(1 - (1 - stats_cfg["confidence_level"]) / 2)
    balance_col, seg_col = config["kpi"]["balance_column"], config["kpi"]["balance_segment_column"]
    _, low, high = _balance_labels(config)

    nonzero = frame[frame[balance_col] > 0]
    flags = kpis.churn_flags(nonzero, config)
    unadjusted = rate_difference(nonzero, config, seg_col, high, low)

    results = []
    for strata in config["balance_engagement"]["standardise_high_vs_low_by"]:
        cells = []
        keyed = nonzero.assign(**{v: _categorical(nonzero[v]) for v in strata})
        for _, sub in keyed.groupby(list(strata), observed=True):
            is_high, is_low = sub[seg_col] == high, sub[seg_col] == low
            f = flags.loc[sub.index]
            cells.append({"n_h": int(is_high.sum()), "c_h": int(f[is_high].sum()),
                          "n_l": int(is_low.sum()), "c_l": int(f[is_low].sum())})
        usable = [c for c in cells if c["n_h"] >= minimum and c["n_l"] >= minimum]
        row: dict[str, Any] = {"strata": " x ".join(strata), "cells": len(cells), "cells_used": len(usable),
                               "coverage": np.nan, "unadjusted_gap_pp": unadjusted["diff_pp"],
                               "rate_high_std": np.nan, "rate_low_std": np.nan, "standardised_gap_pp": np.nan,
                               "ci_low_pp": np.nan, "ci_high_pp": np.nan}
        if usable and len(nonzero):
            sizes = np.array([c["n_h"] + c["n_l"] for c in usable], dtype=float)
            weights = sizes / sizes.sum()
            p_h = np.array([c["c_h"] / c["n_h"] for c in usable])
            p_l = np.array([c["c_l"] / c["n_l"] for c in usable])
            n_h = np.array([c["n_h"] for c in usable], dtype=float)
            n_l = np.array([c["n_l"] for c in usable], dtype=float)
            gap = float((weights * (p_h - p_l)).sum())
            se = math.sqrt(float((weights**2 * (p_h * (1 - p_h) / n_h + p_l * (1 - p_l) / n_l)).sum()))
            row.update(coverage=float(sizes.sum() / len(nonzero)), rate_high_std=float((weights * p_h).sum()),
                       rate_low_std=float((weights * p_l).sum()), standardised_gap_pp=gap * 100,
                       ci_low_pp=(gap - z * se) * 100, ci_high_pp=(gap + z * se) * 100)
        results.append(row)
    return pd.DataFrame(results)


# --------------------------------------------------------------------------------------
# 3. Balance level (equal-sized groups) and salary
# --------------------------------------------------------------------------------------
def churn_by_balance_group(frame: pd.DataFrame, config: dict[str, Any]) -> tuple[pd.DataFrame, list[float]]:
    """Churn rate across equal-sized groups of NON-ZERO balances. Returns (table, cut points)."""
    balance_col = config["kpi"]["balance_column"]
    n_groups = config["balance_engagement"]["balance_quantile_groups"]
    nonzero = frame[frame[balance_col] > 0].copy()
    if nonzero.empty:
        raise AnalysisError("There are no customers with a non-zero balance")
    cuts = compute_quantile_cutpoints(nonzero[balance_col], n_groups)
    labels = [f"Q{i}" for i in range(1, n_groups + 1)]
    labels[0], labels[-1] = f"{labels[0]} (lowest)", f"{labels[-1]} (highest)"
    nonzero[BALANCE_QUANTILE] = assign_quantile_segment(nonzero[balance_col], cuts, labels)

    table = kpis.segment_churn_table(nonzero, BALANCE_QUANTILE, config).rename(columns={BALANCE_QUANTILE: "group"})
    spans = nonzero.groupby(BALANCE_QUANTILE, observed=False)[balance_col].agg(balance_min="min", balance_max="max")
    table["balance_min"] = [spans.loc[g, "balance_min"] for g in table["group"]]
    table["balance_max"] = [spans.loc[g, "balance_max"] for g in table["group"]]
    table["group"] = table["group"].astype(str)
    return table, cuts


def salary_groups(frame: pd.DataFrame, config: dict[str, Any]) -> tuple[pd.Series, list[float]]:
    """Equal-sized salary groups (cut points computed from the data, right-closed). Returns (labels, cut points)."""
    be = config["balance_engagement"]
    cuts = compute_quantile_cutpoints(frame[be["salary_column"]], be["salary_groups"])
    return assign_quantile_segment(frame[be["salary_column"]], cuts, be["salary_labels"]), cuts


def salary_vs_balance(frame: pd.DataFrame, config: dict[str, Any]) -> dict[str, Any]:
    """Salary groups: churn rates, salary x balance-segment grids, and the salary-balance rank correlation.

    Spearman's rho is a rank correlation (-1 to +1; 0 = no monotone relationship). Salary and balance are
    **not** treated as measures of profitability or lifetime value.
    """
    be = config["balance_engagement"]
    balance_col, seg_col = config["kpi"]["balance_column"], config["kpi"]["balance_segment_column"]
    groups, cuts = salary_groups(frame, config)
    work = frame.assign(**{SALARY_BAND: groups})

    overview = kpis.segment_churn_table(work, SALARY_BAND, config).rename(columns={SALARY_BAND: "group"})
    overview["group"] = overview["group"].astype(str)
    grid_all = interaction_table(work, config, SALARY_BAND, seg_col)
    grid_nonzero = interaction_table(work[work[balance_col] > 0], config, SALARY_BAND, seg_col)

    def spearman(subset: pd.DataFrame) -> tuple[int, float, float]:
        constant = subset[be["salary_column"]].nunique() < 2 or subset[balance_col].nunique() < 2
        if len(subset) < 3 or constant:       # a rank correlation is undefined without variation in both columns
            return len(subset), np.nan, np.nan
        res = stats.spearmanr(subset[be["salary_column"]], subset[balance_col])
        return len(subset), float(res.statistic), float(res.pvalue)

    n_nz, rho_nz, p_nz = spearman(work[work[balance_col] > 0])
    n_all, rho_all, p_all = spearman(work)
    return {"overview": overview, "grid_all": grid_all, "grid_non_zero": grid_nonzero, "cutpoints": cuts,
            "n_non_zero": n_nz, "rho_non_zero": rho_nz, "p_non_zero": p_nz,
            "n_all": n_all, "rho_all": rho_all, "p_all": p_all}


# --------------------------------------------------------------------------------------
# 4. Engagement and tenure
# --------------------------------------------------------------------------------------
def engagement_by_segment(frame: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    """Engagement Drop Indicator (inactive churn rate minus active churn rate, in pp) inside every segment."""
    eng_col = config["kpi"]["engagement_column"]
    inactive, active = _engagement_labels(config)

    def row(variable: str, segment: str, subset: pd.DataFrame) -> dict[str, Any]:
        r = rate_difference(subset, config, eng_col, inactive, active)
        return {"variable": variable, "segment": segment, "n_inactive": r["a"]["n"], "churn_inactive": r["a"]["rate"],
                "n_active": r["b"]["n"], "churn_active": r["b"]["rate"], "edi_pp": r["diff_pp"],
                "ci_low_pp": r["ci_low_pp"], "ci_high_pp": r["ci_high_pp"], "status": r["status"]}

    rows = [row("(all customers)", ALL_LABEL, frame)]
    for variable in config["balance_engagement"]["engagement_segment_variables"]:
        column = _categorical(frame[variable])
        for category in column.cat.categories:
            rows.append(row(variable, str(category), frame[column == category]))
    return pd.DataFrame(rows)


def inactive_share(frame: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    """Share of customers who are inactive, per segment, with a Wilson interval (who is disengaged?)."""
    eng_col = config["kpi"]["engagement_column"]
    inactive_label = _engagement_labels(config)[0]
    rows = []
    for variable in config["balance_engagement"]["engagement_segment_variables"]:
        column = _categorical(frame[variable])
        for category in column.cat.categories:
            subset = frame[column == category]
            s = proportion_summary(int((subset[eng_col] == inactive_label).sum()), len(subset), config)
            rows.append({"variable": variable, "segment": str(category), "n": s["n"], "inactive": s["events"],
                         "share_inactive": s["rate"], "ci_low": s["ci_low"], "ci_high": s["ci_high"], "status": s["status"]})
    return pd.DataFrame(rows)


def engagement_grids(frame: pd.DataFrame, config: dict[str, Any]) -> dict[str, pd.DataFrame]:
    """Churn rate by engagement x tenure group, and by engagement x number of products."""
    eng_col = config["kpi"]["engagement_column"]
    return {"tenure_group": interaction_table(frame, config, "TenureGroup", eng_col),
            "products": interaction_table(frame, config, "NumOfProducts", eng_col)}


def tenure_curve(frame: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    """Churn rate for each individual tenure year, with intervals and group sizes."""
    tenure_col = config["balance_engagement"]["tenure_column"]
    work = frame.assign(**{tenure_col: _categorical(frame[tenure_col])})
    table = kpis.segment_churn_table(work, tenure_col, config).rename(columns={tenure_col: "tenure"})
    table["tenure"] = [int(v) for v in table["tenure"]]
    return table


# --------------------------------------------------------------------------------------
# 5. Balance exposure proxy (NOT lost revenue)
# --------------------------------------------------------------------------------------
def exposure_by_variable(frame: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    """Where is the balance held by churned customers? One row per segment of each configured variable.

    This is an EXPOSURE PROXY: balances belonging to customers who exited. It is not lost revenue or profit.
    share_of_all_balance lets you compare a segment's share of churned balance with its share of all balance.
    """
    total_balance = float(frame[config["kpi"]["balance_column"]].sum())
    parts = []
    for variable in config["balance_engagement"]["exposure_variables"]:
        work = frame.assign(**{variable: _categorical(frame[variable])})
        table = kpis.balance_exposure(work, config, by=variable).rename(columns={variable: "segment"})
        table["segment"] = [_label(v) for v in table["segment"]]
        table.insert(0, "variable", variable)
        table["share_of_all_balance"] = table["segment_balance"] / total_balance if total_balance > 0 else np.nan
        parts.append(table)
    return pd.concat(parts, ignore_index=True)


def churned_balance_concentration(frame: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    """Share of churned balance held by the top X% of churned customers (largest balances first)."""
    balance_col = config["kpi"]["balance_column"]
    flags = kpis.churn_flags(frame, config)
    balances = frame.loc[flags, balance_col].sort_values(ascending=False).to_numpy(dtype=float)
    total, n = float(balances.sum()), len(balances)
    rows = []
    for share in config["balance_engagement"]["concentration_top_shares"]:
        k = int(math.ceil(share * n)) if n else 0
        held = float(balances[:k].sum())
        rows.append({"top_share_of_churned_customers": share, "customers": k, "balance_held": held,
                     "share_of_churned_balance": held / total if total > 0 else np.nan,
                     "smallest_balance_in_group": float(balances[k - 1]) if k else np.nan})
    table = pd.DataFrame(rows)
    table.attrs["churned_customers"] = n
    table.attrs["churned_with_zero_balance"] = int((balances == 0).sum())
    return table


def balance_engagement_matrix(frame: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    """Balance segment x engagement: churn rate, churn contribution and churned balance (exposure proxy)."""
    seg_col, eng_col = config["kpi"]["balance_segment_column"], config["kpi"]["engagement_column"]
    rates = kpis.segment_churn_table(frame, [seg_col, eng_col], config)
    exposure = kpis.balance_exposure(frame, config, by=[seg_col, eng_col])
    merged = rates.merge(exposure[[seg_col, eng_col, "segment_balance", "churned_balance",
                                   "churned_share_of_segment_balance", "share_of_all_churned_balance"]],
                         on=[seg_col, eng_col], how="left")
    for column in (seg_col, eng_col):
        merged[column] = [_label(v) for v in merged[column]]
    return merged


# --------------------------------------------------------------------------------------
# Everything together
# --------------------------------------------------------------------------------------
@dataclass
class BalanceEngagementAnalysis:
    high_balance_profile: pd.DataFrame
    churn_within_high_balance: pd.DataFrame
    high_vs_low_by_stratum: pd.DataFrame
    standardised_high_vs_low: pd.DataFrame
    balance_group_churn: pd.DataFrame
    balance_group_cutpoints: list[float]
    salary: dict[str, Any]
    engagement_by_segment: pd.DataFrame
    inactive_share: pd.DataFrame
    engagement_tenure_grid: pd.DataFrame
    engagement_products_grid: pd.DataFrame
    tenure_curve: pd.DataFrame
    exposure_by_variable: pd.DataFrame
    concentration: pd.DataFrame
    balance_engagement_matrix: pd.DataFrame
    countries_without_zero_balance: list[str]


def run_balance_engagement_analysis(df: pd.DataFrame, config: dict[str, Any]) -> BalanceEngagementAnalysis:
    """Run every Phase 5 analysis on the processed customers table."""
    frame = _prepare(df, config)
    geo_col, balance_col = config["kpi"]["geography_column"], config["kpi"]["balance_column"]
    zero_by_country = (frame[balance_col] == 0).groupby(_categorical(frame[geo_col]), observed=False).sum()
    no_zero = [str(c) for c, n in zero_by_country.items() if n == 0]
    quantile_table, cuts = churn_by_balance_group(frame, config)
    grids = engagement_grids(frame, config)
    return BalanceEngagementAnalysis(
        high_balance_profile=high_balance_profile(frame, config),
        churn_within_high_balance=churn_within_high_balance(frame, config),
        high_vs_low_by_stratum=high_vs_low_by_stratum(frame, config),
        standardised_high_vs_low=standardised_high_vs_low(frame, config),
        balance_group_churn=quantile_table, balance_group_cutpoints=cuts,
        salary=salary_vs_balance(frame, config),
        engagement_by_segment=engagement_by_segment(frame, config),
        inactive_share=inactive_share(frame, config),
        engagement_tenure_grid=grids["tenure_group"], engagement_products_grid=grids["products"],
        tenure_curve=tenure_curve(frame, config),
        exposure_by_variable=exposure_by_variable(frame, config),
        concentration=churned_balance_concentration(frame, config),
        balance_engagement_matrix=balance_engagement_matrix(frame, config), countries_without_zero_balance=no_zero)
