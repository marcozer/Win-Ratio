# Win Ratio Statistics Repository

If you cite this repository in academic work, please cite the associated article by Marc-Anthony Chouillard et al.; full publication details will be added here once the paper is published.

Associated study authors: Marc-Anthony Chouillard ([ORCID 0009-0007-6439-6111](https://orcid.org/0009-0007-6439-6111)), Clément Pastier ([ORCID 0000-0002-7736-3999](https://orcid.org/0000-0002-7736-3999)), and Sébastien Gaujoux ([ORCID 0000-0002-1072-7639](https://orcid.org/0000-0002-1072-7639)), for the [Association Française de Chirurgie Study Group](https://www.association-francaise-chirurgie.fr/).

This repository is the public statistical-analysis repository for the distal pancreatectomy study submitted to *JAMA Surgery*. It has two deliverables:

1. A reusable Python library, [`winratio`](/Users/marc-anthony/NC/main/academic/win_ratio/src/winratio), for propensity-score matching and hierarchical win-ratio analysis in retrospective cohorts.
2. A study-specific analysis layer in [`studies/distal_pancreatectomy`](/Users/marc-anthony/NC/main/academic/win_ratio/studies/distal_pancreatectomy) that reproduces the statistical analysis from a public-safe schema.

Marc-Anthony Chouillard is the primary code author and maintainer.

The motivating clinical question is whether patients undergoing minimally invasive distal pancreatectomy have better prioritized postoperative outcomes when treated in higher-volume centers than in lower-volume centers. The repository therefore combines a general-purpose library for retrospective comparative analyses with a concrete distal-pancreatectomy example using propensity-score matching followed by hierarchical win-ratio estimation.

## Public vs Protected Material

- Included here: generic analysis code, synthetic public study data, analysis configurations, public summary outputs, tests, and documentation.
- Excluded from this public tree: raw registry exports, direct identifiers, site names, exact dates, free-text clinical narratives, manuscript-generation files, submission files, and legacy private analyses.
- The committed study dataset is a synthetic fallback. The repository keeps the public analysis schema used by the study scripts while avoiding unsafe row-level disclosure.

## Quick Start

Install the package and the analysis/documentation extras:

```bash
pip install -e .[dev,docs,study]
```

Run the generic package example:

```bash
python examples/basic_usage.py
```

Regenerate the public analysis dataset and outputs:

```bash
python -m studies.distal_pancreatectomy.export_public_data
python -m studies.distal_pancreatectomy.run_public_analysis
```

Run tests and build the documentation site:

```bash
pytest
mkdocs build --strict
```

## Library Example

```python
import pandas as pd

from winratio import WinRatioConfig, WinRatioOutcome, compute_win_ratio

df = pd.DataFrame(
    {
        "group": ["A", "A", "B", "B"],
        "mort90": [0, 0, 1, 0],
        "major_comp": [0, 1, 1, 1],
        "los_days": [7, 8, 11, 9],
    }
)

cfg = WinRatioConfig(
    group_col="group",
    arm_a="A",
    arm_b="B",
    outcomes=[
        WinRatioOutcome("Mortality", "mort90", "binary", "lower"),
        WinRatioOutcome("Major complications", "major_comp", "binary", "lower"),
        WinRatioOutcome("Length of stay", "los_days", "continuous", "lower"),
    ],
)

result = compute_win_ratio(df, cfg)["overall"]
print(result["wr"])
```

## Analysis Reproduction Example

The public analysis configuration is [`studies/distal_pancreatectomy/config/primary_analysis.yaml`](/Users/marc-anthony/NC/main/academic/win_ratio/studies/distal_pancreatectomy/config/primary_analysis.yaml). The default workflow:

1. Generates the public study dataset in [`data/public/distal_pancreatectomy_public.csv`](/Users/marc-anthony/NC/main/academic/win_ratio/data/public/distal_pancreatectomy_public.csv).
2. Runs all-pairs and matched statistical analyses.
3. Writes public summary outputs in [`results/public`](/Users/marc-anthony/NC/main/academic/win_ratio/results/public).

In the distal-pancreatectomy example, the primary matched analysis compares higher-volume centers with lower-volume centers and resolves each matched pair across an ordered hierarchy of postoperative outcomes: 90-day mortality, major complications, clinically relevant pancreatic fistula, readmission, and length of stay.

Example output:

![Example hierarchical flow output for the matched high-volume versus lower-volume center analysis](figure2_consort_flow.png)

*Example hierarchical flow output for the matched high-volume versus lower-volume center analysis.*

This figure illustrates how the hierarchical comparison is resolved tier by tier after propensity-score matching. It is included here as an example of the statistical-analysis output produced by the workflow, not as part of any manuscript-generation system.

## Repository Layout

- [`src/winratio`](/Users/marc-anthony/NC/main/academic/win_ratio/src/winratio): installable Python package.
- [`studies/distal_pancreatectomy`](/Users/marc-anthony/NC/main/academic/win_ratio/studies/distal_pancreatectomy): study-specific statistical-analysis workflow.
- [`examples`](/Users/marc-anthony/NC/main/academic/win_ratio/examples): generic package examples.
- [`data/public`](/Users/marc-anthony/NC/main/academic/win_ratio/data/public): synthetic public dataset and dataset manifest.
- [`results/public`](/Users/marc-anthony/NC/main/academic/win_ratio/results/public): committed public analysis outputs.
- [`docs`](/Users/marc-anthony/NC/main/academic/win_ratio/docs): documentation site content.
- [`tests`](/Users/marc-anthony/NC/main/academic/win_ratio/tests): automated test suite.

## Reviewer Notes

- The public row-level dataset is synthetic by design.
- The package API is fully functional and tested on the public schema.
- The study layer documents what parts of the statistical analysis are reproducible from public data and what requires protected inputs.

Further details start at [`docs/index.md`](/Users/marc-anthony/NC/main/academic/win_ratio/docs/index.md).
