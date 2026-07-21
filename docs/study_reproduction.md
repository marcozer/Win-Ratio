# MIDP Study Demonstrator

The public workflow applies the current analysis architecture to synthetic records. It is intended for code inspection, execution, and unit testing; it does not reproduce observed AFC estimates.

## Locked Public Architecture

- Exposure: study-period mean of more than 10 all minimally invasive pancreatic resections per complete contributed year.
- Primary design: complete-case 1:1 optimal propensity matching without replacement, common support, and exact year-band, hospital-type, and neoadjuvant strata.
- Primary hierarchy: 90-day mortality, major complications, CR-POPF, readmission, exact completed-day LOS.
- Terminal rule: both deaths tie because time to death is unavailable.
- Sensitivities: 1-day and 2-day LOS margins; `<=7`, `8-13`, and `>13` day LOS categories; no LOS; graded Clavien and POPF severity.
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
