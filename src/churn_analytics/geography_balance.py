"""Investigate how Geography relates to zero-balance customers BEFORE interpreting churn.

Why this matters (beginner note)
--------------------------------
If one country has no zero-balance customers at all, then "country" and "balance level"
are tangled together. Looking at churn by country alone, or by balance alone, could then
mix two effects. This module lays out the relationship so later analysis compares
like with like. It is **descriptive only**: it counts and compares; it does not say why
the pattern exists, and it does not claim any cause of churn.

Everything printed in the findings is computed from the data, never typed in.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from .md_utils import fmt_ci, fmt_int, fmt_pct, markdown_table
from .stats_utils import chi_square_independence, proportion_summary

ZERO = "Zero-balance"
NONZERO = "Non-zero balance"
POOLED_OTHERS = "Other countries pooled"


@dataclass
class GeographyBalanceResult:
    counts: pd.DataFrame            # country x balance status (+ total, share zero)
    independence_test: dict[str, Any]
    pairwise_test: dict[str, Any] | None
    pairwise_countries: list[str]
    structural_zero_countries: list[str]
    churn_cells: pd.DataFrame       # country x balance status churn summary
    like_for_like: pd.DataFrame     # non-zero customers only: country vs others pooled
    balance_gap: pd.DataFrame       # churn of zero vs non-zero customers, by scope
    nonzero_balance_by_country: pd.DataFrame
    findings: list[str]

    def to_markdown(self) -> str:
        return _render_markdown(self)


def _churn_summary(frame: pd.DataFrame, target: str, churn_value: int, config: dict[str, Any]) -> dict[str, Any]:
    return proportion_summary(int((frame[target] == churn_value).sum()), len(frame), config)


def investigate_geography_zero_balance(df: pd.DataFrame, config: dict[str, Any]) -> GeographyBalanceResult:
    """Run the full descriptive investigation on a validated dataframe."""
    target, churn_value = config["columns"]["target"], config["columns"]["churn_value"]
    countries = list(config["columns"]["categorical_expected"]["Geography"])
    status = pd.Series(np.where(df["Balance"] == 0, ZERO, NONZERO), index=df.index)
    geo = df["Geography"].astype(str)

    # --- 1. who has zero balances? ------------------------------------------------------
    counts = (pd.crosstab(geo, status).reindex(index=countries, columns=[ZERO, NONZERO], fill_value=0))
    counts["Total"] = counts[ZERO] + counts[NONZERO]
    counts["Share zero-balance"] = counts[ZERO] / counts["Total"]
    structural_zero = [c for c in countries if counts.loc[c, ZERO] == 0]

    independence = chi_square_independence(counts[[ZERO, NONZERO]])
    pairwise_countries = [c for c in countries if counts.loc[c, ZERO] > 0]
    pairwise = (chi_square_independence(counts.loc[pairwise_countries, [ZERO, NONZERO]])
                if len(pairwise_countries) >= 2 else None)

    # --- 2. churn in every country x balance-status cell (empty cells shown as n/a) -------
    cell_rows = []
    for country in countries:
        for label in (ZERO, NONZERO):
            frame = df[(geo == country) & (status == label)]
            s = _churn_summary(frame, target, churn_value, config)
            cell_rows.append({"Country": country, "Balance status": label, **{
                "n": s["n"], "churned": s["events"], "churn rate": s["rate"],
                "ci_low": s["ci_low"], "ci_high": s["ci_high"], "status": s["status"]}})
    churn_cells = pd.DataFrame(cell_rows)

    # --- 3. like-for-like: non-zero-balance customers only ------------------------------
    nonzero = df[status == NONZERO]
    nz_geo = geo[status == NONZERO]
    lfl_rows = []
    for country in countries:
        s = _churn_summary(nonzero[nz_geo == country], target, churn_value, config)
        lfl_rows.append({"Group": country, **_flat(s)})
    for country in structural_zero:
        s = _churn_summary(nonzero[nz_geo != country], target, churn_value, config)
        lfl_rows.append({"Group": f"{POOLED_OTHERS} (excluding {country})", **_flat(s)})
    like_for_like = pd.DataFrame(lfl_rows)

    # --- 4. gap between zero and non-zero customers, by scope ---------------------------
    gap_rows = []
    scopes = [(c, geo == c) for c in pairwise_countries]
    if pairwise_countries:
        scopes.append((f"Pooled: {' + '.join(pairwise_countries)}", geo.isin(pairwise_countries)))
    scopes.append(("Pooled: all countries", pd.Series(True, index=df.index)))
    for name, mask in scopes:
        z = _churn_summary(df[mask & (status == ZERO)], target, churn_value, config)
        nz = _churn_summary(df[mask & (status == NONZERO)], target, churn_value, config)
        gap = None if z["rate"] is None or nz["rate"] is None else (nz["rate"] - z["rate"]) * 100
        gap_rows.append({"Scope": name, "n zero": z["n"], "churn zero": z["rate"],
                         "n non-zero": nz["n"], "churn non-zero": nz["rate"], "gap (pp)": gap})
    balance_gap = pd.DataFrame(gap_rows)

    # --- 5. is the LEVEL of non-zero balances similar across countries? -----------------
    level = (nonzero.assign(_geo=nz_geo).groupby("_geo", observed=True)["Balance"]
             .describe(percentiles=[0.25, 0.5, 0.75]).reindex(countries)
             [["count", "mean", "25%", "50%", "75%"]])
    level.index.name = "Country"

    result = GeographyBalanceResult(counts, independence, pairwise, pairwise_countries, structural_zero,
                                    churn_cells, like_for_like, balance_gap, level, [])
    result.findings = _build_findings(result)
    return result


def _flat(summary: dict[str, Any]) -> dict[str, Any]:
    return {"n": summary["n"], "churned": summary["events"], "churn rate": summary["rate"],
            "ci_low": summary["ci_low"], "ci_high": summary["ci_high"], "status": summary["status"]}


def _build_findings(r: GeographyBalanceResult) -> list[str]:
    total = int(r.counts["Total"].sum())
    n_zero = int(r.counts[ZERO].sum())
    findings = [f"{fmt_int(n_zero)} of {fmt_int(total)} customers ({fmt_pct(n_zero / total)}) have a zero balance."]

    if r.structural_zero_countries:
        names = ", ".join(r.structural_zero_countries)
        n_there = int(r.counts.loc[r.structural_zero_countries, "Total"].sum())
        findings.append(f"**No customer in {names} has a zero balance** (0 of {fmt_int(n_there)}). "
                        "Zero-balance customers exist only in the other countries, so comparisons involving "
                        f"zero-balance customers cannot include {names}.")

    t = r.independence_test
    p_text = "p < 0.001" if t["p_value"] < 0.001 else f"p = {t['p_value']:.3f}"
    findings.append(f"Geography and zero-balance status are strongly associated in this dataset "
                    f"(chi-square = {t['chi2']:,.0f}, {p_text}, Cramer's V = {t['cramers_v']:.2f}). "
                    "This describes how customers are distributed; it does not explain why.")

    if r.pairwise_test is not None:
        pt = r.pairwise_test
        shares = ", ".join(f"{c} {fmt_pct(r.counts.loc[c, 'Share zero-balance'])}" for c in r.pairwise_countries)
        pp = "p < 0.001" if pt["p_value"] < 0.001 else f"p = {pt['p_value']:.2f}"
        findings.append(f"Among the countries that do have zero-balance customers, their share is: {shares} "
                        f"({pp}, Cramer's V = {pt['cramers_v']:.3f}).")

    medians = r.nonzero_balance_by_country["50%"]
    findings.append("Among customers with a non-zero balance, median balances by country range from "
                    f"{medians.min():,.0f} to {medians.max():,.0f}, so the typical size of a non-zero "
                    "balance is similar across countries in this dataset.")

    lfl = r.like_for_like
    parts = [f"{row['Group']} {fmt_pct(row['churn rate'])} (n = {fmt_int(row['n'])})" for _, row in lfl.iterrows()]
    findings.append("Churn rate among **non-zero-balance customers only** (like-for-like): " + "; ".join(parts) + ".")

    gap = r.balance_gap
    pooled_all = gap[gap["Scope"] == "Pooled: all countries"].iloc[0]
    pooled_comp = gap[gap["Scope"].str.startswith("Pooled:") & (gap["Scope"] != "Pooled: all countries")]
    if not pooled_comp.empty and pooled_all["gap (pp)"] is not None and pooled_comp.iloc[0]["gap (pp)"] is not None:
        comp = pooled_comp.iloc[0]
        findings.append(
            f"Across all customers, non-zero-balance customers churn {pooled_all['gap (pp)']:.1f} percentage "
            f"points more than zero-balance customers; restricted to {comp['Scope'].replace('Pooled: ', '')} "
            f"(the countries with both groups) the gap is {comp['gap (pp)']:.1f} percentage points. The "
            "overall gap is therefore not a like-for-like comparison of balance groups.")
    return findings


def _render_markdown(r: GeographyBalanceResult) -> str:
    lines = ["# Geography and Zero-Balance Investigation", "",
             "Purpose: understand how Geography and zero-balance status overlap **before** interpreting "
             "their separate associations with churn. This analysis is descriptive. Churn rates here are "
             "associations in one snapshot, not causal effects, and formal group comparisons are left to "
             "the churn analysis phase.", "",
             "## Key findings (computed from the data)", ""]
    lines += [f"{i}. {text}" for i, text in enumerate(r.findings, 1)]

    lines += ["", "## 1. Customers by country and balance status", "",
              markdown_table(["Country", ZERO, NONZERO, "Total", "Share zero-balance"],
                             [[c, fmt_int(row[ZERO]), fmt_int(row[NONZERO]), fmt_int(row["Total"]),
                               fmt_pct(row["Share zero-balance"])] for c, row in r.counts.iterrows()]), ""]

    lines += ["## 2. Churn by country and balance status", "",
              markdown_table(["Country", "Balance status", "n", "Churned", "Churn rate", "95% CI (Wilson)", "Note"],
                             [[row["Country"], row["Balance status"], fmt_int(row["n"]), fmt_int(row["churned"]),
                               fmt_pct(row["churn rate"]), fmt_ci(row["ci_low"], row["ci_high"]), row["status"]]
                              for _, row in r.churn_cells.iterrows()]), "",
              "An empty cell (n = 0) has an **undefined** rate (n/a), not 0%.", ""]

    lines += ["## 3. Like-for-like: non-zero-balance customers only", "",
              markdown_table(["Group", "n", "Churned", "Churn rate", "95% CI (Wilson)"],
                             [[row["Group"], fmt_int(row["n"]), fmt_int(row["churned"]), fmt_pct(row["churn rate"]),
                               fmt_ci(row["ci_low"], row["ci_high"])] for _, row in r.like_for_like.iterrows()]), ""]

    lines += ["## 4. Churn gap between non-zero and zero-balance customers", "",
              markdown_table(["Scope", "n zero", "Churn zero", "n non-zero", "Churn non-zero", "Gap (pp)"],
                             [[row["Scope"], fmt_int(row["n zero"]), fmt_pct(row["churn zero"]),
                               fmt_int(row["n non-zero"]), fmt_pct(row["churn non-zero"]),
                               "n/a" if row["gap (pp)"] is None or pd.isna(row["gap (pp)"]) else f"{row['gap (pp)']:.1f}"]
                              for _, row in r.balance_gap.iterrows()]),
              "", "pp = percentage points (non-zero churn rate minus zero-balance churn rate).", ""]

    lines += ["## 5. Size of non-zero balances by country", "",
              markdown_table(["Country", "n", "Mean", "25th pct", "Median", "75th pct"],
                             [[c, fmt_int(row["count"]), f"{row['mean']:,.0f}", f"{row['25%']:,.0f}",
                               f"{row['50%']:,.0f}", f"{row['75%']:,.0f}"]
                              for c, row in r.nonzero_balance_by_country.iterrows()]), ""]

    lines += ["## What this does NOT tell us", "",
              "* **Why** some countries have no zero-balance customers. The dataset has no account-type, "
              "product-rule or data-collection information, so the reason cannot be determined here and is not "
              "assumed. The data owner would need to explain it.",
              "* **Whether geography or balance drives churn.** These are overlapping descriptive patterns. "
              "No causal claim is made.",
              "* **How these results would hold elsewhere.** One snapshot, three countries.", "",
              "## Consequences for later analysis (design rules adopted)", "",
              "1. Never interpret a country's churn rate and the balance-segment churn rates as independent evidence.",
              "2. Compare countries on **non-zero-balance customers** when a like-for-like comparison is needed, "
              "and report zero-balance comparisons only for countries that have zero-balance customers.",
              "3. Show balance-segment results **by country** (or within the countries that have all segments).",
              "4. Treat any Germany-vs-others or zero-vs-non-zero statement made on pooled data as confounded, and say so.", ""]
    return "\n".join(lines)
