# MIDP Study Demonstrator

The public workflow applies the current analysis architecture to synthetic records. It is intended for code inspection, execution, and unit testing; it does not reproduce observed AFC estimates.

## Locked Public Architecture

- Exposure: registry-provided, previously published study-period mean annual volume of all minimally invasive pancreatic resections; more than 10 procedures/y vs 10 or fewer.
- Provenance rule: MIDP-only counts cannot replace the all-MIP exposure; center-year reconstruction is an audit only.
- Primary design: complete-case 1:1 optimal propensity matching without replacement, common support, and exact year-band, hospital-type, and neoadjuvant strata.
- Primary hierarchy: 90-day mortality, graded Clavien-Dindo severity, graded CR-POPF severity, readmission, and LOS with differences of 0 or 1 completed day tied.
- Terminal rule: both deaths tie because time to death is unavailable.
- Sensitivities: exact-day and minimum 3-day LOS differences; `<=7`, `8-13`, and `>13` day LOS categories; and no LOS.
- Efficiency sensitivities: matched-sample all-pair GPC and overlap-weighted all-pair GPC.
- Binary comparators: component-derived ideal outcome and textbook outcome.

## Outputs

- `win_ratio_summary.json`: principal estimands and bootstrap metadata.
- `matching_balance.csv`: pre/post matching SMD, KS, and variance diagnostics.
- `hierarchy_sensitivities.csv`: LOS and severity variants.
- `tier_resolution.csv`: conditional first-resolving tiers.
- `binary_benchmarks.csv`: IO/TBO rates, matched differences, and discordance.
- `overlap_weighting_balance.csv`: weighted diagnostics.
- `win_ratio_overview.svg`: editable-text summary figure.

The manuscript's 5000-replicate AFC interval, 50-imputation analysis, observed clinical screen, and trial simulations require protected data and are listed as protected-only in the manifest.
