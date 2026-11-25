# KPI Summary

Headline KPIs computed by `src/churn_analytics/kpis.py` on the processed customers table. Formulas are in `docs/kpi_definitions.md`. All figures are **descriptive associations in one snapshot**, not causal effects. Rates are shown with segment sizes and 95% confidence intervals; the interval for a rate is the Wilson interval.

## 1. Overall Churn Rate

**20.37%** - 2,037 of 10,000 customers churned (95% CI 19.59% to 21.17%).

## 2. Geographic Risk Index (country churn rate / overall churn rate)

1.00 = same as the overall rate. The interval divides the country's Wilson interval by the overall rate treated as fixed, so it is an approximation (each country is part of the overall figure).

### 2a. All customers

| Country | Customers | Churned | Churn rate | Risk index | Index interval (approx.) | Churn contribution | Customer share | Note |
|---|---|---|---|---|---|---|---|---|
| France | 5,014 | 810 | 16.2% | 0.79 | 0.74 to 0.84 | 39.8% | 50.1% | ok |
| Germany | 2,509 | 814 | 32.4% | 1.59 | 1.50 to 1.68 | 40.0% | 25.1% | ok |
| Spain | 2,477 | 413 | 16.7% | 0.82 | 0.75 to 0.89 | 20.3% | 24.8% | ok |

### 2b. Non-zero-balance customers only (like-for-like)

No German customer has a zero balance (see the Geography investigation), so the index above mixes a country difference with a balance-mix difference. Here every country is compared only on customers with a non-zero balance, and the overall rate is recomputed for that group. In this table the churn contribution and customer share are also relative to non-zero-balance customers only.

| Country | Customers | Churned | Churn rate | Risk index | Index interval (approx.) | Churn contribution | Customer share | Note |
|---|---|---|---|---|---|---|---|---|
| France | 2,596 | 473 | 18.2% | 0.76 | 0.70 to 0.82 | 30.8% | 40.7% | ok |
| Germany | 2,509 | 814 | 32.4% | 1.35 | 1.27 to 1.42 | 53.0% | 39.3% | ok |
| Spain | 1,278 | 250 | 19.6% | 0.81 | 0.73 to 0.91 | 16.3% | 20.0% | ok |

## 3. Engagement Drop Indicator (inactive churn rate minus active churn rate)

**+12.6 pp** (95% CI +11.0 pp to +14.2 pp, Newcombe hybrid score method). Inactive members: 26.9% churned (n = 4,849); active members: 14.3% (n = 5,151).

Inactivity may be a *symptom* of a customer already deciding to leave, so this indicator describes an association and does not show which way any influence runs.

By country:

| Country | Inactive n | Inactive churn | Active n | Active churn | EDI (pp) | 95% CI (pp) |
|---|---|---|---|---|---|---|
| France | 2,423 | 21.1% | 2,591 | 11.5% | +9.6 pp | +7.6 to +11.7 |
| Germany | 1,261 | 41.1% | 1,248 | 23.7% | +17.4 pp | +13.7 to +20.9 |
| Spain | 1,165 | 23.3% | 1,312 | 10.7% | +12.6 pp | +9.7 to +15.6 |

## 4. High-Balance Churn Rate (the brief's "High-Value Churn Ratio")

High-balance = balance above the median of non-zero balances (see reports/cleaning_log.md for its value). Balance is **not** profitability or lifetime value.

**24.16%** - 771 of 3,191 high-balance customers churned (95% CI 22.71% to 25.68%). High-balance customers are 31.9% of all customers and **37.8% of all churners** (their churn contribution).

By country (high-balance customers are not spread evenly across countries):

| Country | High-balance n | Churned | Churn rate | 95% CI | Share of country's customers | Note |
|---|---|---|---|---|---|---|
| France | 1,308 | 257 | 19.6% | 17.6% to 21.9% | 26.1% | ok |
| Germany | 1,248 | 394 | 31.6% | 29.1% to 34.2% | 49.7% | ok |
| Spain | 635 | 120 | 18.9% | 16.0% to 22.1% | 25.6% | ok |

## 5. Balance exposure proxy (NOT lost revenue)

Customers who churned held a total balance of **185,588,095**, which is 24.3% of all balances (764,858,893). This is an **exposure proxy**: the dataset has no revenue, margin, fee or interest data, so it says nothing about lost profit or lifetime value.

| Balance segment | Customers | Churned | Churned customers' balance | Churned share of segment balance | Share of all churned balance |
|---|---|---|---|---|---|
| Zero-balance | 3,617 | 500 | 0 | n/a | 0.0% |
| Low-balance | 3,192 | 766 | 74,784,499 | 24.4% | 40.3% |
| High-balance | 3,191 | 771 | 110,803,596 | 24.2% | 59.7% |

## How to read this report

* A **rate** is a share of a group; a **contribution** is a share of all churners. A large segment can contribute a lot even with an average rate.
* Comparisons that pool countries are **confounded** by the Germany / zero-balance overlap; prefer the like-for-like tables (2b and the by-country tables).
* Groups below the configured minimum size have their rate withheld (shown as n/a); groups below the small-sample threshold are flagged in the Note column.
