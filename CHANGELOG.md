# Changelog

## 0.2.1

- Aligned the public MIDP demonstrator with the v25 analysis architecture.
- Clarified that center volume is a supplied, previously published study-period mean of all minimally invasive pancreatic resections; MIDP-only counts cannot replace it.
- Made graded Clavien-Dindo severity, graded CR-POPF severity, and a 1-day LOS tie margin the public primary hierarchy.
- Updated exact-day, minimum 3-day, categorical, and no-LOS sensitivities, tests, documentation, and synthetic outputs.

## 0.2.0

- Branded the distribution as `WinRatioPy` and added the `winratiopy` import while preserving `winratio` compatibility.
- Added binary, ordinal, continuous, categorized, and terminal outcome tiers.
- Corrected shared terminal-event handling: when both patients die and no valid event time exists, lower tiers are not evaluated.
- Added assigned-pair WR, all-pair GPC, weighted GPC, and subject-, pair-, cluster-, propensity-refit/rematch-, and propensity-refit/weighting bootstrap workflows.
- Added explicit complete-case or opt-in simple-imputation matching; silent single imputation is no longer the default.
- Added overlap, ATT, and ATE weights, SMD/KS/variance diagnostics, and effective sample size.
- Updated the synthetic MIDP demonstrator to the fixed `>10` all-MIP/year volume definition, current hierarchy, LOS sensitivities, and component-derived IO/TBO comparators.

## 0.1.0

- Created a public `src/winratio` package for generic win-ratio analyses.
- Added a study-specific statistical-analysis layer under `studies/distal_pancreatectomy`.
- Replaced protected row-level data with a synthetic public fallback and public analysis outputs.
- Added repository documentation, MkDocs configuration, and a pytest suite.
