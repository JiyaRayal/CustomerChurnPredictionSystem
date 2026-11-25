"""Load and validate the project configuration (config/segmentation.toml).

Why this module exists
----------------------
All thresholds live in one TOML file. If someone edits that file and makes a
mistake (labels that do not match the bounds, bounds out of order, a confidence
level of 95 instead of 0.95), we want the project to stop immediately with a
clear message, not quietly produce wrong segments.

Only the Python standard library is used here (``tomllib``, Python 3.11+).
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

# Keys of the binned segmentations described by `lower_bounds` + `labels`.
BINNED_SEGMENTS = ("age", "credit_score", "tenure")
ALLOWED_CI_METHODS = ("wilson",)


class ConfigError(ValueError):
    """Raised when the configuration file is missing or invalid."""


def project_root() -> Path:
    """Return the repository root (two levels above this file's package)."""
    return Path(__file__).resolve().parents[2]


DEFAULT_CONFIG_PATH = project_root() / "config" / "segmentation.toml"


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    """Read the TOML config, validate it, and return it as a dictionary."""
    config_path = Path(path) if path is not None else DEFAULT_CONFIG_PATH
    if not config_path.is_file():
        raise ConfigError(f"Config file not found: {config_path}")
    with config_path.open("rb") as handle:
        config = tomllib.load(handle)
    validate_config(config)
    return config


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _check_binned(name: str, section: Any, problems: list[str]) -> None:
    """Validate one `lower_bounds` / `labels` segmentation block."""
    where = f"segmentation.{name}"
    if not isinstance(section, dict):
        problems.append(f"{where}: section is missing")
        return

    bounds = section.get("lower_bounds")
    labels = section.get("labels")

    if not isinstance(bounds, list) or not bounds or not all(_is_number(b) for b in bounds):
        problems.append(f"{where}.lower_bounds must be a non-empty list of numbers")
        return
    if any(later <= earlier for earlier, later in zip(bounds, bounds[1:])):
        problems.append(f"{where}.lower_bounds must be strictly increasing (got {bounds})")

    if not isinstance(labels, list) or not all(isinstance(x, str) and x.strip() for x in labels):
        problems.append(f"{where}.labels must be a list of non-blank strings")
        return
    if len(labels) != len(bounds) + 1:
        problems.append(
            f"{where}: needs {len(bounds) + 1} labels for {len(bounds)} bounds, got {len(labels)}"
        )
    if len(set(labels)) != len(labels):
        problems.append(f"{where}.labels must be unique (got {labels})")


def _str_list(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(x, str) and x.strip() for x in value)


def _check_schema_and_columns(config: dict[str, Any], problems: list[str]) -> None:
    """Validate [schema], [columns] cross-references and [validation] bounds."""
    schema, columns, validation = config["schema"], config["columns"], config["validation"]

    groups = {k: schema.get(k) for k in
              ("expected_columns", "integer_columns", "float_columns", "string_columns")}
    for key, value in groups.items():
        if not _str_list(value) or not value:
            problems.append(f"schema.{key} must be a non-empty list of column names")
    if problems:
        return

    expected = groups["expected_columns"]
    if len(set(expected)) != len(expected):
        problems.append("schema.expected_columns contains duplicates")
    typed = groups["integer_columns"] + groups["float_columns"] + groups["string_columns"]
    if len(set(typed)) != len(typed):
        problems.append("a column is listed under more than one dtype group in [schema]")
    if set(typed) != set(expected):
        problems.append(
            "integer/float/string columns must together cover exactly expected_columns "
            f"(difference: {sorted(set(typed) ^ set(expected))})"
        )

    for key in ("target", "identifier"):
        if columns.get(key) not in expected:
            problems.append(f"columns.{key} must be one of schema.expected_columns")
    for key in ("excluded_from_features", "remove_from_processed", "binary_columns"):
        value = columns.get(key)
        if not _str_list(value):
            problems.append(f"columns.{key} must be a list of column names")
        elif not set(value) <= set(expected):
            problems.append(f"columns.{key} names unknown columns: {sorted(set(value) - set(expected))}")
    if _str_list(columns.get("binary_columns")) and not set(columns["binary_columns"]) <= set(
        groups["integer_columns"]
    ):
        problems.append("columns.binary_columns must be integer columns")
    if _str_list(columns.get("remove_from_processed")):
        protected = {columns.get("target"), columns.get("identifier")}
        if protected & set(columns["remove_from_processed"]):
            problems.append("columns.remove_from_processed must not contain the target or identifier")

    categories = columns.get("categorical_expected", {})
    for name, allowed in categories.items():
        if name not in groups["string_columns"]:
            problems.append(f"columns.categorical_expected.{name} must be a string column")
        if not _str_list(allowed) or not allowed:
            problems.append(f"columns.categorical_expected.{name} needs a non-empty list of values")

    numeric_keys = ("age_min", "age_max", "credit_score_min", "credit_score_max", "tenure_min",
                    "balance_min", "estimated_salary_min_exclusive", "num_products_min")
    for key in numeric_keys:
        if not _is_number(validation.get(key)):
            problems.append(f"validation.{key} must be a number")
    if all(_is_number(validation.get(k)) for k in ("age_min", "age_max")) and \
            validation["age_min"] >= validation["age_max"]:
        problems.append("validation.age_min must be below age_max")
    if all(_is_number(validation.get(k)) for k in ("credit_score_min", "credit_score_max")) and \
            validation["credit_score_min"] >= validation["credit_score_max"]:
        problems.append("validation.credit_score_min must be below credit_score_max")
    size_cols = validation.get("small_group_check_columns", [])
    if not _str_list(size_cols) or not set(size_cols) <= set(expected):
        problems.append("validation.small_group_check_columns must list known columns")


def _check_kpi(config: dict[str, Any], problems: list[str]) -> None:
    """The [kpi] section must name real columns (or the derived balance segment column)."""
    kpi = config["kpi"]
    expected = set(config["schema"]["expected_columns"])
    for key in ("geography_column", "engagement_column", "balance_column"):
        if kpi.get(key) not in expected:
            problems.append(f"kpi.{key} must be one of schema.expected_columns (got {kpi.get(key)!r})")
    segment_col = kpi.get("balance_segment_column")
    if not isinstance(segment_col, str) or not segment_col.strip():
        problems.append("kpi.balance_segment_column must be a non-blank column name")
    if kpi.get("engagement_column") not in config["columns"].get("binary_columns", []):
        problems.append("kpi.engagement_column must be a binary (0/1) column")


def _check_analysis(config: dict[str, Any], problems: list[str]) -> None:
    """Validate the [analysis] section (variable names are checked against the data at run time)."""
    analysis = config["analysis"]
    variables = analysis.get("segment_variables")
    if not _str_list(variables) or not variables:
        problems.append("analysis.segment_variables must be a non-empty list of column names")
    elif len(set(variables)) != len(variables):
        problems.append("analysis.segment_variables contains duplicates")
    for key in ("sensitivity_variable", "gender_column", "interaction_row", "interaction_col"):
        if not isinstance(analysis.get(key), str) or not analysis[key].strip():
            problems.append(f"analysis.{key} must be a non-blank column name")
    if analysis.get("interaction_row") == analysis.get("interaction_col"):
        problems.append("analysis.interaction_row and interaction_col must differ")
    if not _str_list(analysis.get("numeric_profile_columns")) or not analysis.get("numeric_profile_columns"):
        problems.append("analysis.numeric_profile_columns must be a non-empty list of column names")
    top = analysis.get("top_contribution_gaps")
    if not isinstance(top, int) or isinstance(top, bool) or top < 1:
        problems.append("analysis.top_contribution_gaps must be a positive integer")

    cutoffs, labels = analysis.get("effect_size_cutoffs"), analysis.get("effect_size_labels")
    if not isinstance(cutoffs, list) or not cutoffs or not all(_is_number(c) for c in cutoffs):
        problems.append("analysis.effect_size_cutoffs must be a non-empty list of numbers")
    else:
        if any(b <= a for a, b in zip(cutoffs, cutoffs[1:])) or cutoffs[0] <= 0 or cutoffs[-1] >= 1:
            problems.append("analysis.effect_size_cutoffs must be strictly increasing and between 0 and 1")
        if not _str_list(labels) or len(labels) != len(cutoffs) + 1:
            problems.append("analysis.effect_size_labels needs one more label than effect_size_cutoffs")

    smd = analysis.get("smd_cutoffs")
    if not isinstance(smd, list) or not smd or not all(_is_number(c) for c in smd) or \
            any(b <= a for a, b in zip(smd, smd[1:])) or smd[0] <= 0:
        problems.append("analysis.smd_cutoffs must be strictly increasing positive numbers")
    elif isinstance(cutoffs, list) and len(smd) != len(cutoffs):
        problems.append("analysis.smd_cutoffs must have the same length as effect_size_cutoffs")

    for column, mapping in analysis.get("display_labels", {}).items():
        if not isinstance(mapping, dict) or not all(isinstance(k, str) and isinstance(v, str) and v.strip()
                                                    for k, v in mapping.items()):
            problems.append(f"analysis.display_labels.{column} must map text keys to non-blank labels")


def _check_balance_engagement(config: dict[str, Any], problems: list[str]) -> None:
    """Validate the [balance_engagement] section (variable names are checked against the data at run time)."""
    be = config["balance_engagement"]
    for key in ("within_high_balance_variables", "stratify_high_vs_low_by", "engagement_segment_variables",
                "exposure_variables"):
        if not _str_list(be.get(key)) or not be.get(key):
            problems.append(f"balance_engagement.{key} must be a non-empty list of column names")
    sets = be.get("standardise_high_vs_low_by")
    if not isinstance(sets, list) or not sets or not all(_str_list(group) and group for group in sets):
        problems.append("balance_engagement.standardise_high_vs_low_by must be a non-empty list of non-empty lists of column names")
    for key in ("salary_column", "tenure_column"):
        if not isinstance(be.get(key), str) or not be[key].strip():
            problems.append(f"balance_engagement.{key} must be a non-blank column name")
    for key in ("balance_quantile_groups", "salary_groups"):
        value = be.get(key)
        if not isinstance(value, int) or isinstance(value, bool) or value < 2:
            problems.append(f"balance_engagement.{key} must be an integer of at least 2")
    labels = be.get("salary_labels")
    if not _str_list(labels) or (isinstance(be.get("salary_groups"), int) and len(labels) != be["salary_groups"]):
        problems.append("balance_engagement.salary_labels must have one non-blank label per salary group")
    elif len(set(labels)) != len(labels):
        problems.append("balance_engagement.salary_labels must be unique")
    shares = be.get("concentration_top_shares")
    if not isinstance(shares, list) or not shares or not all(_is_number(x) and 0 < x < 1 for x in shares):
        problems.append("balance_engagement.concentration_top_shares must be numbers strictly between 0 and 1")


def validate_config(config: dict[str, Any]) -> None:
    """Check the config for internal consistency; raise ConfigError listing ALL problems."""
    problems: list[str] = []

    # --- required top-level sections -------------------------------------------------
    for section in ("columns", "schema", "validation", "segmentation", "statistics", "paths", "kpi", "analysis", "balance_engagement"):
        if section not in config:
            problems.append(f"missing required section [{section}]")
    if problems:  # cannot validate further without the sections
        raise ConfigError("Invalid configuration:\n- " + "\n- ".join(problems))

    _check_schema_and_columns(config, problems)
    if not problems:
        _check_kpi(config, problems)
        _check_analysis(config, problems)
        _check_balance_engagement(config, problems)

    # --- columns ---------------------------------------------------------------------
    columns = config["columns"]
    for key in ("target", "identifier", "excluded_from_features"):
        if key not in columns:
            problems.append(f"columns.{key} is missing")
    if columns.get("target") in columns.get("excluded_from_features", []):
        problems.append("columns.target must not be listed in excluded_from_features")

    # --- binned segmentations (age, credit score, tenure) -----------------------------
    segmentation = config["segmentation"]
    for name in BINNED_SEGMENTS:
        _check_binned(name, segmentation.get(name), problems)

    # --- balance segmentation ---------------------------------------------------------
    balance = segmentation.get("balance")
    if not isinstance(balance, dict):
        problems.append("segmentation.balance: section is missing")
    else:
        if balance.get("method") != "median_of_nonzero":
            problems.append("segmentation.balance.method must be 'median_of_nonzero'")
        names = [balance.get(k) for k in ("zero_label", "low_label", "high_label")]
        if not all(isinstance(x, str) and x.strip() for x in names):
            problems.append("segmentation.balance needs non-blank zero_label, low_label, high_label")
        elif len(set(names)) != 3:
            problems.append("segmentation.balance labels must be unique")

    # --- optional credit-score sensitivity check -------------------------------------
    sens = config.get("sensitivity", {}).get("credit_score")
    if sens is not None:
        n_groups = sens.get("n_groups")
        labels = sens.get("labels")
        if sens.get("method") != "quantile":
            problems.append("sensitivity.credit_score.method must be 'quantile'")
        if not isinstance(n_groups, int) or isinstance(n_groups, bool) or n_groups < 2:
            problems.append("sensitivity.credit_score.n_groups must be an integer >= 2")
        elif not isinstance(labels, list) or len(labels) != n_groups:
            problems.append("sensitivity.credit_score.labels must have n_groups entries")

    # --- statistics -------------------------------------------------------------------
    stats = config["statistics"]
    level = stats.get("confidence_level")
    if not _is_number(level) or not 0 < level < 1:
        problems.append("statistics.confidence_level must be between 0 and 1 (e.g. 0.95, not 95)")
    if stats.get("ci_method") not in ALLOWED_CI_METHODS:
        problems.append(f"statistics.ci_method must be one of {ALLOWED_CI_METHODS}")
    small = stats.get("small_group_threshold")
    minimum = stats.get("min_reportable_group_size")
    if not all(isinstance(v, int) and not isinstance(v, bool) and v >= 1 for v in (small, minimum)):
        problems.append("statistics group-size thresholds must be positive integers")
    elif minimum > small:
        problems.append(
            "statistics.min_reportable_group_size must not exceed small_group_threshold"
        )

    if problems:
        raise ConfigError("Invalid configuration:\n- " + "\n- ".join(problems))
