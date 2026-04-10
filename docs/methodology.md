# Methodology

The win ratio compares two study arms using a prioritized sequence of outcomes. Each cross-arm pair is evaluated against the highest-priority outcome first. If that comparison is tied, the next outcome is used, and so on until the pair is resolved or all outcomes are tied.

The package supports:

- binary outcomes where either lower or higher values are favorable
- continuous outcomes with exact ties, one-day tolerance rules, or threshold-based LOS comparisons
- all-pairs comparisons
- matched-pair comparisons
- multi-arm designs reduced to pairwise win-ratio comparisons
- bootstrap uncertainty estimation at the subject, matched-pair, or cluster level

The public study example uses a standard postoperative hierarchy:

1. Mortality
2. Major complications
3. Clinically relevant pancreatic fistula
4. Reoperation
5. Readmission
6. Length of stay
