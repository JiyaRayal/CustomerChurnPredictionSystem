"""Shared test fixtures."""

import numpy as np
import pandas as pd
import pytest

from churn_analytics.config import load_config, project_root


@pytest.fixture(scope="session")
def config():
    """The real project config. Tests must deep-copy it before changing anything."""
    return load_config()


@pytest.fixture()
def valid_df(config):
    """A small, perfectly valid synthetic dataset (60 customers) with the real schema."""
    rng = np.random.default_rng(0)
    n = 60
    df = pd.DataFrame({
        "Year": 2025,
        "CustomerId": np.arange(15600000, 15600000 + n),
        "Surname": [f"Name{i}" for i in range(n)],
        "CreditScore": rng.integers(350, 851, n),
        "Geography": ["France", "Germany", "Spain"] * 20,
        "Gender": ["Female", "Male"] * 30,
        "Age": rng.integers(18, 80, n),
        "Tenure": rng.integers(0, 11, n),
        "Balance": rng.uniform(1000, 200000, n).round(2),
        "NumOfProducts": rng.integers(1, 4, n),
        "HasCrCard": rng.integers(0, 2, n),
        "IsActiveMember": rng.integers(0, 2, n),
        "EstimatedSalary": rng.uniform(1000, 200000, n).round(2),
        "Exited": [0, 1] * 30,
    })
    df.loc[df.index[::4], "Balance"] = 0.0
    assert list(df.columns) == config["schema"]["expected_columns"]
    return df


@pytest.fixture(scope="session")
def raw_path(config):
    path = project_root() / config["paths"]["raw_data"]
    if not path.is_file():
        pytest.skip("Raw CSV not present (git-ignored by default; see data/README.md)")
    return path


@pytest.fixture(scope="session")
def raw_df(raw_path):
    """The real raw dataset, read directly (independent of project loaders)."""
    return pd.read_csv(raw_path)
