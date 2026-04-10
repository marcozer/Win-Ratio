from __future__ import annotations

from dataclasses import asdict
from typing import Dict, Any, Tuple, Optional, List

import numpy as np
import pandas as pd

from .config import WinRatioConfig, WinRatioOutcome, MultiArmWinRatioConfig


def _compare_single_outcome(
    a_val, b_val, outcome: WinRatioOutcome
) -> int:
    """Compare a single outcome value pair.

    Returns: 1 if A wins, -1 if B wins, 0 if tie/indeterminate.

    Supports enhanced LOS tolerance modes:
    - exact: use tie_tol as threshold (current behavior)
    - tolerance_1day: need >= 1 day difference for win/loss
    - threshold_based: winner is one meeting threshold when other doesn't
    """
    # Missing handling
    if pd.isna(a_val) or pd.isna(b_val):
        if outcome.missing_is == "win":
            return 1
        if outcome.missing_is == "loss":
            return -1
        return 0

    if outcome.kind == "binary":
        # Assume 1 = event (unfavorable), 0 = no event (favorable)
        # Favor lower if direction == "lower" (typical adverse outcome)
        if outcome.direction == "lower":
            if a_val == 0 and b_val == 1:
                return 1
            if a_val == 1 and b_val == 0:
                return -1
            return 0
        else:  # direction == "higher"
            if a_val == 1 and b_val == 0:
                return 1
            if a_val == 0 and b_val == 1:
                return -1
            return 0

    # continuous - handle different LOS tolerance modes
    los_mode = getattr(outcome, 'los_tolerance_mode', 'exact')
    los_threshold = getattr(outcome, 'los_threshold', None)

    if los_mode == "threshold_based" and los_threshold is not None:
        # Winner is the one meeting threshold when the other doesn't
        a_meets = float(a_val) <= los_threshold
        b_meets = float(b_val) <= los_threshold
        if a_meets and not b_meets:
            return 1 if outcome.direction == "lower" else -1
        if b_meets and not a_meets:
            return -1 if outcome.direction == "lower" else 1
        # Both meet or neither meets - tie
        return 0

    if los_mode == "tolerance_1day":
        # Need >= 1 day difference for win/loss
        diff = float(a_val) - float(b_val)
        tolerance = 1.0
        if abs(diff) < tolerance:
            return 0
        if outcome.direction == "lower":
            return 1 if diff < 0 else -1
        else:
            return 1 if diff > 0 else -1

    # exact mode (default) - use tie_tol
    diff = float(a_val) - float(b_val)
    if abs(diff) <= outcome.tie_tol:
        return 0
    if outcome.direction == "lower":
        return 1 if diff < 0 else -1
    else:
        return 1 if diff > 0 else -1


def _compare_pair(
    a_row: pd.Series,
    b_row: pd.Series,
    outcomes: List[WinRatioOutcome],
) -> int:
    """Compare two subjects across prioritized outcomes.

    Returns 1 if A wins, -1 if B wins, 0 if tie across all outcomes.
    """
    for oc in outcomes:
        res = _compare_single_outcome(a_row.get(oc.column), b_row.get(oc.column), oc)
        if res != 0:
            return res
    return 0


def _compare_pair_with_level(
    a_row: pd.Series,
    b_row: pd.Series,
    outcomes: List[WinRatioOutcome],
) -> Tuple[int, Optional[int]]:
    """Compare two subjects and return (result, deciding_outcome_index).

    deciding_outcome_index: 0-based index into outcomes list, or None if tie.
    """
    for idx, oc in enumerate(outcomes):
        res = _compare_single_outcome(a_row.get(oc.column), b_row.get(oc.column), oc)
        if res != 0:
            return res, idx
    return 0, None


def compute_win_ratio_all_pairs(
    df: pd.DataFrame,
    cfg: WinRatioConfig,
    strata_values: Optional[Tuple] = None,
    chunk_size: int = 512,
) -> Dict[str, Any]:
    """Compute win ratio via all-pairs comparison with optional chunking.

    Returns dictionary with wins, losses, ties, WR, and meta.
    """
    subset = df.copy()
    if strata_values and cfg.strata:
        for col, val in zip(cfg.strata, strata_values):
            subset = subset[subset[col] == val]

    a = subset[subset[cfg.group_col] == cfg.arm_a]
    b = subset[subset[cfg.group_col] == cfg.arm_b]

    n_a, n_b = len(a), len(b)
    if n_a == 0 or n_b == 0:
        return {
            "wins": 0,
            "losses": 0,
            "ties": 0,
            "wr": np.nan,
            "details": {
                "n_a": n_a,
                "n_b": n_b,
                "strata": strata_values,
                "config": {**asdict(cfg), "outcomes": [asdict(o) for o in cfg.outcomes]},
            },
        }

    n_levels = len(cfg.outcomes)
    tier_wins = [0] * n_levels
    tier_losses = [0] * n_levels

    # Vectorized hierarchical comparison (fast for moderate pair counts).
    # Fall back to chunked python loop when pair grid is very large.
    max_pairs_vectorized = 5_000_000
    if n_a * n_b > max_pairs_vectorized:
        wins = 0
        losses = 0
        ties = 0
        tier_ties = 0  # count of ties across all tiers

        a_idx = a.index.to_list()
        for start in range(0, n_a, chunk_size):
            stop = min(start + chunk_size, n_a)
            a_block = a.loc[a_idx[start:stop]]
            for _, a_row in a_block.iterrows():
                for _, b_row in b.iterrows():
                    cmp_res, level = _compare_pair_with_level(a_row, b_row, cfg.outcomes)
                    if cmp_res > 0:
                        wins += 1
                        if level is not None:
                            tier_wins[level] += 1
                    elif cmp_res < 0:
                        losses += 1
                        if level is not None:
                            tier_losses[level] += 1
                    else:
                        ties += 1
                        tier_ties += 1
    else:
        a_reset = a.reset_index(drop=True)
        b_reset = b.reset_index(drop=True)
        unresolved = np.ones((n_a, n_b), dtype=bool)

        for idx, oc in enumerate(cfg.outcomes):
            a_vals = _col_as_float_array(a_reset, oc.column)
            b_vals = _col_as_float_array(b_reset, oc.column)
            win_mask, loss_mask, tie_mask = _outcome_masks(a_vals, b_vals, oc)

            eff_win = unresolved & win_mask
            eff_loss = unresolved & loss_mask
            tier_wins[idx] = int(eff_win.sum())
            tier_losses[idx] = int(eff_loss.sum())

            unresolved &= tie_mask

        wins = int(sum(tier_wins))
        losses = int(sum(tier_losses))
        ties = int(unresolved.sum())
        tier_ties = ties

    wr = np.nan
    if losses > 0:
        wr = wins / losses
    elif wins > 0 and losses == 0:
        wr = np.inf
    else:
        wr = np.nan

    return {
        "wins": int(wins),
        "losses": int(losses),
        "ties": int(ties),
        "wr": float(wr) if np.isfinite(wr) else wr,
        "details": {
            "n_a": n_a,
            "n_b": n_b,
            "strata": strata_values,
            "group_col": cfg.group_col,
            "arm_a": cfg.arm_a,
            "arm_b": cfg.arm_b,
            "pair_strategy": cfg.pair_strategy,
            "tier_wins": tier_wins,
            "tier_losses": tier_losses,
            "tier_ties": tier_ties,
        },
    }


def compute_win_ratio(
    df: pd.DataFrame,
    cfg: WinRatioConfig,
) -> Dict[str, Any]:
    """High-level WR computation with optional stratification.

    Returns overall result and optional per-stratum results.
    """
    if not cfg.outcomes:
        raise ValueError("No outcomes configured for win ratio.")

    # Matched strategy: if pair_id is provided, compute pairwise only
    if cfg.pair_strategy == 'matched' and cfg.pair_id:
        return {"overall": compute_win_ratio_matched(df, cfg)}

    if cfg.strata:
        # Iterate over all unique strata combinations
        strata_df = df[cfg.strata].drop_duplicates()
        per = []
        for _, row in strata_df.iterrows():
            key = tuple(row[c] for c in cfg.strata)
            res = compute_win_ratio_all_pairs(df, cfg, strata_values=key)
            res["strata"] = {c: v for c, v in zip(cfg.strata, key)}
            per.append(res)

        # Stratified overall = sum within-stratum wins/losses (no cross-stratum comparisons)
        n_levels = len(cfg.outcomes)
        strat_wins = int(sum(r.get("wins", 0) for r in per))
        strat_losses = int(sum(r.get("losses", 0) for r in per))
        strat_ties = int(sum(r.get("ties", 0) for r in per))
        tier_wins = [0] * n_levels
        tier_losses = [0] * n_levels
        for r in per:
            dw = (r.get("details", {}) or {}).get("tier_wins") or []
            dl = (r.get("details", {}) or {}).get("tier_losses") or []
            for i in range(min(n_levels, len(dw))):
                tier_wins[i] += int(dw[i])
            for i in range(min(n_levels, len(dl))):
                tier_losses[i] += int(dl[i])

        strat_wr = np.nan
        if strat_losses > 0:
            strat_wr = strat_wins / strat_losses
        elif strat_wins > 0 and strat_losses == 0:
            strat_wr = np.inf

        # Also compute unstratified overall for reference (includes cross-stratum pairs)
        overall_unstratified = compute_win_ratio_all_pairs(df, cfg, strata_values=None)

        overall = {
            "wins": strat_wins,
            "losses": strat_losses,
            "ties": strat_ties,
            "wr": float(strat_wr) if np.isfinite(strat_wr) else strat_wr,
            "details": {
                "n_a": int(df[df[cfg.group_col] == cfg.arm_a].shape[0]),
                "n_b": int(df[df[cfg.group_col] == cfg.arm_b].shape[0]),
                "strata": "stratified",
                "strata_cols": cfg.strata,
                "n_strata": int(len(per)),
                "group_col": cfg.group_col,
                "arm_a": cfg.arm_a,
                "arm_b": cfg.arm_b,
                "pair_strategy": cfg.pair_strategy,
                "tier_wins": tier_wins,
                "tier_losses": tier_losses,
                "tier_ties": strat_ties,
            },
        }
        return {"overall": overall, "overall_unstratified": overall_unstratified, "by_strata": per}

    # No strata
    return {"overall": compute_win_ratio_all_pairs(df, cfg)}


def compute_win_ratio_matched(
    df: pd.DataFrame,
    cfg: WinRatioConfig,
) -> Dict[str, Any]:
    """Compute win ratio using matched pairs defined by `pair_id`.

    Expects exactly one A and one B per `pair_id`. Extra or missing are ignored.
    """
    pid = cfg.pair_id
    if not pid:
        raise ValueError("pair_id must be set for matched strategy")

    wins = 0
    losses = 0
    ties = 0
    pair_count = 0
    n_levels = len(cfg.outcomes)
    tier_wins = [0] * n_levels
    tier_losses = [0] * n_levels

    # Count subjects in each arm
    a = df[df[cfg.group_col] == cfg.arm_a]
    b = df[df[cfg.group_col] == cfg.arm_b]
    n_a = len(a)
    n_b = len(b)

    for pid_val, g in df.groupby(pid):
        ga = g[g[cfg.group_col] == cfg.arm_a]
        gb = g[g[cfg.group_col] == cfg.arm_b]
        if len(ga) != 1 or len(gb) != 1:
            continue
        pair_count += 1
        a_row = ga.iloc[0]
        b_row = gb.iloc[0]
        res, level = _compare_pair_with_level(a_row, b_row, cfg.outcomes)
        if res > 0:
            wins += 1
            if level is not None:
                tier_wins[level] += 1
        elif res < 0:
            losses += 1
            if level is not None:
                tier_losses[level] += 1
        else:
            ties += 1

    wr = np.nan
    if losses > 0:
        wr = wins / losses
    elif wins > 0 and losses == 0:
        wr = np.inf
    else:
        wr = np.nan

    return {
        'wins': int(wins),
        'losses': int(losses),
        'ties': int(ties),
        'wr': float(wr) if np.isfinite(wr) else wr,
        'details': {
            'n_a': n_a,
            'n_b': n_b,
            'pairs': pair_count,
            'group_col': cfg.group_col,
            'arm_a': cfg.arm_a,
            'arm_b': cfg.arm_b,
            'pair_strategy': cfg.pair_strategy,
            'pair_id': cfg.pair_id,
            'tier_wins': tier_wins,
            'tier_losses': tier_losses,
        }
    }


def bootstrap_win_ratio_matched(
    df: pd.DataFrame,
    cfg: WinRatioConfig,
    n_boot: int = 1000,
    seed: int = 42,
) -> Dict[str, Any]:
    """Bootstrap for matched WR: resample pairs with replacement.
    Vectorized using precomputed pair outcomes.
    """
    if cfg.pair_strategy != 'matched' or not cfg.pair_id:
        raise ValueError("bootstrap_win_ratio_matched requires matched strategy and pair_id")

    pid = cfg.pair_id
    # Precompute pair results
    items: List[int] = []
    pair_results: List[int] = []  # 1 win, -1 loss, 0 tie for A vs B
    for pid_val, g in df.groupby(pid):
        ga = g[g[cfg.group_col] == cfg.arm_a]
        gb = g[g[cfg.group_col] == cfg.arm_b]
        if len(ga) != 1 or len(gb) != 1:
            continue
        res = _compare_pair(ga.iloc[0], gb.iloc[0], cfg.outcomes)
        items.append(pid_val)
        pair_results.append(res)

    if not pair_results:
        return {'wr': np.nan, 'ci': (np.nan, np.nan), 'n_boot': n_boot, 'wr_samples': []}

    pr = np.array(pair_results, dtype=int)
    rng = np.random.default_rng(seed)
    m = pr.size
    # counts of resampled pairs per replicate: multinomial(m, 1/m)
    F = rng.multinomial(n=m, pvals=np.full(m, 1.0/m), size=n_boot).T  # (m, R)
    wins_vec = F.T @ (pr == 1).astype(int)
    losses_vec = F.T @ (pr == -1).astype(int)

    wr_samples = np.full(n_boot, np.nan, dtype=float)
    mask = losses_vec > 0
    wr_samples[mask] = wins_vec[mask] / losses_vec[mask]
    wr_samples[~mask & (wins_vec > 0)] = np.inf

    finite = wr_samples[np.isfinite(wr_samples)]
    if finite.size == 0:
        ci = (np.nan, np.nan)
    else:
        lower = np.percentile(finite, 2.5)
        upper = np.percentile(finite, 97.5)
        ci = (float(lower), float(upper))

    point = compute_win_ratio_matched(df, cfg)['wr']
    return {'wr': float(point) if np.isfinite(point) else point, 'ci': ci, 'n_boot': n_boot, 'wr_samples': finite.tolist()}


def bootstrap_win_ratio(
    df: pd.DataFrame,
    cfg: WinRatioConfig,
    n_boot: int = 1000,
    seed: int = 42,
) -> Dict[str, Any]:
    """Subject-level bootstrap for WR with all-pairs comparison.

    Resamples subjects within each arm with replacement to preserve dependence.
    Returns WR estimate, percentile CI, and distribution.
    """
    rng = np.random.default_rng(seed)

    # Original estimate (aligned with compute_win_ratio: stratified if cfg.strata set)
    orig = compute_win_ratio(df, cfg)["overall"]["wr"]

    # Stratified bootstrap: resample subjects within each stratum and arm
    if cfg.strata:
        wins_vec = np.zeros(n_boot, dtype=np.float64)
        losses_vec = np.zeros(n_boot, dtype=np.float64)

        strata_df = df[cfg.strata].drop_duplicates()
        for _, row in strata_df.iterrows():
            key = tuple(row[c] for c in cfg.strata)

            sub = df.copy()
            for col, val in zip(cfg.strata, key):
                sub = sub[sub[col] == val]

            a = sub[sub[cfg.group_col] == cfg.arm_a].copy()
            b = sub[sub[cfg.group_col] == cfg.arm_b].copy()
            if a.empty or b.empty:
                continue

            W, L, _T = _precompute_pair_result_matrices(a, b, cfg)
            n_a = a.shape[0]
            n_b = b.shape[0]
            fA = rng.multinomial(n=n_a, pvals=np.full(n_a, 1.0 / n_a), size=n_boot).T.astype(np.float32, copy=False)
            fB = rng.multinomial(n=n_b, pvals=np.full(n_b, 1.0 / n_b), size=n_boot).T.astype(np.float32, copy=False)

            Wf = W.astype(np.float32, copy=False)
            Lf = L.astype(np.float32, copy=False)
            wins_mat = Wf @ fB
            losses_mat = Lf @ fB
            wins_vec += np.sum(wins_mat * fA, axis=0)
            losses_vec += np.sum(losses_mat * fA, axis=0)
    else:
        # Split arms
        a = df[df[cfg.group_col] == cfg.arm_a].copy()
        b = df[df[cfg.group_col] == cfg.arm_b].copy()
        if a.empty or b.empty:
            raise ValueError("One or both arms are empty after filtering by group_col and arms.")

        W, L, _T = _precompute_pair_result_matrices(a, b, cfg)
        n_a = a.shape[0]
        n_b = b.shape[0]
        fA = rng.multinomial(n=n_a, pvals=np.full(n_a, 1.0 / n_a), size=n_boot).T.astype(np.float32, copy=False)
        fB = rng.multinomial(n=n_b, pvals=np.full(n_b, 1.0 / n_b), size=n_boot).T.astype(np.float32, copy=False)
        Wf = W.astype(np.float32, copy=False)
        Lf = L.astype(np.float32, copy=False)
        wins_mat = Wf @ fB
        losses_mat = Lf @ fB
        wins_vec = np.sum(wins_mat * fA, axis=0).astype(np.float64)
        losses_vec = np.sum(losses_mat * fA, axis=0).astype(np.float64)

    wr_samples = np.full(n_boot, np.nan, dtype=float)
    mask = losses_vec > 0
    wr_samples[mask] = wins_vec[mask] / losses_vec[mask]
    wr_samples[~mask & (wins_vec > 0)] = np.inf

    finite = wr_samples[np.isfinite(wr_samples)]
    if finite.size == 0:
        ci = (np.nan, np.nan)
    else:
        lower = np.percentile(finite, 2.5)
        upper = np.percentile(finite, 97.5)
        ci = (float(lower), float(upper))

    return {
        "wr": float(orig) if np.isfinite(orig) else orig,
        "ci": ci,
        "n_boot": int(n_boot),
        "seed": int(seed),
        "bootstrap_type": "subject_within_strata" if cfg.strata else "subject",
        "wr_samples": finite.tolist(),
    }


def bootstrap_win_ratio_cluster(
    df: pd.DataFrame,
    cfg: WinRatioConfig,
    cluster_col: str,
    n_boot: int = 1000,
    seed: int = 42,
) -> Dict[str, Any]:
    """Cluster (e.g., center-level) bootstrap for all-pairs WR.

    Resamples clusters with replacement and keeps all patients within each
    selected cluster (with multiplicity). This is recommended when outcomes
    are correlated within clusters and/or when the exposure is cluster-level.
    """
    if cfg.pair_strategy != "all_pairs":
        raise ValueError("bootstrap_win_ratio_cluster supports all_pairs only")
    if cluster_col not in df.columns:
        raise ValueError(f"cluster_col {cluster_col!r} not found in dataframe")

    rng = np.random.default_rng(seed)

    # Original estimate aligned with compute_win_ratio (stratified if cfg.strata set)
    point = compute_win_ratio(df, cfg)["overall"]["wr"]

    wins_vec = np.zeros(n_boot, dtype=np.float64)
    losses_vec = np.zeros(n_boot, dtype=np.float64)
    n_clusters_total = 0

    if cfg.strata:
        strata_df = df[cfg.strata].drop_duplicates()
        for _, row in strata_df.iterrows():
            key = tuple(row[c] for c in cfg.strata)
            sub = df.copy()
            for col, val in zip(cfg.strata, key):
                sub = sub[sub[col] == val]

            a = sub[sub[cfg.group_col] == cfg.arm_a].copy()
            b = sub[sub[cfg.group_col] == cfg.arm_b].copy()
            if a.empty or b.empty:
                continue

            clusters = pd.Index(pd.concat([a[cluster_col], b[cluster_col]], axis=0).dropna().unique())
            if clusters.empty:
                continue
            clusters = clusters.sort_values()
            m = int(clusters.size)
            n_clusters_total += m
            cluster_to_idx = {c: i for i, c in enumerate(clusters)}
            a_cidx = a[cluster_col].map(cluster_to_idx).to_numpy()
            b_cidx = b[cluster_col].map(cluster_to_idx).to_numpy()

            W, L, _T = _precompute_pair_result_matrices(a, b, cfg)
            C = rng.multinomial(n=m, pvals=np.full(m, 1.0 / m), size=n_boot).T  # (m, R)
            fA = C[a_cidx, :].astype(np.float32, copy=False)
            fB = C[b_cidx, :].astype(np.float32, copy=False)
            Wf = W.astype(np.float32, copy=False)
            Lf = L.astype(np.float32, copy=False)
            wins_mat = Wf @ fB
            losses_mat = Lf @ fB
            wins_vec += np.sum(wins_mat * fA, axis=0)
            losses_vec += np.sum(losses_mat * fA, axis=0)
    else:
        a = df[df[cfg.group_col] == cfg.arm_a].copy()
        b = df[df[cfg.group_col] == cfg.arm_b].copy()
        if a.empty or b.empty:
            raise ValueError("One or both arms are empty after filtering by group_col and arms.")

        clusters = pd.Index(pd.concat([a[cluster_col], b[cluster_col]], axis=0).dropna().unique())
        if clusters.empty:
            raise ValueError("No non-missing clusters found for cluster bootstrap.")
        clusters = clusters.sort_values()
        m = int(clusters.size)
        n_clusters_total = m
        cluster_to_idx = {c: i for i, c in enumerate(clusters)}

        a_cidx = a[cluster_col].map(cluster_to_idx).to_numpy()
        b_cidx = b[cluster_col].map(cluster_to_idx).to_numpy()

        W, L, _T = _precompute_pair_result_matrices(a, b, cfg)
        C = rng.multinomial(n=m, pvals=np.full(m, 1.0 / m), size=n_boot).T  # (m, R)
        fA = C[a_cidx, :].astype(np.float32, copy=False)
        fB = C[b_cidx, :].astype(np.float32, copy=False)
        Wf = W.astype(np.float32, copy=False)
        Lf = L.astype(np.float32, copy=False)
        wins_mat = Wf @ fB
        losses_mat = Lf @ fB
        wins_vec = np.sum(wins_mat * fA, axis=0).astype(np.float64)
        losses_vec = np.sum(losses_mat * fA, axis=0).astype(np.float64)

    wr_samples = np.full(n_boot, np.nan, dtype=float)
    mask = losses_vec > 0
    wr_samples[mask] = wins_vec[mask] / losses_vec[mask]
    wr_samples[~mask & (wins_vec > 0)] = np.inf

    finite = wr_samples[np.isfinite(wr_samples)]
    if finite.size == 0:
        ci = (np.nan, np.nan)
    else:
        lower = np.percentile(finite, 2.5)
        upper = np.percentile(finite, 97.5)
        ci = (float(lower), float(upper))

    return {
        "wr": float(point) if np.isfinite(point) else point,
        "ci": ci,
        "n_boot": int(n_boot),
        "seed": int(seed),
        "bootstrap_type": "cluster_within_strata" if cfg.strata else "cluster",
        "cluster_col": cluster_col,
        "n_clusters": int(n_clusters_total),
        "wr_samples": finite.tolist(),
    }


def _col_as_float_array(df: pd.DataFrame, col: str) -> np.ndarray:
    """Return df[col] as float array, coercing errors to NaN."""
    if col not in df.columns:
        return np.full(df.shape[0], np.nan, dtype=float)
    s = df[col]
    if s.dtype.kind in "iufc":
        return s.to_numpy(dtype=float, copy=False)
    return pd.to_numeric(s, errors="coerce").to_numpy(dtype=float, copy=False)


def _outcome_masks(
    a_vals: np.ndarray,
    b_vals: np.ndarray,
    outcome: WinRatioOutcome,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Vectorized (win, loss, tie) masks for one outcome across all pairs.

    Supports enhanced LOS tolerance modes:
    - exact: use tie_tol as threshold (current behavior)
    - tolerance_1day: need >= 1 day difference for win/loss
    - threshold_based: winner is one meeting threshold when other doesn't
    """
    a = a_vals.astype(float, copy=False)
    b = b_vals.astype(float, copy=False)
    a_nan = np.isnan(a)[:, None]
    b_nan = np.isnan(b)[None, :]
    missing = a_nan | b_nan

    if outcome.kind == "binary":
        a0 = (a[:, None] == 0.0)
        a1 = (a[:, None] == 1.0)
        b0 = (b[None, :] == 0.0)
        b1 = (b[None, :] == 1.0)
        if outcome.direction == "lower":
            win = a0 & b1
            loss = a1 & b0
        else:
            win = a1 & b0
            loss = a0 & b1

        if outcome.missing_is == "tie":
            win &= ~missing
            loss &= ~missing
        elif outcome.missing_is == "win":
            win |= missing
            loss &= ~missing
        elif outcome.missing_is == "loss":
            loss |= missing
            win &= ~missing
        tie = ~(win | loss)
        return win, loss, tie

    # continuous - handle different LOS tolerance modes
    los_mode = getattr(outcome, 'los_tolerance_mode', 'exact')
    los_threshold = getattr(outcome, 'los_threshold', None)

    if los_mode == "threshold_based" and los_threshold is not None:
        # Winner is the one meeting threshold when the other doesn't
        a_meets = (a[:, None] <= los_threshold)
        b_meets = (b[None, :] <= los_threshold)
        if outcome.direction == "lower":
            win = a_meets & ~b_meets
            loss = ~a_meets & b_meets
        else:
            win = ~a_meets & b_meets
            loss = a_meets & ~b_meets
    elif los_mode == "tolerance_1day":
        # Need >= 1 day difference for win/loss
        diff = a[:, None] - b[None, :]
        tolerance = 1.0
        if outcome.direction == "lower":
            win = diff < -tolerance
            loss = diff > tolerance
        else:
            win = diff > tolerance
            loss = diff < -tolerance
    else:
        # exact mode (default)
        diff = a[:, None] - b[None, :]
        tol = float(outcome.tie_tol or 0.0)
        if outcome.direction == "lower":
            win = diff < -tol
            loss = diff > tol
        else:
            win = diff > tol
            loss = diff < -tol

    if outcome.missing_is == "tie":
        win &= ~missing
        loss &= ~missing
    elif outcome.missing_is == "win":
        win |= missing
        loss &= ~missing
    elif outcome.missing_is == "loss":
        loss |= missing
        win &= ~missing
    tie = ~(win | loss)
    return win, loss, tie


def bootstrap_win_ratio_cluster_within_arm(
    df: pd.DataFrame,
    cfg: WinRatioConfig,
    cluster_col: str,
    n_boot: int = 1000,
    seed: int = 42,
) -> Dict[str, Any]:
    """Cluster bootstrap resampling clusters *within each arm* (A and B) separately.

    This keeps the number of clusters per arm fixed across replicates and is a
    useful sensitivity analysis when the exposure is cluster-level (e.g., center
    volume classification).
    """
    if cfg.pair_strategy != "all_pairs":
        raise ValueError("bootstrap_win_ratio_cluster_within_arm supports all_pairs only")
    if cluster_col not in df.columns:
        raise ValueError(f"cluster_col {cluster_col!r} not found in dataframe")

    rng = np.random.default_rng(seed)
    point = compute_win_ratio(df, cfg)["overall"]["wr"]

    wins_vec = np.zeros(n_boot, dtype=np.float64)
    losses_vec = np.zeros(n_boot, dtype=np.float64)
    n_clusters_a_total = 0
    n_clusters_b_total = 0

    def _run_one(sub: pd.DataFrame) -> None:
        nonlocal wins_vec, losses_vec, n_clusters_a_total, n_clusters_b_total

        a = sub[sub[cfg.group_col] == cfg.arm_a].copy()
        b = sub[sub[cfg.group_col] == cfg.arm_b].copy()
        if a.empty or b.empty:
            return

        ca = pd.Index(a[cluster_col].dropna().unique()).sort_values()
        cb = pd.Index(b[cluster_col].dropna().unique()).sort_values()
        if ca.empty or cb.empty:
            return

        m_a = int(ca.size)
        m_b = int(cb.size)
        n_clusters_a_total += m_a
        n_clusters_b_total += m_b

        map_a = {c: i for i, c in enumerate(ca)}
        map_b = {c: i for i, c in enumerate(cb)}
        a_cidx = a[cluster_col].map(map_a).to_numpy()
        b_cidx = b[cluster_col].map(map_b).to_numpy()

        W, L, _T = _precompute_pair_result_matrices(a, b, cfg)
        Wf = W.astype(np.float32, copy=False)
        Lf = L.astype(np.float32, copy=False)

        Ca = rng.multinomial(n=m_a, pvals=np.full(m_a, 1.0 / m_a), size=n_boot).T.astype(np.float32, copy=False)
        Cb = rng.multinomial(n=m_b, pvals=np.full(m_b, 1.0 / m_b), size=n_boot).T.astype(np.float32, copy=False)

        fA = Ca[a_cidx, :]  # (n_a, R)
        fB = Cb[b_cidx, :]  # (n_b, R)

        wins_mat = Wf @ fB
        losses_mat = Lf @ fB
        wins_vec += np.sum(wins_mat * fA, axis=0)
        losses_vec += np.sum(losses_mat * fA, axis=0)

    if cfg.strata:
        strata_df = df[cfg.strata].drop_duplicates()
        for _, row in strata_df.iterrows():
            sub = df.copy()
            for col, val in zip(cfg.strata, tuple(row[c] for c in cfg.strata)):
                sub = sub[sub[col] == val]
            _run_one(sub)
    else:
        _run_one(df)

    wr_samples = np.full(n_boot, np.nan, dtype=float)
    mask = losses_vec > 0
    wr_samples[mask] = wins_vec[mask] / losses_vec[mask]
    wr_samples[~mask & (wins_vec > 0)] = np.inf

    finite = wr_samples[np.isfinite(wr_samples)]
    if finite.size == 0:
        ci = (np.nan, np.nan)
    else:
        lower = np.percentile(finite, 2.5)
        upper = np.percentile(finite, 97.5)
        ci = (float(lower), float(upper))

    return {
        "wr": float(point) if np.isfinite(point) else point,
        "ci": ci,
        "n_boot": int(n_boot),
        "seed": int(seed),
        "bootstrap_type": "cluster_within_arm_within_strata" if cfg.strata else "cluster_within_arm",
        "cluster_col": cluster_col,
        "n_clusters_a": int(n_clusters_a_total),
        "n_clusters_b": int(n_clusters_b_total),
        "wr_samples": finite.tolist(),
    }


def _precompute_pair_result_matrices(
    a: pd.DataFrame,
    b: pd.DataFrame,
    cfg: WinRatioConfig,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Precompute pairwise result indicator matrices for wins/losses/ties.

    Returns (W, L, T) each with shape (n_a, n_b) as uint8 indicators.
    """
    n_a = a.shape[0]
    n_b = b.shape[0]
    W = np.zeros((n_a, n_b), dtype=np.uint8)
    L = np.zeros((n_a, n_b), dtype=np.uint8)
    unresolved = np.ones((n_a, n_b), dtype=bool)

    a_reset = a.reset_index(drop=True)
    b_reset = b.reset_index(drop=True)

    for oc in cfg.outcomes:
        a_vals = _col_as_float_array(a_reset, oc.column)
        b_vals = _col_as_float_array(b_reset, oc.column)
        win_mask, loss_mask, tie_mask = _outcome_masks(a_vals, b_vals, oc)
        eff_win = unresolved & win_mask
        eff_loss = unresolved & loss_mask
        W[eff_win] = 1
        L[eff_loss] = 1
        unresolved &= tie_mask

    T = unresolved.astype(np.uint8)
    return W, L, T


# =============================================================================
# Multi-Arm Win Ratio Functions
# =============================================================================


def _multi_arm_to_pairwise_config(
    multi_cfg: MultiArmWinRatioConfig,
    arm_a: str,
    arm_b: str,
) -> WinRatioConfig:
    """Convert MultiArmWinRatioConfig to WinRatioConfig for a specific pair."""
    return WinRatioConfig(
        group_col=multi_cfg.group_col,
        arm_a=arm_a,
        arm_b=arm_b,
        outcomes=multi_cfg.outcomes,
        strata=multi_cfg.strata,
        id_col=multi_cfg.id_col,
        pair_strategy=multi_cfg.pair_strategy,
        pair_id=multi_cfg.pair_id,
    )


def compute_win_ratio_multi_arm(
    df: pd.DataFrame,
    cfg: MultiArmWinRatioConfig,
) -> Dict[str, Any]:
    """Compute win ratio for all pairwise comparisons in a multi-arm design.

    Args:
        df: DataFrame with outcome columns and arm assignment
        cfg: MultiArmWinRatioConfig with arms and comparison pairs

    Returns:
        Dictionary with:
        - comparisons: list of pairwise comparison results
        - summary: aggregated statistics
    """
    from itertools import combinations

    # Determine comparison pairs
    if cfg.comparison_pairs:
        pairs = cfg.comparison_pairs
    else:
        # All pairwise combinations
        pairs = list(combinations(cfg.arms, 2))

    results = []
    for arm_a, arm_b in pairs:
        pairwise_cfg = _multi_arm_to_pairwise_config(cfg, arm_a, arm_b)
        wr_result = compute_win_ratio(df, pairwise_cfg)

        comparison = {
            "arm_a": arm_a,
            "arm_b": arm_b,
            "arm_a_label": cfg.arm_labels.get(arm_a, arm_a),
            "arm_b_label": cfg.arm_labels.get(arm_b, arm_b),
            **wr_result["overall"],
        }
        results.append(comparison)

    # Summary
    n_comparisons = len(results)
    n_significant_nominal = sum(
        1 for r in results
        if r.get("wr", np.nan) != 1.0 and np.isfinite(r.get("wr", np.nan))
    )

    return {
        "comparisons": results,
        "summary": {
            "n_arms": len(cfg.arms),
            "arms": cfg.arms,
            "arm_labels": cfg.arm_labels,
            "n_comparisons": n_comparisons,
            "reference_arm": cfg.reference_arm,
        },
    }


def bootstrap_win_ratio_multi_arm(
    df: pd.DataFrame,
    cfg: MultiArmWinRatioConfig,
    n_boot: int = 2000,
    cluster_col: Optional[str] = None,
    seed: int = 42,
) -> Dict[str, Any]:
    """Bootstrap CIs for all pairwise comparisons in multi-arm design.

    Args:
        df: DataFrame with outcome columns and arm assignment
        cfg: MultiArmWinRatioConfig
        n_boot: Number of bootstrap replicates
        cluster_col: Column for cluster bootstrap (e.g., CENTRE)
        seed: Random seed

    Returns:
        Dictionary with comparisons including bootstrap CIs
    """
    from itertools import combinations

    # Determine comparison pairs
    if cfg.comparison_pairs:
        pairs = cfg.comparison_pairs
    else:
        pairs = list(combinations(cfg.arms, 2))

    results = []
    for i, (arm_a, arm_b) in enumerate(pairs):
        pairwise_cfg = _multi_arm_to_pairwise_config(cfg, arm_a, arm_b)

        # Use different seed for each comparison for reproducibility
        pair_seed = seed + i

        if cluster_col:
            boot_result = bootstrap_win_ratio_cluster(
                df, pairwise_cfg, cluster_col, n_boot, pair_seed
            )
        else:
            if pairwise_cfg.pair_strategy == "matched" and pairwise_cfg.pair_id:
                boot_result = bootstrap_win_ratio_matched(
                    df, pairwise_cfg, n_boot, pair_seed
                )
            else:
                boot_result = bootstrap_win_ratio(
                    df, pairwise_cfg, n_boot, pair_seed
                )

        comparison = {
            "arm_a": arm_a,
            "arm_b": arm_b,
            "arm_a_label": cfg.arm_labels.get(arm_a, arm_a),
            "arm_b_label": cfg.arm_labels.get(arm_b, arm_b),
            "wr": boot_result["wr"],
            "ci_lower": boot_result["ci"][0],
            "ci_upper": boot_result["ci"][1],
            "n_boot": boot_result["n_boot"],
        }
        results.append(comparison)

    return {
        "comparisons": results,
        "summary": {
            "n_arms": len(cfg.arms),
            "arms": cfg.arms,
            "n_comparisons": len(results),
            "n_boot": n_boot,
            "cluster_col": cluster_col,
        },
    }


def compute_pvalue_from_bootstrap(
    wr: float,
    ci_lower: float,
    ci_upper: float,
    null_wr: float = 1.0,
) -> float:
    """Approximate p-value from bootstrap CI using normal approximation.

    This is a standard approach when the null hypothesis is that WR = 1.0.
    Uses log(WR) for better normality.
    """
    if not np.isfinite(wr) or wr <= 0:
        return np.nan
    if not np.isfinite(ci_lower) or not np.isfinite(ci_upper):
        return np.nan
    if ci_lower <= 0 or ci_upper <= 0:
        return np.nan

    # Work on log scale for normality
    log_wr = np.log(wr)
    log_ci_lower = np.log(ci_lower)
    log_ci_upper = np.log(ci_upper)
    log_null = np.log(null_wr)

    # Estimate SE from CI width (95% CI spans ~3.92 SEs)
    log_se = (log_ci_upper - log_ci_lower) / 3.92

    if log_se <= 0:
        return np.nan

    # Z-score
    z = abs(log_wr - log_null) / log_se

    # Two-tailed p-value
    from scipy.stats import norm
    p_value = 2 * (1 - norm.cdf(z))

    return float(p_value)


def adjust_pvalues_holm(
    p_values: List[float],
    alpha: float = 0.05,
) -> Tuple[List[float], List[bool]]:
    """Apply Holm-Bonferroni correction for multiple comparisons.

    Args:
        p_values: List of unadjusted p-values
        alpha: Family-wise error rate

    Returns:
        Tuple of (adjusted_p_values, significant_flags)
    """
    n = len(p_values)
    if n == 0:
        return [], []

    # Handle NaN p-values
    valid_idx = [i for i, p in enumerate(p_values) if np.isfinite(p)]
    valid_p = [p_values[i] for i in valid_idx]

    if not valid_p:
        return [np.nan] * n, [False] * n

    # Sort by p-value
    sorted_indices = np.argsort(valid_p)
    sorted_p = [valid_p[i] for i in sorted_indices]

    # Holm-Bonferroni adjustment
    adjusted_p_sorted = []
    cummax = 0.0
    for i, p in enumerate(sorted_p):
        m = len(valid_p)
        adjusted = p * (m - i)
        adjusted = max(adjusted, cummax)  # Enforce monotonicity
        adjusted = min(adjusted, 1.0)  # Cap at 1
        cummax = adjusted
        adjusted_p_sorted.append(adjusted)

    # Map back to original order
    adjusted_p = [np.nan] * n
    for i, orig_idx in enumerate(valid_idx):
        # Find position in sorted order
        sort_pos = list(sorted_indices).index(valid_idx.index(orig_idx))
        adjusted_p[orig_idx] = adjusted_p_sorted[sort_pos]

    # Determine significance
    significant = [
        adj_p <= alpha if np.isfinite(adj_p) else False
        for adj_p in adjusted_p
    ]

    return adjusted_p, significant


def add_pvalues_to_multi_arm_results(
    results: Dict[str, Any],
    alpha: float = 0.05,
) -> Dict[str, Any]:
    """Add p-values and Holm-adjusted p-values to multi-arm results.

    Modifies the comparisons in place to add:
    - p_value: unadjusted p-value from bootstrap CI
    - p_value_holm: Holm-adjusted p-value
    - significant_holm: True if significant after Holm correction
    """
    comparisons = results.get("comparisons", [])

    # Compute unadjusted p-values
    p_values = []
    for comp in comparisons:
        p = compute_pvalue_from_bootstrap(
            comp.get("wr", np.nan),
            comp.get("ci_lower", np.nan),
            comp.get("ci_upper", np.nan),
        )
        comp["p_value"] = p
        p_values.append(p)

    # Apply Holm correction
    adjusted_p, significant = adjust_pvalues_holm(p_values, alpha)

    for comp, adj_p, sig in zip(comparisons, adjusted_p, significant):
        comp["p_value_holm"] = adj_p
        comp["significant_holm"] = sig

    # Update summary
    results["summary"]["alpha"] = alpha
    results["summary"]["n_significant_nominal"] = sum(
        1 for p in p_values if np.isfinite(p) and p < alpha
    )
    results["summary"]["n_significant_holm"] = sum(significant)

    return results
