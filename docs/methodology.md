# Methodology

## Hierarchical comparison

Each cross-arm pair is compared at the highest-priority outcome. A difference resolves the pair; a tie advances to the next tier. The result is an arm-A win, arm-B win, or complete tie.

The win ratio is arm-A wins divided by arm-B wins. Ties remain in information-yield and win-difference calculations but are excluded from the ratio denominator and numerator.

Supported tiers:

- binary events, with lower or higher values favorable;
- ordinal severity values;
- continuous values with a clinical tie margin;
- categorized continuous values using ordered cut points;
- terminal events that stop lower-tier evaluation when both patients experience the event.

For example, `Outcome.continuous("los", margin=2)` treats LOS differences of 0, 1, or 2 completed days as ties. `Outcome.ordinal("los", cutpoints=[7, 13])` creates the categories `<=7`, `8-13`, and `>13` days.

## Estimands

**Assigned-pair WR** compares only the records assigned to the same matched pair. It targets retained treated records represented by the matching design.

**All-pair GPC** compares every arm-A record with every arm-B record, optionally within strata. On a matched sample it is an efficiency sensitivity, not the assigned-pair estimand.

**Weighted GPC** multiplies arm-specific subject weights for each cross-arm comparison. The result includes WR, favorable-pair probability, win difference, information rate, and tier attribution.

These estimands are related but not interchangeable; the analysis should name which one is primary.

## Adjustment

`propensity_match` performs 1:1 nearest-neighbor or optimal matching without replacement. Covariates must be named explicitly so outcome columns cannot enter by accident. Complete cases are the default. `missing="simple"` is available only as an explicit option and should not be confused with multiple imputation.

`estimate_propensity_weights` estimates overlap, ATT, or ATE weights. Multiply imputed datasets should estimate the score separately within each imputation; WinRatioPy does not silently create or pool imputations.

Design diagnostics include SMD, absolute SMD, variance ratio, weighted KS distance, weight summaries, and Kish effective sample size.

## Uncertainty

Available bootstrap units include subjects, assigned pairs, and clusters. For cluster-level exposures, `bootstrap_propensity_matched_win_ratio` resamples clusters separately within arm, refits the propensity model, rematches, and recomputes the WR. `bootstrap_propensity_weighted_gpc` similarly refits weights in every cluster bootstrap sample.

Fixed-match pair bootstrap and fixed-weight cluster bootstrap remain useful when the design itself is intentionally conditioned on, but they quantify less uncertainty than score-refitted analyses.

## Interpretation

Tier counts describe where comparisons were first resolved conditional on all preceding tiers tying. They are not independent component effects. A higher information rate also does not prove higher statistical power; efficiency depends on the data-generating mechanism, hierarchy, tie margins, and binary thresholds.
