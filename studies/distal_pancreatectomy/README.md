# Distal Pancreatectomy Demonstrator

This study layer applies WinRatioPy to a synthetic MIDP cohort using the current public analysis architecture.

- `preprocess.py`: fixed schema, component reconstruction, synthetic data generator, and disclosure checks.
- `export_public_data.py`: writes the synthetic public dataset; locally supplied governed exports require an explicit local-only flag and must never be committed.
- `run_public_analysis.py`: matching, assigned-pair WR, hierarchy sensitivities, matched all-pair GPC, overlap weighting, IO/TBO, diagnostics, and public figures.
- `config/primary_analysis.yaml`: exposure, endpoint, design, and sensitivity definitions.

The higher-volume group means more than 10 all minimally invasive pancreatic resections per complete contributed year. The code refuses to derive this exposure from distal pancreatectomy counts alone.

The primary public hierarchy is mortality, major complications, CR-POPF, readmission, and exact-day LOS. Both deaths stop as a tie. Sensitivities cover graded severity, 1- and 2-day margins, no LOS, and LOS categories of `<=7`, `8-13`, and `>13` days.

The committed [dataset](../../data/public/distal_pancreatectomy_public.csv) is synthetic. The generated estimates demonstrate software behavior and are not manuscript results.
