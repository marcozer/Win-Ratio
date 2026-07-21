# Workflows

## Assigned-Pair Analysis

1. Define the exposure and covariates before outcome inspection.
2. Run `propensity_match(..., missing="drop")` or supply a prespecified external match.
3. Check SMD, KS, overlap, retained records, and center contribution.
4. Fit `WinRatio(...).fit(matched_df, pair_id="PAIR_ID")`.
5. Use pair bootstrap for fixed-match inference or `bootstrap_propensity_matched_win_ratio` to include score and matching uncertainty.

## Weighted All-Pair Analysis

1. Estimate overlap, ATT, or ATE weights with `estimate_propensity_weights`.
2. Inspect weighted balance, ESS, and maximum weights.
3. Run `compute_weighted_gpc` with the generated weight column.
4. Use `bootstrap_propensity_weighted_gpc` when score-estimation uncertainty and center clustering must be represented.

## Multiple Imputation

Create multiple imputations outside the propensity model, estimate the score and endpoint separately in each completed dataset, and pool with a method appropriate to the estimand. Outcomes may inform imputation but must not enter the propensity score merely because they were used by the imputer. WinRatioPy never performs hidden single imputation.

## Public MIDP Demonstrator

```bash
python -m studies.distal_pancreatectomy.export_public_data
python -m studies.distal_pancreatectomy.run_public_analysis --n-boot 400
```

Outputs are written to `results/public` and are accompanied by a manifest that separates public synthetic results from protected-only analyses.
