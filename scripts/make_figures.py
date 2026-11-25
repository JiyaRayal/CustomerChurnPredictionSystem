"""Draw the report charts:  python scripts/make_figures.py

Run `python scripts/run_pipeline.py` first (it creates the processed data this script reads).
Charts need Matplotlib and Seaborn. If those cannot be loaded on your computer (for example a
security policy blocks them), this script says so and stops; everything else in the project
(tables, reports, tests) still works without them.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


def main() -> int:
    from churn_analytics.config import load_config, project_root
    from churn_analytics.data_loader import load_processed_data, resolve_path
    from churn_analytics.analysis import run_segment_analysis
    from churn_analytics.balance_engagement import run_balance_engagement_analysis
    from churn_analytics import kpis

    config = load_config()
    processed = resolve_path(config, "processed_dir") / "customers_segmented.csv"
    if not processed.is_file():
        print("Processed data not found. Run `python scripts/run_pipeline.py` first.")
        return 1
    try:
        from churn_analytics.visualization import make_all_figures, make_balance_engagement_figures
        import matplotlib, seaborn  # noqa: F401  (checks that the libraries can really be loaded)
    except ImportError as error:
        print(f"Charts could not be created because a plotting library failed to load:\n  {error}\n"
              "The tables and reports do not need it. Install Matplotlib and Seaborn, or ask your IT support to allow them.")
        return 1

    df = load_processed_data(processed, config)
    analysis = run_segment_analysis(df, config)
    overall = kpis.overall_churn_rate(df, config)["rate"]
    out_dir = project_root() / config["paths"]["figures_dir"]
    be = run_balance_engagement_analysis(df, config)
    drawn = {**make_all_figures(analysis, config, overall, out_dir),
             **make_balance_engagement_figures(be, config, overall, out_dir)}
    for name, path in drawn.items():
        print(f"  wrote {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
