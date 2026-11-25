"""Guard: the raw dataset must match the checksum recorded when it was first copied."""

import hashlib

import pytest

from churn_analytics.config import load_config, project_root


def test_raw_csv_matches_recorded_sha256():
    cfg = load_config()
    root = project_root()
    csv_path = root / cfg["paths"]["raw_data"]
    sums_path = root / cfg["paths"]["raw_checksums"]

    if not csv_path.is_file():
        pytest.skip("Raw CSV not present (it is git-ignored by default; see data/README.md).")

    recorded = {}
    for line in sums_path.read_text().splitlines():
        digest, name = line.split(maxsplit=1)
        recorded[name.strip().lstrip("*")] = digest

    actual = hashlib.sha256(csv_path.read_bytes()).hexdigest()
    assert actual == recorded[csv_path.name], "Raw dataset has been modified!"
