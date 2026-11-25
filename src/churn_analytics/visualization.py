"""Static charts for the reports (Matplotlib + Seaborn).

Beginner notes
--------------
* Matplotlib is imported **inside** the functions, not at the top of the file. That way the
  rest of the project (analysis, reports, tests) works even on a computer where plotting
  libraries cannot be loaded (for example when a security policy blocks their compiled files).
* Charts use the non-interactive "Agg" backend: they are saved as PNG files, never shown on screen.
* Every chart shows group sizes or intervals where they matter, has a plain-language title, and
  uses the same colours for the same ideas (blue = churn rate, orange = overall / contribution,
  grey = customer share, hatched = small sample).
* Charts show the same numbers as the tables: they are drawn from the ``SegmentAnalysis`` tables.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .analysis import SegmentAnalysis
from .stats_utils import STATUS_SMALL

BLUE, ORANGE, GREY, RED = "#2F6DB5", "#E07B39", "#9AA0A6", "#B23A48"
EFFECT_COLOURS = ["#C9CED6", "#8FB4DC", "#4F86C6", "#1F4E8C"]   # negligible -> large


def _setup():
    """Import plotting libraries lazily and pick the file-only backend."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import seaborn as sns
    sns.set_theme(style="whitegrid", context="notebook")
    return plt, sns


def _save(fig, plt, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return path


# --------------------------------------------------------------------------------------
def plot_churn_rate_by_segment(a: SegmentAnalysis, config: dict[str, Any], overall_rate: float, out: Path) -> Path:
    """One small chart per variable: churn rate by segment with 95% interval and group size."""
    plt, _ = _setup()
    variables = config["analysis"]["segment_variables"]
    small = config["statistics"]["small_group_threshold"]
    ncols = 3
    nrows = int(np.ceil(len(variables) / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=(15, 3.4 * nrows))
    axes = np.atleast_1d(axes).ravel()

    for ax, variable in zip(axes, variables):
        part = a.overview[a.overview["variable"] == variable].reset_index(drop=True)
        y = np.arange(len(part))
        rates = part["churn_rate"].to_numpy(dtype=float) * 100
        # clip at 0: a rate of exactly 100% has an upper bound of 0.9999999..., which would give a tiny negative bar
        low = np.clip((part["churn_rate"] - part["ci_low"]).to_numpy(dtype=float) * 100, 0, None)
        high = np.clip((part["ci_high"] - part["churn_rate"]).to_numpy(dtype=float) * 100, 0, None)
        bars = ax.barh(y, np.nan_to_num(rates), xerr=[np.nan_to_num(low), np.nan_to_num(high)], color=BLUE,
                       error_kw={"ecolor": "#333333", "capsize": 3, "lw": 1})
        for bar, status in zip(bars, part["status"]):
            if status == STATUS_SMALL:
                bar.set_hatch("//"); bar.set_alpha(0.6)
        ax.axvline(overall_rate * 100, color=ORANGE, ls="--", lw=1.5)
        ax.set_yticks(y)
        ax.set_yticklabels([f"{s} (n={n:,})" for s, n in zip(part["segment"], part["n"])], fontsize=9)
        ax.invert_yaxis()
        ax.set_xlim(0, 122)                       # extra room on the right for the value labels
        ax.set_xticks(range(0, 101, 20))
        ax.tick_params(labelbottom=True)           # show the scale on every panel, not only the bottom row
        ax.set_title(variable, fontsize=11, loc="left", fontweight="bold")
        for yi, rate, upper in zip(y, rates, high):
            if np.isnan(rate):  # no rate to draw (empty or too small): say so instead of showing an empty row
                ax.text(2, yi, "n/a", va="center", fontsize=8)
            else:
                ax.text(rate + upper + 1.5, yi, f"{rate:.1f}%", va="center", fontsize=9, fontweight="bold")
    for ax in axes[len(variables):]:
        ax.axis("off")
    for ax in axes[:len(variables)]:
        ax.set_xlabel("Churn rate (%)")
    fig.suptitle(f"Churn rate by customer segment (95% confidence intervals; dashed line = overall "
                 f"{overall_rate * 100:.1f}%)", fontsize=14, y=1.0)
    fig.text(0.01, -0.005, f"Hatched bars: small sample (fewer than {small} customers). Single-variable views; "
             "associations, not causal effects.", fontsize=9, color="#555555")
    fig.tight_layout()
    return _save(fig, plt, out)


def plot_association_strength(a: SegmentAnalysis, config: dict[str, Any], out: Path) -> Path:
    """Cramer's V per variable, coloured by its effect-size label."""
    plt, _ = _setup()
    analysis = config["analysis"]
    data = a.association.dropna(subset=["cramers_v"]).sort_values("cramers_v")
    labels = analysis["effect_size_labels"]
    fig, ax = plt.subplots(figsize=(9, 0.55 * len(data) + 2))
    colours = [EFFECT_COLOURS[labels.index(e)] for e in data["effect"]]
    ax.grid(axis="y", visible=False)
    ax.barh(data["variable"], data["cramers_v"], color=colours, edgecolor="#333333", lw=0.6)
    for cutoff in analysis["effect_size_cutoffs"]:
        ax.axvline(cutoff, color=GREY, ls=":", lw=1)
    for value, variable in zip(data["cramers_v"], data["variable"]):
        ax.text(value + 0.005, variable, f"{value:.2f}", va="center", fontsize=9)
    handles = [plt.Rectangle((0, 0), 1, 1, color=c, ec="#333333") for c in EFFECT_COLOURS]
    ax.legend(handles, labels, title="Effect size", loc="lower right", frameon=True)
    ax.set_xlabel("Cramer's V (0 = no association, 1 = perfect association)")
    ax.set_xlim(0, max(0.6, data["cramers_v"].max() + 0.08))
    ax.set_title("How strongly does each variable go with churn?", fontsize=13, loc="left", fontweight="bold")
    fig.tight_layout()
    return _save(fig, plt, out)


def plot_share_vs_contribution(a: SegmentAnalysis, config: dict[str, Any], out: Path, top_variables: int = 6) -> Path:
    """Share of customers vs share of churners, for the variables most strongly associated with churn."""
    plt, _ = _setup()
    variables = list(a.association.dropna(subset=["cramers_v"])["variable"].head(top_variables))
    ncols = 3
    nrows = int(np.ceil(len(variables) / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=(15, 4.0 * nrows), sharey=True)
    axes = np.atleast_1d(axes).ravel()
    for index, (ax, variable) in enumerate(zip(axes, variables)):
        part = a.overview[a.overview["variable"] == variable].reset_index(drop=True)
        x = np.arange(len(part))
        ax.grid(axis="x", visible=False)           # vertical grid lines add nothing to a column chart
        ax.bar(x - 0.2, part["share_of_customers"] * 100, 0.4, color=GREY, label="Share of customers")
        ax.bar(x + 0.2, part["churn_contribution"].fillna(0) * 100, 0.4, color=ORANGE, label="Share of churners")
        ax.set_xticks(x)
        ax.set_xticklabels(part["segment"], rotation=20, ha="right", fontsize=9)
        ax.set_title(variable, fontsize=11, loc="left", fontweight="bold")
        ax.set_ylabel("% of all customers / churners" if index % ncols == 0 else "")
    for ax in axes[len(variables):]:
        ax.axis("off")
    axes[0].legend(loc="upper right", fontsize=9)
    fig.suptitle("Where are the churners? Share of customers vs share of churners, by segment", fontsize=14, y=1.0)
    fig.tight_layout()
    return _save(fig, plt, out)


def _rate_grid(table: pd.DataFrame, row_var: str, col_var: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Pivot a two-variable churn table into (rates in %, annotation text) grids for a heatmap."""
    order_r, order_c = list(dict.fromkeys(table[row_var])), list(dict.fromkeys(table[col_var]))
    rates = table.pivot(index=row_var, columns=col_var, values="churn_rate").reindex(index=order_r, columns=order_c) * 100
    counts = table.pivot(index=row_var, columns=col_var, values="n").reindex(index=order_r, columns=order_c)
    status = table.pivot(index=row_var, columns=col_var, values="status").reindex(index=order_r, columns=order_c)
    labels = rates.copy().astype(object)
    for r in rates.index:
        for c in rates.columns:
            n = int(counts.loc[r, c])
            labels.loc[r, c] = f"n/a\n(n={n:,})" if np.isnan(rates.loc[r, c]) else \
                f"{rates.loc[r, c]:.1f}%\n(n={n:,})" + ("*" if status.loc[r, c] == STATUS_SMALL else "")
    return rates.astype(float), labels


def _draw_heatmaps(views, row_var: str, col_var: str, suptitle: str, footnote: str, out: Path, figsize=(15, 4.6)) -> Path:
    """Draw one annotated heatmap per (title, table) view on a shared colour scale."""
    plt, sns = _setup()
    grids = [(title, *_rate_grid(table, row_var, col_var)) for title, table in views]
    vmax = float(np.nanmax([g.to_numpy(dtype=float).max() for _, g, _ in grids]))
    fig, axes = plt.subplots(1, len(grids), figsize=figsize, sharey=True)
    axes = np.atleast_1d(axes)
    for ax, (title, rates, labels) in zip(axes, grids):
        sns.heatmap(rates, annot=labels, fmt="", cmap="YlOrRd", vmin=0, vmax=vmax, ax=ax, cbar=ax is axes[-1],
                    cbar_kws={"label": "Churn rate (%)"}, linewidths=1, linecolor="white", annot_kws={"fontsize": 9})
        for i in range(rates.shape[0]):          # seaborn skips empty cells, so write their "n/a (n=...)" note ourselves
            for j in range(rates.shape[1]):
                if np.isnan(rates.iloc[i, j]):
                    ax.text(j + 0.5, i + 0.5, labels.iloc[i, j], ha="center", va="center", fontsize=9, color="#777777")
        ax.set_title(title, fontsize=12, loc="left", fontweight="bold")
        ax.set_xlabel(col_var)
        ax.set_ylabel(row_var if ax is axes[0] else "")
    fig.suptitle(suptitle, fontsize=14, y=1.03)
    fig.text(0.01, -0.03, footnote, fontsize=9, color="#555555")
    fig.tight_layout()
    return _save(fig, plt, out)


def plot_geography_age_heatmap(a: SegmentAnalysis, config: dict[str, Any], out: Path) -> Path:
    """Country x age churn rates for all customers and for non-zero-balance customers (like-for-like)."""
    row_var, col_var = config["analysis"]["interaction_row"], config["analysis"]["interaction_col"]
    return _draw_heatmaps(
        [("All customers", a.geography_age_all), ("Non-zero-balance customers only", a.geography_age_non_zero)],
        row_var, col_var, f"Churn rate by {row_var} and {col_var} (* = small sample, n/a = not shown)",
        "No German customer has a zero balance, so the right-hand panel is the like-for-like country comparison.", out)


def plot_gender_gap(a: SegmentAnalysis, config: dict[str, Any], out: Path) -> Path:
    """Gender gap (first minus second configured gender) overall and by country, with intervals."""
    plt, _ = _setup()
    g = a.gender.dropna(subset=[c for c in a.gender.columns if c.startswith("gap_pp")]).reset_index(drop=True)
    gap_col = next(c for c in g.columns if c.startswith("gap_pp"))
    gap_label = gap_col.split("(")[1].rstrip(")")
    fig, ax = plt.subplots(figsize=(9, 0.8 * len(g) + 2))
    y = np.arange(len(g))
    ax.errorbar(g[gap_col], y, xerr=[np.clip(g[gap_col] - g["ci_low_pp"], 0, None),
                                     np.clip(g["ci_high_pp"] - g[gap_col], 0, None)], fmt="o", color=BLUE,
                ecolor="#333333", capsize=4, ms=7)
    ax.axvline(0, color=GREY, lw=1)
    ax.set_yticks(y); ax.set_yticklabels(g["scope"])
    ax.grid(axis="y", visible=False)
    for yi, v, upper in zip(y, g[gap_col], g["ci_high_pp"]):       # labels sit right of the interval, clear of the title
        ax.text(upper + 0.25, yi, f"{v:+.1f} pp", ha="left", va="center", fontsize=10, fontweight="bold")
    ax.set_xlim(min(0, g["ci_low_pp"].min()) - 0.5, g["ci_high_pp"].max() + 2.5)
    ax.set_ylim(len(g) - 0.5, -0.5)
    ax.set_xlabel(f"Churn-rate gap, {gap_label} (percentage points, 95% interval)")
    ax.set_title("Churn-rate gap between genders, overall and by country", fontsize=13, loc="left", fontweight="bold")
    fig.tight_layout()
    return _save(fig, plt, out)


def plot_profile_effect_sizes(a: SegmentAnalysis, config: dict[str, Any], out: Path) -> Path:
    """Standardised difference (Cohen's d) between churned and retained customers, per numeric column."""
    plt, _ = _setup()
    data = a.profile_numeric.reset_index(drop=True)
    y = np.arange(len(data))
    fig, ax = plt.subplots(figsize=(9, 0.7 * len(data) + 2.2))
    ax.errorbar(data["cohens_d"], y, xerr=[np.clip(data["cohens_d"] - data["d_ci_low"], 0, None),
                                           np.clip(data["d_ci_high"] - data["cohens_d"], 0, None)],
                fmt="o", color=BLUE, ecolor="#333333", capsize=4, ms=7)
    ax.axvline(0, color="#333333", lw=1)
    ax.grid(False)                                   # the grid would compete with the labelled cut-off lines
    names = config["analysis"]["effect_size_labels"][1:]
    for cutoff, name in zip(config["analysis"]["smd_cutoffs"], names):
        for sign in (-1, 1):
            ax.axvline(sign * cutoff, color=GREY, ls=":", lw=1)
        ax.text(cutoff, -0.62, name, ha="center", va="bottom", fontsize=9, color="#555555")
        ax.text(-cutoff, -0.62, name, ha="center", va="bottom", fontsize=9, color="#555555")
    ax.set_ylim(len(data) - 0.4, -0.75)
    ax.set_yticks(y); ax.set_yticklabels(data["column"])
    cutoffs_text = " / ".join(f"{c:g}" for c in config["analysis"]["smd_cutoffs"])
    ax.set_xlabel(f"Standardised difference d (churned minus retained); dotted lines mark {cutoffs_text}")
    ax.set_title("How different are churned and retained customers?", fontsize=13, loc="left", fontweight="bold")
    fig.tight_layout()
    return _save(fig, plt, out)


FIGURES = {
    "churn_rate_by_segment.png": "churn_rate_by_segment",
    "association_strength.png": "association_strength",
    "share_vs_contribution.png": "share_vs_contribution",
    "geography_age_heatmap.png": "geography_age_heatmap",
    "gender_gap.png": "gender_gap",
    "profile_effect_sizes.png": "profile_effect_sizes",
}


def make_all_figures(a: SegmentAnalysis, config: dict[str, Any], overall_rate: float, out_dir: Path) -> dict[str, Path]:
    """Draw every report figure into ``out_dir`` and return {file name: path}."""
    out_dir = Path(out_dir)
    return {
        "churn_rate_by_segment.png": plot_churn_rate_by_segment(a, config, overall_rate, out_dir / "churn_rate_by_segment.png"),
        "association_strength.png": plot_association_strength(a, config, out_dir / "association_strength.png"),
        "share_vs_contribution.png": plot_share_vs_contribution(a, config, out_dir / "share_vs_contribution.png"),
        "geography_age_heatmap.png": plot_geography_age_heatmap(a, config, out_dir / "geography_age_heatmap.png"),
        "gender_gap.png": plot_gender_gap(a, config, out_dir / "gender_gap.png"),
        "profile_effect_sizes.png": plot_profile_effect_sizes(a, config, out_dir / "profile_effect_sizes.png"),
    }


# ======================================================================================
# Phase 5 figures: high-balance, salary, engagement, tenure, balance exposure
# ======================================================================================
def _dot_whisker(ax, labels, values, low, high, colours, hollow=None, zero_line=True):
    """Horizontal dots with interval whiskers; hollow dots mark small samples."""
    y = np.arange(len(labels))
    values, low, high = (np.asarray(x, dtype=float) for x in (values, low, high))
    hollow = hollow if hollow is not None else [False] * len(labels)
    for yi, v, lo, hi, colour, is_hollow in zip(y, values, low, high, colours, hollow):
        if np.isnan(v):
            ax.text(0, yi, "n/a", va="center", ha="center", fontsize=8, color="#777777")
            continue
        ax.errorbar(v, yi, xerr=[[max(v - lo, 0)], [max(hi - v, 0)]], fmt="o", color=colour, ecolor="#333333",
                    capsize=3, ms=7, mfc="white" if is_hollow else colour)
    if zero_line:
        ax.axvline(0, color=GREY, lw=1)
    ax.set_yticks(y); ax.set_yticklabels(labels, fontsize=9)
    ax.set_ylim(len(labels) - 0.5, -0.5)
    ax.grid(axis="y", visible=False)


def plot_high_vs_low_balance(b, config: dict[str, Any], out: Path) -> Path:
    """High-balance minus Low-balance churn gap (non-zero balances), inside strata and directly standardised."""
    plt, _ = _setup()
    strata = b.high_vs_low_by_stratum
    std = b.standardised_high_vs_low.dropna(subset=["standardised_gap_pp"])
    labels = [("All non-zero customers" if r.stratum == "All customers" else f"{r.variable}: {r.stratum}") for r in strata.itertuples()]
    values, low, high = list(strata["gap_pp"]), list(strata["ci_low_pp"]), list(strata["ci_high_pp"])
    colours = [BLUE] * len(strata)
    labels += [f"Standardised by {r.strata}" for r in std.itertuples()]
    values += list(std["standardised_gap_pp"]); low += list(std["ci_low_pp"]); high += list(std["ci_high_pp"])
    colours += [ORANGE] * len(std)
    fig, ax = plt.subplots(figsize=(10, 0.55 * len(labels) + 2))
    _dot_whisker(ax, labels, values, low, high, colours)
    ax.set_xlabel("High-balance minus Low-balance churn rate (percentage points, 95% interval)")
    ax.set_title("High-balance vs Low-balance churn: any difference?", fontsize=13, loc="left", fontweight="bold")
    fig.text(0.01, -0.02, "Non-zero balances only. Orange = directly standardised over the same customer mix. "
             "Intervals that include 0 mean no detectable difference.", fontsize=9, color="#555555")
    fig.tight_layout()
    return _save(fig, plt, out)


def plot_churn_by_balance_group(b, config: dict[str, Any], out: Path) -> Path:
    """Churn rate across equal-sized groups of non-zero balances, with the zero-balance rate for reference."""
    plt, _ = _setup()
    t = b.balance_group_churn.reset_index(drop=True)
    seg_col = config["kpi"]["balance_segment_column"]
    zero_label = config["segmentation"]["balance"]["zero_label"]
    m = b.balance_engagement_matrix
    zero_rows = m[m[seg_col] == zero_label]
    zero_rate = zero_rows["churned"].sum() / zero_rows["n"].sum() if zero_rows["n"].sum() else np.nan
    nonzero = t["churned"].sum() / t["n"].sum()
    x = np.arange(len(t))
    rates = t["churn_rate"].to_numpy(dtype=float) * 100
    err = [np.clip(rates - t["ci_low"].to_numpy(dtype=float) * 100, 0, None), np.clip(t["ci_high"].to_numpy(dtype=float) * 100 - rates, 0, None)]
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.bar(x, rates, yerr=err, color=BLUE, error_kw={"ecolor": "#333333", "capsize": 4})
    for xi, r in zip(x, rates):        # labels sit inside the bars so they never collide with the reference lines
        ax.text(xi, r / 2, f"{r:.1f}%", ha="center", va="center", fontsize=11, fontweight="bold", color="white")
    ax.axhline(nonzero * 100, color=ORANGE, ls="--", lw=1.5, label=f"All non-zero balances ({nonzero * 100:.1f}%)")
    if not np.isnan(zero_rate):
        ax.axhline(zero_rate * 100, color=GREY, ls=":", lw=1.8, label=f"Zero-balance customers ({zero_rate * 100:.1f}%)")
    ax.set_xticks(x)
    ax.set_xticklabels([f"{g}\n{lo / 1000:,.0f}k-{hi / 1000:,.0f}k\n(n={n:,})" for g, lo, hi, n in
                        zip(t["group"], t["balance_min"], t["balance_max"], t["n"])], fontsize=9)
    ax.set_ylim(0, max(rates.max() * 1.35, 10)); ax.grid(axis="x", visible=False)
    ax.set_ylabel("Churn rate (%)")
    ax.set_title("Churn rate by size of balance (non-zero balances, equal-sized groups, 95% CI)", fontsize=13, loc="left", fontweight="bold")
    ax.legend(loc="upper left")
    fig.tight_layout()
    return _save(fig, plt, out)


def plot_salary_balance_heatmap(b, config: dict[str, Any], out: Path) -> Path:
    """Salary group x balance segment churn rates (all customers, and non-zero balances only)."""
    seg_col = config["kpi"]["balance_segment_column"]
    return _draw_heatmaps(
        [("All customers", b.salary["grid_all"]), ("Non-zero-balance customers only", b.salary["grid_non_zero"])],
        "SalaryBand", seg_col, "Churn rate by salary group and balance segment (* = small sample, n/a = not shown)",
        "Salary groups are equal-sized thirds. Salary and balance are recorded amounts, not measures of profitability.", out, figsize=(14, 4.4))


def plot_engagement_gap_by_segment(b, config: dict[str, Any], out: Path) -> Path:
    """Inactive-minus-active churn gap inside each segment (hollow = small sample)."""
    plt, _ = _setup()
    t = b.engagement_by_segment.reset_index(drop=True)
    labels = [("All customers" if r.segment == "All customers" else f"{r.variable}: {r.segment}") for r in t.itertuples()]
    colours = [ORANGE if r.segment == "All customers" else BLUE for r in t.itertuples()]
    hollow = [r.status == STATUS_SMALL for r in t.itertuples()]
    fig, ax = plt.subplots(figsize=(10, 0.36 * len(t) + 2))
    _dot_whisker(ax, labels, t["edi_pp"], t["ci_low_pp"], t["ci_high_pp"], colours, hollow)
    ax.axvline(float(t.loc[0, "edi_pp"]), color=ORANGE, ls="--", lw=1.2)
    ax.set_xlabel("Churn rate of inactive members minus active members (percentage points, 95% interval)")
    ax.set_title("Is the engagement gap present in every segment?", fontsize=13, loc="left", fontweight="bold")
    fig.text(0.01, -0.01, "Hollow dots: small sample. n/a: group too small to show. Dashed line: overall gap. Association, not cause: "
             "inactivity may be a symptom of leaving.", fontsize=9, color="#555555")
    fig.tight_layout()
    return _save(fig, plt, out)


def plot_tenure_curve(b, config: dict[str, Any], overall_rate: float, out: Path) -> Path:
    """Churn rate by tenure year with intervals, and the number of customers in each year."""
    plt, _ = _setup()
    t = b.tenure_curve.reset_index(drop=True)
    fig, (ax, ax2) = plt.subplots(2, 1, figsize=(10, 6.5), sharex=True, gridspec_kw={"height_ratios": [3, 1]})
    rates = t["churn_rate"].to_numpy(dtype=float) * 100
    ax.fill_between(t["tenure"], t["ci_low"] * 100, t["ci_high"] * 100, color=BLUE, alpha=0.2, label="95% interval")
    ax.plot(t["tenure"], rates, "o-", color=BLUE, lw=2, label="Churn rate")
    ax.axhline(overall_rate * 100, color=ORANGE, ls="--", lw=1.5, label=f"Overall ({overall_rate * 100:.1f}%)")
    ax.set_ylim(0, max(30, float(np.nanmax(t["ci_high"] * 100)) + 3)); ax.set_ylabel("Churn rate (%)")
    ax.legend(loc="upper right", ncol=3, fontsize=9)
    ax.set_title("Churn rate by years with the bank (tenure)", fontsize=13, loc="left", fontweight="bold")
    ax2.bar(t["tenure"], t["n"], color=GREY)
    ax2.set_ylabel("Customers"); ax2.set_xlabel("Tenure (years)"); ax2.set_xticks(t["tenure"]); ax2.grid(axis="x", visible=False)
    fig.tight_layout()
    return _save(fig, plt, out)


def plot_churned_balance_exposure(b, config: dict[str, Any], out: Path) -> Path:
    """Share of all churned balance by balance segment and engagement (exposure proxy, not lost revenue)."""
    plt, _ = _setup()
    seg_col, eng_col = config["kpi"]["balance_segment_column"], config["kpi"]["engagement_column"]
    m = b.balance_engagement_matrix
    segments = list(dict.fromkeys(m[seg_col]))
    engagement = list(dict.fromkeys(m[eng_col]))
    colours = {engagement[0]: ORANGE, engagement[-1]: BLUE}
    fig, ax = plt.subplots(figsize=(10, 5.5))
    width = 0.38
    for k, level in enumerate(engagement):
        part = m[m[eng_col] == level].set_index(seg_col).reindex(segments)
        xs = np.arange(len(segments)) + (k - (len(engagement) - 1) / 2) * width
        vals = part["share_of_all_churned_balance"].fillna(0).to_numpy(dtype=float) * 100
        ax.bar(xs, vals, width, color=colours.get(level, GREY), label=level)
        for xi, v, rate, n in zip(xs, vals, part["churn_rate"], part["n"]):
            ax.text(xi, v + 0.8, f"{v:.1f}%\nchurn {rate * 100:.1f}%\n(n={int(n):,})", ha="center", fontsize=9)
    ax.set_xticks(np.arange(len(segments))); ax.set_xticklabels(segments)
    ax.set_ylim(0, max(45, float(m["share_of_all_churned_balance"].max() * 100) + 12)); ax.grid(axis="x", visible=False)
    ax.set_ylabel("Share of all churned balance (%)")
    ax.legend(title="Engagement", loc="upper left")
    ax.set_title("Where is the balance held by churned customers?", fontsize=13, loc="left", fontweight="bold")
    fig.text(0.01, -0.01, "Balance exposure proxy: balances of customers who left. Not lost revenue, profit or lifetime value.",
             fontsize=9, color="#555555")
    fig.tight_layout()
    return _save(fig, plt, out)


def make_balance_engagement_figures(b, config: dict[str, Any], overall_rate: float, out_dir: Path) -> dict[str, Path]:
    """Draw the Phase 5 figures into ``out_dir`` and return {file name: path}."""
    out_dir = Path(out_dir)
    return {
        "high_vs_low_balance.png": plot_high_vs_low_balance(b, config, out_dir / "high_vs_low_balance.png"),
        "churn_by_balance_group.png": plot_churn_by_balance_group(b, config, out_dir / "churn_by_balance_group.png"),
        "salary_balance_heatmap.png": plot_salary_balance_heatmap(b, config, out_dir / "salary_balance_heatmap.png"),
        "engagement_gap_by_segment.png": plot_engagement_gap_by_segment(b, config, out_dir / "engagement_gap_by_segment.png"),
        "tenure_churn_curve.png": plot_tenure_curve(b, config, overall_rate, out_dir / "tenure_churn_curve.png"),
        "churned_balance_exposure.png": plot_churned_balance_exposure(b, config, out_dir / "churned_balance_exposure.png"),
    }
