# Overview

This documentation describes the public repository for the statistical analyses used in the distal pancreatectomy study.

The repository separates:

- a generic Python library in `src/winratio` for propensity-score matching and win-ratio analysis
- a study-specific public analysis layer in `studies/distal_pancreatectomy`
- a public synthetic dataset and public analysis outputs

The clinical use case in this repository is a retrospective comparison of outcomes after minimally invasive distal pancreatectomy, with emphasis on whether higher-volume centers achieve a more favorable ordered postoperative course than lower-volume centers after adjustment by propensity-score matching.

Start with the root README for installation and commands, then use the pages in this site for the package API, study workflow, and data governance details.
