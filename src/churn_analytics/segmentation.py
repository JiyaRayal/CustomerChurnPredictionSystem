"""Create derived segment columns from the thresholds in config/segmentation.toml.

Beginner notes
--------------
* **Left-closed bins.** A bin includes its lower bound and excludes the next bound.
  With age bounds [30, 46, 61]: 29 -> "Under 30", 30 -> "30-45", 45 -> "30-45", 46 -> "46-60".
  Because each bin starts exactly where the previous one ends, a value can never fall in
  two bins or in none.
* **The first and last bins are open-ended** (they extend to minus/plus infinity), so every
  finite number gets a label. Whether a value is *plausible* (e.g. age 5) is the job of
  validation, not segmentation: such records are flagged there and kept here.
* **Loud failure.** If a value cannot be segmented (missing, or a negative balance, which the
  documented balance rule does not cover), we raise an error and explain, instead of
  quietly producing a missing or wrong label.
* **The balance cut-off is computed from the data**, not typed in: the median of the
  NON-ZERO balances. Customers with a zero balance are their own segment so they do not
  distort the Low/High split.
"""

from __future__ import annotations

from typing import Any, Sequence

import numpy as np
import pandas as pd

# Names of the derived columns added to the dataset.
AGE_BAND = "AgeBand"
CREDIT_BAND = "CreditScoreBand"
CREDIT_TERCILE = "CreditScoreTercile"
TENURE_GROUP = "TenureGroup"
BALANCE_SEGMENT = "BalanceSegment"
DERIVED_COLUMNS = (AGE_BAND, CREDIT_BAND, TENURE_GROUP, BALANCE_SEGMENT, CREDIT_TERCILE)


class SegmentationError(ValueError):
    """Raised when values cannot be segmented under the documented rules."""


def _require_complete(values: pd.Series, name: str) -> None:
    if values.isna().any():
        raise SegmentationError(
            f"{name}: {int(values.isna().sum())} missing value(s); fix or review them before segmenting"
        )


def assign_binned_segment(values: pd.Series, lower_bounds: Sequence[float],
                          labels: Sequence[str]) -> pd.Series:
    """Label each value using left-closed bins (see module docstring)."""
    _require_complete(values, str(values.name))
    edges = [-np.inf, *lower_bounds, np.inf]
    result = pd.cut(values, bins=edges, right=False, labels=list(labels), ordered=True)
    if result.isna().any():  # cannot happen for finite numbers; guards against surprises
        raise SegmentationError(f"{values.name}: some values received no segment")
    return result


def _require_valid_balance(balance: pd.Series) -> None:
    _require_complete(balance, "Balance")
    if (balance < 0).any():
        raise SegmentationError(
            f"Balance: {int((balance < 0).sum())} negative value(s). The documented rule only "
            "covers zero and positive balances; review these records before segmenting."
        )


def compute_balance_threshold(balance: pd.Series) -> float:
    """Median of the NON-ZERO balances (the cut between Low-balance and High-balance)."""
    _require_valid_balance(balance)
    non_zero = balance[balance > 0]
    if non_zero.empty:
        raise SegmentationError("Balance: there are no non-zero balances to take a median of")
    return float(non_zero.median())


def assign_balance_segment(balance: pd.Series, threshold: float, zero_label: str,
                           low_label: str, high_label: str) -> pd.Series:
    """Zero-balance if == 0; Low-balance if 0 < b <= threshold; High-balance if b > threshold."""
    _require_valid_balance(balance)
    labels = np.select([balance == 0, balance <= threshold], [zero_label, low_label],
                       default=high_label)
    return pd.Series(pd.Categorical(labels, categories=[zero_label, low_label, high_label],
                                    ordered=True), index=balance.index, name=BALANCE_SEGMENT)


def compute_quantile_cutpoints(values: pd.Series, n_groups: int) -> list[float]:
    """Cut points that split ``values`` into ``n_groups`` roughly equal-sized groups."""
    _require_complete(values, str(values.name))
    cuts = [float(c) for c in np.quantile(values, [k / n_groups for k in range(1, n_groups)])]
    if any(b <= a for a, b in zip(cuts, cuts[1:])):
        raise SegmentationError(f"{values.name}: quantile cut points are not distinct: {cuts}")
    return cuts


def assign_quantile_segment(values: pd.Series, cutpoints: Sequence[float],
                            labels: Sequence[str]) -> pd.Series:
    """Label values using right-closed bins: first group is <= first cut point, and so on."""
    _require_complete(values, str(values.name))
    edges = [-np.inf, *cutpoints, np.inf]
    return pd.cut(values, bins=edges, right=True, labels=list(labels), ordered=True)


def segment_category_orders(config: dict[str, Any]) -> dict[str, list[str]]:
    """Label order of every categorical column (used when saving and re-loading data)."""
    seg, sens = config["segmentation"], config["sensitivity"]["credit_score"]
    bal = seg["balance"]
    orders = {
        AGE_BAND: list(seg["age"]["labels"]),
        CREDIT_BAND: list(seg["credit_score"]["labels"]),
        TENURE_GROUP: list(seg["tenure"]["labels"]),
        BALANCE_SEGMENT: [bal["zero_label"], bal["low_label"], bal["high_label"]],
        CREDIT_TERCILE: list(sens["labels"]),
    }
    for name, allowed in config["columns"]["categorical_expected"].items():
        orders[name] = list(allowed)
    return orders


def add_segments(df: pd.DataFrame, config: dict[str, Any]) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Return a COPY of ``df`` with the derived segment columns, plus metadata.

    Metadata records what was actually used (the computed balance threshold, tercile cut
    points, the configured bins) and the size of every segment, so results are traceable.
    """
    seg = config["segmentation"]
    out = df.copy()

    out[AGE_BAND] = assign_binned_segment(out["Age"], seg["age"]["lower_bounds"], seg["age"]["labels"])
    out[CREDIT_BAND] = assign_binned_segment(out["CreditScore"], seg["credit_score"]["lower_bounds"],
                                             seg["credit_score"]["labels"])
    out[TENURE_GROUP] = assign_binned_segment(out["Tenure"], seg["tenure"]["lower_bounds"],
                                              seg["tenure"]["labels"])

    threshold = compute_balance_threshold(out["Balance"])
    bal = seg["balance"]
    out[BALANCE_SEGMENT] = assign_balance_segment(out["Balance"], threshold, bal["zero_label"],
                                                  bal["low_label"], bal["high_label"])

    sens = config["sensitivity"]["credit_score"]
    cuts = compute_quantile_cutpoints(out["CreditScore"], sens["n_groups"])
    out[CREDIT_TERCILE] = assign_quantile_segment(out["CreditScore"], cuts, sens["labels"])

    small = config["statistics"]["small_group_threshold"]
    sizes = []
    for column in DERIVED_COLUMNS:
        counts = out[column].value_counts().reindex(out[column].cat.categories, fill_value=0)
        for label, n in counts.items():
            sizes.append({"segment_variable": column, "segment": str(label), "n": int(n),
                          "share": float(n / len(out)) if len(out) else None,
                          "small_sample": bool(n < small)})

    metadata = {
        "balance_threshold_median_of_nonzero": threshold,
        "balance_nonzero_count": int((out["Balance"] > 0).sum()),
        "credit_score_tercile_cutpoints": cuts,
        "thresholds_used": {k: seg[k] for k in ("age", "credit_score", "tenure", "balance")},
        "segment_sizes": sizes,
    }
    return out, metadata
