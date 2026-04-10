# Anonymization Policy

The public repository excludes:

- direct identifiers
- site names
- exact dates
- free-text fields
- narrative operative reports
- pathology narratives
- medication lists
- linkage codes

The public analysis schema uses:

- neutral `site_id` labels
- year bands instead of exact years or dates
- age and BMI bands instead of exact raw values when derived from protected data
- collapsed pathology groups

If a protected dataset fails the disclosure audit, the workflow writes a synthetic fallback instead of exporting the derived row-level data.
