# Public Data Dictionary

The committed rows are synthetic.

Design fields include neutral site ID, two-year band, hospital type, age, sex, BMI, ASA group, CCI, malignancy, neoadjuvant treatment, collapsed histology, tumor size, functional impairment, prior abdominal surgery, chronic pancreatitis, kidney disease, cardiac history, volume group, and spleen-management group.

Outcome fields:

- `mort90`: death within 90 days;
- `clavien_grade`: 0, III, or IV severity representation;
- `clavien_major`: grade III or higher indicator;
- `popf_grade`: 0, B, or C severity representation;
- `popf_BC`: clinically relevant POPF indicator;
- `postpancreatectomy_hemorrhage` and `bile_leak`;
- `reoperation` and `readmission`;
- `los_days`: completed postoperative days;
- `ideal_outcome`: survival without major complication, CR-POPF, readmission, or reoperation and LOS `<=13` days;
- `textbook_outcome`: survival without major complication, CR-POPF, hemorrhage, bile leak, or readmission.

`treatment_group` is derived only from a supplied mean annual all-MIP field. The preprocessing code intentionally refuses to substitute MIDP-only counts.
