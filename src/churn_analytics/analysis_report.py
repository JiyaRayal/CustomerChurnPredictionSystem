"""Write the Phase 4 Markdown report from a ``SegmentAnalysis``.

Every number and every sentence about the data is computed from the analysis tables.
The wording is descriptive: it says how variables go together in this dataset and never
claims that one thing causes another.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from .analysis import SegmentAnalysis
from .md_utils import fmt_ci, fmt_int, fmt_pct, markdown_table
from .stats_utils import STATUS_EMPTY, STATUS_SMALL, STATUS_WITHHELD


def _fmt_p(p: Any) -> str:
    if p is None or pd.isna(p):
        return "n/a"
    return "<0.001" if p < 0.001 else f"{p:.3f}"


def _fmt_ratio(value: Any) -> str:
    return "n/a" if value is None or pd.isna(value) else f"{value:.2f}"


def _fmt_pp(value: Any, digits: int = 1) -> str:
    return "n/a" if value is None or pd.isna(value) else f"{value:+.{digits}f} pp"


def _fmt_num(value: Any, digits: int = 1) -> str:
    return "n/a" if value is None or pd.isna(value) else f"{value:,.{digits}f}"


def _note(status: str) -> str:
    return "" if status == "ok" else status


def _cell(row: pd.Series | None) -> str:
    """One matrix cell: 'rate (n=...)', with '*' for small samples and n/a where no rate is shown."""
    if row is None:
        return "n/a"
    n = fmt_int(row["n"])
    if row["status"] in (STATUS_EMPTY, STATUS_WITHHELD) or pd.isna(row["churn_rate"]):
        return f"n/a (n={n})"
    return f"{row['churn_rate'] * 100:.1f}% (n={n})" + ("*" if row["status"] == STATUS_SMALL else "")


def _matrix(table: pd.DataFrame, row_var: str, col_var: str) -> str:
    cols = list(dict.fromkeys(table[col_var]))
    rows = []
    for row_label in dict.fromkeys(table[row_var]):
        cells = []
        for col_label in cols:
            hit = table[(table[row_var] == row_label) & (table[col_var] == col_label)]
            cells.append(_cell(hit.iloc[0] if len(hit) else None))
        rows.append([row_label, *cells])
    return markdown_table([row_var, *cols], rows)


def _band_text(lower_bounds: list[float]) -> str:
    """Describe fixed bands from the config, e.g. '<580, 580-739, >=740'."""
    b = lower_bounds
    parts = [f"<{b[0]:g}"] + [f"{b[i]:g}-{b[i + 1] - 1:g}" for i in range(len(b) - 1)] + [f">={b[-1]:g}"]
    return ", ".join(parts)


# --------------------------------------------------------------------------------------
# Findings (all computed)
# --------------------------------------------------------------------------------------
def _findings(a: SegmentAnalysis, config: dict[str, Any], overall_rate: float, n_total: int) -> list[str]:
    small = config["statistics"]["small_group_threshold"]
    out = [f"Overall churn rate is {fmt_pct(overall_rate, 2)} across {fmt_int(n_total)} customers."]

    assoc = a.association.dropna(subset=["cramers_v"])
    top = assoc.head(3)
    out.append("Strongest single-variable associations with churn (Cramer's V): " + "; ".join(
        f"**{r.variable}** (V = {r.cramers_v:.2f}, {r.effect})" for r in top.itertuples()) + ".")
    weak = assoc[assoc["effect"] == config["analysis"]["effect_size_labels"][0]]
    if not weak.empty:
        out.append("Variables with a negligible association with churn in this dataset: " + ", ".join(
            f"{r.variable} (V = {r.cramers_v:.2f})" for r in weak.itertuples()) + ".")

    rated = a.overview.dropna(subset=["churn_rate"]).sort_values("churn_rate", ascending=False)
    out.append("Highest segment churn rates: " + "; ".join(
        f"{r.variable} = {r.segment} {fmt_pct(r.churn_rate)} (n = {fmt_int(r.n)}"
        + (", small sample" if r.status == STATUS_SMALL else "") + ")" for r in rated.head(5).itertuples()) + ".")

    gaps = a.overview.dropna(subset=["contribution_minus_share_pp"])
    gaps = gaps[gaps["contribution_minus_share_pp"] > 0].sort_values("contribution_minus_share_pp", ascending=False)
    if not gaps.empty:
        out.append("Segments contributing the most churners beyond their share of customers: " + "; ".join(
            f"{r.variable} = {r.segment} ({fmt_pct(r.churn_contribution)} of churners vs {fmt_pct(r.share_of_customers)} "
            "of customers)" for r in gaps.head(3).itertuples()) + ".")

    gender = a.gender
    gap_col = next(c for c in gender.columns if c.startswith("gap_pp"))
    overall_gap = gender.iloc[0]
    by_country = gender.iloc[1:].dropna(subset=[gap_col])
    if not by_country.empty:
        out.append(f"Gender: the gap ({gap_col.split('(')[1].rstrip(')')}) is {_fmt_pp(overall_gap[gap_col])} overall "
                   f"(95% CI {_fmt_pp(overall_gap['ci_low_pp'])} to {_fmt_pp(overall_gap['ci_high_pp'])}) and ranges from "
                   f"{_fmt_pp(by_country[gap_col].min())} to {_fmt_pp(by_country[gap_col].max())} across countries.")

    cells = a.geography_age_all
    solid = cells[(cells["status"] == "ok") & cells["churn_rate"].notna()]
    if not solid.empty:
        hi = solid.loc[solid["churn_rate"].idxmax()]
        lo = solid.loc[solid["churn_rate"].idxmin()]
        row_var, col_var = list(cells.columns[:2])
        out.append(f"Country x age (cells with at least {small} customers): highest churn is {hi[row_var]} / {hi[col_var]} "
                   f"at {fmt_pct(hi['churn_rate'])} (n = {fmt_int(hi['n'])}); lowest is {lo[row_var]} / {lo[col_var]} "
                   f"at {fmt_pct(lo['churn_rate'])} (n = {fmt_int(lo['n'])}).")

    ca = a.credit_sensitivity_association.set_index("variable")
    alt_name = config["analysis"]["sensitivity_variable"]
    if {"CreditScoreBand", alt_name} <= set(ca.index):
        fixed, alt = ca.loc["CreditScoreBand"], ca.loc[alt_name]
        out.append(f"Credit score: with the fixed bands V = {fixed['cramers_v']:.2f} ({fixed['effect']}; spread "
                   f"{fixed['spread_pp']:.1f} pp); with equal-sized terciles V = {alt['cramers_v']:.2f} ({alt['effect']}; "
                   f"spread {alt['spread_pp']:.1f} pp).")

    num = a.profile_numeric
    notable = num[num["effect"] != config["analysis"]["effect_size_labels"][0]]
    if not notable.empty:
        out.append("Churned vs retained customers differ most on: " + "; ".join(
            f"{r.column} (churned mean {_fmt_num(r.mean_churned)} vs retained {_fmt_num(r.mean_retained)}, "
            f"d = {r.cohens_d:+.2f}, {r.effect})" for r in notable.itertuples()) + ".")

    extreme = a.overview[a.overview["churn_rate"].isin([0.0, 1.0])]
    if not extreme.empty:
        out.append("**Worth confirming with the data owner:** " + "; ".join(
            f"{r.variable} = {r.segment} has a churn rate of exactly {fmt_pct(r.churn_rate, 0)} "
            f"({fmt_int(r.churned)} of {fmt_int(r.n)} customers)" for r in extreme.itertuples()) +
            ". The data cannot show why; an extreme result in a small group may reflect how the data was recorded.")
    return out


# --------------------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------------------
def render_report(a: SegmentAnalysis, config: dict[str, Any], overall_rate: float, n_total: int) -> str:
    analysis = config["analysis"]
    small = config["statistics"]["small_group_threshold"]
    minimum = config["statistics"]["min_reportable_group_size"]
    top_n = analysis["top_contribution_gaps"]

    lines = ["# Segment Churn Analysis", "",
             "Descriptive analysis of how churn varies across customer segments, produced by "
             "`src/churn_analytics/analysis.py`. Segment boundaries come from `config/segmentation.toml` "
             "(see `docs/segmentation_rules.md`). Rates are shown with group sizes and 95% Wilson confidence "
             "intervals. A group with no customers has an undefined rate (n/a), not 0%; groups below "
             f"{minimum} customers have their rate withheld and groups below {small} are flagged "
             "*small sample* (marked * in matrices).", "",
             "**How to read this report:** every table is a *single-variable* or *two-variable* view. Age, number of "
             "products, balance, activity and country are related to each other, and none of the tables controls for "
             "the others. All findings are **associations in one snapshot, not causal effects**.", "",
             "## Key findings (computed from the data)", ""]
    lines += [f"{i}. {text}" for i, text in enumerate(_findings(a, config, overall_rate, n_total), 1)]

    # 1. association ranking
    lines += ["", "## 1. Strength of association with churn", "",
              "Cramer's V is an effect size from 0 (no association) to 1 (perfect). Labels use the cut-offs in the "
              f"config ({', '.join(str(c) for c in analysis['effect_size_cutoffs'])}), which are conventions for "
              "describing size, not tests of importance.", "",
              markdown_table(["Rank", "Variable", "Groups", "Cramer's V", "Effect", "Highest-churn segment",
                              "Lowest-churn segment", "Spread (pp)", "p-value", "Note"],
                             [[i, r.variable, r.groups, _fmt_num(r.cramers_v, 3), r.effect,
                               f"{r.highest_segment} ({fmt_pct(r.highest_rate)}){'*' if r.highest_status == STATUS_SMALL else ''}",
                               f"{r.lowest_segment} ({fmt_pct(r.lowest_rate)}){'*' if r.lowest_status == STATUS_SMALL else ''}",
                               _fmt_num(r.spread_pp),
                               _fmt_p(r.p_value), r.note] for i, r in enumerate(a.association.itertuples(), 1)]), "",
              f"With {len(a.association)} variables compared, p-values are almost all tiny in a dataset of this size; "
              "read the effect size (V) and the group sizes, not the p-value. 'Spread' is the gap between the "
              "highest and lowest segment rate among segments with a reportable rate; `*` marks a small-sample segment, "
              "which can make the spread look larger than it would for well-populated groups.", ""]

    # 2. per-variable tables
    lines += ["## 2. Churn by segment", "",
              "'Rate vs overall' is the segment rate divided by the overall rate (1.00 = average). "
              "'Contribution' is the segment's share of all churners; compare it with its share of customers.", ""]
    for variable in analysis["segment_variables"]:
        part = a.overview[a.overview["variable"] == variable]
        lines += [f"### {variable}", "",
                  markdown_table(["Segment", "Customers", "Churned", "Churn rate", "95% CI", "Share of customers",
                                  "Churn contribution", "Rate vs overall", "Note"],
                                 [[r.segment, fmt_int(r.n), fmt_int(r.churned), fmt_pct(r.churn_rate),
                                   fmt_ci(r.ci_low, r.ci_high), fmt_pct(r.share_of_customers),
                                   fmt_pct(r.churn_contribution), _fmt_ratio(r.rate_ratio), _note(r.status)]
                                  for r in part.itertuples()]), ""]

    # 3. rate vs contribution
    gaps = a.overview.dropna(subset=["contribution_minus_share_pp"]).copy()
    gaps["abs_gap"] = gaps["contribution_minus_share_pp"].abs()
    gaps = gaps.sort_values("abs_gap", ascending=False).head(top_n)
    lines += ["## 3. Churn rate vs churn contribution", "",
              f"The {top_n} segments whose share of churners differs most from their share of customers "
              "(a positive gap means more churners than the segment's size alone would suggest). Within one variable "
              "the gaps add up to zero.", "",
              markdown_table(["Variable", "Segment", "Customers", "Churn rate", "Share of customers",
                              "Churn contribution", "Gap (pp)", "Note"],
                             [[r.variable, r.segment, fmt_int(r.n), fmt_pct(r.churn_rate), fmt_pct(r.share_of_customers),
                               fmt_pct(r.churn_contribution), _fmt_pp(r.contribution_minus_share_pp), _note(r.status)]
                              for r in gaps.itertuples()]), ""]

    # 4. gender
    g = a.gender
    gap_col = next(c for c in g.columns if c.startswith("gap_pp"))
    first, second = [c[len("churn "):] for c in g.columns if c.startswith("churn ")]
    lines += ["## 4. Gender comparison", "",
              f"Gap = churn rate of {first} minus churn rate of {second}, in percentage points, with a Newcombe 95% interval.", "",
              markdown_table(["Scope", f"{first} n", f"{first} churn", f"{second} n", f"{second} churn", "Gap", "95% CI (pp)", "Note"],
                             [[r["scope"], fmt_int(r[f"n {first}"]), fmt_pct(r[f"churn {first}"]), fmt_int(r[f"n {second}"]),
                               fmt_pct(r[f"churn {second}"]), _fmt_pp(r[gap_col]),
                               "n/a" if pd.isna(r["ci_low_pp"]) else f"{r['ci_low_pp']:+.1f} to {r['ci_high_pp']:+.1f}",
                               _note(r["status"])] for r in g.to_dict("records")]), ""]

    # 5. interactions
    row_var, col_var = analysis["interaction_row"], analysis["interaction_col"]
    seg_col = config["kpi"]["balance_segment_column"]
    lines += ["## 5. Two-variable views", "",
              "Cell format: churn rate (customers). `*` = small sample (fewer than "
              f"{small} customers); `n/a` = rate not shown because the group is empty or below {minimum} customers.", "",
              f"### 5a. {row_var} x {col_var}, all customers", "", _matrix(a.geography_age_all, row_var, col_var), "",
              f"### 5b. {row_var} x {col_var}, non-zero-balance customers only (like-for-like)", "",
              "No German customer has a zero balance, so this view compares countries on customers with a balance.", "",
              _matrix(a.geography_age_non_zero, row_var, col_var), "",
              f"### 5c. {row_var} x balance segment", "",
              "Balance-segment results are shown by country because the countries differ in how many zero-balance "
              "customers they have (none in Germany).", "",
              _matrix(a.geography_balance, row_var, seg_col), ""]

    # 6. credit sensitivity
    lines += ["## 6. Credit score: sensitivity to the chosen grouping", "",
              f"The fixed bands ({_band_text(config['segmentation']['credit_score']['lower_bounds'])}) are an analytical choice. This repeats the analysis with "
              "equal-sized terciles to see whether conclusions depend on that choice.", "",
              markdown_table(["Grouping", "Segment", "Customers", "Churned", "Churn rate", "95% CI", "Note"],
                             [[r.variable, r.segment, fmt_int(r.n), fmt_int(r.churned), fmt_pct(r.churn_rate),
                               fmt_ci(r.ci_low, r.ci_high), _note(r.status)]
                              for r in a.credit_sensitivity_overview.itertuples()]), "",
              markdown_table(["Grouping", "Cramer's V", "Effect", "Spread (pp)", "p-value"],
                             [[r.variable, _fmt_num(r.cramers_v, 3), r.effect, _fmt_num(r.spread_pp), _fmt_p(r.p_value)]
                              for r in a.credit_sensitivity_association.itertuples()]), ""]

    # 7. profiles
    lines += ["## 7. Churned vs retained customers", "",
              "### 7a. Numeric characteristics", "",
              "d = standardised mean difference (churned minus retained, pooled standard deviation), with an "
              "approximate 95% interval; labels use the cut-offs in the config "
              f"({', '.join(str(c) for c in analysis['smd_cutoffs'])}).", "",
              markdown_table(["Column", "Mean churned", "Mean retained", "Median churned", "Median retained", "d", "95% CI of d", "Effect"],
                             [[r.column, _fmt_num(r.mean_churned, 2), _fmt_num(r.mean_retained, 2), _fmt_num(r.median_churned, 2),
                               _fmt_num(r.median_retained, 2), f"{r.cohens_d:+.2f}", f"{r.d_ci_low:+.2f} to {r.d_ci_high:+.2f}",
                               r.effect] for r in a.profile_numeric.itertuples()]), "",
              "### 7b. Composition", "",
              "Share of retained customers and share of churned customers in each segment. This is the reverse view of "
              "the rate tables: a segment can be common among churners without having a high churn rate.", "",
              markdown_table(["Variable", "Segment", "% of retained", "% of churned", "Difference (pp)"],
                             [[r.variable, r.segment, fmt_pct(r.pct_of_retained), fmt_pct(r.pct_of_churned),
                               _fmt_pp(r.diff_pp)] for r in a.profile_categorical.itertuples()]), ""]

    # 8. cautions
    lines += ["## 8. What this analysis cannot tell us", "",
              "* **Cause.** These are associations in one snapshot. Nothing here shows that a characteristic makes "
              "customers leave, or why a segment differs.",
              "* **Overlap between variables.** Each table looks at one (or two) variables at a time. Age, number of "
              "products, balance, activity and country are related to each other, so a difference seen for one variable may "
              "partly reflect another. No multivariable adjustment is performed in this project.",
              "* **Multiple comparisons.** Many segments and variables are compared; some differences will look "
              "larger by chance, especially in small groups. Prefer large groups and effect sizes.",
              "* **Small groups.** Segments marked *small sample* have wide intervals; rates below the minimum size are withheld.",
              "* **Geography and balance.** No German customer has a zero balance, so Geography and balance-segment results "
              "overlap; use the like-for-like and by-country views (5b, 5c).",
              "* **Extreme rates.** A rate of exactly 0% or 100% in a small group should be confirmed with the data owner "
              "before being interpreted.",
              "* **Scope.** One snapshot of three countries; the meaning of `Exited` is an assumption (decision D6) and the data's "
              "provenance is unconfirmed.", ""]
    return "\n".join(lines)
