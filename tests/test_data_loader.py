"""Tests for checksum verification and data loading."""

import hashlib
import shutil

import pandas as pd
import pytest

from churn_analytics.data_loader import (DataIntegrityError, load_processed_data, load_raw_data,
                                         read_recorded_checksum, sha256_of_file, verify_raw_checksum)
from churn_analytics.segmentation import add_segments


def _make_root(tmp_path, config, content=b"a,b\n1,2\n", record=True):
    """Create a throwaway project root containing a tiny 'raw' CSV and its checksum file."""
    raw = tmp_path / config["paths"]["raw_data"]
    raw.parent.mkdir(parents=True)
    raw.write_bytes(content)
    if record:
        digest = hashlib.sha256(content).hexdigest()
        (tmp_path / config["paths"]["raw_checksums"]).write_text(f"{digest}  {raw.name}\n")
    return raw


def test_sha256_matches_hashlib(tmp_path):
    f = tmp_path / "x.bin"
    f.write_bytes(b"hello")
    assert sha256_of_file(f) == hashlib.sha256(b"hello").hexdigest()


def test_read_recorded_checksum_handles_binary_marker(tmp_path):
    sums = tmp_path / "SHA256SUMS"
    sums.write_text("abc123 *file.csv\n")
    assert read_recorded_checksum(sums, "file.csv") == "abc123"


def test_missing_checksum_record_raises(tmp_path):
    sums = tmp_path / "SHA256SUMS"
    sums.write_text("abc123  other.csv\n")
    with pytest.raises(DataIntegrityError, match="No checksum recorded"):
        read_recorded_checksum(sums, "file.csv")


def test_verify_passes_for_unchanged_file(tmp_path, config):
    _make_root(tmp_path, config)
    assert len(verify_raw_checksum(config, tmp_path)) == 64


def test_verify_detects_a_modified_file(tmp_path, config):
    raw = _make_root(tmp_path, config)
    raw.write_bytes(b"a,b\n1,3\n")  # one character changed
    with pytest.raises(DataIntegrityError, match="does not match"):
        verify_raw_checksum(config, tmp_path)


def test_verify_reports_missing_raw_file(tmp_path, config):
    with pytest.raises(DataIntegrityError, match="not found"):
        verify_raw_checksum(config, tmp_path)


def test_verify_reports_missing_checksum_file(tmp_path, config):
    _make_root(tmp_path, config, record=False)
    with pytest.raises(DataIntegrityError, match="Checksum file not found"):
        verify_raw_checksum(config, tmp_path)


def test_load_raw_data_refuses_modified_file(tmp_path, config):
    raw = _make_root(tmp_path, config)
    raw.write_bytes(b"tampered")
    with pytest.raises(DataIntegrityError):
        load_raw_data(config, tmp_path)


def test_load_real_raw_data_has_expected_structure(config, raw_path):
    df = load_raw_data(config)
    assert df.shape == (10000, 14)
    assert list(df.columns) == config["schema"]["expected_columns"]


def test_loading_never_modifies_the_raw_file(config, raw_path):
    before = sha256_of_file(raw_path)
    load_raw_data(config)
    assert sha256_of_file(raw_path) == before


def test_processed_round_trip_restores_ordered_categories(tmp_path, config, valid_df):
    segmented, _ = add_segments(valid_df.drop(columns=["Surname"]), config)
    path = tmp_path / "p.csv"
    segmented.to_csv(path, index=False)
    loaded = load_processed_data(path, config)
    assert list(loaded["AgeBand"].cat.categories) == ["Under 30", "30-45", "46-60", "61+"]
    assert loaded["AgeBand"].cat.ordered
    assert not loaded["Geography"].cat.ordered
    assert list(loaded["BalanceSegment"].cat.categories) == ["Zero-balance", "Low-balance", "High-balance"]
