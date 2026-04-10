"""Public package interface for win-ratio analyses."""

from .config import (
    MultiArmWinRatioConfig,
    WinRatioConfig,
    WinRatioOutcome,
    config_from_dict,
    multi_arm_config_from_dict,
)
from .inference import compute_e_value, compute_e_value_for_ci, logwr_wald_ci, logwr_wald_p_value
from .match import MatchResult, propensity_match
from .summary import bootstrap_p_value_from_samples, summarize_component_outcomes, summarize_wr_metrics_from_overall
from .wr import (
    bootstrap_win_ratio,
    bootstrap_win_ratio_cluster,
    bootstrap_win_ratio_cluster_within_arm,
    bootstrap_win_ratio_matched,
    bootstrap_win_ratio_multi_arm,
    compute_pvalue_from_bootstrap,
    compute_win_ratio,
    compute_win_ratio_all_pairs,
    compute_win_ratio_matched,
    compute_win_ratio_multi_arm,
)

__version__ = "0.1.0"

__all__ = [
    "MatchResult",
    "MultiArmWinRatioConfig",
    "WinRatioConfig",
    "WinRatioOutcome",
    "bootstrap_p_value_from_samples",
    "bootstrap_win_ratio",
    "bootstrap_win_ratio_cluster",
    "bootstrap_win_ratio_cluster_within_arm",
    "bootstrap_win_ratio_matched",
    "bootstrap_win_ratio_multi_arm",
    "compute_e_value",
    "compute_e_value_for_ci",
    "compute_pvalue_from_bootstrap",
    "compute_win_ratio",
    "compute_win_ratio_all_pairs",
    "compute_win_ratio_matched",
    "compute_win_ratio_multi_arm",
    "config_from_dict",
    "logwr_wald_ci",
    "logwr_wald_p_value",
    "multi_arm_config_from_dict",
    "propensity_match",
    "summarize_component_outcomes",
    "summarize_wr_metrics_from_overall",
]
