# Cleaning and Segmentation Log

Every decision below was applied by code, with counts computed from the data. The raw CSV was not modified.

* Raw file SHA-256: `31be60acb8660d5a343b85debd4ad444953305d855834ea0dd09f11c659002a2`

## Cleaning decisions

| ID | Action | Rationale | Rows affected | Columns |
|---|---|---|---|---|
| C1 | Keep every customer record; none deleted | Deleting records needs a justified reason; validation found no FAIL-level problems | 0 | (all) |
| C2 | No imputation performed | Raw data contains 0 missing values, so there is nothing to fill in | 0 | (all) |
| C3 | Keep records flagged by plausibility checks | Flagged records are reviewed by a person, never auto-removed. Plausibility check status: PASS (no records flagged) | 0 | Age, CreditScore, Tenure, Balance, EstimatedSalary, NumOfProducts |
| C4 | Remove column(s) from the processed copy: Surname | Personal and non-analytical; the raw file still contains them. Columns only, no rows | 0 | Surname |
| C5 | Keep CustomerId as identifier only; keep Year as metadata | Neither is used for segmentation or as a feature (config: excluded_from_features). Year has a single value | 0 | CustomerId, Year |
| C6 | Convert Geography and Gender to fixed-order categories | Reliable grouping and consistent chart order; labels unchanged | 0 | Geography, Gender |
| C7 | Keep binary fields as 0/1 integers | Validated to contain only 0 and 1 | 0 | HasCrCard, IsActiveMember, Exited |
| C8 | Add derived segment columns: AgeBand, CreditScoreBand, TenureGroup, BalanceSegment, CreditScoreTercile | Thresholds read from config/segmentation.toml; every row receives exactly one label per variable | 10,000 | AgeBand, CreditScoreBand, TenureGroup, BalanceSegment, CreditScoreTercile |
| C9 | Proof: original values unchanged | Cells whose value differs from the raw file in retained columns: 0. Rows in: 10,000; rows out: 10,000 | 0 | (all retained) |

## Values computed from the data

* **Balance threshold** (median of the 6,383 non-zero balances): **119,839.69**. Low-balance: 0 < balance <= 119,839.69; High-balance: balance > 119,839.69.
* **Credit-score tercile cut points** (sensitivity grouping, right-closed): 608.00, 695.00.

## Segment sizes

| Segment variable | Segment | Customers | Share | Small sample? |
|---|---|---|---|---|
| AgeBand | Under 30 | 1,641 | 16.4% | no |
| AgeBand | 30-45 | 6,248 | 62.5% | no |
| AgeBand | 46-60 | 1,647 | 16.5% | no |
| AgeBand | 61+ | 464 | 4.6% | no |
| CreditScoreBand | Low | 2,362 | 23.6% | no |
| CreditScoreBand | Medium | 5,759 | 57.6% | no |
| CreditScoreBand | High | 1,879 | 18.8% | no |
| TenureGroup | New | 2,496 | 25.0% | no |
| TenureGroup | Mid-term | 5,005 | 50.0% | no |
| TenureGroup | Long-term | 2,499 | 25.0% | no |
| BalanceSegment | Zero-balance | 3,617 | 36.2% | no |
| BalanceSegment | Low-balance | 3,192 | 31.9% | no |
| BalanceSegment | High-balance | 3,191 | 31.9% | no |
| CreditScoreTercile | Low (tercile) | 3,363 | 33.6% | no |
| CreditScoreTercile | Medium (tercile) | 3,334 | 33.3% | no |
| CreditScoreTercile | High (tercile) | 3,303 | 33.0% | no |

Small sample = fewer customers than `small_group_threshold` in the config. Shares within one variable sum to 100%.
