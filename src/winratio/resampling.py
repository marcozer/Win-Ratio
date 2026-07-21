from __future__ import annotations

from typing import Any, Iterable, Optional

import numpy as np
import pandas as pd

from .config import WinRatioConfig
from .gpc import compute_weighted_gpc
from .match import MatchResult, propensity_match
from .weights import estimate_propensity_weights
from .wr import compute_win_ratio


def _resample_clusters_within_arm(
    df: pd.DataFrame,
    cfg: WinRatioConfig,
    cluster_col: str,
    rng: np.random.Generator,
) -> pd.DataFrame:
    pieces = []
    for arm in (cfg.arm_a, cfg.arm_b):
        arm_data = df[df[cfg.group_col] == arm]
        clusters = arm_data[cluster_col].dropna().unique()
        if len(clusters) == 0:
            continue
        sampled = rng.choice(clusters, size=len(clusters), replace=True)
        for draw, cluster in enumerate(sampled):
            piece = arm_data[arm_data[cluster_col] == cluster].copy()
            piece[cluster_col] = f"BOOT_{arm}_{draw:04d}"
            pieces.append(piece)
    if not pieces:
        return df.iloc[0:0].copy()
    return pd.concat(pieces, ignore_index=True)


def _percentile_interval(samples: np.ndarray, alpha: float) -> tuple[float, float]:
    finite = samples[np.isfinite(samples)]
    if finite.size == 0:
        return (np.nan, np.nan)
    return (
        float(np.percentile(finite, 100 * alpha / 2)),
        float(np.percentile(finite, 100 * (1 - alpha / 2))),
    )


def bootstrap_propensity_matched_win_ratio(
    df: pd.DataFrame,
    cfg: WinRatioConfig,
    *,
    covariates: Iterable[str],
    cluster_col: str,
    exact_cols: Optional[Iterable[str]] = None,
    caliper: Optional[float] = None,
    method: str = "optimal",
    trim_common_support: bool = True,
    missing: str = "drop",
    n_boot: int = 1000,
    seed: int = 42,
    alpha: float = 0.05,
) -> dict[str, Any]:
    """Center-resample, refit the score, rematch, and recompute assigned-pair WR.

    Clusters are resampled separately within each arm, which is appropriate for
    a cluster-level exposure. Failed replicates are retained as missing rather
    than silently replaced.
    """

    if cluster_col not in df.columns:
        raise ValueError(f"cluster column {cluster_col!r} not found")
    if n_boot <= 0:
        raise ValueError("n_boot must be positive")
    if not 0 < alpha < 1:
        raise ValueError("alpha must be in (0, 1)")
    covariates = list(covariates)
    exact_cols = list(exact_cols or [])

    def fit(source: pd.DataFrame, fit_seed: int) -> tuple[MatchResult, float]:
        matching = propensity_match(
            source,
            treat_col=cfg.group_col,
            treated_value=cfg.arm_a,
            covariates=covariates,
            exact_cols=exact_cols,
            caliper=caliper,
            method=method,
            trim_common_support=trim_common_support,
            missing=missing,
            random_state=fit_seed,
        )
        matched_cfg = WinRatioConfig(
            group_col=cfg.group_col,
            arm_a=cfg.arm_a,
            arm_b=cfg.arm_b,
            outcomes=cfg.outcomes,
            pair_strategy="matched",
            pair_id="PAIR_ID",
        )
        estimate = compute_win_ratio(matching.matched_df, matched_cfg)["overall"]["wr"]
        return matching, estimate

    original_matching, point = fit(df, seed)
    rng = np.random.default_rng(seed)
    wr_samples = np.full(n_boot, np.nan, dtype=float)
    pair_samples = np.zeros(n_boot, dtype=int)
    n_completed = 0
    for iteration in range(n_boot):
        sampled = _resample_clusters_within_arm(df, cfg, cluster_col, rng)
        try:
            matching, wr_samples[iteration] = fit(sampled, seed + iteration + 1)
            pair_samples[iteration] = matching.pairs
            n_completed += 1
        except (ValueError, np.linalg.LinAlgError):
            continue

    finite = wr_samples[np.isfinite(wr_samples)]
    return {
        "wr": float(point) if np.isfinite(point) else point,
        "ci": _percentile_interval(wr_samples, alpha),
        "n_boot": int(n_boot),
        "n_successful": int(n_completed),
        "n_finite": int(finite.size),
        "seed": int(seed),
        "alpha": float(alpha),
        "bootstrap_type": "cluster_within_arm_propensity_refit_rematch",
        "cluster_col": cluster_col,
        "wr_samples": finite.tolist(),
        "pair_samples": pair_samples[pair_samples > 0].tolist(),
        "original_matching": original_matching,
    }


def bootstrap_propensity_weighted_gpc(
    df: pd.DataFrame,
    cfg: WinRatioConfig,
    *,
    covariates: Iterable[str],
    cluster_col: str,
    estimand: str = "overlap",
    missing: str = "drop",
    trim_common_support: bool = True,
    n_boot: int = 1000,
    seed: int = 42,
    alpha: float = 0.05,
) -> dict[str, Any]:
    """Center-resample, refit propensity weights, and recompute weighted GPC."""

    if cluster_col not in df.columns:
        raise ValueError(f"cluster column {cluster_col!r} not found")
    covariates = list(covariates)

    def fit(source: pd.DataFrame, fit_seed: int) -> tuple[Any, dict[str, Any]]:
        weighting = estimate_propensity_weights(
            source,
            treatment=cfg.group_col,
            treated=cfg.arm_a,
            covariates=covariates,
            estimand=estimand,
            missing=missing,
            trim_common_support=trim_common_support,
            seed=fit_seed,
        )
        estimate = compute_weighted_gpc(weighting.weighted_df, cfg, weight_col="analysis_weight")
        return weighting, estimate

    original_weighting, point = fit(df, seed)
    rng = np.random.default_rng(seed)
    wr_samples = np.full(n_boot, np.nan, dtype=float)
    n_completed = 0
    for iteration in range(n_boot):
        sampled = _resample_clusters_within_arm(df, cfg, cluster_col, rng)
        try:
            _, estimate = fit(sampled, seed + iteration + 1)
            wr_samples[iteration] = estimate["wr"]
            n_completed += 1
        except (ValueError, np.linalg.LinAlgError):
            continue

    finite = wr_samples[np.isfinite(wr_samples)]
    return {
        "wr": point["wr"],
        "ci": _percentile_interval(wr_samples, alpha),
        "n_boot": int(n_boot),
        "n_successful": int(n_completed),
        "n_finite": int(finite.size),
        "seed": int(seed),
        "alpha": float(alpha),
        "bootstrap_type": "cluster_within_arm_propensity_refit_weighted_gpc",
        "cluster_col": cluster_col,
        "wr_samples": finite.tolist(),
        "original_weighting": original_weighting,
    }
