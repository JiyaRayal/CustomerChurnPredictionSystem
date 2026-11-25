"""Tiny helpers for writing Markdown reports (no extra dependencies)."""

from __future__ import annotations

import math
from typing import Any, Sequence


def markdown_table(headers: Sequence[str], rows: Sequence[Sequence[Any]]) -> str:
    """Render a Markdown table. Cells are converted with ``str``; pipes are escaped."""
    def cell(value: Any) -> str:
        return str(value).replace("|", "\\|").replace("\n", " ")

    lines = ["| " + " | ".join(cell(h) for h in headers) + " |",
             "|" + "|".join("---" for _ in headers) + "|"]
    lines += ["| " + " | ".join(cell(c) for c in row) + " |" for row in rows]
    return "\n".join(lines)


def _missing(value: Any) -> bool:
    """True for None and for NaN (pandas turns None into NaN inside DataFrames)."""
    return value is None or (isinstance(value, float) and math.isnan(value))


def fmt_int(value: Any) -> str:
    return "n/a" if _missing(value) else f"{int(value):,}"


def fmt_pct(fraction: Any, digits: int = 1) -> str:
    """Format a fraction (0.2037) as a percentage ('20.4%'); None becomes 'n/a'."""
    return "n/a" if _missing(fraction) else f"{fraction * 100:.{digits}f}%"


def fmt_ci(low: Any, high: Any, digits: int = 1) -> str:
    return "n/a" if _missing(low) or _missing(high) else f"{fmt_pct(low, digits)} to {fmt_pct(high, digits)}"
