from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

FORBIDDEN_COLUMN_PATTERNS = (
    "code",
    "centre",
    "center",
    "date",
    "texte",
    "detail",
    "remarque",
    "comment",
    "narrative",
    "free_text",
    "medication",
)

PUBLIC_COLUMNS = [
    "site_id",
    "year_band",
    "hospital_type",
    "age_years",
    "age_band",
    "sex",
    "bmi",
    "bmi_band",
    "asa_group",
    "asa_ge3",
    "cci",
    "malignant_case",
    "neoadjuvant",
    "pathology_group",
    "tumor_size_mm",
    "functional_impairment",
    "prior_abdominal_surgery",
    "chronic_pancreatitis",
    "kidney_disease",
    "cardiac_history",
    "treatment_group",
    "spleen_management",
    "mort90",
    "clavien_grade",
    "clavien_major",
    "popf_grade",
    "popf_BC",
    "postpancreatectomy_hemorrhage",
    "bile_leak",
    "reoperation",
    "readmission",
    "los_days",
    "ideal_outcome",
    "textbook_outcome",
]

MIP_VOLUME_COLUMNS = (
    "MIP_VOLUME_ANNUAL",
    "VOLUME_MIP_ANNUEL",
    "MIP_PER_YEAR",
    "VOL_MIP",
    "N_MIP_AN",
)


def _series(data: pd.DataFrame, *names: str) -> pd.Series:
    for name in names:
        if name in data.columns:
            return data[name]
    return pd.Series(index=data.index, dtype=object)


def _to_binary(value: object) -> float:
    if pd.isna(value):
        return float("nan")
    normalized = str(value).strip().lower()
    if normalized in {"oui", "o", "1", "true", "vrai", "yes", "y", "b", "c"}:
        return 1.0
    if normalized in {"non", "n", "0", "false", "faux", "no", "", "a"}:
        return 0.0
    try:
        return float(normalized)
    except ValueError:
        return float("nan")


def _to_float(value: object) -> float:
    if value in ("", None) or pd.isna(value):
        return float("nan")
    try:
        return float(str(value).replace(",", "."))
    except ValueError:
        return float("nan")


def _collapse_category(value: object, mapping: Dict[str, str], default: str = "OTHER") -> str:
    if pd.isna(value):
        return default
    normalized = str(value).strip().upper()
    return mapping.get(normalized, default)


def _clavien_severity(value: object) -> float:
    if pd.isna(value):
        return float("nan")
    text = str(value).strip().upper().replace(" ", "")
    if text.startswith("V") or text.startswith("4") or text.startswith("5"):
        return 4.0
    if text.startswith("III") or text.startswith("3"):
        return 3.0
    numeric = _to_float(value)
    if np.isfinite(numeric):
        return 4.0 if numeric >= 4 else (3.0 if numeric >= 3 else 0.0)
    return 0.0


def _popf_severity(value: object) -> int:
    text = "" if pd.isna(value) else str(value).strip().upper()
    if text == "C":
        return 2
    if text == "B":
        return 1
    return 0


def _derive_binary_benchmarks(out: pd.DataFrame) -> pd.DataFrame:
    no_mortality = out["mort90"] == 0
    no_major = out["clavien_major"] == 0
    no_popf = out["popf_BC"] == 0
    no_readmission = out["readmission"] == 0
    out["ideal_outcome"] = (
        no_mortality
        & no_major
        & no_popf
        & no_readmission
        & (out["reoperation"] == 0)
        & (out["los_days"] <= 13)
    ).astype(int)
    out["textbook_outcome"] = (
        no_mortality
        & no_major
        & no_popf
        & no_readmission
        & (out["postpancreatectomy_hemorrhage"] == 0)
        & (out["bile_leak"] == 0)
    ).astype(int)
    return out


def derive_public_analysis_dataset(raw_df: pd.DataFrame) -> pd.DataFrame:
    """Convert a protected registry export into the public analysis schema.

    The volume group is never inferred from distal pancreatectomy counts. A
    source field containing mean annual *all-MIP* volume is required.
    """

    data = raw_df.copy()
    center_col = "CENTRE" if "CENTRE" in data.columns else "CENTER"
    year_col = "ANNEE" if "ANNEE" in data.columns else "YEAR"
    if center_col not in data.columns or year_col not in data.columns:
        raise ValueError("Protected dataset must contain center and year columns.")

    volume_col = next((column for column in MIP_VOLUME_COLUMNS if column in data.columns), None)
    if volume_col is None:
        raise ValueError(
            "A mean annual all-MIP volume field is required; MIDP-only case counts "
            "must not be substituted for the prespecified >10 MIP/year exposure."
        )

    center_lookup = {
        center: f"SITE_{index:02d}"
        for index, center in enumerate(sorted(data[center_col].dropna().astype(str).unique()), start=1)
    }
    out = pd.DataFrame(index=data.index)
    out["site_id"] = data[center_col].map(center_lookup)

    years = pd.to_numeric(data[year_col], errors="coerce")
    year_floor = (np.floor(years / 2.0) * 2).astype("Int64")
    out["year_band"] = (
        year_floor.astype(str).str.replace("<NA>", "UNKNOWN", regex=False)
        + "-"
        + (year_floor + 1).astype(str).str.replace("<NA>", "UNKNOWN", regex=False)
    )

    hospital_map = {
        "CHU": "ACADEMIC",
        "ESPIC": "PUBLIC",
        "CHG": "PUBLIC",
        "PUBLIC": "PUBLIC",
        "PRIVE": "PRIVATE",
        "PRIVÉ": "PRIVATE",
        "PRIVATE": "PRIVATE",
    }
    out["hospital_type"] = _series(data, "TYPE_HOPITAL", "HOSPITAL_TYPE", "STATUT").map(
        lambda value: _collapse_category(value, hospital_map, default="UNKNOWN")
    )

    age = pd.to_numeric(_series(data, "AGE"), errors="coerce")
    out["age_years"] = age.round(1)
    out["age_band"] = pd.cut(
        age,
        bins=[0, 49, 59, 69, 79, 120],
        labels=["<50", "50-59", "60-69", "70-79", "80+"],
        include_lowest=True,
    ).astype(str).replace("nan", "UNKNOWN")

    bmi = pd.to_numeric(_series(data, "IMC", "BMI"), errors="coerce")
    out["bmi"] = bmi.round(1)
    out["bmi_band"] = pd.cut(
        bmi,
        bins=[0, 18.5, 25, 30, 100],
        labels=["UNDER_18_5", "NORMAL", "OVERWEIGHT", "OBESE"],
        include_lowest=True,
    ).astype(str).replace("nan", "UNKNOWN")

    sex_map = {"M": "MALE", "F": "FEMALE", "H": "MALE"}
    out["sex"] = _series(data, "SEXE", "SEX").map(
        lambda value: sex_map.get(str(value).strip().upper(), "UNKNOWN")
    )
    asa = pd.to_numeric(_series(data, "ASA"), errors="coerce")
    out["asa_group"] = pd.cut(
        asa,
        bins=[0, 1, 2, 3, 10],
        labels=["ASA1", "ASA2", "ASA3", "ASA4PLUS"],
        include_lowest=True,
    ).astype(str).replace("nan", "UNKNOWN")
    out["asa_ge3"] = (asa >= 3).astype(int)
    out["cci"] = pd.to_numeric(_series(data, "CCI", "CHARLSON"), errors="coerce")
    out["malignant_case"] = _series(data, "MALIN").map(_to_binary)
    out["neoadjuvant"] = _series(data, "NEOADJ", "NEOADJ_ANY").map(_to_binary)

    pathology_map = {
        "ADK": "DUCTAL_ADENOCARCINOMA",
        "PDAC": "DUCTAL_ADENOCARCINOMA",
        "TNE": "NEUROENDOCRINE",
        "PANET": "NEUROENDOCRINE",
        "TIPMP": "IPMN",
        "IPMN": "IPMN",
        "TSPP": "SOLID_PSEUDOPAPILLARY",
        "CM": "CYSTIC_MUCINOUS",
    }
    out["pathology_group"] = _series(data, "ANAPATH", "PATHOLOGY").map(
        lambda value: _collapse_category(value, pathology_map, default="OTHER")
    )
    out["tumor_size_mm"] = pd.to_numeric(_series(data, "TAILLE_TUMEUR", "TUMOR_SIZE"), errors="coerce")
    out["functional_impairment"] = _series(data, "AUTONOMIE", "FUNCTIONAL_IMPAIRMENT").map(_to_binary)
    out["prior_abdominal_surgery"] = _series(data, "ATCD_CHIR_ABDO", "PRIOR_ABDOMINAL_SURGERY").map(_to_binary)
    out["chronic_pancreatitis"] = _series(data, "PANCREATITE_CHRONIQUE", "CHRONIC_PANCREATITIS").map(_to_binary)
    out["kidney_disease"] = _series(data, "INSUFFISANCE_RENALE", "KIDNEY_DISEASE").map(_to_binary)
    out["cardiac_history"] = _series(data, "ATCD_CARDIAQUE", "CARDIAC_HISTORY").map(_to_binary)
    annual_volume = pd.to_numeric(data[volume_col], errors="coerce")
    out["treatment_group"] = np.where(annual_volume > 10.0, "HIGH_VOLUME", "OTHER")

    splenectomy = _series(data, "SPLENECTOMIE")
    vessel_resection = _series(data, "PG_RESECTION_VSX")
    spleen_groups = []
    for splenic_flag, vessel_flag in zip(splenectomy, vessel_resection):
        splenic_text = str(splenic_flag).strip().upper() if not pd.isna(splenic_flag) else ""
        vessel_text = str(vessel_flag).strip().upper() if not pd.isna(vessel_flag) else ""
        if splenic_text == "OUI":
            spleen_groups.append("PLANNED_SPLENECTOMY")
        elif splenic_text in {"URG", "ACCIDENTELLE", "UNPLANNED"}:
            spleen_groups.append("UNPLANNED_SPLENECTOMY")
        elif splenic_text == "NON" and vessel_text == "NON":
            spleen_groups.append("PRESERVE_KIMURA")
        elif splenic_text == "NON":
            spleen_groups.append("PRESERVE_WARSHAW")
        else:
            spleen_groups.append("OTHER")
    out["spleen_management"] = spleen_groups

    deaths = _series(data, "DECES").map(_to_binary)
    death_delay = _series(data, "DECES_DELAI").map(_to_float)
    out["mort90"] = (((deaths == 1.0) & (death_delay <= 90)) | ((deaths == 1.0) & death_delay.isna())).astype(int)
    raw_clavien = _series(data, "CLAVIEN")
    out["clavien_grade"] = raw_clavien.map(_clavien_severity).fillna(0).astype(int)
    if "CLAVIEN MAJEUR" in data.columns:
        out["clavien_major"] = data["CLAVIEN MAJEUR"].map(_to_binary).fillna(0).astype(int)
    else:
        out["clavien_major"] = (out["clavien_grade"] >= 3).astype(int)
    out["popf_grade"] = _series(data, "POPF").map(_popf_severity).astype(int)
    out["popf_BC"] = (out["popf_grade"] > 0).astype(int)
    out["postpancreatectomy_hemorrhage"] = _series(data, "HPP", "PPH").map(_to_binary).fillna(0).astype(int)
    out["bile_leak"] = _series(data, "FISTULE_BILIAIRE", "BILE_LEAK").map(_to_binary).fillna(0).astype(int)
    out["reoperation"] = _series(data, "REOPERATION").map(_to_binary).fillna(0).astype(int)
    out["readmission"] = _series(data, "REHOSPITALISATION", "READMISSION").map(_to_binary).fillna(0).astype(int)
    out["los_days"] = _series(data, "LHS", "LOS").map(_to_float).round(0)
    out = _derive_binary_benchmarks(out)
    return out[PUBLIC_COLUMNS].copy()


def audit_public_dataframe(df: pd.DataFrame) -> Tuple[bool, List[str]]:
    """Check the public schema against fixed disclosure rules."""

    violations: List[str] = []
    lower_columns = [column.lower() for column in df.columns]
    for column in lower_columns:
        if any(pattern in column for pattern in FORBIDDEN_COLUMN_PATTERNS):
            violations.append(f"forbidden column name: {column}")
    for column in df.columns:
        series = df[column]
        if pd.api.types.is_object_dtype(series) or pd.api.types.is_string_dtype(series):
            non_missing = series.dropna().astype(str)
            max_len = non_missing.str.len().max() if not non_missing.empty else 0
            if max_len and max_len > 32:
                violations.append(f"possible free-text column: {column}")
    for column in PUBLIC_COLUMNS:
        if column not in df.columns:
            violations.append(f"missing required public column: {column}")
    return (len(violations) == 0, violations)


def create_synthetic_public_dataset(n: int = 800, seed: int = 42) -> pd.DataFrame:
    """Create a synthetic, correlated MIDP dataset for public demonstrations."""

    rng = np.random.default_rng(seed)
    sites = [f"SITE_{index:02d}" for index in range(1, 21)]
    high_volume_sites = set(sites[:5])
    site_type = {
        site: ("ACADEMIC" if index % 3 == 0 else ("PUBLIC" if index % 3 == 1 else "PRIVATE"))
        for index, site in enumerate(sites)
    }
    rows = []

    for _ in range(n):
        site_id = rng.choice(sites, p=np.array([2.0] * 5 + [1.0] * 15) / 25.0)
        high_volume = site_id in high_volume_sites
        age = float(np.clip(rng.normal(60, 15), 18, 90))
        bmi = float(np.clip(rng.normal(26.2, 5.2), 15, 48))
        sex = rng.choice(["MALE", "FEMALE"], p=[0.43, 0.57])
        asa = int(rng.choice([1, 2, 3, 4], p=[0.08, 0.49, 0.38, 0.05]))
        cci = int(np.clip(rng.poisson(1.2 + 0.03 * max(age - 60, 0)), 0, 9))
        pathology = rng.choice(
            ["DUCTAL_ADENOCARCINOMA", "NEUROENDOCRINE", "IPMN", "SOLID_PSEUDOPAPILLARY", "OTHER"],
            p=[0.30, 0.22, 0.17, 0.06, 0.25],
        )
        malignant = int(pathology == "DUCTAL_ADENOCARCINOMA" or rng.random() < 0.10)
        neoadjuvant = int(pathology == "DUCTAL_ADENOCARCINOMA" and rng.random() < 0.35)
        tumor_size = float(np.clip(rng.lognormal(np.log(28), 0.55), 4, 130))
        functional = int(rng.random() < 0.03 + 0.003 * max(age - 65, 0))
        prior_surgery = int(rng.random() < 0.28)
        chronic_pancreatitis = int(rng.random() < 0.07)
        kidney = int(rng.random() < 0.04 + 0.003 * max(age - 65, 0))
        cardiac = int(rng.random() < 0.08 + 0.005 * max(age - 60, 0))

        baseline = (
            0.35 * (asa >= 3)
            + 0.22 * (bmi >= 30)
            + 0.18 * (pathology == "NEUROENDOCRINE")
            + 0.12 * kidney
            - 0.30 * high_volume
        )
        popf_probability = 1 / (1 + np.exp(-(-1.75 + baseline)))
        popf_bc = int(rng.random() < popf_probability)
        popf_grade = 2 if popf_bc and rng.random() < 0.12 else (1 if popf_bc else 0)
        major_probability = 1 / (1 + np.exp(-(-2.15 + baseline + 1.0 * popf_bc)))
        major = int(rng.random() < major_probability)
        clavien_grade = 4 if major and rng.random() < 0.18 else (3 if major else 0)
        mortality = int(rng.random() < (0.003 + 0.045 * (clavien_grade == 4)))
        readmission = int(rng.random() < (0.075 + 0.16 * popf_bc + 0.04 * major))
        reoperation = int(rng.random() < (0.025 + 0.16 * (clavien_grade == 4) + 0.10 * (popf_grade == 2)))
        hemorrhage = int(rng.random() < (0.035 + 0.08 * major))
        bile_leak = int(rng.random() < 0.015)
        los = int(
            max(
                3,
                round(
                    rng.normal(8.2 if high_volume else 9.7, 2.5)
                    + 3.0 * popf_bc
                    + 4.5 * major
                    + 1.5 * readmission
                ),
            )
        )
        spleen = rng.choice(
            ["PRESERVE_KIMURA", "PRESERVE_WARSHAW", "PLANNED_SPLENECTOMY", "UNPLANNED_SPLENECTOMY"],
            p=[0.38, 0.16, 0.40, 0.06],
        )
        rows.append(
            {
                "site_id": site_id,
                "year_band": rng.choice(["2016-2017", "2018-2019", "2020-2021"], p=[0.28, 0.36, 0.36]),
                "hospital_type": site_type[site_id],
                "age_years": round(age, 1),
                "age_band": pd.cut(
                    [age],
                    [0, 49, 59, 69, 79, 120],
                    labels=["<50", "50-59", "60-69", "70-79", "80+"],
                )[0],
                "sex": sex,
                "bmi": round(bmi, 1),
                "bmi_band": pd.cut(
                    [bmi],
                    [0, 18.5, 25, 30, 100],
                    labels=["UNDER_18_5", "NORMAL", "OVERWEIGHT", "OBESE"],
                )[0],
                "asa_group": f"ASA{asa}" if asa < 4 else "ASA4PLUS",
                "asa_ge3": int(asa >= 3),
                "cci": cci,
                "malignant_case": malignant,
                "neoadjuvant": neoadjuvant,
                "pathology_group": pathology,
                "tumor_size_mm": round(tumor_size, 1),
                "functional_impairment": functional,
                "prior_abdominal_surgery": prior_surgery,
                "chronic_pancreatitis": chronic_pancreatitis,
                "kidney_disease": kidney,
                "cardiac_history": cardiac,
                "treatment_group": "HIGH_VOLUME" if high_volume else "OTHER",
                "spleen_management": spleen,
                "mort90": mortality,
                "clavien_grade": clavien_grade,
                "clavien_major": major,
                "popf_grade": popf_grade,
                "popf_BC": popf_bc,
                "postpancreatectomy_hemorrhage": hemorrhage,
                "bile_leak": bile_leak,
                "reoperation": reoperation,
                "readmission": readmission,
                "los_days": los,
            }
        )

    public = pd.DataFrame(rows)
    public = _derive_binary_benchmarks(public)
    return public[PUBLIC_COLUMNS].copy()


def write_public_dataset(df: pd.DataFrame, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
