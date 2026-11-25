"""KPI functions. The exact definitions live in docs/kpi_definitions.md and must match this code.

Beginner notes
--------------
* Every function takes a DataFrame (the processed customers table, or any filtered part of
  it) and the project config. The KPIs describe **whatever rows you pass in**. If a
  dashboard filters to "Germany, age 46-60", then "total churned" in a contribution
  figure means "total churned among those filtered customers".
* **Empty is not zero.** If there are no customers in a group the rate is undefined and is
  returned as ``None`` with a status explaining why. A real 0% means "customers existed and
  none churned".
* **Small groups** follow the config: n below ``small_group_threshold`` is flagged; n below
  ``min_reportable_group_size`` has its rate withheld (counts are still returned).
* **No silent row loss.** Group tables are built with ``dropna=False`` so every customer is
  counted, and the code checks that group sizes add back up to the total.
* These are **descriptive associations** in one snapshot. None of them shows that a segment
  characteristic *causes* churn.
"""

from __future__ import annotations

from typing import Any, Sequence

import numpy as np
import pandas as pd

from .stats_utils import (STATUS_EMPTY, STATUS_OK, STATUS_SMALL, STATUS_WITHHELD,
                          newcombe_difference_interval, proportion_summary)

STATUS_OVERALL_ZERO = "n/a (overall churn rate is 0)"
STATUS_OVERALL_UNAVAILABLE = "n/a (overall rate unavailable)"


class KPIError(ValueError):
    """Raised when the data cannot support a KPI (missing column, invalid target, ...)."""


# --------------------------------------------------------------------------------------
# Input checks
# --------------------------------------------------------------------------------------
def _require_columns(df: pd.DataFrame, columns: Sequence[str]) -> None:
    missing = [c for c in columns if c not in df.columns]
    if missing:
        raise KPIError(f"Missing column(s) {missing}. For derived segments, run the Phase 2 pipeline first.")


def churn_flags(df: pd.DataFrame, config: dict[str, Any]) -> pd.Series:
    """Boolean Series: True where the customer churned. Refuses invalid target values."""
    target, churn_value = config["columns"]["target"], config["columns"]["churn_value"]
    _require_columns(df, [target])
    values = df[target]
    if values.isna().any():
        raise KPIError(f"{target} has {int(values.isna().sum())} missing value(s); churn cannot be measured")
    if not values.isin([0, 1]).all():
        raise KPIError(f"{target} must contain only 0 and 1")
    return values == churn_value


def _binary_column(df: pd.DataFrame, column: str) -> pd.Series:
    _require_columns(df, [column])
    values = df[column]
    if values.isna().any() or not values.isin([0, 1]).all():
        raise KPIError(f"{column} must be a complete 0/1 column")
    return values


# --------------------------------------------------------------------------------------
# 1. Overall Churn Rate
# --------------------------------------------------------------------------------------
def overall_churn_rate(df: pd.DataFrame, config: dict[str, Any]) -> dict[str, Any]:
    """Overall Churn Rate = churned customers / all customers (valid rows passed in)."""
    flags = churn_flags(df, config)
    return {"kpi": "Overall Churn Rate", **proportion_summary(int(flags.sum()), len(df), config)}


# --------------------------------------------------------------------------------------
# 2 + 3. Segment Churn Rate and Churn Contribution
# --------------------------------------------------------------------------------------
def segment_churn_table(df: pd.DataFrame, by: str | Sequence[str], config: dict[str, Any]) -> pd.DataFrame:
    """Churn rate, churn contribution and customer share for every segment of ``by``.

    * Segment Churn Rate  = churned in segment / all customers in segment
    * Churn Contribution  = churned in segment / all churned customers
    * Share of customers  = customers in segment / all customers
    Pass a list for ``by`` to drill down (e.g. ["Geography", "AgeBand"]). Empty combinations
    of categorical columns are kept, with n = 0 and an undefined (n/a) rate.
    """
    columns = [by] if isinstance(by, str) else list(by)
    _require_columns(df, columns)
    flags = churn_flags(df, config)
    total_n, total_churned = len(df), int(flags.sum())

    work = df[columns].copy()
    work["_churned"] = flags.astype(int)
    grouped = (work.groupby(columns, observed=False, dropna=False)
               .agg(n=("_churned", "size"), churned=("_churned", "sum")).reset_index())
    if int(grouped["n"].sum()) != total_n:  # safety net: no customer may be lost or double counted
        raise KPIError("Segment sizes do not add up to the number of customers")

    summaries = [proportion_summary(int(r.churned), int(r.n), config) for r in grouped.itertuples()]
    grouped["churn_rate"] = [s["rate"] for s in summaries]
    grouped["ci_low"] = [s["ci_low"] for s in summaries]
    grouped["ci_high"] = [s["ci_high"] for s in summaries]
    grouped["status"] = [s["status"] for s in summaries]
    grouped["share_of_customers"] = grouped["n"] / total_n if total_n else np.nan
    grouped["churn_contribution"] = grouped["churned"] / total_churned if total_churned else np.nan
    for column in ("churn_rate", "ci_low", "ci_high"):
        grouped[column] = grouped[column].astype(float)
    return grouped


# --------------------------------------------------------------------------------------
# 4. Geographic Risk Index
# --------------------------------------------------------------------------------------
def geographic_risk_index(df: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    """Geographic Risk Index = country churn rate / overall churn rate.

    1.0 = same as overall; 1.5 = 50% higher. Undefined (n/a) when the overall churn rate is
    0 or unavailable, or when the country's own rate is unavailable.

    The index interval divides the country's Wilson interval by the overall rate treated as
    a fixed number. This is an approximation: each country is part of the overall figure
    (so they are not independent), and the overall rate has its own small uncertainty.
    """
    geo = config["kpi"]["geography_column"]
    _require_columns(df, [geo])
    work = df.copy()
    expected = config["columns"]["categorical_expected"].get(geo)
    if expected:  # keep every configured country in the table, even if it has no customers
        work[geo] = pd.Categorical(work[geo], categories=expected)

    overall = overall_churn_rate(work, config)
    table = segment_churn_table(work, geo, config)
    base = overall["rate"]
    table["overall_rate"] = base

    index, low, high, note = [], [], [], []
    for row in table.itertuples():
        rate = row.churn_rate
        if base is None:
            index.append(None); low.append(None); high.append(None); note.append(STATUS_OVERALL_UNAVAILABLE)
        elif base == 0:
            index.append(None); low.append(None); high.append(None); note.append(STATUS_OVERALL_ZERO)
        elif pd.isna(rate):
            index.append(None); low.append(None); high.append(None); note.append(f"n/a (group: {row.status})")
        else:
            index.append(rate / base); low.append(row.ci_low / base); high.append(row.ci_high / base)
            note.append(row.status)
    table["risk_index"] = pd.Series(index, dtype=float)
    table["index_ci_low"] = pd.Series(low, dtype=float)
    table["index_ci_high"] = pd.Series(high, dtype=float)
    table["index_note"] = note
    return table


# --------------------------------------------------------------------------------------
# 5. Engagement Drop Indicator
# --------------------------------------------------------------------------------------
def engagement_drop_indicator(df: pd.DataFrame, config: dict[str, Any]) -> dict[str, Any]:
    """Engagement Drop Indicator = churn rate of inactive members - churn rate of active members.

    Reported in percentage points (pp). The interval uses Newcombe's hybrid score method.
    Caution: inactivity may be a *symptom* of a customer already deciding to leave, so the
    indicator describes an association and does not show which way any influence runs.
    """
    column = config["kpi"]["engagement_column"]
    engagement = _binary_column(df, column)
    flags = churn_flags(df, config)

    inactive, active = engagement == 0, engagement == 1
    s_in = proportion_summary(int(flags[inactive].sum()), int(inactive.sum()), config)
    s_ac = proportion_summary(int(flags[active].sum()), int(active.sum()), config)

    result: dict[str, Any] = {"kpi": "Engagement Drop Indicator", "inactive": s_in, "active": s_ac,
                              "edi_pp": None, "ci_low_pp": None, "ci_high_pp": None}
    if s_in["n"] == 0 or s_ac["n"] == 0:
        result["status"] = STATUS_EMPTY
    elif s_in["rate"] is None or s_ac["rate"] is None:
        result["status"] = STATUS_WITHHELD
    else:
        diff, low, high = newcombe_difference_interval(
            s_in["events"], s_in["n"], s_ac["events"], s_ac["n"], config["statistics"]["confidence_level"])
        result.update(edi_pp=diff * 100, ci_low_pp=low * 100, ci_high_pp=high * 100)
        small = STATUS_SMALL in (s_in["status"], s_ac["status"])
        result["status"] = STATUS_SMALL if small else STATUS_OK
    return result


# --------------------------------------------------------------------------------------
# 6. High-Balance Churn Rate (the brief's "High-Value Churn Ratio") and balance exposure
# --------------------------------------------------------------------------------------
def balance_exposure(df: pd.DataFrame, config: dict[str, Any],
                     by: str | Sequence[str] | None = None) -> pd.DataFrame:
    """Balance EXPOSURE PROXY: total balance held by churned customers (overall or per segment).

    This is NOT lost revenue, profit or lifetime value: the dataset has no revenue, margin,
    fee or interest information. It only shows how much account balance belonged to
    customers who exited.
    """
    balance_col = config["kpi"]["balance_column"]
    columns = [] if by is None else ([by] if isinstance(by, str) else list(by))
    _require_columns(df, columns + [balance_col])
    if df[balance_col].isna().any():
        raise KPIError(f"{balance_col} has missing values; exposure cannot be computed")
    flags = churn_flags(df, config)

    work = df[columns + [balance_col]].copy()
    work["_churned"] = flags.astype(int)
    work["_churned_balance"] = work[balance_col].where(flags, 0.0)
    if columns:
        grouped = (work.groupby(columns, observed=False, dropna=False)
                   .agg(n=("_churned", "size"), churned=("_churned", "sum"),
                        segment_balance=(balance_col, "sum"), churned_balance=("_churned_balance", "sum"))
                   .reset_index())
    else:
        grouped = pd.DataFrame([{"segment": "All customers", "n": len(work), "churned": int(flags.sum()),
                                 "segment_balance": float(work[balance_col].sum()),
                                 "churned_balance": float(work["_churned_balance"].sum())}])

    total_churned_balance = float(work["_churned_balance"].sum())
    grouped["churned_share_of_segment_balance"] = np.where(
        grouped["segment_balance"] > 0, grouped["churned_balance"] / grouped["segment_balance"].where(
            grouped["segment_balance"] > 0, 1), np.nan)
    grouped["share_of_all_churned_balance"] = (grouped["churned_balance"] / total_churned_balance
                                               if total_churned_balance > 0 else np.nan)
    return grouped


def high_balance_churn_rate(df: pd.DataFrame, config: dict[str, Any]) -> dict[str, Any]:
    """High-Balance Churn Rate = churned High-balance customers / all High-balance customers.

    "High-balance" means a balance above the median of non-zero balances (the Phase 2 segment).
    Companion figures: the segment's share of all customers, its share of all churners
    (a Churn Contribution) and its balance exposure proxy. Balance is not profitability.
    """
    segment_col = config["kpi"]["balance_segment_column"]
    high_label = config["segmentation"]["balance"]["high_label"]
    _require_columns(df, [segment_col])
    flags = churn_flags(df, config)

    in_segment = df[segment_col] == high_label
    n_high, churned_high, total_churned = int(in_segment.sum()), int(flags[in_segment].sum()), int(flags.sum())
    exposure = balance_exposure(df[in_segment], config)
    return {
        "kpi": "High-Balance Churn Rate", "segment": high_label,
        **proportion_summary(churned_high, n_high, config),
        "share_of_customers": n_high / len(df) if len(df) else None,
        "churn_contribution": churned_high / total_churned if total_churned else None,
        "churned_balance": float(exposure.loc[0, "churned_balance"]),
        "segment_balance": float(exposure.loc[0, "segment_balance"]),
    }
