from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Literal

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from .diagnostics import balance_diagnostics, effective_sample_size

WeightEstimand = Literal["overlap", "att", "ate"]
MissingStrategy = Literal["drop", "simple"]


@dataclass
class WeightingResult:
    weighted_df: pd.DataFrame
    propensity_score: pd.Series
    weights: pd.Series
    balance_before: pd.DataFrame
    balance_after: pd.DataFrame
    ess_by_arm: dict[Any, float]
    weight_summary: pd.DataFrame
    covariates: list[str]
    estimand: WeightEstimand
    missing: MissingStrategy
    rows_dropped_missing: int
    model: Pipeline


def _propensity_pipeline(data: pd.DataFrame, covariates: list[str], missing: MissingStrategy, seed: int) -> Pipeline:
    numeric = [column for column in covariates if pd.api.types.is_numeric_dtype(data[column])]
    categorical = [column for column in covariates if column not in numeric]
    numeric_steps = []
    categorical_steps = []
    if missing == "simple":
        numeric_steps.append(("impute", SimpleImputer(strategy="median")))
        categorical_steps.append(("impute", SimpleImputer(strategy="most_frequent")))
    numeric_steps.append(("scale", StandardScaler()))
    categorical_steps.append(("encode", OneHotEncoder(handle_unknown="ignore")))
    transformers = []
    if numeric:
        transformers.append(("numeric", Pipeline(numeric_steps), numeric))
    if categorical:
        transformers.append(("categorical", Pipeline(categorical_steps), categorical))
    return Pipeline(
        [
            ("preprocess", ColumnTransformer(transformers)),
            ("model", LogisticRegression(max_iter=2000, solver="lbfgs", random_state=seed)),
        ]
    )


def estimate_propensity_weights(
    df: pd.DataFrame,
    *,
    treatment: str,
    treated: Any,
    covariates: Iterable[str],
    estimand: WeightEstimand = "overlap",
    missing: MissingStrategy = "drop",
    trim_common_support: bool = True,
    weight_col: str = "analysis_weight",
    propensity_col: str = "propensity_score",
    seed: int = 42,
) -> WeightingResult:
    """Estimate overlap, ATT, or ATE propensity-score weights.

    Complete-case estimation is the default. Simple single imputation is only
    performed when explicitly requested; multiply imputed datasets should be
    passed and analyzed separately.
    """

    covariates = list(covariates)
    if treatment not in df.columns:
        raise ValueError(f"treatment column {treatment!r} not found")
    missing_columns = [column for column in covariates if column not in df.columns]
    if missing_columns:
        raise ValueError(f"covariates not found: {missing_columns}")
    if not covariates:
        raise ValueError("at least one covariate is required")
    if estimand not in {"overlap", "att", "ate"}:
        raise ValueError("estimand must be 'overlap', 'att', or 'ate'")
    if missing not in {"drop", "simple"}:
        raise ValueError("missing must be 'drop' or 'simple'")

    data = df[df[treatment].notna()].copy()
    original_rows = len(data)
    if missing == "drop":
        data = data.dropna(subset=covariates).copy()
    rows_dropped_missing = original_rows - len(data)
    data["_treated"] = (data[treatment] == treated).astype(int)
    if data["_treated"].nunique() != 2:
        raise ValueError("both treatment arms are required after missing-data handling")

    model = _propensity_pipeline(data, covariates, missing, seed)
    model.fit(data[covariates], data["_treated"])
    propensity = pd.Series(model.predict_proba(data[covariates])[:, 1], index=data.index, name=propensity_col)
    propensity = propensity.clip(1e-6, 1 - 1e-6)
    data[propensity_col] = propensity

    if trim_common_support:
        treated_mask = data["_treated"] == 1
        low = max(propensity[treated_mask].min(), propensity[~treated_mask].min())
        high = min(propensity[treated_mask].max(), propensity[~treated_mask].max())
        data = data[(data[propensity_col] >= low) & (data[propensity_col] <= high)].copy()
        propensity = data[propensity_col]

    t = data["_treated"].to_numpy(dtype=float)
    ps = propensity.to_numpy(dtype=float)
    if estimand == "overlap":
        values = np.where(t == 1, 1 - ps, ps)
    elif estimand == "att":
        values = np.where(t == 1, 1.0, ps / (1 - ps))
    else:
        values = np.where(t == 1, 1 / ps, 1 / (1 - ps))
    data[weight_col] = values

    before = balance_diagnostics(data, treatment=treatment, treated=treated, covariates=covariates)
    after = balance_diagnostics(
        data,
        treatment=treatment,
        treated=treated,
        covariates=covariates,
        weights=weight_col,
    )
    ess_by_arm = {
        arm: effective_sample_size(group[weight_col])
        for arm, group in data.groupby(treatment, dropna=False)
    }
    weight_summary = (
        data.groupby(treatment)[weight_col]
        .agg(n="size", minimum="min", median="median", mean="mean", maximum="max", total="sum")
        .reset_index()
    )
    return WeightingResult(
        weighted_df=data.drop(columns=["_treated"]),
        propensity_score=data[propensity_col].copy(),
        weights=data[weight_col].copy(),
        balance_before=before,
        balance_after=after,
        ess_by_arm=ess_by_arm,
        weight_summary=weight_summary,
        covariates=covariates,
        estimand=estimand,
        missing=missing,
        rows_dropped_missing=rows_dropped_missing,
        model=model,
    )
