# WinRatioPy

`WinRatioPy` is a tested Python package for prioritized clinical outcomes. It supports assigned-pair win ratios, all-pair generalized pairwise comparisons (GPC), propensity-score matching and weighting, tier-level decomposition, and cluster-aware inference.

The repository also contains a synthetic public demonstrator for a national minimally invasive distal pancreatectomy (MIDP) analysis. Protected AFC registry data, manuscript-generation files, and observed manuscript estimates are not included.

## Install

```bash
python -m pip install -e ".[dev,docs,study]"
```

The preferred import is `winratiopy`. Existing code that imports `winratio` remains compatible.

## Quick Start

```python
import pandas as pd

from winratiopy import Outcome, WinRatio

data = pd.DataFrame(
    {
        "arm": ["A", "B", "A", "B"],
        "pair": [1, 1, 2, 2],
        "death90": [0, 0, 1, 1],
        "clavien": [0, 3, 4, 3],
        "popf": [0, 1, 2, 0],
        "readmission": [0, 0, 0, 1],
        "los": [7, 10, 12, 9],
    }
)

analysis = WinRatio(
    group="arm",
    arm_a="A",
    arm_b="B",
    outcomes=[
        Outcome.binary("death90", name="90-day mortality", terminal=True),
        Outcome.ordinal("clavien", name="Clavien-Dindo severity"),
        Outcome.ordinal("popf", name="POPF severity"),
        Outcome.binary("readmission", name="Readmission"),
        Outcome.continuous("los", name="Length of stay", margin=2),
    ],
)

result = analysis.fit(data, pair_id="pair", n_boot=1000, seed=42)
print(result.summary())
print(result.tiers())
```

When both patients have a terminal event and no valid event time is available, their comparison stops as a tie. Lower-priority outcomes are not used to rank two deaths.

## Adjustment Workflows

Matching defaults to complete cases; simple single imputation must be explicitly requested.

```python
from winratiopy import propensity_match

matched = propensity_match(
    cohort,
    treat_col="arm",
    treated_value="A",
    covariates=["age", "bmi", "asa_ge3", "histology"],
    exact_cols=["year", "hospital_type", "neoadjuvant"],
    method="optimal",
    missing="drop",
)
```

For analyses using all available records, `estimate_propensity_weights` provides overlap, ATT, and ATE weights. `compute_weighted_gpc` uses subject-weight cross-products and returns the WR, favorable-pair probability, win difference, information rate, and tier attribution.

For center-level exposures, `bootstrap_propensity_matched_win_ratio` resamples centers within arm, refits the propensity score, rematches, and recomputes the assigned-pair WR. `bootstrap_propensity_weighted_gpc` performs the analogous score-refitted weighting analysis.

## MIDP Demonstrator

The public configuration follows the current analysis architecture:

- fixed higher-volume definition: more than 10 **all minimally invasive pancreatic resections** per complete contributed year;
- primary hierarchy: 90-day mortality, major complications, CR-POPF, readmission, exact completed-day LOS;
- both deaths tie when time to death is unavailable;
- graded morbidity/POPF and 1-day, 2-day, no-LOS, and categorical (`<=7`, `8-13`, `>13` days) LOS sensitivities;
- IO and TBO reconstructed from explicit components;
- complete-case 1:1 optimal propensity matching as the public primary design;
- matched-sample all-pair GPC and overlap-weighted GPC sensitivities.

The committed dataset is synthetic. Its estimates demonstrate the software and are not the AFC manuscript results.

```bash
python -m studies.distal_pancreatectomy.export_public_data
python -m studies.distal_pancreatectomy.run_public_analysis --n-boot 400
```

Key files:

- [Public analysis configuration](studies/distal_pancreatectomy/config/primary_analysis.yaml)
- [Synthetic public dataset](data/public/distal_pancreatectomy_public.csv)
- [Public result manifest](results/public/reproducibility_manifest.json)
- [Study-layer documentation](studies/distal_pancreatectomy/README.md)

## Verification

```bash
pytest
ruff check src tests studies examples
mkdocs build --strict
python -m build
```

## Repository Layout

- `src/winratiopy`: preferred import interface.
- `src/winratio`: backward-compatible implementation package.
- `studies/distal_pancreatectomy`: public-safe MIDP workflow.
- `data/public`: synthetic input and disclosure manifest.
- `results/public`: reproducible synthetic outputs.
- `tests`: unit and end-to-end tests.
- `docs`: methodology, API, and reproducibility documentation.

## Citation

Marc-Anthony Chouillard is the primary code author and maintainer. Associated study authors include Clément Pastier and Sébastien Gaujoux for the Association Française de Chirurgie Study Group. Cite the software metadata in [CITATION.cff](CITATION.cff); article details will be added after publication.

License: MIT.
