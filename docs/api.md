# API Reference

Primary public objects:

- `WinRatioOutcome`
- `WinRatioConfig`
- `MultiArmWinRatioConfig`
- `compute_win_ratio`
- `compute_win_ratio_all_pairs`
- `compute_win_ratio_matched`
- `bootstrap_win_ratio`
- `bootstrap_win_ratio_matched`
- `bootstrap_win_ratio_cluster`
- `compute_win_ratio_multi_arm`
- `propensity_match`
- `logwr_wald_ci`
- `logwr_wald_p_value`
- `compute_e_value`
- `compute_e_value_for_ci`

The generic package is intentionally free of paper-specific preprocessing logic. Dataset transformation code belongs in the study layer.
