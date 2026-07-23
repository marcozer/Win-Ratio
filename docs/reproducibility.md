# Reproducibility Boundary

Fully public and reproducible:

- package installation and build;
- endpoint behavior and design diagnostics;
- unit and integration tests;
- synthetic MIDP generation;
- matching, GPC, weighting, benchmark, sensitivity, and bootstrap demonstrators;
- committed synthetic outputs and editable-text SVG figure.

Not reproducible from committed files:

- protected AFC row-level estimates;
- the manuscript's 5000-replicate refit/rematch interval;
- 50 center-aware chained-equation imputations;
- the observed clinical screen and trial simulations;
- identifiable center-year volume provenance files;
- manuscript and journal-submission assets.

The code exposes the required statistical primitives, but the public synthetic estimates must never be presented as manuscript results. `results/public/reproducibility_manifest.json` records this boundary in machine-readable form.
