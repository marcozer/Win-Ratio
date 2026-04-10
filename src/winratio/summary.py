from __future__ import annotations

from typing import Dict, Any, List

import numpy as np
import pandas as pd

from .config import WinRatioConfig, WinRatioOutcome


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
    for i, (w, l) in enumerate(zip(tier_wins, tier_losses), 1):
        w = int(w)
        l = int(l)
        resolved = w + l
        cum_w += w
        cum_l += l
        cum_wr = np.nan
        if cum_l > 0:
            cum_wr = cum_w / cum_l
        elif cum_w > 0 and cum_l == 0:
            cum_wr = np.inf

        rows.append({"metric": f"tier{i}_wins", "value": w})
        rows.append({"metric": f"tier{i}_losses", "value": l})
        rows.append({"metric": f"tier{i}_resolved", "value": resolved})
        rows.append({"metric": f"tier{i}_resolved_pct", "value": (resolved / total_pairs) if total_pairs else np.nan})
        rows.append({"metric": f"tier{i}_cum_wr", "value": cum_wr})

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
