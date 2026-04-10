# Configuration Reference

The study layer uses YAML for reproducible analysis configuration.

Required fields for a two-arm win-ratio configuration:

- `group_col`
- `arm_a`
- `arm_b`
- `outcomes`

Each outcome requires:

- `name`
- `column`
- `kind`: `binary` or `continuous`
- `direction`: `lower` or `higher`

Optional outcome fields:

- `tie_tol`
- `missing_is`
- `los_tolerance_mode`
- `los_threshold`

The public study configuration lives in `studies/distal_pancreatectomy/config/primary_analysis.yaml`.
