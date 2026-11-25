"""Load the raw dataset (after verifying it is unchanged) and re-load processed data.

Beginner notes
--------------
* **Checksum.** A SHA-256 hash is a fingerprint of a file: change one character and the
  fingerprint changes completely. We recorded the raw file's fingerprint in
  ``data/raw/SHA256SUMS``; before analysis we recompute it and refuse to continue on mismatch.
* **Read-only.** This module only ever *reads* the raw CSV. It never writes to it.
* **No type coercion.** We read the CSV with pandas' defaults and let ``validation`` report
  any wrong types or missing values, instead of silently converting them here.
* **Processed CSV and categories.** A CSV cannot remember that a column is an ordered
  category (e.g. "Under 30" < "30-45"), so ``load_processed_data`` restores that order
  from the config.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import pandas as pd

from .config import load_config, project_root
from .segmentation import DERIVED_COLUMNS, segment_category_orders


class DataIntegrityError(RuntimeError):
    """Raised when the raw file is missing or does not match its recorded checksum."""


def resolve_path(config: dict[str, Any], key: str, root: Path | None = None) -> Path:
    """Turn a relative path from the config's [paths] section into an absolute path."""
    return (root or project_root()) / config["paths"][key]


def sha256_of_file(path: Path) -> str:
    """SHA-256 fingerprint of a file, read in chunks so large files are fine."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_recorded_checksum(sums_path: Path, filename: str) -> str:
    """Find ``filename``'s recorded hash inside a ``sha256sum``-style file."""
    if not Path(sums_path).is_file():
        raise DataIntegrityError(f"Checksum file not found: {sums_path}")
    for line in Path(sums_path).read_text().splitlines():
        if not line.strip():
            continue
        digest, name = line.split(maxsplit=1)
        if name.strip().lstrip("*") == filename:
            return digest
    raise DataIntegrityError(f"No checksum recorded for {filename} in {sums_path}")


def verify_raw_checksum(config: dict[str, Any] | None = None, root: Path | None = None) -> str:
    """Check the raw CSV against its recorded checksum; return the verified hash."""
    config = config or load_config()
    raw_path = resolve_path(config, "raw_data", root)
    if not raw_path.is_file():
        raise DataIntegrityError(
            f"Raw data file not found: {raw_path}. Place European_Bank.csv in data/raw/ "
            "(see data/README.md)."
        )
    recorded = read_recorded_checksum(resolve_path(config, "raw_checksums", root), raw_path.name)
    actual = sha256_of_file(raw_path)
    if actual != recorded:
        raise DataIntegrityError(
            f"{raw_path.name} does not match its recorded checksum (expected {recorded[:12]}..., "
            f"got {actual[:12]}...). The raw file may have been modified; restore the original."
        )
    return actual


def load_raw_data(config: dict[str, Any] | None = None, root: Path | None = None,
                  verify: bool = True) -> pd.DataFrame:
    """Read the raw CSV into a DataFrame (verifying the checksum first by default)."""
    config = config or load_config()
    if verify:
        verify_raw_checksum(config, root)
    raw_path = resolve_path(config, "raw_data", root)
    if not raw_path.is_file():
        raise DataIntegrityError(f"Raw data file not found: {raw_path}")
    return pd.read_csv(raw_path)


def load_processed_data(path: Path, config: dict[str, Any] | None = None) -> pd.DataFrame:
    """Read the processed CSV and restore the ordered categorical columns."""
    config = config or load_config()
    df = pd.read_csv(path)
    for column, labels in segment_category_orders(config).items():
        if column in df.columns:
            # Only the derived segments have a natural order (Geography/Gender do not).
            df[column] = pd.Categorical(df[column], categories=labels,
                                        ordered=column in DERIVED_COLUMNS)
    return df
