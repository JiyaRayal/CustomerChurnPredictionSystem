# Data Validation Report

* Rows: **10,000**, columns: **14**
* Source file: `data/raw/European_Bank.csv`
* SHA-256: `31be60acb8660d5a343b85debd4ad444953305d855834ea0dd09f11c659002a2`
* Overall result: **PASSED (no FAIL-level problems)**
* Check results: 11 PASS, 4 INFO, 1 WARN, 0 FAIL

## Summary of checks

| Check | Status | Result |
|---|---|---|
| Schema: columns | **PASS** | all expected columns present, no extras |
| Data types | **PASS** | all columns have the expected types |
| Missing values | **PASS** | no missing or blank values in any column |
| Duplicates: full rows | **PASS** | no fully duplicated rows |
| Duplicates: CustomerId | **PASS** | all 10,000 CustomerId values are unique |
| Duplicates: identical except CustomerId | **PASS** | no records identical except for CustomerId |
| Binary fields (0/1) | **PASS** | all binary columns contain only 0 and 1: HasCrCard, IsActiveMember, Exited |
| Categories: allowed values | **PASS** | all categorical columns contain only the expected values |
| Target: Exited coding | **PASS** | target contains only 0 and 1 |
| Target: both classes present | **PASS** | 2,037 churned (20.37%) and 7,963 retained |
| Plausibility bounds | **PASS** | all values inside the configured plausibility bounds (age, credit score, tenure, balance, salary, products) |
| Constant columns | **INFO** | constant metadata column(s): Year = 2025; no time dimension, excluded from segmentation |
| Numeric ranges | **INFO** | observed minimum and maximum of numeric fields |
| Surname characters | **WARN** | 92 surname(s) contain a literal '?' (possible character loss in the source file; cause not verified). Surname is excluded from analysis, so results are unaffected; values were not altered |
| Small categories | **INFO** | 1 raw category value(s) have fewer than 100 customers: rates for them need extra caution |
| Tenure distribution edges | **INFO** | tenure 0: 413 customers, tenure 10: 490; interior years median 1,012. The cause of the difference is NOT known and is not assumed |

## Details

### Schema: columns (PASS)
* expected_columns: 14
* found_columns: 14

### Categories: allowed values (PASS)
* counts: Geography: France: 5014; Germany: 2509; Spain: 2477; Gender: Male: 5457; Female: 4543

### Target: both classes present (PASS)
* churned: 2037
* retained: 7963
* assumption: Exited = 1 means churned (from the project brief; not verifiable from data)

### Plausibility bounds (PASS)
* records_per_rule: Age outside 18-110: 0; CreditScore outside 300-850: 0; Tenure below 0: 0; Balance below 0: 0; EstimatedSalary not above 0: 0; NumOfProducts below 1: 0

### Constant columns (INFO)
* constant: Year: 2025

### Numeric ranges (INFO)
* CreditScore: 350.00 to 850.00
* Age: 18.00 to 92.00
* Tenure: 0.00 to 10.00
* Balance: 0.00 to 250,898.09
* NumOfProducts: 1.00 to 4.00
* EstimatedSalary: 11.58 to 199,992.48

### Surname characters (WARN)
* examples: H?, L?, Hs?, Y?an, L?

### Small categories (INFO)
* NumOfProducts = 4: 60

### Tenure distribution edges (INFO)
* counts_by_tenure: 0: 413; 1: 1035; 2: 1048; 3: 1009; 4: 989; 5: 1012; 6: 967; 7: 1028; 8: 1025; 9: 984; 10: 490

## What this validation can and cannot confirm

* **Can confirm:** structure, data types, completeness, uniqueness of CustomerId, binary coding, allowed categories, and that the target has both classes.
* **Cannot confirm:** that `Exited = 1` really means the customer left, over what time window, or where the data came from. These are assumptions taken from the project brief (see docs/decisions_log.md D6 and docs/data_provenance.md).
* **WARN-level records are kept.** They are listed so a person can review them; nothing is deleted or corrected automatically.
