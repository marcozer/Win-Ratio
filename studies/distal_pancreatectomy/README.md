# Distal Pancreatectomy Demonstrator

This study layer applies WinRatioPy to a synthetic MIDP cohort using the current public analysis architecture.

- `preprocess.py`: fixed schema, component reconstruction, synthetic data generator, and disclosure checks.
- `export_public_data.py`: writes the synthetic public dataset; locally supplied governed exports require an explicit local-only flag and must never be committed.
- `run_public_analysis.py`: matching, assigned-pair WR, hierarchy sensitivities, matched all-pair GPC, overlap weighting, IO/TBO, diagnostics, and public figures.
- `config/primary_analysis.yaml`: exposure, endpoint, design, and sensitivity definitions.

The higher-volume group uses the registry-provided, previously published study-period mean annual volume of all minimally invasive pancreatic resections and compares more than 10 procedures/y with 10 or fewer. The code refuses to derive this exposure from distal pancreatectomy counts alone; a center-year reconstruction can audit provenance but cannot silently replace the supplied exposure.

The main exploratory public hierarchy is mortality, graded Clavien-Dindo III/IV severity, graded CR-POPF B/C severity, readmission, and LOS, with differences of 0 or 1 completed day tied. Both deaths stop as a tie. Sensitivities cover exact-day and minimum 3-day LOS differences, no LOS, LOS categories of `<=7`, `8-13`, and `>13` days, and 2 fixed order permutations.

The committed [dataset](../../data/public/distal_pancreatectomy_public.csv) is synthetic. The generated estimates demonstrate software behavior and are not manuscript results.
