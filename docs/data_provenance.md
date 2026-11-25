# Data Provenance and Limitations

## The file

| Item | Value |
|---|---|
| File | `data/raw/European_Bank.csv` |
| Size | 10,000 rows x 14 columns |
| SHA-256 | `31be60acb8660d5a343b85debd4ad444953305d855834ea0dd09f11c659002a2` |
| Preserved as | read-only copy; the original was left untouched and verified byte-identical |

## What is known (verified by inspection)

* No missing values, no duplicate rows, no duplicate `CustomerId`.
* `Exited` takes only the values 0 and 1 (2,037 ones = 20.37%).
* `Year` has a single value, 2025.
* No German customer has a zero balance (France: 2,418 zero-balance; Spain: 1,199; Germany: 0).
* `NumOfProducts` = 3 has 266 customers and = 4 has 60.
* Tenure 0 (413) and 10 (490) have about half as many customers as the median interior year
  (about 1,012); the cause is unknown and not assumed.
* 92 surnames contain a literal `?` (for example `Y?an`), which may indicate character loss in the
  source file; the cause is not verified. Surname is excluded from analysis and was not altered.
* Estimated salary ranges from 11.58 to 199,992.48; very low values are not flagged as errors
  because the field is an *estimate* and no rule says what is implausible.
* Geography and zero-balance status are strongly associated (Cramer's V about 0.44). Full details:
  `reports/geography_zero_balance_investigation.md`.

## What is NOT known

* **Origin.** The data's source, collection method and licence are unconfirmed. The column
  layout resembles a widely shared public churn dataset with an added `Year` column, but this
  is an observation, not a verified fact. **The project must not describe this as official
  European Central Bank data** unless a verifiable source is provided.
* **Meaning of `Exited`.** The observation window and the exact churn definition are not
  documented. `1 = churned` is an assumption taken from the project brief.
* **Meaning of `Year`.** Possibly a metadata or extraction-year field. Excluded from
  segmentation unless a justified analytical purpose emerges.
* **Representativeness.** Three countries, one snapshot. Findings describe this dataset and
  should not be generalised to "European banking" as a whole.

## Handling rules

1. The raw file is never modified; all cleaning happens in code on a copy.
2. No record is deleted and no value imputed without a documented, justified reason.
3. `Surname` is excluded from all analysis; `CustomerId` is kept only for identification.
4. `Gender` is used for descriptive comparison only, with no claims about decisions based on it.
5. Results are descriptive associations, not causal effects.
