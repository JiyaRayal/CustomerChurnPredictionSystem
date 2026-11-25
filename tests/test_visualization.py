"""Tests for the figures. They are skipped automatically if Matplotlib/Seaborn cannot be loaded."""

import subprocess
import sys

import pandas as pd
import pytest

from churn_analytics.analysis import run_segment_analysis
from churn_analytics.config import project_root
from churn_analytics.segmentation import add_segments

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def test_importing_the_module_does_not_load_matplotlib():
    """The module must stay importable on a computer where plotting libraries are blocked."""
    code = ("import sys; sys.path.insert(0, r'%s'); import churn_analytics.visualization; "
            "print('matplotlib' in sys.modules)" % (project_root() / "src"))
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert out.stdout.strip() == "False"


@pytest.fixture(scope="module")
def drawn(raw_df, config, tmp_path_factory):
    pytest.importorskip("matplotlib")
    pytest.importorskip("seaborn")
    from churn_analytics.visualization import make_all_figures
    segmented, _ = add_segments(raw_df.drop(columns=["Surname"]), config)
    analysis = run_segment_analysis(segmented, config)
    before = {name: getattr(analysis, name).copy() for name in ("overview", "association", "gender", "profile_numeric")}
    out = tmp_path_factory.mktemp("figs")
    paths = make_all_figures(analysis, config, float(segmented["Exited"].mean()), out)
    return paths, analysis, before


def test_all_six_figures_are_written_as_png_files(drawn):
    paths, _, _ = drawn
    assert set(paths) == {"churn_rate_by_segment.png", "association_strength.png", "share_vs_contribution.png",
                          "geography_age_heatmap.png", "gender_gap.png", "profile_effect_sizes.png"}
    for path in paths.values():
        data = path.read_bytes()
        assert data.startswith(PNG_SIGNATURE) and len(data) > 10_000, path


def test_drawing_does_not_change_the_analysis_tables(drawn):
    _, analysis, before = drawn
    for name, table in before.items():
        pd.testing.assert_frame_equal(getattr(analysis, name), table)


# --- Phase 5 figures ---------------------------------------------------------------------
@pytest.fixture(scope="module")
def drawn_be(raw_df, config, tmp_path_factory):
    pytest.importorskip("matplotlib")
    pytest.importorskip("seaborn")
    from churn_analytics.balance_engagement import run_balance_engagement_analysis
    from churn_analytics.visualization import make_balance_engagement_figures
    segmented, _ = add_segments(raw_df.drop(columns=["Surname"]), config)
    analysis = run_balance_engagement_analysis(segmented, config)
    before = {name: getattr(analysis, name).copy() for name in ("high_vs_low_by_stratum", "engagement_by_segment", "tenure_curve",
                                                               "balance_engagement_matrix")}
    paths = make_balance_engagement_figures(analysis, config, float(segmented["Exited"].mean()), tmp_path_factory.mktemp("figs5"))
    return paths, analysis, before


def test_all_six_balance_engagement_figures_are_written(drawn_be):
    paths, _, _ = drawn_be
    assert set(paths) == {"high_vs_low_balance.png", "churn_by_balance_group.png", "salary_balance_heatmap.png",
                          "engagement_gap_by_segment.png", "tenure_churn_curve.png", "churned_balance_exposure.png"}
    for path in paths.values():
        data = path.read_bytes()
        assert data.startswith(PNG_SIGNATURE) and len(data) > 10_000, path


def test_drawing_balance_engagement_figures_does_not_change_the_tables(drawn_be):
    _, analysis, before = drawn_be
    for name, table in before.items():
        pd.testing.assert_frame_equal(getattr(analysis, name), table)
