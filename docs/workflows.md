# Workflows

## Library Workflow

1. Load or construct a pandas `DataFrame`.
2. Build a `WinRatioConfig`.
3. Run `compute_win_ratio`.
4. Add bootstrap uncertainty estimation if required.

## Public Study Workflow

1. Generate the public dataset with `python -m studies.distal_pancreatectomy.export_public_data`.
2. Run `python -m studies.distal_pancreatectomy.run_public_analysis`.
3. Inspect the public analysis outputs written to `results/public`.

## Matching Workflow

1. Choose the treatment column and treated value.
2. Specify matching covariates and any exact-matching columns.
3. Run `propensity_match`.
4. Feed the matched data into a `WinRatioConfig` with `pair_strategy="matched"` and `pair_id="PAIR_ID"`.
