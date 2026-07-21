from __future__ import annotations

from typing import Any, Optional

import numpy as np
import pandas as pd

from .config import WinRatioConfig
from .diagnostics import effective_sample_size
from .wr import _col_as_float_array, _outcome_masks, _terminal_tie_mask


def _weight_array(frame: pd.DataFrame, weight_col: Optional[str]) -> np.ndarray:
    if weight_col is None:
        return np.ones(frame.shape[0], dtype=float)
    if weight_col not in frame.columns:
        raise ValueError(f"weight column {weight_col!r} not found")
    weights = pd.to_numeric(frame[weight_col], errors="coerce").to_numpy(dtype=float)
    if np.any(~np.isfinite(weights)) or np.any(weights < 0):
        raise ValueError("weights must be finite and nonnegative")
    return weights


def _weighted_gpc_one_stratum(
    frame: pd.DataFrame,
    cfg: WinRatioConfig,
    weight_col: Optional[str],
) -> dict[str, Any]:
    arm_a = frame[frame[cfg.group_col] == cfg.arm_a].reset_index(drop=True)
    arm_b = frame[frame[cfg.group_col] == cfg.arm_b].reset_index(drop=True)
    if arm_a.empty or arm_b.empty:
        return {
            "wins": 0.0,
            "losses": 0.0,
            "ties": 0.0,
            "total_pair_weight": 0.0,
            "tier_wins": [0.0] * len(cfg.outcomes),
            "tier_losses": [0.0] * len(cfg.outcomes),
            "n_a": len(arm_a),
            "n_b": len(arm_b),
            "ess_a": float("nan"),
            "ess_b": float("nan"),
        }

    weights_a = _weight_array(arm_a, weight_col)
    weights_b = _weight_array(arm_b, weight_col)
    pair_weights = weights_a[:, None] * weights_b[None, :]
    unresolved = np.ones(pair_weights.shape, dtype=bool)
    terminal_ties = np.zeros(pair_weights.shape, dtype=bool)
    tier_wins: list[float] = []
    tier_losses: list[float] = []

    for outcome in cfg.outcomes:
        values_a = _col_as_float_array(arm_a, outcome.column)
        values_b = _col_as_float_array(arm_b, outcome.column)
        win_mask, loss_mask, tie_mask = _outcome_masks(values_a, values_b, outcome)
        effective_wins = unresolved & win_mask
        effective_losses = unresolved & loss_mask
        tier_wins.append(float(pair_weights[effective_wins].sum()))
        tier_losses.append(float(pair_weights[effective_losses].sum()))
        terminal_mask = unresolved & _terminal_tie_mask(values_a, values_b, outcome)
        terminal_ties |= terminal_mask
        unresolved &= tie_mask & ~terminal_mask

    total = float(pair_weights.sum())
    wins = float(sum(tier_wins))
    losses = float(sum(tier_losses))
    ties = float(pair_weights[unresolved | terminal_ties].sum())
    return {
        "wins": wins,
        "losses": losses,
        "ties": ties,
        "total_pair_weight": total,
        "tier_wins": tier_wins,
        "tier_losses": tier_losses,
        "n_a": int(len(arm_a)),
        "n_b": int(len(arm_b)),
        "ess_a": effective_sample_size(weights_a),
        "ess_b": effective_sample_size(weights_b),
    }


def compute_weighted_gpc(
    df: pd.DataFrame,
    cfg: WinRatioConfig,
    *,
    weight_col: Optional[str] = None,
) -> dict[str, Any]:
    """Estimate an all-pair generalized pairwise comparison (GPC).

    Pair weights are the cross-product of subject weights. With unit weights,
    this is the conventional all-pair win ratio. Comparisons remain confined
    within configured strata.
    """

    if cfg.pair_strategy != "all_pairs":
        raise ValueError("weighted GPC uses all cross-arm pairs; pair_strategy must be 'all_pairs'")
    if not cfg.outcomes:
        raise ValueError("No outcomes configured for weighted GPC")
    required = [cfg.group_col, *[outcome.column for outcome in cfg.outcomes]]
    missing_columns = sorted({column for column in required if column not in df.columns})
    if missing_columns:
        raise ValueError(f"required columns not found: {missing_columns}")

    if cfg.strata:
        pieces = []
        for _, values in df[cfg.strata].drop_duplicates().iterrows():
            subset = df
            for column in cfg.strata:
                subset = subset[subset[column] == values[column]]
            pieces.append(_weighted_gpc_one_stratum(subset, cfg, weight_col))
    else:
        pieces = [_weighted_gpc_one_stratum(df, cfg, weight_col)]

    wins = float(sum(piece["wins"] for piece in pieces))
    losses = float(sum(piece["losses"] for piece in pieces))
    ties = float(sum(piece["ties"] for piece in pieces))
    total = float(sum(piece["total_pair_weight"] for piece in pieces))
    tier_wins = [float(sum(piece["tier_wins"][i] for piece in pieces)) for i in range(len(cfg.outcomes))]
    tier_losses = [float(sum(piece["tier_losses"][i] for piece in pieces)) for i in range(len(cfg.outcomes))]
    informative = wins + losses
    wr = wins / losses if losses > 0 else (np.inf if wins > 0 else np.nan)
    favorable_probability = (wins + 0.5 * ties) / total if total > 0 else np.nan
    return {
        "wins": wins,
        "losses": losses,
        "ties": ties,
        "wr": float(wr) if np.isfinite(wr) else wr,
        "win_probability_among_informative": wins / informative if informative > 0 else np.nan,
        "favorable_pair_probability": favorable_probability,
        "win_difference": (wins - losses) / total if total > 0 else np.nan,
        "information_rate": informative / total if total > 0 else np.nan,
        "tie_adjusted_odds": (
            favorable_probability / (1 - favorable_probability)
            if np.isfinite(favorable_probability) and 0 < favorable_probability < 1
            else np.nan
        ),
        "details": {
            "n_a": int(sum(piece["n_a"] for piece in pieces)),
            "n_b": int(sum(piece["n_b"] for piece in pieces)),
            "total_pair_weight": total,
            "tier_wins": tier_wins,
            "tier_losses": tier_losses,
            "tier_names": [outcome.name for outcome in cfg.outcomes],
            "weight_col": weight_col,
            "ess_a": float(sum(piece["ess_a"] for piece in pieces if np.isfinite(piece["ess_a"]))),
            "ess_b": float(sum(piece["ess_b"] for piece in pieces if np.isfinite(piece["ess_b"]))),
            "n_strata": len(pieces),
        },
    }


def bootstrap_weighted_gpc(
    df: pd.DataFrame,
    cfg: WinRatioConfig,
    *,
    weight_col: Optional[str] = None,
    cluster_col: Optional[str] = None,
    within_arm: bool = True,
    n_boot: int = 1000,
    seed: int = 42,
) -> dict[str, Any]:
    """Bootstrap weighted GPC by subjects or clusters.

    For a cluster-level exposure, ``within_arm=True`` preserves the number of
    exposed and comparator clusters. Fixed supplied weights are resampled; this
    function does not refit a propensity model.
    """

    if n_boot <= 0:
        raise ValueError("n_boot must be positive")
    if cluster_col is not None and cluster_col not in df.columns:
        raise ValueError(f"cluster column {cluster_col!r} not found")

    point = compute_weighted_gpc(df, cfg, weight_col=weight_col)
    rng = np.random.default_rng(seed)
    samples = np.full(n_boot, np.nan, dtype=float)

    def sample_rows(source: pd.DataFrame) -> pd.DataFrame:
        if cluster_col is None:
            indices = rng.integers(0, len(source), size=len(source))
            return source.iloc[indices].copy()
        clusters = source[cluster_col].dropna().unique()
        sampled = rng.choice(clusters, size=len(clusters), replace=True)
        pieces = [source[source[cluster_col] == cluster].copy() for cluster in sampled]
        return pd.concat(pieces, ignore_index=True) if pieces else source.iloc[0:0].copy()

    for iteration in range(n_boot):
        if within_arm:
            sampled_parts = []
            for arm in (cfg.arm_a, cfg.arm_b):
                arm_frame = df[df[cfg.group_col] == arm]
                sampled_parts.append(sample_rows(arm_frame))
            sampled_df = pd.concat(sampled_parts, ignore_index=True)
        else:
            sampled_df = sample_rows(df)
        samples[iteration] = compute_weighted_gpc(sampled_df, cfg, weight_col=weight_col)["wr"]

    finite = samples[np.isfinite(samples)]
    ci = (
        (float(np.percentile(finite, 2.5)), float(np.percentile(finite, 97.5)))
        if finite.size
        else (np.nan, np.nan)
    )
    return {
        "wr": point["wr"],
        "ci": ci,
        "n_boot": int(n_boot),
        "seed": int(seed),
        "cluster_col": cluster_col,
        "within_arm": bool(within_arm),
        "wr_samples": finite.tolist(),
    }
