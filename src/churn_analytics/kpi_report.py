"""Assemble the headline KPIs into one summary and a Markdown report.

Beginner notes
--------------
This module calls the functions in ``kpis.py`` and lays the results out for a reader.
It applies the design rules adopted after the Geography x zero-balance investigation
(docs/decisions_log.md D24):

* The Geographic Risk Index is shown for **all customers** and again for **non-zero-balance
  customers only**, because no German customer has a zero balance.
* The High-Balance Churn Rate is shown pooled **and by country**, because the countries differ
  in how many high-balance customers they have.

Everything printed is computed from the data. The wording stays descriptive: no causal claims.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from . import kpis
from .md_utils import fmt_ci, fmt_int, fmt_pct, markdown_table


@dataclass
class KpiSummary:
    overall: dict[str, Any]
    geographic_risk_all: pd.DataFrame
    geographic_risk_nonzero: pd.DataFrame
    engagement: dict[str, Any]
    engagement_by_country: pd.DataFrame
    high_balance: dict[str, Any]
    high_balance_by_country: pd.DataFrame
    exposure_by_balance_segment: pd.DataFrame
    exposure_overall: pd.DataFrame

    def to_markdown(self, config: dict[str, Any]) -> str:
        return _render(self, config)


def _fmt_ratio(value: Any) -> str:
    return "n/a" if value is None or pd.isna(value) else f"{value:.2f}"


def _fmt_pp(value: Any) -> str:
    return "n/a" if value is None or pd.isna(value) else f"{value:+.1f} pp"


def _fmt_money(value: Any) -> str:
    return "n/a" if value is None or pd.isna(value) else f"{value:,.0f}"


def build_kpi_summary(df: pd.DataFrame, config: dict[str, Any]) -> KpiSummary:
    """Compute every headline KPI on the processed customers table ``df``."""
    geo = config["kpi"]["geography_column"]
    balance = config["kpi"]["balance_column"]
    segment_col = config["kpi"]["balance_segment_column"]
    countries = list(config["columns"]["categorical_expected"][geo])

    eng_rows, hb_rows = [], []
    for country in countries:
        subset = df[df[geo].astype(str) == country]
        eng = kpis.engagement_drop_indicator(subset, config)
        eng_rows.append({"Country": country, "n inactive": eng["inactive"]["n"],
                         "churn inactive": eng["inactive"]["rate"], "n active": eng["active"]["n"],
                         "churn active": eng["active"]["rate"], "EDI (pp)": eng["edi_pp"],
                         "ci_low": eng["ci_low_pp"], "ci_high": eng["ci_high_pp"], "status": eng["status"]})
        hb = kpis.high_balance_churn_rate(subset, config)
        hb_rows.append({"Country": country, "n high-balance": hb["n"], "churned": hb["events"],
                        "churn rate": hb["rate"], "ci_low": hb["ci_low"], "ci_high": hb["ci_high"],
                        "status": hb["status"], "share of country's customers": hb["share_of_customers"]})

    return KpiSummary(
        overall=kpis.overall_churn_rate(df, config),
        geographic_risk_all=kpis.geographic_risk_index(df, config),
        geographic_risk_nonzero=kpis.geographic_risk_index(df[df[balance] > 0], config),
        engagement=kpis.engagement_drop_indicator(df, config),
        engagement_by_country=pd.DataFrame(eng_rows),
        high_balance=kpis.high_balance_churn_rate(df, config),
        high_balance_by_country=pd.DataFrame(hb_rows),
        exposure_by_balance_segment=kpis.balance_exposure(df, config, by=segment_col),
        exposure_overall=kpis.balance_exposure(df, config),
    )


def _gri_table(table: pd.DataFrame, geo: str) -> str:
    rows = [[getattr(r, geo), fmt_int(r.n), fmt_int(r.churned), fmt_pct(r.churn_rate),
             _fmt_ratio(r.risk_index), "n/a" if pd.isna(r.index_ci_low) else
             f"{r.index_ci_low:.2f} to {r.index_ci_high:.2f}", fmt_pct(r.churn_contribution),
             fmt_pct(r.share_of_customers), r.index_note] for r in table.itertuples()]
    return markdown_table(["Country", "Customers", "Churned", "Churn rate", "Risk index",
                           "Index interval (approx.)", "Churn contribution", "Customer share", "Note"], rows)


def _render(s: KpiSummary, config: dict[str, Any]) -> str:
    geo = config["kpi"]["geography_column"]
    segment_col = config["kpi"]["balance_segment_column"]
    o, e, h = s.overall, s.engagement, s.high_balance
    threshold_note = "the median of non-zero balances (see reports/cleaning_log.md for its value)"

    lines = ["# KPI Summary", "",
             "Headline KPIs computed by `src/churn_analytics/kpis.py` on the processed customers table. "
             "Formulas are in `docs/kpi_definitions.md`. All figures are **descriptive associations in one "
             "snapshot**, not causal effects. Rates are shown with segment sizes and 95% confidence "
             "intervals; the interval for a rate is the Wilson interval.", "",
             "## 1. Overall Churn Rate", "",
             f"**{fmt_pct(o['rate'], 2)}** - {fmt_int(o['events'])} of {fmt_int(o['n'])} customers churned "
             f"(95% CI {fmt_ci(o['ci_low'], o['ci_high'], 2)}).", ""]

    lines += ["## 2. Geographic Risk Index (country churn rate / overall churn rate)", "",
              "1.00 = same as the overall rate. The interval divides the country's Wilson interval by the overall "
              "rate treated as fixed, so it is an approximation (each country is part of the overall figure).", "",
              "### 2a. All customers", "", _gri_table(s.geographic_risk_all, geo), "",
              "### 2b. Non-zero-balance customers only (like-for-like)", "",
              "No German customer has a zero balance (see the Geography investigation), so the index above "
              "mixes a country difference with a balance-mix difference. Here every country is compared only "
              "on customers with a non-zero balance, and the overall rate is recomputed for that group. In this table "
              "the churn contribution and customer share are also relative to non-zero-balance customers only.", "",
              _gri_table(s.geographic_risk_nonzero, geo), ""]

    lines += ["## 3. Engagement Drop Indicator (inactive churn rate minus active churn rate)", "",
              f"**{_fmt_pp(e['edi_pp'])}** (95% CI {_fmt_pp(e['ci_low_pp'])} to {_fmt_pp(e['ci_high_pp'])}, "
              "Newcombe hybrid score method). "
              f"Inactive members: {fmt_pct(e['inactive']['rate'])} churned (n = {fmt_int(e['inactive']['n'])}); "
              f"active members: {fmt_pct(e['active']['rate'])} (n = {fmt_int(e['active']['n'])}).", "",
              "Inactivity may be a *symptom* of a customer already deciding to leave, so this indicator "
              "describes an association and does not show which way any influence runs.", "",
              "By country:", "",
              markdown_table(["Country", "Inactive n", "Inactive churn", "Active n", "Active churn", "EDI (pp)",
                              "95% CI (pp)"],
                             [[r["Country"], fmt_int(r["n inactive"]), fmt_pct(r["churn inactive"]),
                               fmt_int(r["n active"]), fmt_pct(r["churn active"]), _fmt_pp(r["EDI (pp)"]),
                               "n/a" if pd.isna(r["ci_low"]) else f"{r['ci_low']:+.1f} to {r['ci_high']:+.1f}"]
                              for r in s.engagement_by_country.to_dict("records")]), ""]

    lines += ["## 4. High-Balance Churn Rate (the brief's \"High-Value Churn Ratio\")", "",
              f"High-balance = balance above {threshold_note}. Balance is **not** profitability or lifetime value.", "",
              f"**{fmt_pct(h['rate'], 2)}** - {fmt_int(h['events'])} of {fmt_int(h['n'])} high-balance customers churned "
              f"(95% CI {fmt_ci(h['ci_low'], h['ci_high'], 2)}). High-balance customers are {fmt_pct(h['share_of_customers'])} "
              f"of all customers and **{fmt_pct(h['churn_contribution'])} of all churners** (their churn contribution).", "",
              "By country (high-balance customers are not spread evenly across countries):", "",
              markdown_table(["Country", "High-balance n", "Churned", "Churn rate", "95% CI",
                              "Share of country's customers", "Note"],
                             [[r["Country"], fmt_int(r["n high-balance"]), fmt_int(r["churned"]),
                               fmt_pct(r["churn rate"]), fmt_ci(r["ci_low"], r["ci_high"]),
                               fmt_pct(r["share of country's customers"]), r["status"]]
                              for r in s.high_balance_by_country.to_dict("records")]), ""]

    expo = s.exposure_overall.iloc[0]
    lines += ["## 5. Balance exposure proxy (NOT lost revenue)", "",
              f"Customers who churned held a total balance of **{_fmt_money(expo['churned_balance'])}**, which is "
              f"{fmt_pct(expo['churned_share_of_segment_balance'])} of all balances "
              f"({_fmt_money(expo['segment_balance'])}). This is an **exposure proxy**: the dataset has no revenue, "
              "margin, fee or interest data, so it says nothing about lost profit or lifetime value.", "",
              markdown_table(["Balance segment", "Customers", "Churned", "Churned customers' balance",
                              "Churned share of segment balance", "Share of all churned balance"],
                             [[str(r[segment_col]), fmt_int(r["n"]), fmt_int(r["churned"]),
                               _fmt_money(r["churned_balance"]), fmt_pct(r["churned_share_of_segment_balance"]),
                               fmt_pct(r["share_of_all_churned_balance"])]
                              for r in s.exposure_by_balance_segment.to_dict("records")]), "",
              "## How to read this report", "",
              "* A **rate** is a share of a group; a **contribution** is a share of all churners. A large "
              "segment can contribute a lot even with an average rate.",
              "* Comparisons that pool countries are **confounded** by the Germany / zero-balance overlap; prefer "
              "the like-for-like tables (2b and the by-country tables).",
              "* Groups below the configured minimum size have their rate withheld (shown as n/a); groups "
              "below the small-sample threshold are flagged in the Note column.", ""]
    return "\n".join(lines)
