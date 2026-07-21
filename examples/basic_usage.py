from __future__ import annotations

import pandas as pd

from winratiopy import Outcome, WinRatio, compute_weighted_gpc, estimate_propensity_weights

data = pd.DataFrame(
    {
        "arm": ["A", "B", "A", "B", "A", "B"],
        "pair": [1, 1, 2, 2, 3, 3],
        "age": [58, 59, 66, 64, 51, 53],
        "bmi": [25.0, 25.4, 29.1, 28.8, 23.0, 23.8],
        "death90": [0, 0, 1, 1, 0, 0],
        "clavien": [0, 3, 4, 3, 0, 0],
        "popf": [0, 1, 2, 0, 0, 0],
        "readmission": [0, 0, 0, 1, 1, 0],
        "los": [7, 10, 12, 9, 6, 8],
    }
)

outcomes = [
    Outcome.binary("death90", name="90-day mortality", terminal=True),
    Outcome.ordinal("clavien", name="Clavien-Dindo severity"),
    Outcome.ordinal("popf", name="POPF severity"),
    Outcome.binary("readmission", name="Readmission"),
    Outcome.continuous("los", name="Length of stay", margin=2),
]

analysis = WinRatio(group="arm", arm_a="A", arm_b="B", outcomes=outcomes)
matched = analysis.fit(data, pair_id="pair", n_boot=200, seed=42)
print("Assigned-pair WR")
print(matched.summary())
print(matched.tiers().to_string(index=False))

weighting = estimate_propensity_weights(
    data,
    treatment="arm",
    treated="A",
    covariates=["age", "bmi"],
    estimand="overlap",
    trim_common_support=False,
)
weighted = compute_weighted_gpc(
    weighting.weighted_df,
    analysis.fit(data).config,
    weight_col="analysis_weight",
)
print("\nOverlap-weighted all-pair GPC")
print(weighted)
