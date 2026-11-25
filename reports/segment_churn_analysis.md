# Segment Churn Analysis

Descriptive analysis of how churn varies across customer segments, produced by `src/churn_analytics/analysis.py`. Segment boundaries come from `config/segmentation.toml` (see `docs/segmentation_rules.md`). Rates are shown with group sizes and 95% Wilson confidence intervals. A group with no customers has an undefined rate (n/a), not 0%; groups below 30 customers have their rate withheld and groups below 100 are flagged *small sample* (marked * in matrices).

**How to read this report:** every table is a *single-variable* or *two-variable* view. Age, number of products, balance, activity and country are related to each other, and none of the tables controls for the others. All findings are **associations in one snapshot, not causal effects**.

## Key findings (computed from the data)

1. Overall churn rate is 20.37% across 10,000 customers.
2. Strongest single-variable associations with churn (Cramer's V): **NumOfProducts** (V = 0.39, medium); **AgeBand** (V = 0.35, medium); **Geography** (V = 0.17, small).
3. Variables with a negligible association with churn in this dataset: CreditScoreBand (V = 0.02), TenureGroup (V = 0.01), HasCrCard (V = 0.01).
4. Highest segment churn rates: NumOfProducts = 4 100.0% (n = 60, small sample); NumOfProducts = 3 82.7% (n = 266); AgeBand = 46-60 51.1% (n = 1,647); Geography = Germany 32.4% (n = 2,509); NumOfProducts = 1 27.7% (n = 5,084).
5. Segments contributing the most churners beyond their share of customers: AgeBand = 46-60 (41.3% of churners vs 16.5% of customers); NumOfProducts = 1 (69.2% of churners vs 50.8% of customers); IsActiveMember = Inactive (63.9% of churners vs 48.5% of customers).
6. Gender: the gap (Female - Male) is +8.6 pp overall (95% CI +7.0 pp to +10.2 pp) and ranges from +7.6 pp to +9.7 pp across countries.
7. Country x age (cells with at least 100 customers): highest churn is Germany / 46-60 at 67.3% (n = 502); lowest is France / Under 30 at 5.2% (n = 866).
8. Credit score: with the fixed bands V = 0.02 (negligible; spread 2.3 pp); with equal-sized terciles V = 0.02 (negligible; spread 1.8 pp).
9. Churned vs retained customers differ most on: Age (churned mean 44.8 vs retained 37.4, d = +0.74, medium); Balance (churned mean 91,108.5 vs retained 72,745.3, d = +0.30, small).
10. **Worth confirming with the data owner:** NumOfProducts = 4 has a churn rate of exactly 100% (60 of 60 customers). The data cannot show why; an extreme result in a small group may reflect how the data was recorded.

## 1. Strength of association with churn

Cramer's V is an effect size from 0 (no association) to 1 (perfect). Labels use the cut-offs in the config (0.1, 0.3, 0.5), which are conventions for describing size, not tests of importance.

| Rank | Variable | Groups | Cramer's V | Effect | Highest-churn segment | Lowest-churn segment | Spread (pp) | p-value | Note |
|---|---|---|---|---|---|---|---|---|---|
| 1 | NumOfProducts | 4 | 0.388 | medium | 4 (100.0%)* | 2 (7.6%) | 92.4 | <0.001 |  |
| 2 | AgeBand | 4 | 0.351 | medium | 46-60 (51.1%) | Under 30 (7.6%) | 43.6 | <0.001 |  |
| 3 | Geography | 3 | 0.174 | small | Germany (32.4%) | France (16.2%) | 16.3 | <0.001 |  |
| 4 | IsActiveMember | 2 | 0.156 | small | Inactive (26.9%) | Active (14.3%) | 12.6 | <0.001 |  |
| 5 | BalanceSegment | 3 | 0.122 | small | High-balance (24.2%) | Zero-balance (13.8%) | 10.3 | <0.001 |  |
| 6 | Gender | 2 | 0.107 | small | Female (25.1%) | Male (16.5%) | 8.6 | <0.001 |  |
| 7 | CreditScoreBand | 3 | 0.023 | negligible | Low (22.0%) | Medium (19.7%) | 2.3 | 0.068 |  |
| 8 | TenureGroup | 3 | 0.012 | negligible | New (21.2%) | Mid-term (19.9%) | 1.2 | 0.466 |  |
| 9 | HasCrCard | 2 | 0.007 | negligible | No credit card (20.8%) | Has credit card (20.2%) | 0.6 | 0.475 |  |

With 9 variables compared, p-values are almost all tiny in a dataset of this size; read the effect size (V) and the group sizes, not the p-value. 'Spread' is the gap between the highest and lowest segment rate among segments with a reportable rate; `*` marks a small-sample segment, which can make the spread look larger than it would for well-populated groups.

## 2. Churn by segment

'Rate vs overall' is the segment rate divided by the overall rate (1.00 = average). 'Contribution' is the segment's share of all churners; compare it with its share of customers.

### Geography

| Segment | Customers | Churned | Churn rate | 95% CI | Share of customers | Churn contribution | Rate vs overall | Note |
|---|---|---|---|---|---|---|---|---|
| France | 5,014 | 810 | 16.2% | 15.2% to 17.2% | 50.1% | 39.8% | 0.79 |  |
| Germany | 2,509 | 814 | 32.4% | 30.6% to 34.3% | 25.1% | 40.0% | 1.59 |  |
| Spain | 2,477 | 413 | 16.7% | 15.3% to 18.2% | 24.8% | 20.3% | 0.82 |  |

### Gender

| Segment | Customers | Churned | Churn rate | 95% CI | Share of customers | Churn contribution | Rate vs overall | Note |
|---|---|---|---|---|---|---|---|---|
| Female | 4,543 | 1,139 | 25.1% | 23.8% to 26.4% | 45.4% | 55.9% | 1.23 |  |
| Male | 5,457 | 898 | 16.5% | 15.5% to 17.5% | 54.6% | 44.1% | 0.81 |  |

### AgeBand

| Segment | Customers | Churned | Churn rate | 95% CI | Share of customers | Churn contribution | Rate vs overall | Note |
|---|---|---|---|---|---|---|---|---|
| Under 30 | 1,641 | 124 | 7.6% | 6.4% to 8.9% | 16.4% | 6.1% | 0.37 |  |
| 30-45 | 6,248 | 956 | 15.3% | 14.4% to 16.2% | 62.5% | 46.9% | 0.75 |  |
| 46-60 | 1,647 | 842 | 51.1% | 48.7% to 53.5% | 16.5% | 41.3% | 2.51 |  |
| 61+ | 464 | 115 | 24.8% | 21.1% to 28.9% | 4.6% | 5.6% | 1.22 |  |

### CreditScoreBand

| Segment | Customers | Churned | Churn rate | 95% CI | Share of customers | Churn contribution | Rate vs overall | Note |
|---|---|---|---|---|---|---|---|---|
| Low | 2,362 | 520 | 22.0% | 20.4% to 23.7% | 23.6% | 25.5% | 1.08 |  |
| Medium | 5,759 | 1,137 | 19.7% | 18.7% to 20.8% | 57.6% | 55.8% | 0.97 |  |
| High | 1,879 | 380 | 20.2% | 18.5% to 22.1% | 18.8% | 18.7% | 0.99 |  |

### TenureGroup

| Segment | Customers | Churned | Churn rate | 95% CI | Share of customers | Churn contribution | Rate vs overall | Note |
|---|---|---|---|---|---|---|---|---|
| New | 2,496 | 528 | 21.2% | 19.6% to 22.8% | 25.0% | 25.9% | 1.04 |  |
| Mid-term | 5,005 | 998 | 19.9% | 18.9% to 21.1% | 50.0% | 49.0% | 0.98 |  |
| Long-term | 2,499 | 511 | 20.4% | 18.9% to 22.1% | 25.0% | 25.1% | 1.00 |  |

### BalanceSegment

| Segment | Customers | Churned | Churn rate | 95% CI | Share of customers | Churn contribution | Rate vs overall | Note |
|---|---|---|---|---|---|---|---|---|
| Zero-balance | 3,617 | 500 | 13.8% | 12.7% to 15.0% | 36.2% | 24.5% | 0.68 |  |
| Low-balance | 3,192 | 766 | 24.0% | 22.5% to 25.5% | 31.9% | 37.6% | 1.18 |  |
| High-balance | 3,191 | 771 | 24.2% | 22.7% to 25.7% | 31.9% | 37.8% | 1.19 |  |

### NumOfProducts

| Segment | Customers | Churned | Churn rate | 95% CI | Share of customers | Churn contribution | Rate vs overall | Note |
|---|---|---|---|---|---|---|---|---|
| 1 | 5,084 | 1,409 | 27.7% | 26.5% to 29.0% | 50.8% | 69.2% | 1.36 |  |
| 2 | 4,590 | 348 | 7.6% | 6.9% to 8.4% | 45.9% | 17.1% | 0.37 |  |
| 3 | 266 | 220 | 82.7% | 77.7% to 86.8% | 2.7% | 10.8% | 4.06 |  |
| 4 | 60 | 60 | 100.0% | 94.0% to 100.0% | 0.6% | 2.9% | 4.91 | small sample |

### HasCrCard

| Segment | Customers | Churned | Churn rate | 95% CI | Share of customers | Churn contribution | Rate vs overall | Note |
|---|---|---|---|---|---|---|---|---|
| No credit card | 2,945 | 613 | 20.8% | 19.4% to 22.3% | 29.4% | 30.1% | 1.02 |  |
| Has credit card | 7,055 | 1,424 | 20.2% | 19.3% to 21.1% | 70.5% | 69.9% | 0.99 |  |

### IsActiveMember

| Segment | Customers | Churned | Churn rate | 95% CI | Share of customers | Churn contribution | Rate vs overall | Note |
|---|---|---|---|---|---|---|---|---|
| Inactive | 4,849 | 1,302 | 26.9% | 25.6% to 28.1% | 48.5% | 63.9% | 1.32 |  |
| Active | 5,151 | 735 | 14.3% | 13.3% to 15.3% | 51.5% | 36.1% | 0.70 |  |

## 3. Churn rate vs churn contribution

The 8 segments whose share of churners differs most from their share of customers (a positive gap means more churners than the segment's size alone would suggest). Within one variable the gaps add up to zero.

| Variable | Segment | Customers | Churn rate | Share of customers | Churn contribution | Gap (pp) | Note |
|---|---|---|---|---|---|---|---|
| NumOfProducts | 2 | 4,590 | 7.6% | 45.9% | 17.1% | -28.8 pp |  |
| AgeBand | 46-60 | 1,647 | 51.1% | 16.5% | 41.3% | +24.9 pp |  |
| NumOfProducts | 1 | 5,084 | 27.7% | 50.8% | 69.2% | +18.3 pp |  |
| AgeBand | 30-45 | 6,248 | 15.3% | 62.5% | 46.9% | -15.5 pp |  |
| IsActiveMember | Active | 5,151 | 14.3% | 51.5% | 36.1% | -15.4 pp |  |
| IsActiveMember | Inactive | 4,849 | 26.9% | 48.5% | 63.9% | +15.4 pp |  |
| Geography | Germany | 2,509 | 32.4% | 25.1% | 40.0% | +14.9 pp |  |
| BalanceSegment | Zero-balance | 3,617 | 13.8% | 36.2% | 24.5% | -11.6 pp |  |

## 4. Gender comparison

Gap = churn rate of Female minus churn rate of Male, in percentage points, with a Newcombe 95% interval.

| Scope | Female n | Female churn | Male n | Male churn | Gap | 95% CI (pp) | Note |
|---|---|---|---|---|---|---|---|
| All customers | 4,543 | 25.1% | 5,457 | 16.5% | +8.6 pp | +7.0 to +10.2 |  |
| France | 2,261 | 20.3% | 2,753 | 12.7% | +7.6 pp | +5.6 to +9.7 |  |
| Germany | 1,193 | 37.6% | 1,316 | 27.8% | +9.7 pp | +6.1 to +13.4 |  |
| Spain | 1,089 | 21.2% | 1,388 | 13.1% | +8.1 pp | +5.1 to +11.1 |  |

## 5. Two-variable views

Cell format: churn rate (customers). `*` = small sample (fewer than 100 customers); `n/a` = rate not shown because the group is empty or below 30 customers.

### 5a. Geography x AgeBand, all customers

| Geography | Under 30 | 30-45 | 46-60 | 61+ |
|---|---|---|---|---|
| France | 5.2% (n=866) | 11.9% (n=3,168) | 45.8% (n=749) | 19.9% (n=231) |
| Germany | 12.6% (n=372) | 25.3% (n=1,522) | 67.3% (n=502) | 38.9% (n=113) |
| Spain | 7.9% (n=403) | 12.5% (n=1,558) | 40.7% (n=396) | 20.8% (n=120) |

### 5b. Geography x AgeBand, non-zero-balance customers only (like-for-like)

No German customer has a zero balance, so this view compares countries on customers with a balance.

| Geography | Under 30 | 30-45 | 46-60 | 61+ |
|---|---|---|---|---|
| France | 6.5% (n=429) | 13.5% (n=1,649) | 47.7% (n=398) | 26.7% (n=120) |
| Germany | 12.6% (n=372) | 25.3% (n=1,522) | 67.3% (n=502) | 38.9% (n=113) |
| Spain | 12.2% (n=197) | 14.3% (n=796) | 43.9% (n=221) | 23.4% (n=64)* |

### 5c. Geography x balance segment

Balance-segment results are shown by country because the countries differ in how many zero-balance customers they have (none in Germany).

| Geography | Zero-balance | Low-balance | High-balance |
|---|---|---|---|
| France | 13.9% (n=2,418) | 16.8% (n=1,288) | 19.6% (n=1,308) |
| Germany | n/a (n=0) | 33.3% (n=1,261) | 31.6% (n=1,248) |
| Spain | 13.6% (n=1,199) | 20.2% (n=643) | 18.9% (n=635) |

## 6. Credit score: sensitivity to the chosen grouping

The fixed bands (<580, 580-739, >=740) are an analytical choice. This repeats the analysis with equal-sized terciles to see whether conclusions depend on that choice.

| Grouping | Segment | Customers | Churned | Churn rate | 95% CI | Note |
|---|---|---|---|---|---|---|
| CreditScoreBand | Low | 2,362 | 520 | 22.0% | 20.4% to 23.7% |  |
| CreditScoreBand | Medium | 5,759 | 1,137 | 19.7% | 18.7% to 20.8% |  |
| CreditScoreBand | High | 1,879 | 380 | 20.2% | 18.5% to 22.1% |  |
| CreditScoreTercile | Low (tercile) | 3,363 | 724 | 21.5% | 20.2% to 22.9% |  |
| CreditScoreTercile | Medium (tercile) | 3,334 | 659 | 19.8% | 18.4% to 21.2% |  |
| CreditScoreTercile | High (tercile) | 3,303 | 654 | 19.8% | 18.5% to 21.2% |  |

| Grouping | Cramer's V | Effect | Spread (pp) | p-value |
|---|---|---|---|---|
| CreditScoreBand | 0.023 | negligible | 2.3 | 0.068 |
| CreditScoreTercile | 0.020 | negligible | 1.8 | 0.123 |

## 7. Churned vs retained customers

### 7a. Numeric characteristics

d = standardised mean difference (churned minus retained, pooled standard deviation), with an approximate 95% interval; labels use the cut-offs in the config (0.2, 0.5, 0.8).

| Column | Mean churned | Mean retained | Median churned | Median retained | d | 95% CI of d | Effect |
|---|---|---|---|---|---|---|---|
| Age | 44.84 | 37.41 | 45.00 | 36.00 | +0.74 | +0.69 to +0.79 | medium |
| CreditScore | 645.35 | 651.85 | 646.00 | 653.00 | -0.07 | -0.12 to -0.02 | negligible |
| Balance | 91,108.54 | 72,745.30 | 109,349.29 | 92,072.68 | +0.30 | +0.25 to +0.35 | small |
| EstimatedSalary | 101,465.68 | 99,738.39 | 102,460.84 | 99,645.04 | +0.03 | -0.02 to +0.08 | negligible |
| Tenure | 4.93 | 5.03 | 5.00 | 5.00 | -0.03 | -0.08 to +0.01 | negligible |

### 7b. Composition

Share of retained customers and share of churned customers in each segment. This is the reverse view of the rate tables: a segment can be common among churners without having a high churn rate.

| Variable | Segment | % of retained | % of churned | Difference (pp) |
|---|---|---|---|---|
| Geography | France | 52.8% | 39.8% | -13.0 pp |
| Geography | Germany | 21.3% | 40.0% | +18.7 pp |
| Geography | Spain | 25.9% | 20.3% | -5.6 pp |
| Gender | Female | 42.7% | 55.9% | +13.2 pp |
| Gender | Male | 57.3% | 44.1% | -13.2 pp |
| AgeBand | Under 30 | 19.1% | 6.1% | -13.0 pp |
| AgeBand | 30-45 | 66.5% | 46.9% | -19.5 pp |
| AgeBand | 46-60 | 10.1% | 41.3% | +31.2 pp |
| AgeBand | 61+ | 4.4% | 5.6% | +1.3 pp |
| CreditScoreBand | Low | 23.1% | 25.5% | +2.4 pp |
| CreditScoreBand | Medium | 58.0% | 55.8% | -2.2 pp |
| CreditScoreBand | High | 18.8% | 18.7% | -0.2 pp |
| TenureGroup | New | 24.7% | 25.9% | +1.2 pp |
| TenureGroup | Mid-term | 50.3% | 49.0% | -1.3 pp |
| TenureGroup | Long-term | 25.0% | 25.1% | +0.1 pp |
| BalanceSegment | Zero-balance | 39.1% | 24.5% | -14.6 pp |
| BalanceSegment | Low-balance | 30.5% | 37.6% | +7.1 pp |
| BalanceSegment | High-balance | 30.4% | 37.8% | +7.5 pp |
| NumOfProducts | 1 | 46.2% | 69.2% | +23.0 pp |
| NumOfProducts | 2 | 53.3% | 17.1% | -36.2 pp |
| NumOfProducts | 3 | 0.6% | 10.8% | +10.2 pp |
| NumOfProducts | 4 | 0.0% | 2.9% | +2.9 pp |
| HasCrCard | No credit card | 29.3% | 30.1% | +0.8 pp |
| HasCrCard | Has credit card | 70.7% | 69.9% | -0.8 pp |
| IsActiveMember | Inactive | 44.5% | 63.9% | +19.4 pp |
| IsActiveMember | Active | 55.5% | 36.1% | -19.4 pp |

## 8. What this analysis cannot tell us

* **Cause.** These are associations in one snapshot. Nothing here shows that a characteristic makes customers leave, or why a segment differs.
* **Overlap between variables.** Each table looks at one (or two) variables at a time. Age, number of products, balance, activity and country are related to each other, so a difference seen for one variable may partly reflect another. No multivariable adjustment is performed in this project.
* **Multiple comparisons.** Many segments and variables are compared; some differences will look larger by chance, especially in small groups. Prefer large groups and effect sizes.
* **Small groups.** Segments marked *small sample* have wide intervals; rates below the minimum size are withheld.
* **Geography and balance.** No German customer has a zero balance, so Geography and balance-segment results overlap; use the like-for-like and by-country views (5b, 5c).
* **Extreme rates.** A rate of exactly 0% or 100% in a small group should be confirmed with the data owner before being interpreted.
* **Scope.** One snapshot of three countries; the meaning of `Exited` is an assumption (decision D6) and the data's provenance is unconfirmed.
