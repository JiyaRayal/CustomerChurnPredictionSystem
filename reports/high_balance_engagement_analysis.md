# High-Balance, Salary, Engagement and Tenure Analysis

Descriptive analysis produced by `src/churn_analytics/balance_engagement.py`. Rates come with group sizes and 95% Wilson intervals; differences between two groups use Newcombe intervals (percentage points, pp). A group with no customers is n/a (not 0%); groups below 30 customers have their rate withheld; groups below 100 are flagged *small sample* (marked * in matrices).

**Terms.** *High-balance* means a balance above the median of non-zero balances (see `reports/cleaning_log.md`). It is **not** a measure of profitability or lifetime value, and neither is salary. *Balance exposure proxy* is the balance held by customers who churned; it is **not lost revenue**, because the dataset has no revenue, margin or fee data.

**How to read this report:** results are single- or two-variable views of one snapshot. They are associations, not causal effects, and no table controls for every other variable.

## Key findings (computed from the data)

1. Churn rates by balance segment: High-balance 24.2% (n = 3,191), Low-balance 24.0% (n = 3,192), Zero-balance 13.8% (n = 3,617).
2. Among customers with a non-zero balance, High-balance customers churn +0.2 pp compared with Low-balance customers (95% CI -1.9 to +2.3 pp). Inside 7 country / age strata the High-minus-Low gap ranges from -1.7 pp to +3.0 pp; the interval excludes zero in 0 of them.
3. Directly standardised High-minus-Low gap (same customer mix for both groups): by Geography +0.22 pp (95% CI -1.8 to +2.3, covering 100% of non-zero customers); by Geography x AgeBand +0.48 pp (95% CI -1.5 to +2.4, covering 99% of non-zero customers). High-balance customers' churn rate is higher than Zero-balance customers'. Every standardised interval includes zero, so High-balance customers are not distinguishable from comparable Low-balance customers in this dataset.
4. Segments most over-represented among High-balance customers (share of High-balance vs share of all customers): NumOfProducts = 1 (65.6% vs 50.8%, +14.8 pp); Geography = Germany (39.1% vs 25.1%, +14.0 pp); Gender = Male (55.8% vs 54.6%, +1.2 pp). Differences of a point or two are small.
5. Highest churn among High-balance customers (segments with at least 100 customers): AgeBand = 46-60 55.0% (n = 549); Geography = Germany 31.6% (n = 1,248); IsActiveMember = Inactive 31.2% (n = 1,569).
6. Across equal-sized groups of non-zero balances, churn ranges from 20.8% (Q1 (lowest)) to 26.8% (Q3), a spread of 6.0 percentage points, with no steady rise or fall across the groups.
7. Salary: churn rates across salary thirds range from 19.8% to 21.2%. The rank correlation between salary and balance among non-zero-balance customers is -0.001 (p = 0.925): no statistically detectable monotone relationship in this dataset.
8. Engagement: inactive members churn +12.6 pp more than active members overall (95% CI +11.0 to +14.2). The gap is positive in 18 of 18 segments where it can be estimated; the largest among segments with at least 100 customers per group is AgeBand = 46-60 (+33.0 pp). A larger gap (+70.8 pp in AgeBand = 61+) rests on a small sample (n = 89 inactive, 375 active).
9. Tenure: churn by tenure year ranges from 17.2% (year 7) to 23.0% (year 0). The rank correlation between tenure year and churn rate across the 11 years is -0.37 (p = 0.259): no statistically detectable trend in this dataset.
10. Balance exposure proxy (balance held by customers who churned; **not lost revenue**): 185.6M, 24.3% of all balances. High-balance customers hold 59.7% of it; inactive High-balance customers alone hold 38.0% while being 15.7% of customers.
11. Concentration: the top 10% of churned customers (by balance) hold 18.9% of the churned balance; 500 of 2,037 churned customers had a zero balance and add nothing to it.

## 1. Who are the High-balance customers?

Share of High-balance customers in each segment compared with the share of all customers. 'High-balance share of segment' is the percentage of the segment's customers who are High-balance.

| Variable | Segment | High-balance customers | % of High-balance | % of all customers | Difference (pp) | High-balance share of segment |
|---|---|---|---|---|---|---|
| Geography | France | 1,308 | 41.0% | 50.1% | -9.1 pp | 26.1% |
| Geography | Germany | 1,248 | 39.1% | 25.1% | +14.0 pp | 49.7% |
| Geography | Spain | 635 | 19.9% | 24.8% | -4.9 pp | 25.6% |
| Gender | Female | 1,411 | 44.2% | 45.4% | -1.2 pp | 31.1% |
| Gender | Male | 1,780 | 55.8% | 54.6% | +1.2 pp | 32.6% |
| AgeBand | Under 30 | 510 | 16.0% | 16.4% | -0.4 pp | 31.1% |
| AgeBand | 30-45 | 1,982 | 62.1% | 62.5% | -0.4 pp | 31.7% |
| AgeBand | 46-60 | 549 | 17.2% | 16.5% | +0.7 pp | 33.3% |
| AgeBand | 61+ | 150 | 4.7% | 4.6% | +0.1 pp | 32.3% |
| TenureGroup | New | 808 | 25.3% | 25.0% | +0.4 pp | 32.4% |
| TenureGroup | Mid-term | 1,578 | 49.5% | 50.0% | -0.6 pp | 31.5% |
| TenureGroup | Long-term | 805 | 25.2% | 25.0% | +0.2 pp | 32.2% |
| NumOfProducts | 1 | 2,093 | 65.6% | 50.8% | +14.8 pp | 41.2% |
| NumOfProducts | 2 | 991 | 31.1% | 45.9% | -14.8 pp | 21.6% |
| NumOfProducts | 3 | 82 | 2.6% | 2.7% | -0.1 pp | 30.8% |
| NumOfProducts | 4 | 25 | 0.8% | 0.6% | +0.2 pp | 41.7% |
| IsActiveMember | Inactive | 1,569 | 49.2% | 48.5% | +0.7 pp | 32.4% |
| IsActiveMember | Active | 1,622 | 50.8% | 51.5% | -0.7 pp | 31.5% |

## 2. Churn among High-balance customers

Churn rates inside the High-balance group only. Contributions are shares of High-balance churners.

### Geography

| Segment | Customers | Churned | Churn rate | 95% CI | Share of High-balance customers | Contribution to High-balance churn | Note |
|---|---|---|---|---|---|---|---|
| France | 1,308 | 257 | 19.6% | 17.6% to 21.9% | 41.0% | 33.3% |  |
| Germany | 1,248 | 394 | 31.6% | 29.1% to 34.2% | 39.1% | 51.1% |  |
| Spain | 635 | 120 | 18.9% | 16.0% to 22.1% | 19.9% | 15.6% |  |

### Gender

| Segment | Customers | Churned | Churn rate | 95% CI | Share of High-balance customers | Contribution to High-balance churn | Note |
|---|---|---|---|---|---|---|---|
| Female | 1,411 | 416 | 29.5% | 27.2% to 31.9% | 44.2% | 54.0% |  |
| Male | 1,780 | 355 | 19.9% | 18.2% to 21.9% | 55.8% | 46.0% |  |

### AgeBand

| Segment | Customers | Churned | Churn rate | 95% CI | Share of High-balance customers | Contribution to High-balance churn | Note |
|---|---|---|---|---|---|---|---|
| Under 30 | 510 | 58 | 11.4% | 8.9% to 14.4% | 16.0% | 7.5% |  |
| 30-45 | 1,982 | 366 | 18.5% | 16.8% to 20.2% | 62.1% | 47.5% |  |
| 46-60 | 549 | 302 | 55.0% | 50.8% to 59.1% | 17.2% | 39.2% |  |
| 61+ | 150 | 45 | 30.0% | 23.2% to 37.8% | 4.7% | 5.8% |  |

### TenureGroup

| Segment | Customers | Churned | Churn rate | 95% CI | Share of High-balance customers | Contribution to High-balance churn | Note |
|---|---|---|---|---|---|---|---|
| New | 808 | 199 | 24.6% | 21.8% to 27.7% | 25.3% | 25.8% |  |
| Mid-term | 1,578 | 375 | 23.8% | 21.7% to 25.9% | 49.5% | 48.6% |  |
| Long-term | 805 | 197 | 24.5% | 21.6% to 27.6% | 25.2% | 25.6% |  |

### NumOfProducts

| Segment | Customers | Churned | Churn rate | 95% CI | Share of High-balance customers | Contribution to High-balance churn | Note |
|---|---|---|---|---|---|---|---|
| 1 | 2,093 | 546 | 26.1% | 24.3% to 28.0% | 65.6% | 70.8% |  |
| 2 | 991 | 124 | 12.5% | 10.6% to 14.7% | 31.1% | 16.1% |  |
| 3 | 82 | 76 | 92.7% | 84.9% to 96.6% | 2.6% | 9.9% | small sample |
| 4 | 25 | 25 | n/a | n/a | 0.8% | 3.2% | withheld (too small) |

### IsActiveMember

| Segment | Customers | Churned | Churn rate | 95% CI | Share of High-balance customers | Contribution to High-balance churn | Note |
|---|---|---|---|---|---|---|---|
| Inactive | 1,569 | 490 | 31.2% | 29.0% to 33.6% | 49.2% | 63.6% |  |
| Active | 1,622 | 281 | 17.3% | 15.6% to 19.2% | 50.8% | 36.4% |  |

## 3. High-balance vs Low-balance, like for like

Zero-balance customers are left out because they are a different group (and no customer in Germany has a zero balance). Gap = High-balance churn rate minus Low-balance churn rate, in percentage points.

### 3a. Inside each stratum

| Variable | Stratum | High n | High churn | Low n | Low churn | Gap (pp) | 95% CI (pp) | Note |
|---|---|---|---|---|---|---|---|---|
| (all non-zero customers) | All customers | 3,191 | 24.2% | 3,192 | 24.0% | +0.2 pp | -1.9 to +2.3 |  |
| Geography | France | 1,308 | 19.6% | 1,288 | 16.8% | +2.9 pp | -0.1 to +5.8 |  |
| Geography | Germany | 1,248 | 31.6% | 1,261 | 33.3% | -1.7 pp | -5.4 to +1.9 |  |
| Geography | Spain | 635 | 18.9% | 643 | 20.2% | -1.3 pp | -5.7 to +3.0 |  |
| AgeBand | Under 30 | 510 | 11.4% | 488 | 8.4% | +3.0 pp | -0.8 to +6.7 |  |
| AgeBand | 30-45 | 1,982 | 18.5% | 1,985 | 17.9% | +0.5 pp | -1.9 to +2.9 |  |
| AgeBand | 46-60 | 549 | 55.0% | 572 | 56.5% | -1.5 pp | -7.3 to +4.3 |  |
| AgeBand | 61+ | 150 | 30.0% | 147 | 31.3% | -1.3 pp | -11.7 to +9.1 |  |

### 3b. Directly standardised gap

Both groups are averaged over the same customer mix (each stratum weighted by its share of non-zero customers), so a difference in country or age mix cannot create a gap by itself. Strata where either group has fewer than 30 customers are left out and the weights re-scaled; 'coverage' is the share of non-zero customers represented. The interval is a normal approximation.

| Strata | Cells (used) | Coverage | Unadjusted gap (pp) | High churn (std.) | Low churn (std.) | Standardised gap (pp) | 95% CI (pp, approx.) |
|---|---|---|---|---|---|---|---|
| Geography | 3 (3) | 100% | +0.16 pp | 24.2% | 24.0% | +0.22 pp | -1.8 to +2.3 |
| Geography x AgeBand | 12 (11) | 99% | +0.16 pp | 24.3% | 23.8% | +0.48 pp | -1.5 to +2.4 |

## 4. Does churn change with the size of the balance?

Non-zero balances split into 5 equal-sized groups (cut points computed from the data: 95,677, 112,289, 127,148, 144,571).

| Balance group | Balance range | Customers | Churned | Churn rate | 95% CI | Note |
|---|---|---|---|---|---|---|
| Q1 (lowest) | 3,769 to 95,676 | 1,277 | 265 | 20.8% | 18.6% to 23.1% |  |
| Q2 | 95,679 to 112,282 | 1,276 | 321 | 25.2% | 22.9% to 27.6% |  |
| Q3 | 112,290 to 127,147 | 1,277 | 342 | 26.8% | 24.4% to 29.3% |  |
| Q4 | 127,154 to 144,554 | 1,276 | 316 | 24.8% | 22.5% to 27.2% |  |
| Q5 (highest) | 144,582 to 250,898 | 1,277 | 293 | 22.9% | 20.7% to 25.3% |  |

## 5. Salary and balance

Salary is split into 3 equal-sized groups (cut points: 67,057, 132,802). Salary and balance describe what a customer is recorded as earning and holding; neither is treated as profitability or lifetime value.

| Salary group | Customers | Churned | Churn rate | 95% CI | Note |
|---|---|---|---|---|---|
| Lower salary third | 3,334 | 671 | 20.1% | 18.8% to 21.5% |  |
| Middle salary third | 3,333 | 659 | 19.8% | 18.5% to 21.2% |  |
| Upper salary third | 3,333 | 707 | 21.2% | 19.9% to 22.6% |  |

Spearman rank correlation between salary and balance: **-0.001** among non-zero-balance customers (n = 6,383, p = 0.925); +0.012 among all customers (n = 10,000, p = 0.239).

Cell format: churn rate (customers). `*` = small sample; `n/a` = rate not shown.

### 5a. Salary group x balance segment, all customers

| SalaryBand | Zero-balance | Low-balance | High-balance |
|---|---|---|---|
| Lower salary third | 13.1% (n=1,227) | 22.3% (n=1,050) | 26.1% (n=1,057) |
| Middle salary third | 14.0% (n=1,204) | 23.9% (n=1,073) | 22.2% (n=1,056) |
| Upper salary third | 14.3% (n=1,186) | 25.8% (n=1,069) | 24.2% (n=1,078) |

### 5b. Salary group x balance segment, non-zero-balance customers

| SalaryBand | Zero-balance | Low-balance | High-balance |
|---|---|---|---|
| Lower salary third | n/a (n=0) | 22.3% (n=1,050) | 26.1% (n=1,057) |
| Middle salary third | n/a (n=0) | 23.9% (n=1,073) | 22.2% (n=1,056) |
| Upper salary third | n/a (n=0) | 25.8% (n=1,069) | 24.2% (n=1,078) |

## 6. Engagement

Engagement Drop Indicator = churn rate of inactive members minus churn rate of active members (pp, Newcombe interval). Inactivity may be a *symptom* of a customer already deciding to leave, so this describes an association and does not show which way any influence runs.

| Variable | Segment | Inactive n | Inactive churn | Active n | Active churn | Gap (pp) | 95% CI (pp) | Note |
|---|---|---|---|---|---|---|---|---|
| (all customers) | All customers | 4,849 | 26.9% | 5,151 | 14.3% | +12.6 pp | +11.0 to +14.2 |  |
| Geography | France | 2,423 | 21.1% | 2,591 | 11.5% | +9.6 pp | +7.6 to +11.7 |  |
| Geography | Germany | 1,261 | 41.1% | 1,248 | 23.7% | +17.4 pp | +13.7 to +20.9 |  |
| Geography | Spain | 1,165 | 23.3% | 1,312 | 10.7% | +12.6 pp | +9.7 to +15.6 |  |
| Gender | Female | 2,259 | 32.1% | 2,284 | 18.1% | +14.0 pp | +11.5 to +16.4 |  |
| Gender | Male | 2,590 | 22.3% | 2,867 | 11.2% | +11.1 pp | +9.1 to +13.1 |  |
| AgeBand | Under 30 | 804 | 9.8% | 837 | 5.4% | +4.4 pp | +1.9 to +7.1 |  |
| AgeBand | 30-45 | 3,169 | 19.3% | 3,079 | 11.2% | +8.1 pp | +6.4 to +9.9 |  |
| AgeBand | 46-60 | 787 | 68.4% | 860 | 35.3% | +33.0 pp | +28.4 to +37.5 |  |
| AgeBand | 61+ | 89 | 82.0% | 375 | 11.2% | +70.8 pp | +60.9 to +78.0 | small sample |
| TenureGroup | New | 1,148 | 28.6% | 1,348 | 14.8% | +13.7 pp | +10.5 to +17.0 |  |
| TenureGroup | Mid-term | 2,441 | 26.0% | 2,564 | 14.2% | +11.8 pp | +9.6 to +14.0 |  |
| TenureGroup | Long-term | 1,260 | 27.0% | 1,239 | 13.8% | +13.2 pp | +10.1 to +16.3 |  |
| NumOfProducts | 1 | 2,521 | 36.7% | 2,563 | 18.9% | +17.7 pp | +15.3 to +20.1 |  |
| NumOfProducts | 2 | 2,144 | 9.9% | 2,446 | 5.6% | +4.3 pp | +2.8 to +5.9 |  |
| NumOfProducts | 3 | 153 | 88.2% | 113 | 75.2% | +13.0 pp | +3.7 to +22.7 |  |
| NumOfProducts | 4 | 31 | 100.0% | 29 | n/a | n/a | n/a | withheld (too small) |
| BalanceSegment | Zero-balance | 1,744 | 18.3% | 1,873 | 9.6% | +8.7 pp | +6.5 to +11.0 |  |
| BalanceSegment | Low-balance | 1,536 | 32.0% | 1,656 | 16.5% | +15.5 pp | +12.5 to +18.4 |  |
| BalanceSegment | High-balance | 1,569 | 31.2% | 1,622 | 17.3% | +13.9 pp | +11.0 to +16.8 |  |

### 6a. Who is inactive?

| Variable | Segment | Customers | Inactive | Share inactive | 95% CI | Note |
|---|---|---|---|---|---|---|
| Geography | France | 5,014 | 2,423 | 48.3% | 46.9% to 49.7% |  |
| Geography | Germany | 2,509 | 1,261 | 50.3% | 48.3% to 52.2% |  |
| Geography | Spain | 2,477 | 1,165 | 47.0% | 45.1% to 49.0% |  |
| Gender | Female | 4,543 | 2,259 | 49.7% | 48.3% to 51.2% |  |
| Gender | Male | 5,457 | 2,590 | 47.5% | 46.1% to 48.8% |  |
| AgeBand | Under 30 | 1,641 | 804 | 49.0% | 46.6% to 51.4% |  |
| AgeBand | 30-45 | 6,248 | 3,169 | 50.7% | 49.5% to 52.0% |  |
| AgeBand | 46-60 | 1,647 | 787 | 47.8% | 45.4% to 50.2% |  |
| AgeBand | 61+ | 464 | 89 | 19.2% | 15.9% to 23.0% |  |
| TenureGroup | New | 2,496 | 1,148 | 46.0% | 44.0% to 48.0% |  |
| TenureGroup | Mid-term | 5,005 | 2,441 | 48.8% | 47.4% to 50.2% |  |
| TenureGroup | Long-term | 2,499 | 1,260 | 50.4% | 48.5% to 52.4% |  |
| NumOfProducts | 1 | 5,084 | 2,521 | 49.6% | 48.2% to 51.0% |  |
| NumOfProducts | 2 | 4,590 | 2,144 | 46.7% | 45.3% to 48.2% |  |
| NumOfProducts | 3 | 266 | 153 | 57.5% | 51.5% to 63.3% |  |
| NumOfProducts | 4 | 60 | 31 | 51.7% | 39.3% to 63.8% | small sample |
| BalanceSegment | Zero-balance | 3,617 | 1,744 | 48.2% | 46.6% to 49.8% |  |
| BalanceSegment | Low-balance | 3,192 | 1,536 | 48.1% | 46.4% to 49.9% |  |
| BalanceSegment | High-balance | 3,191 | 1,569 | 49.2% | 47.4% to 50.9% |  |

### 6b. Churn by tenure group and engagement

| TenureGroup | Inactive | Active |
|---|---|---|
| New | 28.6% (n=1,148) | 14.8% (n=1,348) |
| Mid-term | 26.0% (n=2,441) | 14.2% (n=2,564) |
| Long-term | 27.0% (n=1,260) | 13.8% (n=1,239) |

### 6c. Churn by number of products and engagement

| NumOfProducts | Inactive | Active |
|---|---|---|
| 1 | 36.7% (n=2,521) | 18.9% (n=2,563) |
| 2 | 9.9% (n=2,144) | 5.6% (n=2,446) |
| 3 | 88.2% (n=153) | 75.2% (n=113) |
| 4 | 100.0% (n=31)* | n/a (n=29) |

## 7. Tenure

| Tenure (years) | Customers | Churned | Churn rate | 95% CI | Note |
|---|---|---|---|---|---|
| 0 | 413 | 95 | 23.0% | 19.2% to 27.3% |  |
| 1 | 1,035 | 232 | 22.4% | 20.0% to 25.1% |  |
| 2 | 1,048 | 201 | 19.2% | 16.9% to 21.7% |  |
| 3 | 1,009 | 213 | 21.1% | 18.7% to 23.7% |  |
| 4 | 989 | 203 | 20.5% | 18.1% to 23.2% |  |
| 5 | 1,012 | 209 | 20.7% | 18.3% to 23.3% |  |
| 6 | 967 | 196 | 20.3% | 17.9% to 22.9% |  |
| 7 | 1,028 | 177 | 17.2% | 15.0% to 19.6% |  |
| 8 | 1,025 | 197 | 19.2% | 16.9% to 21.7% |  |
| 9 | 984 | 213 | 21.6% | 19.2% to 24.3% |  |
| 10 | 490 | 101 | 20.6% | 17.3% to 24.4% |  |

Tenure year 0 has 413 customers and year 10 has 490, against a median of 1,012 for the years in between. The cause of any difference is not known and is not assumed.

## 8. Balance exposure proxy (NOT lost revenue)

Balance held by customers who churned. It shows where balances sit among leavers; it says nothing about revenue, profit or lifetime value.

### 8a. High-balance / engagement matrix

| Balance segment | Engagement | Customers | Churn rate | 95% CI | Share of churners | Churned customers' balance | Share of all churned balance |
|---|---|---|---|---|---|---|---|
| Zero-balance | Inactive | 1,744 | 18.3% | 16.6% to 20.2% | 15.7% | 0.0M | 0.0% |
| Zero-balance | Active | 1,873 | 9.6% | 8.4% to 11.0% | 8.8% | 0.0M | 0.0% |
| Low-balance | Inactive | 1,536 | 32.0% | 29.7% to 34.4% | 24.2% | 48.0M | 25.9% |
| Low-balance | Active | 1,656 | 16.5% | 14.8% to 18.4% | 13.5% | 26.8M | 14.4% |
| High-balance | Inactive | 1,569 | 31.2% | 29.0% to 33.6% | 24.1% | 70.4M | 38.0% |
| High-balance | Active | 1,622 | 17.3% | 15.6% to 19.2% | 13.8% | 40.4M | 21.7% |

### 8b. By variable

| Variable | Segment | Customers | Churned | Balance held by churned | Share of all churned balance | Share of all balance | Churned share of segment balance |
|---|---|---|---|---|---|---|---|
| Geography | France | 5,014 | 810 | 57.7M | 31.1% | 40.7% | 18.5% |
| Geography | Germany | 2,509 | 814 | 98.0M | 52.8% | 39.3% | 32.6% |
| Geography | Spain | 2,477 | 413 | 29.9M | 16.1% | 20.0% | 19.6% |
| Gender | Female | 4,543 | 1,139 | 101.4M | 54.6% | 44.9% | 29.5% |
| Gender | Male | 5,457 | 898 | 84.2M | 45.4% | 55.1% | 20.0% |
| AgeBand | Under 30 | 1,641 | 124 | 12.4M | 6.7% | 15.8% | 10.3% |
| AgeBand | 30-45 | 6,248 | 956 | 87.4M | 47.1% | 62.0% | 18.4% |
| AgeBand | 46-60 | 1,647 | 842 | 75.2M | 40.5% | 17.5% | 56.0% |
| AgeBand | 61+ | 464 | 115 | 10.6M | 5.7% | 4.6% | 30.1% |
| NumOfProducts | 1 | 5,084 | 1,409 | 129.7M | 69.9% | 65.5% | 25.9% |
| NumOfProducts | 2 | 4,590 | 348 | 31.4M | 16.9% | 31.1% | 13.2% |
| NumOfProducts | 3 | 266 | 220 | 18.9M | 10.2% | 2.6% | 94.1% |
| NumOfProducts | 4 | 60 | 60 | 5.6M | 3.0% | 0.7% | 100.0% |
| IsActiveMember | Inactive | 4,849 | 1,302 | 118.5M | 63.8% | 48.9% | 31.7% |
| IsActiveMember | Active | 5,151 | 735 | 67.1M | 36.2% | 51.1% | 17.2% |
| BalanceSegment | Zero-balance | 3,617 | 500 | 0.0M | 0.0% | 0.0% | n/a |
| BalanceSegment | Low-balance | 3,192 | 766 | 74.8M | 40.3% | 40.1% | 24.4% |
| BalanceSegment | High-balance | 3,191 | 771 | 110.8M | 59.7% | 59.9% | 24.2% |

### 8c. Concentration

Churned customers sorted by balance, largest first. 500 of 2,037 churned customers had a zero balance.

| Top share of churned customers | Customers | Balance held | Share of churned balance | Smallest balance in group |
|---|---|---|---|---|
| 10% | 204 | 35.0M | 18.9% | 152,086 |
| 20% | 408 | 64.4M | 34.7% | 136,911 |
| 50% | 1,019 | 139.3M | 75.0% | 109,349 |

## 9. What this analysis cannot tell us

* **Cause.** These are associations in one snapshot. Nothing shows that balance, salary, inactivity or tenure makes customers leave.
* **Value.** High balance, salary and balance exposure are not profitability, revenue or lifetime value; no such data exists here.
* **Overlap.** Country, age, products, activity and balance are related. Stratification and standardisation (section 3) reduce differences in country and age mix only; they do not adjust for everything else.
* **Why.** The data cannot explain why segments differ, or why no customer in Germany has a zero balance. Extreme rates in small groups should be confirmed with the data owner.
* **Small groups.** Segments marked *small sample* have wide intervals; rates below the minimum size are withheld. Many segments are compared, so some differences will look larger by chance.
* **Scope.** One snapshot of three countries; the meaning of `Exited` is an assumption (decision D6) and the data's provenance is unconfirmed.
