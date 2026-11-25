# Customer Segmentation & Churn Pattern Analytics in European Banking

A segmentation-driven analysis of customer churn for a Unified Mentor internship project.
It measures overall churn, compares churn across customer segments, identifies high-risk
and high-balance segments, and will deliver an interactive dashboard, a research paper
and an executive summary.

> **Important:** the dataset's provenance is unconfirmed. This project does **not** claim
> the data is official European Central Bank data. All findings are descriptive
> associations in a single snapshot, not causal effects.

## Project status

| Phase | Content | Status |
|---|---|---|
| 0 | Dataset inspection | Done |
| 1 | Project scaffold, config, documentation | Done |
| 2 | Data ingestion, validation, cleaning, derived segments, Geography x zero-balance investigation | Done |
| 3 | KPI module (6 KPIs + balance exposure proxy) and KPI summary report | Done |
| 4 | Segment churn analysis, report and six charts | Done |
| 5 | **High-balance, salary, engagement, tenure and balance-exposure analysis, report and six charts** | **Done (awaiting review)** |
| 6 | Streamlit dashboard | Not started |
| 7 | Research paper and executive summary | Not started |
| 8 | QA and packaging | Not started |

Not built yet: the Streamlit dashboard, research paper and executive summary.
Modules marked *placeholder* contain only a description of their planned purpose.

## Repository layout

```
churn-analytics-project/
├── config/segmentation.toml     # ALL thresholds, schema and statistical settings (single source of truth)
├── data/
│   ├── raw/                     # original CSV (read-only) + SHA256SUMS fingerprint
│   └── processed/               # generated: customers_segmented.csv, segmentation_metadata.json
├── docs/
│   ├── code_guide.md            # beginner-friendly explanation of how the code fits together
│   ├── kpi_definitions.md       # exact formula, numerator, denominator, empty-group rule per KPI
│   ├── analysis_methods.md      # measures and rules used in the segment analysis
│   ├── balance_engagement_methods.md # measures and rules used in the Phase 5 analysis
│   ├── segmentation_rules.md    # every segment boundary explained
│   ├── data_provenance.md       # what is and is not known about the data
│   ├── decisions_log.md         # each decision and its status
│   └── source/project_brief.txt # the official requirements, as supplied
├── src/churn_analytics/
│   ├── config.py                # loads and validates the config
│   ├── data_loader.py           # checksum-verified loading of raw data; reloading processed data
│   ├── validation.py            # data-quality checks -> validation report
│   ├── cleaning.py              # documented cleaning decisions (no silent changes)
│   ├── segmentation.py          # age / credit / tenure / balance segments from config thresholds
│   ├── geography_balance.py     # Geography x zero-balance investigation
│   ├── stats_utils.py           # Wilson interval, group-size rules, chi-square
│   ├── md_utils.py              # Markdown helpers for reports
│   ├── kpis.py                  # KPI functions (formulas in docs/kpi_definitions.md)
│   ├── kpi_report.py            # headline KPI summary -> reports/kpi_summary.md
│   ├── analysis.py              # segment churn analysis (rates, contributions, Cramer's V, drill-downs, profiles)
│   ├── analysis_report.py       # -> reports/segment_churn_analysis.md
│   ├── balance_engagement.py    # high-balance, salary, engagement, tenure, balance exposure proxy
│   ├── balance_engagement_report.py # -> reports/high_balance_engagement_analysis.md
│   ├── visualization.py         # twelve report charts (plotting libraries imported lazily)
│   ├── pipeline.py              # runs the whole flow and writes outputs
├── scripts/run_pipeline.py      # one-command runner (data, tables, reports)
├── scripts/make_figures.py      # draws the charts into reports/figures/ (needs Matplotlib + Seaborn)
├── app/streamlit_app.py         # placeholder (Phase 6)
├── tests/                       # unit and end-to-end tests
├── reports/
│   ├── validation_report.md                    # generated
│   ├── cleaning_log.md                         # generated
│   ├── geography_zero_balance_investigation.md # generated
│   ├── kpi_summary.md                          # generated
│   ├── segment_churn_analysis.md               # generated
│   ├── high_balance_engagement_analysis.md     # generated
│   ├── figures/                                # generated charts (PNG)
│   └── tables/                                 # generated CSV tables
├── requirements.txt / requirements-dev.txt
└── pytest.ini
```

## Setup

Requires **Python 3.11 or newer** (the config loader uses the built-in `tomllib`).

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
```

Place `European_Bank.csv` in `data/raw/` if it is not there (the CSV is git-ignored by
default; see `data/README.md`), then verify it and run the tests:

```bash
cd data/raw && sha256sum -c SHA256SUMS && cd ../..
pytest                              # run the tests
python scripts/run_pipeline.py      # verify -> validate -> clean/segment -> investigate -> KPIs -> write reports
```

To draw the charts (optional; needs Matplotlib and Seaborn):

```bash
python scripts/make_figures.py
```

The pipeline writes only to `data/processed/` and `reports/`. It stops immediately if the raw
file's checksum does not match, or if validation finds a FAIL-level problem (the validation
report is still written so you can see why).

## Design principles

1. **One source of truth for thresholds.** Code reads `config/segmentation.toml` and never hard-codes cut-offs.
2. **Raw data is sacred.** It is never edited; a checksum test detects any change.
3. **No silent deletion or imputation.** Anything excluded is counted and explained.
4. **Rates always come with segment size** and a confidence interval; small groups are flagged.
5. **Associations, not causes.** Wording in all outputs reflects this.
6. **Every number in the paper traces to code.** Nothing is typed in by hand.

## Known limitations

* Provenance, licence, and the exact meaning of `Exited` and `Year` are unconfirmed.
* One snapshot, three countries: not a basis for conclusions about "European banking" generally.
* No revenue or profit fields: balance-based figures are exposure proxies, not financial loss.
* Requirement ambiguities and the choices made are logged in `docs/decisions_log.md`.

## Troubleshooting (Windows)

* **"No such file or directory" for `scripts\run_pipeline.py`, or "No module named churn_analytics":** extracting a zip can
  create a folder inside a folder. Run `cd churn-analytics-project` until `dir` shows `src`, `tests`, `scripts` and `pytest.ini`.
* **`pip.exe` / `pytest.exe` blocked by Device Guard:** call them through Python instead: `python -m pip install ...`, `python -m pytest`.
* **"DLL load failed ... Application Control policy" when importing pandas:** `pyarrow` (installed as a dependency of Streamlit)
  can be blocked. The project does not need it: `python -m pip uninstall pyarrow -y`. The dashboard (Phase 6) will need a different
  route if it stays blocked (for example Streamlit Community Cloud or IT approval).
* **Charts fail to load Matplotlib:** the tables and reports are unaffected; see the message printed by `scripts/make_figures.py`.
