# Data Governance

The committed public cohort is fully synthetic. No protected patient record is included.

Excluded material includes direct identifiers, site names, exact dates, free text, operative and pathology narratives, medications, linkage codes, protected manuscript outputs, and registry source files.

The schema audit checks column names, required fields, and obvious free-text leakage. It is a code safeguard, not a formal reidentification-risk assessment or substitute for AFC governance approval. Protected export is disabled unless the local-only command explicitly enables it, and a locally derived dataset must not be committed merely because it passes this audit.

Neutral site labels are retained in the synthetic data so cluster-aware methods can be executed. They do not map to actual institutions.
