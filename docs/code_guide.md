# Code Guide (Phases 2-5) - how the pieces fit and why

Read this if you want to understand *why* the code is built the way it is.

## The flow

```
raw CSV --verify checksum--> load --> validate --> clean + segment --> investigate --> reports
 (never edited)               |         |              |                  |
                          data_loader  validation   cleaning +        geography_balance
                                                    segmentation
```
Run it all with `python scripts/run_pipeline.py`. The logic is in `src/churn_analytics/pipeline.py`. After the investigation, `kpis.py` and `kpi_report.py` compute the headline KPIs from the processed data and write `reports/kpi_summary.md`.

## Module by module

| Module | Job | Key design decision |
|---|---|---|
| `config.py` | Reads and checks `config/segmentation.toml` | Bad thresholds stop the project immediately, with every problem listed at once |
| `data_loader.py` | Reads the raw CSV | Recomputes the file's SHA-256 "fingerprint" first and refuses to continue if it changed. Never writes to `data/raw/` |
| `validation.py` | Runs the quality checks | Four result levels: PASS, INFO, WARN, FAIL. Only FAIL stops the pipeline; WARN records are kept and listed |
| `cleaning.py` | Builds the processed dataset | Refuses to run on failed validation. Changes columns only, never records or values, and proves it by counting changed cells (0) |
| `segmentation.py` | Adds age, credit, tenure and balance segments | Thresholds come from the config; the balance cut-off is computed from the data; impossible cases raise errors |
| `geography_balance.py` | Investigates Geography x zero-balance | Descriptive only; empty cells are "n/a", never 0% |
| `stats_utils.py` | Wilson interval, group-size rules, chi-square | Shared with the Phase 3 KPI code, so the rules live in one place |
| `md_utils.py` | Small Markdown formatting helpers | Treats both `None` and `NaN` as "n/a" (a bug here was caught during review) |
| `kpis.py` | The KPI functions (churn rate, contribution, risk index, engagement drop, high-balance, exposure) | Work on whatever rows you pass in, so dashboard filters simply re-run them. Empty groups give n/a, never 0 |
| `kpi_report.py` | Collects the headline KPIs into `reports/kpi_summary.md` | Shows the risk index twice (all vs non-zero-balance customers) because of the Germany finding |
| `analysis.py` | Segment churn analysis: rate vs contribution, Cramer's V ranking, group differences, Geography x age, churned vs retained | Every table is single- or two-variable and descriptive; empty cells stay in the table as n/a |
| `analysis_report.py` | Writes `reports/segment_churn_analysis.md` | Findings sentences are generated from the tables, so no number is typed by hand |
| `visualization.py` | Six report charts (Matplotlib + Seaborn) | Plotting libraries are imported inside the functions, so the rest of the project works without them |
| `balance_engagement.py` | High-balance, salary vs balance, engagement, tenure and the balance exposure proxy | High vs Low-balance is compared like for like: non-zero balances only, inside strata, and standardised to the same customer mix |
| `balance_engagement_report.py` | Writes `reports/high_balance_engagement_analysis.md` | Trend / relationship / verdict sentences are computed from the numbers, not typed |
| `pipeline.py` | Runs everything and writes outputs | Writes the validation report *before* stopping on failure, so you can see what went wrong |

## Ideas worth understanding

* **Left-closed bins.** "30-45" means 30 <= age < 46. Each bin starts exactly where the previous ends, so a value cannot be in two bins or none. First and last bins are open-ended so every record gets a label.
* **Why the balance cut uses non-zero balances only.** 36% of customers have a zero balance. Including them would drag the median down and make "High-balance" mean something different.
* **Empty is not zero.** A group with no customers has an undefined churn rate (n/a). A group with customers and no churners has a real rate of 0%. Mixing these up would mislead readers.
* **Warn, don't delete.** An age of 5 would be flagged, not removed. A person decides; the code never guesses.
* **Confidence intervals.** A churn rate from a sample is uncertain. The Wilson interval shows a plausible range, and is wider for smaller groups.
* **p-values vs effect size.** With 10,000 rows almost any association gives a tiny p-value, so reports also give Cramer's V (0 = unrelated, 1 = perfectly linked).
* **Reproducibility.** Outputs contain no timestamps, so rerunning produces byte-identical files (tested).
* **Tests deliberately break things.** Most tests damage a valid dataset in one way and confirm the right check fires. As a sanity check, four bugs were injected into a throwaway copy of the code and the tests caught every one.

## Phase 3 ideas worth understanding

* **Rate vs contribution.** A rate is "what share of *this group* left". A contribution is "what share of *all leavers* came from this group". A big group with an average rate can still contribute most of the churn.
* **Geographic Risk Index.** Country rate divided by the overall rate: 1.0 means average, 1.6 means 60% higher than average. Because each country is part of the overall figure, the index is a convenient summary, not a precise test.
* **Percentage points vs percent.** If inactive members churn at 27% and active at 14%, the gap is about 13 *percentage points*. It is not "13%".
* **Confidence interval for a difference.** Newcombe's method builds the interval for "rate A minus rate B" from each group's Wilson interval. The code was checked against a published example.
* **Exposure proxy.** The balance held by customers who left. It is not money the bank lost: the data has no revenue or profit.
* **Why the KPI tests use a made-up dataset.** The 200-customer fixture is designed so every KPI can be worked out on paper (France 20/100, Germany 30/60, Spain 10/40). Real-data tests then re-derive each KPI with plain pandas as an independent check.

## Phase 4 ideas worth understanding

* **Single-variable views overlap.** Age, products, balance, activity and country are related to each other. Each table answers "how does churn differ across this variable?", not "what drives churn?".
* **Cramer's V.** A number from 0 to 1 for "how strongly do this variable and churn go together". With 10,000 rows even tiny differences have tiny p-values, so we read V (the size) instead.
* **Cohen's d.** The gap between two averages measured in standard deviations, so ages and balances can be compared on one scale.
* **Extreme results.** A group where 100% churned (60 of 60 customers with four products) is a reason to ask the data owner how the data was recorded, not a reason to invent an explanation.
* **Idempotent functions.** `prepare_for_analysis` can be called twice with the same result. A bug here (calling it twice crashed) was found during development and is now covered by a test.
* **Why charts live in a separate script.** A security policy on the owner's computer blocked one compiled library, so plotting is kept out of the core pipeline: tables, reports and tests never need it.

## Phase 5 ideas worth understanding

* **Comparing like with like.** High-balance customers are mostly in Germany, and Germany churns more. A raw comparison with everyone else would mix "high balance" with "German". So we compare High with Low-balance customers *inside* each country and age band.
* **Direct standardisation.** Take the High-vs-Low gap in each country, then average the gaps using the same country weights for both groups. A different country mix can no longer create a gap by itself. The tests include a made-up case where the raw gap is 26.7 points but the standardised gap is 13.3.
* **Rank correlation (Spearman).** Asks "when salary goes up, does balance tend to go up?" using ranks, so a few huge values do not distort it. Zero means no such tendency.
* **Computed wording.** Sentences like "no steady trend" are produced by checking the numbers. If the data changed, the sentence would change with it. Hand-typed claims were found and removed during development.
* **Equivalent mutants.** When we deliberately break the code to test the tests, one change had no effect because the code already did the same thing elsewhere. That is not a missing test; the same change in the place where it matters is caught.
* **Exposure is not revenue.** The balance held by customers who left shows where money sat, not what the bank earned from it.
