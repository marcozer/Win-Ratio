"""Public package interface for WinRatioPy analyses."""

from .analysis import Outcome, WinRatio, WinRatioAnalysis, WinRatioResult
from .config import (
    MultiArmWinRatioConfig,
    WinRatioConfig,
    WinRatioOutcome,
    config_from_dict,
    multi_arm_config_from_dict,
)
from .diagnostics import balance_diagnostics, effective_sample_size
from .gpc import bootstrap_weighted_gpc, compute_weighted_gpc
from .inference import compute_e_value, compute_e_value_for_ci, logwr_wald_ci, logwr_wald_p_value
from .match import MatchResult, propensity_match
from .resampling import bootstrap_propensity_matched_win_ratio, bootstrap_propensity_weighted_gpc
from .summary import (
    bootstrap_p_value_from_samples,
    paired_risk_difference_bootstrap,
    summarize_component_outcomes,
    summarize_wr_metrics_from_overall,
)
from .weights import WeightingResult, estimate_propensity_weights
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

__version__ = "0.2.1"

__all__ = [
    "MatchResult",
    "MultiArmWinRatioConfig",
    "Outcome",
    "WeightingResult",
    "WinRatio",
    "WinRatioAnalysis",
    "WinRatioConfig",
    "WinRatioOutcome",
    "WinRatioResult",
    "balance_diagnostics",
    "bootstrap_p_value_from_samples",
    "bootstrap_propensity_matched_win_ratio",
    "bootstrap_propensity_weighted_gpc",
    "bootstrap_weighted_gpc",
    "bootstrap_win_ratio",
    "bootstrap_win_ratio_cluster",
    "bootstrap_win_ratio_cluster_within_arm",
    "bootstrap_win_ratio_matched",
    "bootstrap_win_ratio_multi_arm",
    "compute_e_value",
    "compute_e_value_for_ci",
    "compute_pvalue_from_bootstrap",
    "compute_weighted_gpc",
    "compute_win_ratio",
    "compute_win_ratio_all_pairs",
    "compute_win_ratio_matched",
    "compute_win_ratio_multi_arm",
    "config_from_dict",
    "effective_sample_size",
    "estimate_propensity_weights",
    "logwr_wald_ci",
    "logwr_wald_p_value",
    "multi_arm_config_from_dict",
    "propensity_match",
    "paired_risk_difference_bootstrap",
    "summarize_component_outcomes",
    "summarize_wr_metrics_from_overall",
]
