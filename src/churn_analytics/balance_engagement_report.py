"""Write the Phase 5 Markdown report from a ``BalanceEngagementAnalysis``.

Every number and every sentence about the data is computed from the analysis tables. The wording is
descriptive: it says how things go together in this dataset and never that one thing causes another.
Balance is never equated with profitability, and balance exposure is never called lost revenue.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

from .analysis_report import _fmt_p, _fmt_pp, _matrix, _note
from .balance_engagement import BalanceEngagementAnalysis
from .md_utils import fmt_ci, fmt_int, fmt_pct, markdown_table
from .stats_utils import STATUS_SMALL


def _money(value: Any) -> str:
    return "n/a" if value is None or pd.isna(value) else f"{value / 1e6:,.1f}M"


def _ci_pp(low: Any, high: Any) -> str:
    return "n/a" if pd.isna(low) or pd.isna(high) else f"{low:+.1f} to {high:+.1f}"


def _excludes_zero(low: Any, high: Any) -> bool:
    return not (pd.isna(low) or pd.isna(high)) and (low > 0 or high < 0)


def _tenure_note(curve: pd.DataFrame) -> str:
    """Describe the customer counts at the first and last tenure year versus the years in between (computed)."""
    if len(curve) < 3:
        return ""
    interior = curve.iloc[1:-1]["n"]
    first, last = curve.iloc[0], curve.iloc[-1]
    return (f"Tenure year {int(first['tenure'])} has {fmt_int(first['n'])} customers and year {int(last['tenure'])} has {fmt_int(last['n'])}, "
            f"against a median of {fmt_int(interior.median())} for the years in between. The cause of any difference is not known and is not assumed.")


# --------------------------------------------------------------------------------------
# Findings (all computed)
# --------------------------------------------------------------------------------------
def _findings(a: BalanceEngagementAnalysis, config: dict[str, Any]) -> list[str]:
    seg_col, eng_col = config["kpi"]["balance_segment_column"], config["kpi"]["engagement_column"]
    zero_label, low_label, high_label = (config["segmentation"]["balance"][k] for k in ("zero_label", "low_label", "high_label"))
    out: list[str] = []

    # 1. high vs low vs zero
    m = a.balance_engagement_matrix
    by_seg = m.groupby(seg_col)[["n", "churned"]].sum()
    rate = lambda label: by_seg.loc[label, "churned"] / by_seg.loc[label, "n"] if label in by_seg.index and by_seg.loc[label, "n"] else np.nan
    overall_row = a.high_vs_low_by_stratum.iloc[0]
    out.append(f"Churn rates by balance segment: {high_label} {fmt_pct(rate(high_label))} (n = {fmt_int(by_seg.loc[high_label, 'n'])}), "
               f"{low_label} {fmt_pct(rate(low_label))} (n = {fmt_int(by_seg.loc[low_label, 'n'])}), "
               f"{zero_label} {fmt_pct(rate(zero_label))} (n = {fmt_int(by_seg.loc[zero_label, 'n'])}).")

    # 2. like-for-like
    gap_text = (f"Among customers with a non-zero balance, High-balance customers churn {_fmt_pp(overall_row['gap_pp'])} compared with "
                f"Low-balance customers (95% CI {_ci_pp(overall_row['ci_low_pp'], overall_row['ci_high_pp'])} pp)")
    strata = a.high_vs_low_by_stratum.iloc[1:].dropna(subset=["gap_pp"])
    n_sig = int(sum(_excludes_zero(r.ci_low_pp, r.ci_high_pp) for r in strata.itertuples()))
    out.append(gap_text + f". Inside {len(strata)} country / age strata the High-minus-Low gap ranges from "
               f"{_fmt_pp(strata['gap_pp'].min())} to {_fmt_pp(strata['gap_pp'].max())}; the interval excludes zero in {n_sig} of them.")
    std = a.standardised_high_vs_low.dropna(subset=["standardised_gap_pp"])
    if not std.empty:
        any_gap = any(_excludes_zero(r.ci_low_pp, r.ci_high_pp) for r in std.itertuples())
        vs_zero = "higher" if rate(high_label) > rate(zero_label) else "not higher"
        verdict = (f"At least one standardised interval excludes zero, so {high_label} and comparable {low_label} customers do differ in this dataset."
                   if any_gap else
                   f"Every standardised interval includes zero, so {high_label} customers are not distinguishable from comparable {low_label} customers in this dataset.")
        out.append("Directly standardised High-minus-Low gap (same customer mix for both groups): " + "; ".join(
            f"by {r.strata} {_fmt_pp(r.standardised_gap_pp, 2)} (95% CI {_ci_pp(r.ci_low_pp, r.ci_high_pp)}, covering {fmt_pct(r.coverage, 0)} "
            f"of non-zero customers)" for r in std.itertuples()) + f". {high_label} customers' churn rate is {vs_zero} than {zero_label} customers'. " + verdict)

    # 3. who they are
    prof = a.high_balance_profile
    over = prof[prof["n_high_balance"] > 0].sort_values("diff_pp", ascending=False).head(3)
    out.append("Segments most over-represented among High-balance customers (share of High-balance vs share of all customers): " + "; ".join(
        f"{r.variable} = {r.segment} ({fmt_pct(r.pct_of_high_balance)} vs {fmt_pct(r.pct_of_all)}, {_fmt_pp(r.diff_pp)})"
        for r in over.itertuples()) + ". Differences of a point or two are small.")

    # 4. within high-balance
    within = a.churn_within_high_balance
    solid = within[within["status"] == "ok"].sort_values("churn_rate", ascending=False).head(3)
    if not solid.empty:
        out.append("Highest churn among High-balance customers (segments with at least "
                   f"{config['statistics']['small_group_threshold']} customers): " + "; ".join(
            f"{r.variable} = {r.segment} {fmt_pct(r.churn_rate)} (n = {fmt_int(r.n)})" for r in solid.itertuples()) + ".")

    # 5. balance level
    bg = a.balance_group_churn.dropna(subset=["churn_rate"])
    if not bg.empty:
        hi, lo = bg.loc[bg["churn_rate"].idxmax()], bg.loc[bg["churn_rate"].idxmin()]
        steps = np.diff(bg["churn_rate"].to_numpy(dtype=float))
        shape = ("a steady rise" if (steps > 0).all() else "a steady fall" if (steps < 0).all()
                 else "no steady rise or fall across the groups")
        out.append(f"Across equal-sized groups of non-zero balances, churn ranges from {fmt_pct(lo['churn_rate'])} ({lo['group']}) to "
                   f"{fmt_pct(hi['churn_rate'])} ({hi['group']}), a spread of {(hi['churn_rate'] - lo['churn_rate']) * 100:.1f} percentage points, "
                   f"with {shape}.")

    # 6. salary
    sal = a.salary
    srates = sal["overview"].dropna(subset=["churn_rate"])
    relation = ("no statistically detectable monotone relationship" if sal["p_non_zero"] >= 0.05
                else "a statistically detectable monotone relationship (check its size before reading anything into it)")
    out.append(f"Salary: churn rates across salary thirds range from {fmt_pct(srates['churn_rate'].min())} to {fmt_pct(srates['churn_rate'].max())}. "
               f"The rank correlation between salary and balance among non-zero-balance customers is {sal['rho_non_zero']:+.3f} "
               f"(p = {_fmt_p(sal['p_non_zero'])}): {relation} in this dataset.")

    # 7. engagement
    eng = a.engagement_by_segment
    overall_eng = eng.iloc[0]
    valid = eng.iloc[1:].dropna(subset=["edi_pp"])
    positive = int((valid["edi_pp"] > 0).sum())
    solid = valid[valid["status"] == "ok"]
    top = (solid if not solid.empty else valid).sort_values("edi_pp", ascending=False).iloc[0]
    top_any = valid.sort_values("edi_pp", ascending=False).iloc[0]
    caveat = ""
    if top_any["edi_pp"] > top["edi_pp"]:
        caveat = (f" A larger gap ({_fmt_pp(top_any['edi_pp'])} in {top_any['variable']} = {top_any['segment']}) rests on a small sample"
                  f" (n = {fmt_int(top_any['n_inactive'])} inactive, {fmt_int(top_any['n_active'])} active).")
    out.append(f"Engagement: inactive members churn {_fmt_pp(overall_eng['edi_pp'])} more than active members overall "
               f"(95% CI {_ci_pp(overall_eng['ci_low_pp'], overall_eng['ci_high_pp'])}). The gap is positive in {positive} of "
               f"{len(valid)} segments where it can be estimated; the largest among segments with at least "
               f"{config['statistics']['small_group_threshold']} customers per group is {top['variable']} = {top['segment']} ({_fmt_pp(top['edi_pp'])})."
               + caveat)

    # 8. tenure
    tc = a.tenure_curve.dropna(subset=["churn_rate"])
    if len(tc) >= 3:
        hi, lo = tc.loc[tc["churn_rate"].idxmax()], tc.loc[tc["churn_rate"].idxmin()]
        rho = stats.spearmanr(tc["tenure"], tc["churn_rate"])
        trend = ("no statistically detectable trend" if rho.pvalue >= 0.05
                 else "a statistically detectable trend (check its size before reading anything into it)")
        out.append(f"Tenure: churn by tenure year ranges from {fmt_pct(lo['churn_rate'])} (year {int(lo['tenure'])}) to {fmt_pct(hi['churn_rate'])} "
                   f"(year {int(hi['tenure'])}). The rank correlation between tenure year and churn rate across the {len(tc)} years is "
                   f"{rho.statistic:+.2f} (p = {_fmt_p(rho.pvalue)}): {trend} in this dataset.")

    # 9. exposure
    expo_all = a.exposure_by_variable
    bal_rows = expo_all[expo_all["variable"] == seg_col].set_index("segment")
    churned_total = float(bal_rows["churned_balance"].sum())
    total_balance = float(bal_rows["segment_balance"].sum())
    hb = m[(m[seg_col] == high_label)]
    inactive_label = config["analysis"]["display_labels"][eng_col]["0"]
    hb_inactive = hb[hb[eng_col] == inactive_label]
    conc = a.concentration
    out.append(f"Balance exposure proxy (balance held by customers who churned; **not lost revenue**): {_money(churned_total)}, "
               f"{fmt_pct(churned_total / total_balance if total_balance else np.nan)} of all balances. "
               f"{high_label} customers hold {fmt_pct(float(hb['share_of_all_churned_balance'].sum()))} of it"
               + (f"; inactive {high_label} customers alone hold {fmt_pct(float(hb_inactive['share_of_all_churned_balance'].sum()))} "
                  f"while being {fmt_pct(float(hb_inactive['share_of_customers'].sum()))} of customers" if not hb_inactive.empty else "") + ".")
    out.append(f"Concentration: the top {fmt_pct(conc.iloc[0]['top_share_of_churned_customers'], 0)} of churned customers (by balance) hold "
               f"{fmt_pct(conc.iloc[0]['share_of_churned_balance'])} of the churned balance; "
               f"{fmt_int(conc.attrs.get('churned_with_zero_balance', 0))} of {fmt_int(conc.attrs.get('churned_customers', 0))} churned customers "
               "had a zero balance and add nothing to it.")
    return out


# --------------------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------------------
def render_report(a: BalanceEngagementAnalysis, config: dict[str, Any]) -> str:
    seg_col, eng_col = config["kpi"]["balance_segment_column"], config["kpi"]["engagement_column"]
    be = config["balance_engagement"]
    small = config["statistics"]["small_group_threshold"]
    minimum = config["statistics"]["min_reportable_group_size"]
    conf = int(round(config["statistics"]["confidence_level"] * 100))
    high_label = config["segmentation"]["balance"]["high_label"]

    lines = ["# High-Balance, Salary, Engagement and Tenure Analysis", "",
             "Descriptive analysis produced by `src/churn_analytics/balance_engagement.py`. Rates come with group sizes and "
             f"{conf}% Wilson intervals; differences between two groups use Newcombe intervals (percentage points, pp). A group with "
             f"no customers is n/a (not 0%); groups below {minimum} customers have their rate withheld; groups below {small} are flagged "
             "*small sample* (marked * in matrices).", "",
             "**Terms.** *High-balance* means a balance above the median of non-zero balances (see `reports/cleaning_log.md`). It is "
             "**not** a measure of profitability or lifetime value, and neither is salary. *Balance exposure proxy* is the balance held by "
             "customers who churned; it is **not lost revenue**, because the dataset has no revenue, margin or fee data.", "",
             "**How to read this report:** results are single- or two-variable views of one snapshot. They are associations, not causal "
             "effects, and no table controls for every other variable.", "",
             "## Key findings (computed from the data)", ""]
    lines += [f"{i}. {text}" for i, text in enumerate(_findings(a, config), 1)]

    # 1
    prof = a.high_balance_profile
    lines += ["", "## 1. Who are the High-balance customers?", "",
              "Share of High-balance customers in each segment compared with the share of all customers. "
              "'High-balance share of segment' is the percentage of the segment's customers who are High-balance.", "",
              markdown_table(["Variable", "Segment", "High-balance customers", "% of High-balance", "% of all customers", "Difference (pp)",
                              "High-balance share of segment"],
                             [[r.variable, r.segment, fmt_int(r.n_high_balance), fmt_pct(r.pct_of_high_balance), fmt_pct(r.pct_of_all),
                               _fmt_pp(r.diff_pp), fmt_pct(r.high_share_of_segment)] for r in prof.itertuples()]), ""]

    # 2
    w = a.churn_within_high_balance
    lines += [f"## 2. Churn among {high_label} customers", "",
              f"Churn rates inside the {high_label} group only. Contributions are shares of {high_label} churners.", ""]
    for variable in be["within_high_balance_variables"]:
        part = w[w["variable"] == variable]
        lines += [f"### {variable}", "",
                  markdown_table(["Segment", "Customers", "Churned", "Churn rate", f"{conf}% CI", "Share of High-balance customers",
                                  "Contribution to High-balance churn", "Note"],
                                 [[r.segment, fmt_int(r.n), fmt_int(r.churned), fmt_pct(r.churn_rate), fmt_ci(r.ci_low, r.ci_high),
                                   fmt_pct(r.share_of_customers), fmt_pct(r.churn_contribution), _note(r.status)] for r in part.itertuples()]), ""]

    # 3
    hl = a.high_vs_low_by_stratum
    lines += ["## 3. High-balance vs Low-balance, like for like", "",
              "Zero-balance customers are left out because they are a different group"
              + (f" (and no customer in {', '.join(a.countries_without_zero_balance)} has a zero balance)" if a.countries_without_zero_balance else "")
              + ". Gap = High-balance churn rate minus Low-balance churn rate, in percentage points.", "",
              "### 3a. Inside each stratum", "",
              markdown_table(["Variable", "Stratum", "High n", "High churn", "Low n", "Low churn", "Gap (pp)", f"{conf}% CI (pp)", "Note"],
                             [[r.variable, r.stratum, fmt_int(r.n_high), fmt_pct(r.churn_high), fmt_int(r.n_low), fmt_pct(r.churn_low),
                               _fmt_pp(r.gap_pp), _ci_pp(r.ci_low_pp, r.ci_high_pp), _note(r.status)] for r in hl.itertuples()]), "",
              "### 3b. Directly standardised gap", "",
              "Both groups are averaged over the same customer mix (each stratum weighted by its share of non-zero customers), so a "
              "difference in country or age mix cannot create a gap by itself. Strata where either group has fewer than "
              f"{minimum} customers are left out and the weights re-scaled; 'coverage' is the share of non-zero customers represented. "
              "The interval is a normal approximation.", "",
              markdown_table(["Strata", "Cells (used)", "Coverage", "Unadjusted gap (pp)", "High churn (std.)", "Low churn (std.)",
                              "Standardised gap (pp)", f"{conf}% CI (pp, approx.)"],
                             [[r.strata, f"{r.cells} ({r.cells_used})", fmt_pct(r.coverage, 0), _fmt_pp(r.unadjusted_gap_pp, 2),
                               fmt_pct(r.rate_high_std), fmt_pct(r.rate_low_std), _fmt_pp(r.standardised_gap_pp, 2),
                               _ci_pp(r.ci_low_pp, r.ci_high_pp)] for r in a.standardised_high_vs_low.itertuples()]), ""]

    # 4
    cuts = ", ".join(f"{c:,.0f}" for c in a.balance_group_cutpoints)
    lines += ["## 4. Does churn change with the size of the balance?", "",
              f"Non-zero balances split into {be['balance_quantile_groups']} equal-sized groups (cut points computed from the data: {cuts}).", "",
              markdown_table(["Balance group", "Balance range", "Customers", "Churned", "Churn rate", f"{conf}% CI", "Note"],
                             [[r.group, f"{r.balance_min:,.0f} to {r.balance_max:,.0f}", fmt_int(r.n), fmt_int(r.churned),
                               fmt_pct(r.churn_rate), fmt_ci(r.ci_low, r.ci_high), _note(r.status)] for r in a.balance_group_churn.itertuples()]), ""]

    # 5
    sal = a.salary
    scuts = ", ".join(f"{c:,.0f}" for c in sal["cutpoints"])
    lines += ["## 5. Salary and balance", "",
              f"Salary is split into {be['salary_groups']} equal-sized groups (cut points: {scuts}). Salary and balance describe what a "
              "customer is recorded as earning and holding; neither is treated as profitability or lifetime value.", "",
              markdown_table(["Salary group", "Customers", "Churned", "Churn rate", f"{conf}% CI", "Note"],
                             [[r.group, fmt_int(r.n), fmt_int(r.churned), fmt_pct(r.churn_rate), fmt_ci(r.ci_low, r.ci_high), _note(r.status)]
                              for r in sal["overview"].itertuples()]), "",
              f"Spearman rank correlation between salary and balance: **{sal['rho_non_zero']:+.3f}** among non-zero-balance customers "
              f"(n = {fmt_int(sal['n_non_zero'])}, p = {_fmt_p(sal['p_non_zero'])}); {sal['rho_all']:+.3f} among all customers "
              f"(n = {fmt_int(sal['n_all'])}, p = {_fmt_p(sal['p_all'])}).", "",
              "Cell format: churn rate (customers). `*` = small sample; `n/a` = rate not shown.", "",
              "### 5a. Salary group x balance segment, all customers", "", _matrix(sal["grid_all"], "SalaryBand", seg_col), "",
              "### 5b. Salary group x balance segment, non-zero-balance customers", "", _matrix(sal["grid_non_zero"], "SalaryBand", seg_col), ""]

    # 6
    eng = a.engagement_by_segment
    lines += ["## 6. Engagement", "",
              "Engagement Drop Indicator = churn rate of inactive members minus churn rate of active members (pp, Newcombe interval). "
              "Inactivity may be a *symptom* of a customer already deciding to leave, so this describes an association and does not show "
              "which way any influence runs.", "",
              markdown_table(["Variable", "Segment", "Inactive n", "Inactive churn", "Active n", "Active churn", "Gap (pp)", f"{conf}% CI (pp)", "Note"],
                             [[r.variable, r.segment, fmt_int(r.n_inactive), fmt_pct(r.churn_inactive), fmt_int(r.n_active), fmt_pct(r.churn_active),
                               _fmt_pp(r.edi_pp), _ci_pp(r.ci_low_pp, r.ci_high_pp), _note(r.status)] for r in eng.itertuples()]), "",
              "### 6a. Who is inactive?", "",
              markdown_table(["Variable", "Segment", "Customers", "Inactive", "Share inactive", f"{conf}% CI", "Note"],
                             [[r.variable, r.segment, fmt_int(r.n), fmt_int(r.inactive), fmt_pct(r.share_inactive), fmt_ci(r.ci_low, r.ci_high),
                               _note(r.status)] for r in a.inactive_share.itertuples()]), "",
              "### 6b. Churn by tenure group and engagement", "", _matrix(a.engagement_tenure_grid, "TenureGroup", eng_col), "",
              "### 6c. Churn by number of products and engagement", "", _matrix(a.engagement_products_grid, "NumOfProducts", eng_col), ""]

    # 7
    lines += ["## 7. Tenure", "",
              markdown_table(["Tenure (years)", "Customers", "Churned", "Churn rate", f"{conf}% CI", "Note"],
                             [[r.tenure, fmt_int(r.n), fmt_int(r.churned), fmt_pct(r.churn_rate), fmt_ci(r.ci_low, r.ci_high), _note(r.status)]
                              for r in a.tenure_curve.itertuples()]), "",
              _tenure_note(a.tenure_curve), ""]

    # 8
    m = a.balance_engagement_matrix
    lines += ["## 8. Balance exposure proxy (NOT lost revenue)", "",
              "Balance held by customers who churned. It shows where balances sit among leavers; it says nothing about revenue, profit or "
              "lifetime value.", "",
              "### 8a. High-balance / engagement matrix", "",
              markdown_table(["Balance segment", "Engagement", "Customers", "Churn rate", f"{conf}% CI", "Share of churners", "Churned customers' balance",
                              "Share of all churned balance"],
                             [[getattr(r, seg_col), getattr(r, eng_col), fmt_int(r.n), fmt_pct(r.churn_rate), fmt_ci(r.ci_low, r.ci_high),
                               fmt_pct(r.churn_contribution), _money(r.churned_balance), fmt_pct(r.share_of_all_churned_balance)]
                              for r in m.itertuples()]), "",
              "### 8b. By variable", "",
              markdown_table(["Variable", "Segment", "Customers", "Churned", "Balance held by churned", "Share of all churned balance",
                              "Share of all balance", "Churned share of segment balance"],
                             [[r.variable, r.segment, fmt_int(r.n), fmt_int(r.churned), _money(r.churned_balance),
                               fmt_pct(r.share_of_all_churned_balance), fmt_pct(r.share_of_all_balance),
                               fmt_pct(r.churned_share_of_segment_balance)] for r in a.exposure_by_variable.itertuples()]), "",
              "### 8c. Concentration", "",
              f"Churned customers sorted by balance, largest first. {fmt_int(a.concentration.attrs.get('churned_with_zero_balance', 0))} of "
              f"{fmt_int(a.concentration.attrs.get('churned_customers', 0))} churned customers had a zero balance.", "",
              markdown_table(["Top share of churned customers", "Customers", "Balance held", "Share of churned balance", "Smallest balance in group"],
                             [[fmt_pct(r.top_share_of_churned_customers, 0), fmt_int(r.customers), _money(r.balance_held),
                               fmt_pct(r.share_of_churned_balance), f"{r.smallest_balance_in_group:,.0f}"] for r in a.concentration.itertuples()]), ""]

    # 9
    lines += ["## 9. What this analysis cannot tell us", "",
              "* **Cause.** These are associations in one snapshot. Nothing shows that balance, salary, inactivity or tenure makes customers leave.",
              "* **Value.** High balance, salary and balance exposure are not profitability, revenue or lifetime value; no such data exists here.",
              "* **Overlap.** Country, age, products, activity and balance are related. Stratification and standardisation (section 3) reduce "
              "differences in country and age mix only; they do not adjust for everything else.",
              "* **Why.** The data cannot explain why segments differ"
              + (f", or why no customer in {', '.join(a.countries_without_zero_balance)} has a zero balance" if a.countries_without_zero_balance else "")
              + ". Extreme rates in small groups should be confirmed with the data owner.",
              "* **Small groups.** Segments marked *small sample* have wide intervals; rates below the minimum size are withheld. Many segments "
              "are compared, so some differences will look larger by chance.",
              "* **Scope.** One snapshot of three countries; the meaning of `Exited` is an assumption (decision D6) and the data's provenance is unconfirmed.", ""]
    return "\n".join(lines)
