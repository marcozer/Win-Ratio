from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Optional

import numpy as np
import pandas as pd

from .config import WinRatioConfig, WinRatioOutcome
from .gpc import bootstrap_weighted_gpc, compute_weighted_gpc
from .wr import (
    bootstrap_win_ratio,
    bootstrap_win_ratio_cluster,
    bootstrap_win_ratio_cluster_within_arm,
    bootstrap_win_ratio_matched,
    compute_win_ratio,
)


@dataclass
class WinRatioResult:
    """Fitted estimate plus reporting helpers."""

    estimate: dict[str, Any]
    config: WinRatioConfig
    bootstrap: Optional[dict[str, Any]] = None
    method: str = "all_pairs"

    def summary(self) -> dict[str, Any]:
        result = dict(self.estimate)
        if self.bootstrap is not None:
            result["ci_lower"], result["ci_upper"] = self.bootstrap["ci"]
            result["n_boot"] = self.bootstrap["n_boot"]
        return result

    def tiers(self) -> pd.DataFrame:
        details = self.estimate.get("details", {}) or {}
        wins = details.get("tier_wins", [])
        losses = details.get("tier_losses", [])
        total = float(self.estimate.get("wins", 0) + self.estimate.get("losses", 0) + self.estimate.get("ties", 0))
        rows = []
        remaining = total
        for index, outcome in enumerate(self.config.outcomes):
            tier_wins = float(wins[index]) if index < len(wins) else 0.0
            tier_losses = float(losses[index]) if index < len(losses) else 0.0
            resolved = tier_wins + tier_losses
            rows.append(
                {
                    "priority": index + 1,
                    "outcome": outcome.name,
                    "wins": tier_wins,
                    "losses": tier_losses,
                    "resolved": resolved,
                    "conditional_resolution": resolved / remaining if remaining > 0 else np.nan,
                    "overall_resolution": resolved / total if total > 0 else np.nan,
                }
            )
            remaining -= resolved
        return pd.DataFrame(rows)


class WinRatioAnalysis:
    """Convenient object-oriented interface for two-arm WR/GPC analyses."""

    def __init__(
        self,
        *,
        group: str,
        arm_a: Any,
        arm_b: Any,
        outcomes: Iterable[WinRatioOutcome],
        strata: Optional[Iterable[str]] = None,
    ) -> None:
        self.group = group
        self.arm_a = arm_a
        self.arm_b = arm_b
        self.outcomes = list(outcomes)
        self.strata = list(strata) if strata is not None else None
        if not self.outcomes:
            raise ValueError("at least one outcome tier is required")

    def fit(
        self,
        df: pd.DataFrame,
        *,
        pair_id: Optional[str] = None,
        weight_col: Optional[str] = None,
        cluster_col: Optional[str] = None,
        cluster_within_arm: bool = False,
        n_boot: int = 0,
        seed: int = 42,
    ) -> WinRatioResult:
        """Fit matched-pair WR, all-pair WR, or weighted all-pair GPC."""

        if pair_id is not None and weight_col is not None:
            raise ValueError("choose assigned-pair WR or weighted all-pair GPC, not both")
        strategy = "matched" if pair_id is not None else "all_pairs"
        cfg = WinRatioConfig(
            group_col=self.group,
            arm_a=self.arm_a,
            arm_b=self.arm_b,
            outcomes=self.outcomes,
            strata=self.strata,
            pair_strategy=strategy,
            pair_id=pair_id,
        )

        if weight_col is not None:
            estimate = compute_weighted_gpc(df, cfg, weight_col=weight_col)
            bootstrap = (
                bootstrap_weighted_gpc(
                    df,
                    cfg,
                    weight_col=weight_col,
                    cluster_col=cluster_col,
                    n_boot=n_boot,
                    seed=seed,
                )
                if n_boot
                else None
            )
            return WinRatioResult(estimate, cfg, bootstrap, method="weighted_gpc")

        estimate = compute_win_ratio(df, cfg)["overall"]
        bootstrap = None
        if n_boot:
            if pair_id is not None:
                bootstrap = bootstrap_win_ratio_matched(df, cfg, n_boot=n_boot, seed=seed)
            elif cluster_col is not None:
                bootstrap_function = (
                    bootstrap_win_ratio_cluster_within_arm if cluster_within_arm else bootstrap_win_ratio_cluster
                )
                bootstrap = bootstrap_function(df, cfg, cluster_col=cluster_col, n_boot=n_boot, seed=seed)
            else:
                bootstrap = bootstrap_win_ratio(df, cfg, n_boot=n_boot, seed=seed)
        return WinRatioResult(estimate, cfg, bootstrap, method=strategy)


WinRatio = WinRatioAnalysis
Outcome = WinRatioOutcome
