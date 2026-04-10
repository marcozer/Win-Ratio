# Distal Pancreatectomy Study Layer

This folder contains the public statistical-analysis layer for the distal pancreatectomy study.

- `export_public_data.py`: converts a protected registry export into the public schema or writes the synthetic fallback.
- `audit_public_dataset.py`: checks a candidate public CSV against fixed disclosure rules.
- `run_public_analysis.py`: runs the public all-pairs and matched analyses and writes public summary outputs.
- `config/primary_analysis.yaml`: public analysis configuration.

The committed dataset in [`data/public/distal_pancreatectomy_public.csv`](/Users/marc-anthony/NC/main/academic/win_ratio/data/public/distal_pancreatectomy_public.csv) is synthetic. The public schema mirrors the analysis-ready variables while excluding identifiers, dates, site names, and free text.
