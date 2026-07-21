# Configuration Reference

A two-arm configuration requires `group_col`, `arm_a`, `arm_b`, and an ordered `outcomes` list.

```yaml
group_col: treatment_group
arm_a: HIGH_VOLUME
arm_b: OTHER
pair_strategy: all_pairs
outcomes:
  - name: Mortality within 90 days
    column: mort90
    kind: binary
    direction: lower
    terminal: true
    terminal_value: 1
  - name: Length of stay
    column: los_days
    kind: continuous
    direction: lower
    tie_tol: 2
```

Outcome fields:

- `kind`: `binary`, `ordinal`, or `continuous`;
- `direction`: `lower` or `higher` values are favorable;
- `tie_tol`: inclusive continuous tie margin;
- `cutpoints`: ordered boundaries for categorization;
- `terminal`: stop lower tiers when both values equal `terminal_value`;
- `missing_is`: `tie`, `win`, or `loss` (default `tie`).

The MIDP configuration also records its exposure definition, matching covariates, exact strata, missing-data policy, benchmark definitions, and hierarchy sensitivities in `studies/distal_pancreatectomy/config/primary_analysis.yaml`.
