from __future__ import annotations

from typing import Any, Dict, List

import numpy as np
import pandas as pd

from .config import WinRatioConfig


def summarize_component_outcomes(df: pd.DataFrame, cfg: WinRatioConfig) -> pd.DataFrame:
    """Summarize component outcomes (by arm) for a given WR config.

    Returns a wide table: one row per outcome, with arm-specific counts and
    rates or summary statistics.
    """
    if cfg.group_col not in df.columns:
        raise ValueError(f"group_col {cfg.group_col!r} not found in dataframe")

    arms = [(cfg.arm_a, "A"), (cfg.arm_b, "B")]
    rows: List[Dict[str, Any]] = []

    for oc in cfg.outcomes:
        row: Dict[str, Any] = {
            "outcome": oc.name,
            "column": oc.column,
            "kind": oc.kind,
            "direction": oc.direction,
            "tie_tol": float(oc.tie_tol),
            "missing_is": oc.missing_is,
        }

        for arm_value, arm_tag in arms:
            sub = df[df[cfg.group_col] == arm_value]
            s = sub[oc.column] if oc.column in sub.columns else pd.Series(dtype=float)
            n_total = int(sub.shape[0])
            n_nonmissing = int(s.notna().sum()) if n_total else 0

            row[f"{arm_tag}_arm_value"] = arm_value
            row[f"{arm_tag}_n"] = n_total
            row[f"{arm_tag}_n_nonmissing"] = n_nonmissing

            if oc.kind == "binary":
                events = int((s == 1).sum()) if n_nonmissing else 0
                rate = float(events / n_nonmissing) if n_nonmissing else np.nan
                row[f"{arm_tag}_events"] = events
                row[f"{arm_tag}_rate"] = rate
            else:
                x = pd.to_numeric(s, errors="coerce")
                row[f"{arm_tag}_mean"] = float(x.mean()) if n_nonmissing else np.nan
                row[f"{arm_tag}_sd"] = float(x.std(ddof=1)) if n_nonmissing else np.nan
                row[f"{arm_tag}_median"] = float(x.median()) if n_nonmissing else np.nan
                row[f"{arm_tag}_q1"] = float(x.quantile(0.25)) if n_nonmissing else np.nan
                row[f"{arm_tag}_q3"] = float(x.quantile(0.75)) if n_nonmissing else np.nan

        rows.append(row)

    return pd.DataFrame(rows)


def summarize_wr_metrics_from_overall(overall: Dict[str, Any]) -> pd.DataFrame:
    """Derive reporting-friendly WR metrics from an overall WR result dict."""
    wins = int(overall.get("wins", 0))
    losses = int(overall.get("losses", 0))
    ties = int(overall.get("ties", 0))
    wr = overall.get("wr", np.nan)
    details = overall.get("details", {}) or {}
    tier_wins = details.get("tier_wins") or []
    tier_losses = details.get("tier_losses") or []

    total_pairs = wins + losses + ties
    decided = wins + losses

    rows: List[Dict[str, Any]] = []
    rows.append({"metric": "total_pairs", "value": total_pairs})
    rows.append({"metric": "wins", "value": wins})
    rows.append({"metric": "losses", "value": losses})
    rows.append({"metric": "ties", "value": ties})
    rows.append({"metric": "win_ratio", "value": wr})
    rows.append({"metric": "decided_pairs", "value": decided})
    rows.append({"metric": "decided_pct", "value": (decided / total_pairs) if total_pairs else np.nan})
    rows.append({"metric": "ties_pct", "value": (ties / total_pairs) if total_pairs else np.nan})
    rows.append({"metric": "net_benefit", "value": ((wins - losses) / total_pairs) if total_pairs else np.nan})

    cum_w = 0
    cum_l = 0
    for i, (tier_win, tier_loss) in enumerate(zip(tier_wins, tier_losses), 1):
        tier_win = int(tier_win)
        tier_loss = int(tier_loss)
        resolved = tier_win + tier_loss
        cum_w += tier_win
        cum_l += tier_loss
        cum_wr = np.nan
        if cum_l > 0:
            cum_wr = cum_w / cum_l
        elif cum_w > 0 and cum_l == 0:
            cum_wr = np.inf

        rows.append({"metric": f"tier{i}_wins", "value": tier_win})
        rows.append({"metric": f"tier{i}_losses", "value": tier_loss})
        rows.append({"metric": f"tier{i}_resolved", "value": resolved})
        rows.append({"metric": f"tier{i}_resolved_pct", "value": (resolved / total_pairs) if total_pairs else np.nan})
        rows.append({"metric": f"tier{i}_cum_wr", "value": cum_wr})

    return pd.DataFrame(rows)


def paired_risk_difference_bootstrap(
    df: pd.DataFrame,
    cfg: WinRatioConfig,
    n_boot: int = 1000,
    seed: int = 42,
    alpha: float = 0.05,
) -> pd.DataFrame:
    """Estimate binary outcome risk differences after 1:1 matching.

    The estimate is arm A event risk minus arm B event risk. Bootstrap samples
    resample complete matched pairs with replacement, so concordant pairs remain
    in the estimate with a pair-level difference of zero.
    """
    if cfg.pair_strategy != "matched" or not cfg.pair_id:
        raise ValueError("paired_risk_difference_bootstrap requires matched strategy and pair_id")
    if cfg.group_col not in df.columns:
        raise ValueError(f"group_col {cfg.group_col!r} not found in dataframe")
    if cfg.pair_id not in df.columns:
        raise ValueError(f"pair_id {cfg.pair_id!r} not found in dataframe")
    if n_boot <= 0:
        raise ValueError("n_boot must be positive")
    if not 0.0 < alpha < 1.0:
        raise ValueError("alpha must be in (0, 1)")

    rng = np.random.default_rng(seed)
    rows: List[Dict[str, Any]] = []

    for oc in cfg.outcomes:
        if oc.kind != "binary":
            continue

        pair_diffs: List[float] = []
        a_values: List[int] = []
        b_values: List[int] = []
        n_eligible_pairs = 0

        for _, g in df.groupby(cfg.pair_id):
            ga = g[g[cfg.group_col] == cfg.arm_a]
            gb = g[g[cfg.group_col] == cfg.arm_b]
            if len(ga) != 1 or len(gb) != 1:
                continue

            n_eligible_pairs += 1
            a_val = pd.to_numeric(pd.Series([ga.iloc[0].get(oc.column)]), errors="coerce").iloc[0]
            b_val = pd.to_numeric(pd.Series([gb.iloc[0].get(oc.column)]), errors="coerce").iloc[0]
            if pd.isna(a_val) or pd.isna(b_val):
                continue
            if a_val not in (0, 1) or b_val not in (0, 1):
                continue

            a_int = int(a_val)
            b_int = int(b_val)
            a_values.append(a_int)
            b_values.append(b_int)
            pair_diffs.append(float(a_int - b_int))

        diffs = np.asarray(pair_diffs, dtype=float)
        a_arr = np.asarray(a_values, dtype=int)
        b_arr = np.asarray(b_values, dtype=int)
        n_complete = int(diffs.size)

        if n_complete:
            risk_a = float(a_arr.mean())
            risk_b = float(b_arr.mean())
            rd = float(diffs.mean())
            samples = np.empty(n_boot, dtype=float)
            for i in range(n_boot):
                sample_idx = rng.integers(0, n_complete, size=n_complete)
                samples[i] = float(diffs[sample_idx].mean())
            ci = (
                float(np.percentile(samples, 100 * alpha / 2)),
                float(np.percentile(samples, 100 * (1 - alpha / 2))),
            )
        else:
            risk_a = np.nan
            risk_b = np.nan
            rd = np.nan
            ci = (np.nan, np.nan)

        a_event_b_no_event = int(((a_arr == 1) & (b_arr == 0)).sum()) if n_complete else 0
        a_no_event_b_event = int(((a_arr == 0) & (b_arr == 1)).sum()) if n_complete else 0
        both_event = int(((a_arr == 1) & (b_arr == 1)).sum()) if n_complete else 0
        neither_event = int(((a_arr == 0) & (b_arr == 0)).sum()) if n_complete else 0

        rows.append(
            {
                "outcome": oc.name,
                "column": oc.column,
                "A_arm_value": cfg.arm_a,
                "B_arm_value": cfg.arm_b,
                "n_pairs_eligible": int(n_eligible_pairs),
                "n_pairs_complete": n_complete,
                "n_pairs_excluded_missing_or_invalid": int(n_eligible_pairs - n_complete),
                "A_events": int(a_arr.sum()) if n_complete else 0,
                "B_events": int(b_arr.sum()) if n_complete else 0,
                "A_risk": risk_a,
                "B_risk": risk_b,
                "risk_difference_A_minus_B": rd,
                "ci_lower": ci[0],
                "ci_upper": ci[1],
                "alpha": float(alpha),
                "n_boot": int(n_boot),
                "seed": int(seed),
                "both_event": both_event,
                "neither_event": neither_event,
                "A_event_B_no_event": a_event_b_no_event,
                "A_no_event_B_event": a_no_event_b_event,
            }
        )

    return pd.DataFrame(rows)


def bootstrap_p_value_from_samples(wr_samples: List[float], null_wr: float = 1.0) -> float:
    """Two-sided p-value based on bootstrap WR samples relative to a null value.

    This is a descriptive bootstrap-based p-value (not a permutation p-value).
    """
    if not wr_samples:
        return float("nan")
    s = np.asarray(wr_samples, dtype=float)
    s = s[np.isfinite(s)]
    if s.size == 0:
        return float("nan")
    p_low = float(np.mean(s <= null_wr))
    p_high = float(np.mean(s >= null_wr))
    return float(2.0 * min(p_low, p_high))
