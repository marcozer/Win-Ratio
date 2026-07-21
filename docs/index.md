# WinRatioPy

WinRatioPy implements hierarchical win-ratio and generalized pairwise-comparison analyses for clinical outcomes. It combines endpoint construction, matching or weighting, balance diagnostics, tier decomposition, and bootstrap inference in one installable package.

The preferred import is `winratiopy`; `winratio` remains available for backward compatibility.

The included MIDP workflow is a synthetic public demonstrator. It mirrors the current endpoint and design architecture but cannot reproduce protected AFC estimates without governed source data.

Use the documentation in this order:

1. **Methodology** for estimands, hierarchy behavior, and inference.
2. **API Reference** for callable objects.
3. **Configurations** for YAML-defined analyses.
4. **Study Reproduction** for the MIDP demonstrator.
5. **Reproducibility** and **Anonymization** for the public/protected boundary.
