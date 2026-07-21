# API Reference

## High-Level Interface

- `Outcome` / `WinRatioOutcome`: binary, ordinal, or continuous tier definition.
- `WinRatio` / `WinRatioAnalysis`: two-arm analysis builder.
- `WinRatioResult.summary()`: estimate and optional interval.
- `WinRatioResult.tiers()`: tier-resolution table.

## Core Estimation

- `compute_win_ratio`
- `compute_win_ratio_all_pairs`
- `compute_win_ratio_matched`
- `compute_win_ratio_multi_arm`
- `compute_weighted_gpc`

## Bootstrap Inference

- `bootstrap_win_ratio`
- `bootstrap_win_ratio_matched`
- `bootstrap_win_ratio_cluster`
- `bootstrap_win_ratio_cluster_within_arm`
- `bootstrap_weighted_gpc`
- `bootstrap_propensity_matched_win_ratio`
- `bootstrap_propensity_weighted_gpc`

## Design

- `propensity_match`: 1:1 nearest or optimal matching.
- `estimate_propensity_weights`: overlap, ATT, or ATE weights.
- `balance_diagnostics`: SMD, variance ratio, and KS statistics.
- `effective_sample_size`: Kish ESS.
- `MatchResult` and `WeightingResult`: fitted design objects and diagnostics.

## Reporting and Inference Helpers

- `paired_risk_difference_bootstrap`
- `summarize_component_outcomes`
- `summarize_wr_metrics_from_overall`
- `logwr_wald_ci`
- `logwr_wald_p_value`
- `compute_e_value`
- `compute_e_value_for_ci`

The generic package contains no pancreatic-surgery-specific variable mapping. Study preprocessing belongs under `studies/`.
