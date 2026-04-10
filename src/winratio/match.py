from __future__ import annotations

from dataclasses import dataclass
from typing import List, Literal, Optional

import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.neighbors import NearestNeighbors
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


@dataclass
class MatchResult:
    matched_df: pd.DataFrame
    pairs: int
    dropped_rows: int
    ps: pd.Series
    balance_before: pd.DataFrame
    balance_after: pd.DataFrame
    full_df: Optional[pd.DataFrame] = None
    covariates: Optional[List[str]] = None
    exact_cols: Optional[List[str]] = None
    caliper: Optional[float] = None
    method: str = "nearest"
    treat_col: Optional[str] = None
    treated_value: Optional[object] = None


def _standardized_mean_diff(x_t: np.ndarray, x_c: np.ndarray) -> float:
    mean_t = np.nanmean(x_t)
    mean_c = np.nanmean(x_c)
    ddof_t = 1 if x_t.size > 1 else 0
    ddof_c = 1 if x_c.size > 1 else 0
    var_t = np.nanvar(x_t, ddof=ddof_t)
    var_c = np.nanvar(x_c, ddof=ddof_c)
    pooled = np.sqrt((var_t + var_c) / 2.0 + 1e-12)
    return float((mean_t - mean_c) / pooled)


def _balance_table(design_matrix: pd.DataFrame, treat_col: str, columns: List[str]) -> pd.DataFrame:
    treated_mask = design_matrix[treat_col] == 1
    rows = []
    for column in columns:
        x_t = design_matrix.loc[treated_mask, column].to_numpy(dtype=float)
        x_c = design_matrix.loc[~treated_mask, column].to_numpy(dtype=float)
        rows.append(
            {
                "variable": column,
                "SMD": _standardized_mean_diff(x_t, x_c),
                "mean_t": float(np.nanmean(x_t)),
                "mean_c": float(np.nanmean(x_c)),
            }
        )
    return pd.DataFrame(rows)


def _default_covariates(df: pd.DataFrame, treat_col: str, exact_cols: Optional[List[str]]) -> List[str]:
    excluded = {treat_col, "_T", "_PS", "_LPS", "PAIR_ID"}
    if exact_cols:
        excluded.update(exact_cols)
    covariates = [column for column in df.columns if column not in excluded]
    return [column for column in covariates if df[column].nunique(dropna=True) > 1]


def propensity_match(
    df: pd.DataFrame,
    treat_col: str,
    treated_value: object,
    covariates: Optional[List[str]] = None,
    additional_covariates: Optional[List[str]] = None,
    exact_cols: Optional[List[str]] = None,
    caliper: Optional[float] = None,
    method: Literal["nearest", "optimal"] = "optimal",
    trim_common_support: bool = True,
    random_state: int = 42,
) -> MatchResult:
    """Perform 1:1 propensity-score matching for a binary treatment indicator."""

    data = df.copy()
    data = data[data[treat_col].notna()].copy()
    data["_T"] = (data[treat_col] == treated_value).astype(int)

    if covariates is None:
        covariates = _default_covariates(data, treat_col=treat_col, exact_cols=exact_cols)
    else:
        covariates = list(covariates)

    if additional_covariates:
        for column in additional_covariates:
            if column in data.columns and column not in covariates:
                covariates.append(column)

    if exact_cols:
        covariates = [column for column in covariates if column not in set(exact_cols)]

    if not covariates:
        raise ValueError("propensity_match requires at least one covariate.")

    numeric_cols = [column for column in covariates if data[column].dtype.kind in "iufc"]
    categorical_cols = [column for column in covariates if column not in numeric_cols]

    preprocessor = ColumnTransformer(
        [
            (
                "num",
                Pipeline(
                    [
                        ("impute", SimpleImputer(strategy="median")),
                        ("scale", StandardScaler()),
                    ]
                ),
                numeric_cols,
            ),
            (
                "cat",
                Pipeline(
                    [
                        ("impute", SimpleImputer(strategy="most_frequent")),
                        ("encode", OneHotEncoder(handle_unknown="ignore")),
                    ]
                ),
                categorical_cols,
            ),
        ]
    )

    model = Pipeline(
        [
            ("pre", preprocessor),
            ("logit", LogisticRegression(max_iter=2000, solver="lbfgs", random_state=random_state)),
        ]
    )

    X = data[covariates]
    y = data["_T"]
    model.fit(X, y)

    ps = pd.Series(model.predict_proba(X)[:, 1], index=data.index, name="pscore")
    data["_PS"] = ps
    clipped = ps.clip(1e-6, 1 - 1e-6)
    data["_LPS"] = np.log(clipped / (1 - clipped))

    if trim_common_support:
        treated_mask = data["_T"] == 1
        control_mask = ~treated_mask
        low = max(data.loc[treated_mask, "_PS"].min(), data.loc[control_mask, "_PS"].min())
        high = min(data.loc[treated_mask, "_PS"].max(), data.loc[control_mask, "_PS"].max())
        data = data[(data["_PS"] >= low) & (data["_PS"] <= high)].copy()
        X = data[covariates]

    if data["_T"].nunique() < 2:
        raise ValueError("Matching requires both treatment arms after filtering.")

    if caliper is None:
        caliper = float(0.2 * data["_LPS"].std(ddof=1))

    transformed = model.named_steps["pre"].transform(X)
    feature_names: List[str] = list(numeric_cols)
    if categorical_cols:
        encoder = model.named_steps["pre"].named_transformers_["cat"].named_steps["encode"]
        feature_names.extend(list(encoder.get_feature_names_out(categorical_cols)))
    design_matrix = pd.DataFrame(
        transformed.toarray() if hasattr(transformed, "toarray") else transformed,
        index=data.index,
        columns=feature_names,
    )
    balance_before = _balance_table(
        pd.concat([design_matrix, data["_T"]], axis=1).rename(columns={"_T": "T"}),
        treat_col="T",
        columns=feature_names,
    )

    matched_rows = []
    pair_id = 0
    used_controls: set[int] = set()

    strata_values = [tuple([None])]
    if exact_cols:
        unique_rows = data[exact_cols].dropna().drop_duplicates()
        strata_values = [tuple(row[column] for column in exact_cols) for _, row in unique_rows.iterrows()]

    for key in strata_values:
        if exact_cols:
            mask = np.logical_and.reduce([data[column] == value for column, value in zip(exact_cols, key)])
            subset = data[mask].copy()
        else:
            subset = data.copy()

        treated = subset[subset["_T"] == 1]
        control = subset[subset["_T"] == 0]
        if treated.empty or control.empty:
            continue

        if method == "nearest":
            nearest = NearestNeighbors(n_neighbors=1)
            nearest.fit(control[["_LPS"]])
            distances, indices = nearest.kneighbors(treated[["_LPS"]])

            for treated_index, distance, control_idx in zip(treated.index, distances.ravel(), indices.ravel()):
                if distance > caliper:
                    continue
                control_index = int(control.index[control_idx])
                if control_index in used_controls:
                    continue
                used_controls.add(control_index)
                pair_id += 1
                pair = data.loc[[treated_index, control_index]].copy()
                pair["PAIR_ID"] = pair_id
                matched_rows.append(pair)
        else:
            treated_scores = treated["_LPS"].to_numpy(dtype=float)
            control_scores = control["_LPS"].to_numpy(dtype=float)
            distances = np.abs(treated_scores[:, None] - control_scores[None, :])
            large_cost = float(caliper) + 1.0
            cost = np.where(distances <= caliper, distances, large_cost)
            cost = np.hstack([cost, np.full((cost.shape[0], cost.shape[0]), large_cost, dtype=float)])
            row_ind, col_ind = linear_sum_assignment(cost)

            for row_idx, col_idx in zip(row_ind, col_ind):
                if col_idx >= control.shape[0] or cost[row_idx, col_idx] > caliper:
                    continue
                treated_index = int(treated.index[row_idx])
                control_index = int(control.index[col_idx])
                if control_index in used_controls:
                    continue
                used_controls.add(control_index)
                pair_id += 1
                pair = data.loc[[treated_index, control_index]].copy()
                pair["PAIR_ID"] = pair_id
                matched_rows.append(pair)

    if not matched_rows:
        return MatchResult(
            matched_df=data.iloc[0:0].copy(),
            pairs=0,
            dropped_rows=len(data),
            ps=data["_PS"].copy(),
            balance_before=balance_before,
            balance_after=balance_before.copy(),
            full_df=data,
            covariates=covariates,
            exact_cols=exact_cols,
            caliper=caliper,
            method=method,
            treat_col=treat_col,
            treated_value=treated_value,
        )

    matched_df = pd.concat(matched_rows, axis=0)
    matched_matrix = model.named_steps["pre"].transform(matched_df[covariates])
    matched_design = pd.DataFrame(
        matched_matrix.toarray() if hasattr(matched_matrix, "toarray") else matched_matrix,
        index=matched_df.index,
        columns=feature_names,
    )
    balance_after = _balance_table(
        pd.concat([matched_design, matched_df["_T"]], axis=1).rename(columns={"_T": "T"}),
        treat_col="T",
        columns=feature_names,
    )

    return MatchResult(
        matched_df=matched_df,
        pairs=pair_id,
        dropped_rows=int(data.shape[0] - matched_df.shape[0]),
        ps=data["_PS"].copy(),
        balance_before=balance_before,
        balance_after=balance_after,
        full_df=data,
        covariates=covariates,
        exact_cols=exact_cols,
        caliper=caliper,
        method=method,
        treat_col=treat_col,
        treated_value=treated_value,
    )
