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
    "age_band",
    "sex",
    "bmi_band",
    "asa_group",
    "malignant_case",
    "neoadjuvant",
    "pathology_group",
    "treatment_group",
    "spleen_management",
    "mort90",
    "clavien_major",
    "popf_BC",
    "reoperation",
    "readmission",
    "los_days",
]


def _to_binary(value: object) -> float:
    if pd.isna(value):
        return float("nan")
    normalized = str(value).strip().lower()
    if normalized in {"oui", "o", "1", "true", "vrai", "yes", "y"}:
        return 1.0
    if normalized in {"non", "n", "0", "false", "faux", "no", ""}:
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


def derive_public_analysis_dataset(raw_df: pd.DataFrame) -> pd.DataFrame:
    """Convert a protected registry export into the public analysis schema."""

    data = raw_df.copy()
    center_col = "CENTRE" if "CENTRE" in data.columns else "CENTER"
    year_col = "ANNEE" if "ANNEE" in data.columns else "YEAR"

    if center_col not in data.columns or year_col not in data.columns:
        raise ValueError("Protected dataset must contain center and year columns.")

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

    age = pd.to_numeric(data.get("AGE"), errors="coerce")
    out["age_band"] = pd.cut(
        age,
        bins=[0, 49, 59, 69, 79, 120],
        labels=["<50", "50-59", "60-69", "70-79", "80+"],
        include_lowest=True,
    ).astype(str).replace("nan", "UNKNOWN")

    bmi = pd.to_numeric(data.get("IMC"), errors="coerce")
    out["bmi_band"] = pd.cut(
        bmi,
        bins=[0, 18.5, 25, 30, 100],
        labels=["UNDER_18_5", "NORMAL", "OVERWEIGHT", "OBESE"],
        include_lowest=True,
    ).astype(str).replace("nan", "UNKNOWN")

    sex_map = {"M": "MALE", "F": "FEMALE", "H": "MALE"}
    out["sex"] = data.get("SEXE", pd.Series(index=data.index)).map(
        lambda value: sex_map.get(str(value).strip().upper(), "UNKNOWN")
    )

    asa = pd.to_numeric(data.get("ASA"), errors="coerce")
    out["asa_group"] = pd.cut(
        asa,
        bins=[0, 1, 2, 3, 10],
        labels=["ASA1", "ASA2", "ASA3", "ASA4PLUS"],
        include_lowest=True,
    ).astype(str).replace("nan", "UNKNOWN")

    out["malignant_case"] = data.get("MALIN", pd.Series(index=data.index)).map(_to_binary).fillna(0.0).astype(int)
    out["neoadjuvant"] = data.get("NEOADJ", pd.Series(index=data.index)).map(_to_binary).fillna(0.0).astype(int)

    pathology_map = {
        "ADK": "DUCTAL_ADENOCARCINOMA",
        "TNE": "NEUROENDOCRINE",
        "TIPMP": "IPMN",
        "TSPP": "SOLID_PSEUDOPAPILLARY",
        "CM": "CYSTIC_MUCINOUS",
        "CCK": "CHOLANGIOCARCINOMA",
    }
    out["pathology_group"] = data.get("ANAPATH", pd.Series(index=data.index)).map(
        lambda value: _collapse_category(value, pathology_map, default="OTHER")
    )

    work = data.copy()
    if "CHIRURGIE" in work.columns:
        work = work[work["CHIRURGIE"] == "PG"]
    counts = work.groupby(center_col).size().rename("n_cases")
    years_per_center = work.groupby(center_col)[year_col].nunique().rename("n_years")
    center_volume = pd.concat([counts, years_per_center], axis=1).fillna(0)
    center_volume["avg_per_year"] = center_volume.apply(
        lambda row: (row["n_cases"] / row["n_years"]) if row["n_years"] else 0.0,
        axis=1,
    )
    center_volume["treatment_group"] = np.where(center_volume["avg_per_year"] > 20.0, "HIGH_VOLUME", "OTHER")
    out["treatment_group"] = data[center_col].map(center_volume["treatment_group"]).fillna("OTHER")

    splenectomy = data.get("SPLENECTOMIE", pd.Series(index=data.index))
    vessel_resection = data.get("PG_RESECTION_VSX", pd.Series(index=data.index))
    spleen_groups = []
    for splenic_flag, vessel_flag in zip(splenectomy, vessel_resection):
        splenic_text = str(splenic_flag).strip().upper() if not pd.isna(splenic_flag) else ""
        vessel_text = str(vessel_flag).strip().upper() if not pd.isna(vessel_flag) else ""
        if splenic_text == "OUI":
            spleen_groups.append("PLANNED_SPLENECTOMY")
        elif splenic_text == "URG":
            spleen_groups.append("UNPLANNED_SPLENECTOMY")
        elif splenic_text == "NON" and vessel_text == "NON":
            spleen_groups.append("PRESERVE_KIMURA")
        elif splenic_text == "NON":
            spleen_groups.append("PRESERVE_WARSHAW")
        else:
            spleen_groups.append("OTHER")
    out["spleen_management"] = spleen_groups

    deaths = data.get("DECES", pd.Series(index=data.index)).map(_to_binary)
    death_delay = data.get("DECES_DELAI", pd.Series(index=data.index)).map(_to_float)
    out["mort90"] = (((deaths == 1.0) & (death_delay <= 90)) | ((deaths == 1.0) & death_delay.isna())).astype(int)

    if "CLAVIEN MAJEUR" in data.columns:
        out["clavien_major"] = data["CLAVIEN MAJEUR"].map(_to_binary).fillna(0.0).astype(int)
    else:
        clavien = data.get("CLAVIEN", pd.Series(index=data.index)).map(_to_float)
        out["clavien_major"] = (clavien >= 3).fillna(False).astype(int)

    out["popf_BC"] = data.get("POPF", pd.Series(index=data.index)).map(
        lambda value: 1 if str(value).strip().upper() in {"B", "C"} else 0
    )
    out["reoperation"] = data.get("REOPERATION", pd.Series(index=data.index)).map(_to_binary).fillna(0.0).astype(int)
    out["readmission"] = data.get("REHOSPITALISATION", pd.Series(index=data.index)).map(_to_binary).fillna(0.0).astype(int)
    out["los_days"] = data.get("LHS", pd.Series(index=data.index)).map(_to_float).round(0)

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


def create_synthetic_public_dataset(n: int = 240, seed: int = 42) -> pd.DataFrame:
    """Create a synthetic dataset that follows the public analysis schema."""

    rng = np.random.default_rng(seed)
    sites = [f"SITE_{index:02d}" for index in range(1, 13)]
    high_volume_sites = set(sites[:4])
    rows = []

    for _ in range(n):
        site_id = rng.choice(sites)
        high_volume = site_id in high_volume_sites
        age_band = rng.choice(["<50", "50-59", "60-69", "70-79", "80+"], p=[0.08, 0.18, 0.34, 0.28, 0.12])
        bmi_band = rng.choice(["UNDER_18_5", "NORMAL", "OVERWEIGHT", "OBESE"], p=[0.05, 0.34, 0.38, 0.23])
        asa_group = rng.choice(["ASA1", "ASA2", "ASA3", "ASA4PLUS"], p=[0.09, 0.44, 0.37, 0.10])
        malignant_case = int(rng.random() < 0.42)
        neoadjuvant = int(malignant_case and rng.random() < 0.24)
        pathology_group = rng.choice(
            ["DUCTAL_ADENOCARCINOMA", "NEUROENDOCRINE", "IPMN", "SOLID_PSEUDOPAPILLARY", "OTHER"],
            p=[0.26, 0.24, 0.16, 0.08, 0.26],
        )

        risk = 1.0
        if high_volume:
            risk *= 0.65
        if age_band in {"70-79", "80+"}:
            risk += 0.18
        if asa_group in {"ASA3", "ASA4PLUS"}:
            risk += 0.24
        if malignant_case:
            risk += 0.14
        if neoadjuvant:
            risk += 0.08

        los_base = rng.normal(8.8 if high_volume else 11.0, 2.4)
        rows.append(
            {
                "site_id": site_id,
                "year_band": rng.choice(["2016-2017", "2018-2019", "2020-2021"], p=[0.28, 0.37, 0.35]),
                "age_band": age_band,
                "sex": rng.choice(["MALE", "FEMALE"], p=[0.48, 0.52]),
                "bmi_band": bmi_band,
                "asa_group": asa_group,
                "malignant_case": malignant_case,
                "neoadjuvant": neoadjuvant,
                "pathology_group": pathology_group,
                "treatment_group": "HIGH_VOLUME" if high_volume else "OTHER",
                "spleen_management": rng.choice(
                    ["PRESERVE_KIMURA", "PRESERVE_WARSHAW", "PLANNED_SPLENECTOMY", "UNPLANNED_SPLENECTOMY"],
                    p=[0.39, 0.15, 0.36, 0.10],
                ),
                "mort90": int(rng.random() < 0.02 * risk),
                "clavien_major": int(rng.random() < 0.15 * risk),
                "popf_BC": int(rng.random() < 0.10 * risk),
                "reoperation": int(rng.random() < 0.06 * risk),
                "readmission": int(rng.random() < 0.09 * risk),
                "los_days": int(max(3, round(los_base + rng.normal(0, 1.8) + (0.6 if malignant_case else 0.0)))),
            }
        )

    return pd.DataFrame(rows, columns=PUBLIC_COLUMNS)


def write_public_dataset(df: pd.DataFrame, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
