"""Small statistical helpers shared by the whole project.

Beginner notes
--------------
* A **proportion** (e.g. a churn rate) from a sample is uncertain. A **confidence
  interval** gives a plausible range for the underlying rate. We use the *Wilson*
  interval, which behaves sensibly for small groups and for rates close to 0% or 100%.
* ``proportion_summary`` applies the project's group-size rules from the config:
  an EMPTY group has an undefined rate (never 0%), and a group below the minimum
  reportable size has its rate withheld, but its counts are still shown.
"""

from __future__ import annotations

import math
from typing import Any

import pandas as pd
from scipy import stats

# Status labels returned by proportion_summary
STATUS_OK = "ok"
STATUS_SMALL = "small sample"
STATUS_WITHHELD = "withheld (too small)"
STATUS_EMPTY = "n/a (empty group)"


def wilson_interval(events: int, n: int, confidence_level: float = 0.95) -> tuple[float, float]:
    """Wilson score interval for a proportion ``events / n`` (returned as fractions)."""
    if n <= 0:
        raise ValueError("n must be positive; an empty group has no interval")
    if not 0 <= events <= n:
        raise ValueError(f"events must be between 0 and n (got events={events}, n={n})")
    if not 0 < confidence_level < 1:
        raise ValueError("confidence_level must be between 0 and 1")

    z = stats.norm.ppf(1 - (1 - confidence_level) / 2)
    p = events / n
    denominator = 1 + z**2 / n
    centre = (p + z**2 / (2 * n)) / denominator
    half_width = z * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / denominator
    return max(0.0, centre - half_width), min(1.0, centre + half_width)


def newcombe_difference_interval(events1: int, n1: int, events2: int, n2: int,
                                 confidence_level: float = 0.95) -> tuple[float, float, float]:
    """Interval for the DIFFERENCE between two independent proportions (group 1 minus group 2).

    Uses Newcombe's hybrid score method (Newcombe 1998, "Method 10"): it combines the
    Wilson intervals of the two groups, so it stays sensible for small groups and for
    rates near 0% or 100% (where the simple textbook formula can fail).
    Returns (difference, lower, upper) as fractions. Checked against a published example in
    tests (56/70 vs 48/80 gives 0.2000, 0.0524 to 0.3339).
    """
    low1, high1 = wilson_interval(events1, n1, confidence_level)
    low2, high2 = wilson_interval(events2, n2, confidence_level)
    p1, p2 = events1 / n1, events2 / n2
    difference = p1 - p2
    lower = difference - math.sqrt((p1 - low1) ** 2 + (high2 - p2) ** 2)
    upper = difference + math.sqrt((high1 - p1) ** 2 + (p2 - low2) ** 2)
    return difference, lower, upper


def proportion_summary(events: int, n: int, config: dict[str, Any]) -> dict[str, Any]:
    """Summarise ``events`` out of ``n`` using the config's confidence and size rules.

    Returns a dict with: n, events, rate, ci_low, ci_high, status.
    ``rate``/``ci_*`` are None when the group is empty or below the minimum reportable size.
    """
    settings = config["statistics"]
    summary: dict[str, Any] = {"n": int(n), "events": int(events), "rate": None,
                               "ci_low": None, "ci_high": None}
    if n == 0:
        summary["status"] = STATUS_EMPTY
        return summary
    if n < settings["min_reportable_group_size"]:
        summary["status"] = STATUS_WITHHELD
        return summary

    low, high = wilson_interval(events, n, settings["confidence_level"])
    summary.update(rate=events / n, ci_low=low, ci_high=high)
    summary["status"] = STATUS_SMALL if n < settings["small_group_threshold"] else STATUS_OK
    return summary


def chi_square_independence(table: pd.DataFrame) -> dict[str, Any]:
    """Chi-square test of independence on a counts table, plus Cramer's V.

    The test asks: "if the two variables were unrelated, how surprising is this table?"
    A small p-value means the variables ARE associated in this data. With thousands of
    rows even tiny associations give small p-values, so always read **Cramer's V** (an
    effect size from 0 = no association to 1 = perfect association) alongside it.
    This says nothing about cause.
    """
    counts = table.to_numpy(dtype=float)
    if counts.ndim != 2 or min(counts.shape) < 2:
        raise ValueError("table must have at least 2 rows and 2 columns")
    n = counts.sum()
    if n == 0:
        raise ValueError("table is empty")

    chi2, p_value, dof, expected = stats.chi2_contingency(counts, correction=False)
    cramers_v = math.sqrt(chi2 / (n * (min(counts.shape) - 1)))
    return {"chi2": float(chi2), "dof": int(dof), "p_value": float(p_value),
            "cramers_v": float(cramers_v), "n": int(n),
            "min_expected_count": float(expected.min())}
