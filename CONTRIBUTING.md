# Contributing

## Development Setup

```bash
pip install -e .[dev,docs,study]
```

## Expectations

- Keep the core library in [`src/winratio`](/Users/marc-anthony/NC/main/academic/win_ratio/src/winratio) generic and dataset-agnostic.
- Keep study-specific analysis logic in [`studies/distal_pancreatectomy`](/Users/marc-anthony/NC/main/academic/win_ratio/studies/distal_pancreatectomy).
- Do not add protected data, identifiers, exact dates, site names, or free text.
- Add tests for library behavior and for any public-data handling changes.

## Validation

Run these commands before proposing changes:

```bash
pytest
mkdocs build --strict
python -m studies.distal_pancreatectomy.export_public_data
python -m studies.distal_pancreatectomy.run_public_analysis
```
