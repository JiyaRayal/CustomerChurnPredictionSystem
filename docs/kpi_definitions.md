# KPI Definitions

Status: **implemented in `src/churn_analytics/kpis.py` and covered by tests** (`tests/test_kpis.py`,
`tests/test_stats_utils.py`). This document and the code must always agree; if one changes, change
the other. Headline values on the supplied dataset are in `reports/kpi_summary.md` (generated).

## Implementation map

| KPI | Function | Output |
|---|---|---|
| Overall Churn Rate | `overall_churn_rate` | one dict (n, churned, rate, interval, status) |
| Segment Churn Rate + Churn Contribution + customer share | `segment_churn_table` | table, one row per segment (or per combination when drilling down) |
| Geographic Risk Index | `geographic_risk_index` | table, one row per country |
| Engagement Drop Indicator | `engagement_drop_indicator` | one dict |
| High-Balance Churn Rate | `high_balance_churn_rate` | one dict |
| Balance exposure proxy | `balance_exposure` | table (overall or per segment) |

## Conventions

* A **valid customer** is a record that passes the Phase 2 validation checks. Records are never
  silently dropped. KPI functions refuse input whose target is missing or not 0/1.
* `Exited = 1` means churned (assumption D6; the observation window is undocumented).
* A **segment** is a group defined by one or more segmentation fields (for example
  `Geography = Germany`, or `AgeBand = 46-60 AND IsActiveMember = 0`).
* **KPIs describe the rows passed in.** If a dashboard filters to "Germany, age 46-60", then
  "all customers" and "all churned customers" in the formulas below mean *the filtered customers*.
  Contributions therefore always add up to 100% within the data shown.
* **Empty-group rule:** if a denominator is 0, the KPI is **n/a (undefined)**, never 0. A rate of
  0% means "there were customers and none churned"; n/a means "there were no customers to measure".
* **Small-group rule** (thresholds in `config/segmentation.toml`): n < 100 -> flagged *small sample*;
  n < 30 -> rate withheld as *withheld (too small)* with the count still shown.
* Every rate is shown **with its segment size (n)** and a 95% **Wilson confidence interval**.
* **No customer is lost in a group table:** groups with a missing segment value are kept as their own
  row, and the code checks that group sizes add back up to the total.
* All KPIs are **descriptive associations in one snapshot**. None shows that a segment
  characteristic *causes* churn.

## 1. Overall Churn Rate

| Item | Definition |
|---|---|
| Formula | `churned customers / total valid customers` |
| Numerator | count of customers with `Exited = 1` |
| Denominator | count of all customers |
| Unit | percentage, with n and 95% Wilson interval |
| Empty group | denominator = 0 -> n/a |

## 2. Segment Churn Rate

| Item | Definition |
|---|---|
| Formula | `churned customers in segment / all customers in segment` |
| Numerator | customers in the segment with `Exited = 1` |
| Denominator | all customers in the segment |
| Unit | percentage, with n and 95% Wilson interval |
| Empty group | segment has 0 customers -> n/a (undefined) |
| Small group | see small-group rule above |

## 3. Churn Contribution (always shown with Share of Customers)

| Item | Definition |
|---|---|
| Formula | `churned customers in segment / all churned customers` |
| Numerator | customers in the segment with `Exited = 1` |
| Denominator | total churned customers in the rows passed in |
| Unit | percentage; across one complete, non-overlapping segmentation the values sum to 100% |
| Empty group | total churned customers = 0 -> n/a for every segment |
| Share of Customers | `segment customers / all customers`, shown next to the contribution |

*Why both?* A segment can have a high churn **rate** but a small **contribution** (few customers),
or a modest rate but a large contribution (many customers). Comparing contribution with customer
share shows whether a segment is over- or under-represented among churners.

## 4. Geographic Risk Index (GRI)

| Item | Definition |
|---|---|
| Formula | `country churn rate / overall churn rate` |
| Numerator | churn rate of the country (France, Germany or Spain) |
| Denominator | overall churn rate of the rows passed in |
| Unit | ratio; 1.00 = same as overall, 1.50 = 50% higher than overall |
| Undefined (n/a) when | overall churn rate is 0 or unavailable (empty or below the minimum size), or the country's own rate is unavailable (empty, or below the minimum size) |
| Interval | the country's Wilson interval divided by the overall rate, treating the overall rate as a fixed number |
| Limitations | Each country is part of the overall figure, so the index is not a comparison against "everyone else", and the interval ignores the overall rate's own (small) uncertainty; treat it as approximate. A customer-weighted average of the index is exactly 1 by construction. |
| Required companion view | Because no German customer has a zero balance (see the Geography investigation), the GRI is reported **twice**: for all customers and for **non-zero-balance customers only**, where the overall rate is recomputed for that group. |

## 5. Engagement Drop Indicator (EDI)

| Item | Definition |
|---|---|
| Formula | `churn rate of inactive members - churn rate of active members` |
| Inputs | inactive = `IsActiveMember = 0`; active = `IsActiveMember = 1` (column set in config) |
| Unit | **percentage points (pp)**, not percent; positive = inactive members churn more |
| Undefined (n/a) when | either group has 0 customers, or either group is below the minimum size |
| Interval | **Newcombe hybrid score method** (Newcombe 1998, "Method 10") for the difference of two independent proportions; checked against a published example in the tests |
| Flag | *small sample* if either group has fewer than 100 customers |
| Limitation | Inactivity may be a *symptom* of a customer already deciding to leave, not only a cause. The indicator describes an association and does not establish direction. |

## 6. High-Balance Churn Rate (the brief's "High-Value Churn Ratio")

The brief calls this KPI *High-Value Churn Ratio*. Following the project owner's guidance it is named
**High-Balance Churn Rate**, because balance is not profitability or lifetime value.

| Item | Definition |
|---|---|
| Formula | `churned High-balance customers / all High-balance customers` |
| Segment | `Balance > median of non-zero balances` (threshold computed from the data; see `reports/cleaning_log.md`) |
| Unit | percentage, with n and 95% Wilson interval |
| Empty group | no High-balance customers -> n/a |
| Companion figures | the segment's share of all customers; its share of all churners (a Churn Contribution); its balance exposure proxy |
| Required companion view | reported pooled **and by country**, because countries differ in how many high-balance customers they have |
| Status | **Confirmed**: the project owner accepted the proposed definition (decision D16) |

## Supporting measure: Balance Exposure Proxy

| Item | Definition |
|---|---|
| Formula | `sum of Balance for churned customers` (overall or per segment) |
| Also reported | churned balance as a share of the segment's total balance; the segment's share of all churned balance |
| Undefined (n/a) when | the segment's total balance is 0 (e.g. the Zero-balance segment), or there is no churned balance |
| Meaning | account balances held by customers who left: an **exposure proxy** |
| It is **not** | lost revenue, lost profit or lifetime value: the data contains no revenue, margin, fees or interest information |
