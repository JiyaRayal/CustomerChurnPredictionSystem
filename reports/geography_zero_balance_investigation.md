# Geography and Zero-Balance Investigation

Purpose: understand how Geography and zero-balance status overlap **before** interpreting their separate associations with churn. This analysis is descriptive. Churn rates here are associations in one snapshot, not causal effects, and formal group comparisons are left to the churn analysis phase.

## Key findings (computed from the data)

1. 3,617 of 10,000 customers (36.2%) have a zero balance.
2. **No customer in Germany has a zero balance** (0 of 2,509). Zero-balance customers exist only in the other countries, so comparisons involving zero-balance customers cannot include Germany.
3. Geography and zero-balance status are strongly associated in this dataset (chi-square = 1,898, p < 0.001, Cramer's V = 0.44). This describes how customers are distributed; it does not explain why.
4. Among the countries that do have zero-balance customers, their share is: France 48.2%, Spain 48.4% (p = 0.88, Cramer's V = 0.002).
5. Among customers with a non-zero balance, median balances by country range from 119,703 to 120,135, so the typical size of a non-zero balance is similar across countries in this dataset.
6. Churn rate among **non-zero-balance customers only** (like-for-like): France 18.2% (n = 2,596); Germany 32.4% (n = 2,509); Spain 19.6% (n = 1,278); Other countries pooled (excluding Germany) 18.7% (n = 3,874).
7. Across all customers, non-zero-balance customers churn 10.3 percentage points more than zero-balance customers; restricted to France + Spain (the countries with both groups) the gap is 4.8 percentage points. The overall gap is therefore not a like-for-like comparison of balance groups.

## 1. Customers by country and balance status

| Country | Zero-balance | Non-zero balance | Total | Share zero-balance |
|---|---|---|---|---|
| France | 2,418 | 2,596 | 5,014 | 48.2% |
| Germany | 0 | 2,509 | 2,509 | 0.0% |
| Spain | 1,199 | 1,278 | 2,477 | 48.4% |

## 2. Churn by country and balance status

| Country | Balance status | n | Churned | Churn rate | 95% CI (Wilson) | Note |
|---|---|---|---|---|---|---|
| France | Zero-balance | 2,418 | 337 | 13.9% | 12.6% to 15.4% | ok |
| France | Non-zero balance | 2,596 | 473 | 18.2% | 16.8% to 19.8% | ok |
| Germany | Zero-balance | 0 | 0 | n/a | n/a | n/a (empty group) |
| Germany | Non-zero balance | 2,509 | 814 | 32.4% | 30.6% to 34.3% | ok |
| Spain | Zero-balance | 1,199 | 163 | 13.6% | 11.8% to 15.7% | ok |
| Spain | Non-zero balance | 1,278 | 250 | 19.6% | 17.5% to 21.8% | ok |

An empty cell (n = 0) has an **undefined** rate (n/a), not 0%.

## 3. Like-for-like: non-zero-balance customers only

| Group | n | Churned | Churn rate | 95% CI (Wilson) |
|---|---|---|---|---|
| France | 2,596 | 473 | 18.2% | 16.8% to 19.8% |
| Germany | 2,509 | 814 | 32.4% | 30.6% to 34.3% |
| Spain | 1,278 | 250 | 19.6% | 17.5% to 21.8% |
| Other countries pooled (excluding Germany) | 3,874 | 723 | 18.7% | 17.5% to 19.9% |

## 4. Churn gap between non-zero and zero-balance customers

| Scope | n zero | Churn zero | n non-zero | Churn non-zero | Gap (pp) |
|---|---|---|---|---|---|
| France | 2,418 | 13.9% | 2,596 | 18.2% | 4.3 |
| Spain | 1,199 | 13.6% | 1,278 | 19.6% | 6.0 |
| Pooled: France + Spain | 3,617 | 13.8% | 3,874 | 18.7% | 4.8 |
| Pooled: all countries | 3,617 | 13.8% | 6,383 | 24.1% | 10.3 |

pp = percentage points (non-zero churn rate minus zero-balance churn rate).

## 5. Size of non-zero balances by country

| Country | n | Mean | 25th pct | Median | 75th pct |
|---|---|---|---|---|---|
| France | 2,596 | 119,928 | 98,441 | 120,135 | 141,143 |
| Germany | 2,509 | 119,730 | 102,801 | 119,703 | 137,560 |
| Spain | 1,278 | 119,815 | 98,067 | 119,726 | 140,342 |

## What this does NOT tell us

* **Why** some countries have no zero-balance customers. The dataset has no account-type, product-rule or data-collection information, so the reason cannot be determined here and is not assumed. The data owner would need to explain it.
* **Whether geography or balance drives churn.** These are overlapping descriptive patterns. No causal claim is made.
* **How these results would hold elsewhere.** One snapshot, three countries.

## Consequences for later analysis (design rules adopted)

1. Never interpret a country's churn rate and the balance-segment churn rates as independent evidence.
2. Compare countries on **non-zero-balance customers** when a like-for-like comparison is needed, and report zero-balance comparisons only for countries that have zero-balance customers.
3. Show balance-segment results **by country** (or within the countries that have all segments).
4. Treat any Germany-vs-others or zero-vs-non-zero statement made on pooled data as confounded, and say so.
