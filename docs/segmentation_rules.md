# Segmentation Rules

These are **chosen analytical thresholds for this project**. They are not universally
established banking standards. The authoritative values live in
`config/segmentation.toml`; this page explains them.

## Interval convention

Bins are **left-closed** (include the lower bound, exclude the next one). Each bin starts
exactly where the previous ends, so bins **cannot overlap or leave gaps**.

| Variable | Segment | Rule |
|---|---|---|
| Age | Under 30 | age < 30 |
| | 30-45 | 30 <= age <= 45 |
| | 46-60 | 46 <= age <= 60 |
| | 61+ | age >= 61 |
| Credit score | Low | score < 580 |
| | Medium | 580 <= score <= 739 |
| | High | score >= 740 |
| Tenure (years) | New | 0-2 |
| | Mid-term | 3-7 |
| | Long-term | 8-10 |
| Balance | Zero-balance | balance = 0 |
| | Low-balance | 0 < balance <= T |
| | High-balance | balance > T |

**T** = the median of **non-zero balances only**, computed from the actual dataset at run
time and written to the outputs. It is never typed in by hand. On the supplied dataset the
pipeline computed T = **119,839.69** from 6,383 non-zero balances (independently re-checked
with plain pandas). A balance exactly equal to T is placed in Low-balance.

**Credit-score tercile sensitivity grouping** (`CreditScoreTercile`): cut points are the 1/3
and 2/3 quantiles of the credit scores (608 and 695 in this dataset), right-closed:
"Low (tercile)" = score <= 608, "Medium (tercile)" = 608 < score <= 695, "High (tercile)" =
score > 695. Groups are not exactly equal because many customers share the same score.
It is for checking whether conclusions depend on the fixed 580/740 cut-offs, not a replacement.

**Open-ended end bins:** the first and last bin of each variable extend to minus/plus infinity,
so every record gets exactly one label. Implausible values (for example an age of 5) are
flagged by validation and kept; segmentation never removes records.

**Negative balances** (none exist in this data) would raise an error, because the approved
rule only covers zero and positive balances.

## Notes and caveats

* **Age 60 vs 61:** the original brief's "46-60" and "60+" overlapped at 60. Age 60 now
  belongs only to 46-60; "61+" starts at 61.
* **Credit-score bands** are an analytical choice. As a **sensitivity check** the project
  can also report equal-sized terciles (`[sensitivity.credit_score]`) to see whether
  conclusions depend on the chosen cut-offs.
* **Tenure:** years 0 and 10 hold about half as many customers as years 1-9 in the raw
  data. The cause is **not known** and will not be assumed; the New and Long-term bands
  are reported with their sizes.
* **Small groups:** any segment (or drill-down combination) with fewer than 100 customers
  is flagged; fewer than 30, its rate is withheld. Thresholds are in the config.
* **Never used as segmentation features:** `CustomerId`, `Surname`, `Year`.
* **Geography and balance:** no German customer has a zero balance (investigated in
  `reports/geography_zero_balance_investigation.md`). Design rules adopted: compare countries on
  non-zero-balance customers for like-for-like results; report zero-balance comparisons only for
  countries that have such customers; show balance segments by country; label any pooled
  Germany-vs-others or zero-vs-non-zero comparison as confounded.
