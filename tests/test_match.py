from __future__ import annotations

import pandas as pd

from winratio import propensity_match


def test_propensity_match_creates_pair_ids() -> None:
    df = pd.DataFrame(
        {
            "treatment_group": ["HIGH", "HIGH", "HIGH", "OTHER", "OTHER", "OTHER"],
            "age_band": ["50-59", "60-69", "70-79", "50-59", "60-69", "70-79"],
            "sex": ["MALE", "FEMALE", "MALE", "MALE", "FEMALE", "MALE"],
            "asa_group": ["ASA2", "ASA3", "ASA3", "ASA2", "ASA3", "ASA3"],
        }
    )
    result = propensity_match(
        df,
        treat_col="treatment_group",
        treated_value="HIGH",
        covariates=["age_band", "sex", "asa_group"],
        method="nearest",
    )
    assert "PAIR_ID" in result.matched_df.columns
    assert result.pairs >= 1
