# Decisions Log

Records important choices and who made them. **Approved** = confirmed by the project owner.
**Proposed** = suggested by the assistant, awaiting confirmation.

| ID | Decision | Rationale | Status |
|---|---|---|---|
| D1 | Age bands: Under 30, 30-45, 46-60, 61+ | Fixes the overlap at age 60 in the brief | Approved |
| D2 | Credit bands: Low <580, Medium 580-739, High >=740, documented as analytical choices; terciles as sensitivity check | Brief gave no thresholds | Approved |
| D3 | Tenure: New 0-2, Mid-term 3-7, Long-term 8-10 | Brief gave no thresholds | Approved |
| D4 | Balance: Zero own segment; Low/High split at median of non-zero balances, computed from data | Avoids the 36% zero-balance mass distorting the split | Approved |
| D5 | Use "high-balance customers", not "high-value"; salary/balance never equated with profit or lifetime value | Data has no revenue or profit fields | Approved |
| D6 | `Exited = 1` treated as churn; stated as an assumption | Window and definition undocumented | Approved |
| D7 | Five KPI definitions as specified (overall, segment, contribution, GRI, EDI) | Brief gave no formulas | Approved |
| D8 | Treat `Year` as metadata; exclude from segmentation | Constant value 2025; no time dimension | Approved |
| D9 | Do not claim ECB provenance | Source unverified | Approved |
| D10 | Raw CSV git-ignored by default; checksum committed | Provenance and licence unconfirmed; file contains surnames. Trade-off: a fresh clone cannot reproduce without adding the CSV | Accepted\* |
| D11 | Config in TOML, read with Python's built-in `tomllib` | No extra dependency; comments allowed in the file. Requires Python >= 3.11 | Accepted\* |
| D12 | Bins described by `lower_bounds` + `labels`, left-closed | Overlaps and gaps are impossible by construction | Accepted\* |
| D13 | Small-sample thresholds: flag n < 100, withhold rate n < 30 | Reasonable analytical convention; not a standard | Accepted\* |
| D14 | 95% Wilson confidence intervals for churn rates | Behaves well for small n and extreme rates | Accepted\* |
| D15 | Plausibility bounds (age 18-110, credit score 300-850) used only to flag, never delete | Assumptions to confirm in Phase 2 | Accepted\* |
| D16 | "High-Value Churn Ratio" in the brief becomes "High-Balance Churn Rate" = churned high-balance / all high-balance | Not in the five KPIs you confirmed | Accepted (owner confirmed defaults before Phase 3) |
| D17 | Tests run via `pytest.ini` (`pythonpath = src`) without packaging the project | Simplest setup for a beginner | Accepted\* |
| D18 | Validation result levels: PASS / INFO / WARN / FAIL. FAIL stops the pipeline; WARN records are kept and reported | Humans, not code, decide what to do with bad data | Accepted\* |
| D19 | `prepare_dataset` refuses to run if validation has any FAIL; no automatic cleaning of failed data | Prevents silent deletion or imputation | Accepted\* |
| D20 | Surname removed from the processed copy (columns only, never rows). CustomerId kept for identification; Year kept as metadata; neither is a feature | Privacy and relevance; raw file keeps everything | Accepted\* |
| D21 | Tie rules: balance exactly equal to the threshold -> Low-balance; credit-score terciles are right-closed (<= cut point) | Needed an explicit rule so results are unambiguous | Accepted\* |
| D22 | A negative balance (none exist) raises an error instead of receiving a label | The approved balance rule only covers zero and positive balances | Accepted\* |
| D23 | First and last bins are open-ended; implausible values are flagged by validation, not excluded by segmentation | Every record gets a label; review stays with a person | Accepted\* |
| D24 | Geography/zero-balance design rules: compare countries on non-zero-balance customers for like-for-like; report zero-balance comparisons only for countries that have them; show balance segments by country; label pooled comparisons as confounded | Germany has no zero-balance customers (verified) | Accepted\* |
| D25 | Processed data saved as CSV (no extra dependency); ordered categories are restored by `load_processed_data` | Simplicity for a beginner project | Accepted\* |
| D26 | All generated reports contain no timestamps, so reruns are byte-identical (tested) | Reproducibility | Accepted\* |
| D27 | Engagement Drop Indicator interval: Newcombe hybrid score method; value in percentage points (inactive minus active) | Suited to small groups and extreme rates; verified against a published example | Accepted (defaults confirmed) |
| D28 | Geographic Risk Index interval: country Wilson interval divided by the overall rate (treated as fixed); labelled approximate | Simple and transparent; the overall rate is itself built from the countries | Accepted (defaults confirmed) |
| D29 | KPIs describe the rows passed in; contributions are relative to those rows | Lets dashboard filters recompute KPIs consistently | Accepted (defaults confirmed) |
| D30 | Group tables keep missing segment values as their own row and check that sizes add up | No silent loss of customers | Accepted (defaults confirmed) |
| D31 | GRI is always shown for all customers AND for non-zero-balance customers; high-balance churn is shown pooled AND by country | Applies design rules D24 after the Germany / zero-balance finding | Accepted (defaults confirmed) |
| D32 | Paper deliverable: Word (.docx), IMRaD structure, only references the owner verifies; page limit and citation style not specified by the owner | Owner has only the project description; default chosen | Accepted default; revisit in Phase 7 |
| D33 | Phase 4 compares nine variables (incl. IsActiveMember and tenure groups) in simple rate tables; deeper engagement / tenure / salary / balance work is Phase 5 | Matches objective 2 of the brief without duplicating Phase 5 | Accepted (defaults; please review) |
| D34 | Rate ratio (segment rate / overall rate) and contribution gap are supporting measures for every segment | Generalises the Geographic Risk Index; not among the brief's KPIs | Accepted (defaults; please review) |
| D35 | Association strength = Cramer's V with Cohen's conventions (0.10 / 0.30 / 0.50) as descriptive labels from the config; p-values reported but not the focus | Large n makes p-values uninformative | Accepted (defaults; please review) |
| D36 | Numeric profile differences use Cohen's d (0.2 / 0.5 / 0.8) with an approximate interval | Simple, scale-free comparison of churned vs retained | Accepted (defaults; please review) |
| D37 | No multivariable or predictive model; single- and two-variable views with an explicit overlap caveat | Not required by the brief; keeps claims honest | Accepted (defaults; please review) |
| D38 | Gender gap = first configured gender minus second (Female - Male), Newcombe interval, overall and by country | Consistent with the engagement indicator | Accepted (defaults; please review) |
| D39 | Charts are produced by a separate script and Matplotlib is imported lazily | A security policy blocked a compiled library (pyarrow) on the owner's Windows machine, so the core pipeline must not depend on plotting libraries | Accepted (defaults; please review) |
| D40 | Segment rates of exactly 0% or 100% are listed as "worth confirming with the data owner" | NumOfProducts = 4 shows 60 of 60 churned; the data cannot explain it | Accepted (defaults; please review) |
| D41 | Readable labels for 0/1 columns live in the config (`[analysis.display_labels]`) | Display only; no values altered | Accepted (defaults; please review) |
| D42 | Phase 5 covers high-balance customers, salary vs balance, engagement, tenure and the balance exposure proxy in one module and report | Matches objectives 3 and 5 of the brief and the brief's high-value churn analysis | Accepted (defaults; please review) |
| D43 | High-balance vs Low-balance is compared among non-zero balances only, inside strata, and with a directly standardised gap (same weights for both groups; strata with a group below 30 customers left out; normal-approximation interval) | Zero-balance customers are a different group; this answers whether high-balance customers differ from comparable customers | Accepted (defaults; please review) |
| D44 | Salary and balance groups are equal-sized groups computed from the data (analysis only, not added to the processed data); group counts and labels are in the config | No arbitrary cut-offs; keeps Phase 2 output unchanged | Accepted (defaults; please review) |
| D45 | Spearman rank correlation for salary vs balance | Robust to skew and the zero-balance mass | Accepted (defaults; please review) |
| D46 | Balance exposure proxy is also broken down by variable and by concentration (top 10% / 20% / 50% of churned customers); never described as revenue | Answers the brief's revenue-risk question without inventing revenue | Accepted (defaults; please review) |
| D47 | Report sentences about trends, relationships, verdicts and data facts are computed from the numbers, not fixed text | Fixed claims can become false when data changes; found and fixed during development | Accepted (defaults; please review) |
| D48 | The largest engagement gap is reported among segments with at least 100 customers per group; a larger gap in a small sample is only a caveat | Small groups produce extreme, unreliable values | Accepted (defaults; please review) |
| D49 | Tenure is shown for each year with intervals and a rank correlation across years; no explanation is assumed for the small counts at the first and last year | Not enough evidence for a cause | Accepted (defaults; please review) |

\* **Accepted** by the project owner's instruction to proceed using "the decisions discussed above" (D10-D26), and later "do what is right" using the defaults (D27-D32). These were not individually confirmed, so please correct any you disagree with. D10 (raw CSV kept out of git) was not explicitly answered and remains at its default.
