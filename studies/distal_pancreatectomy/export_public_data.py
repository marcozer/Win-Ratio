from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from .preprocess import (
    audit_public_dataframe,
    create_synthetic_public_dataset,
    derive_public_analysis_dataset,
    write_public_dataset,
)


def build_public_dataset(
    protected_csv: Path | None,
    output_path: Path,
    seed: int,
    *,
    allow_protected_export: bool = False,
) -> dict:
    if protected_csv is not None and protected_csv.exists():
        if not allow_protected_export:
            raise ValueError(
                "Protected-data export is disabled by default. "
                "Use the explicit local-only flag after governance review."
            )
        raw_df = pd.read_csv(protected_csv)
        public_df = derive_public_analysis_dataset(raw_df)
        is_safe, violations = audit_public_dataframe(public_df)
        if is_safe:
            source_type = "deidentified-derived"
            notes = ["Protected input was converted to the public analysis schema and passed the disclosure audit."]
        else:
            public_df = create_synthetic_public_dataset(seed=seed)
            source_type = "synthetic-fallback"
            notes = ["Derived dataset failed the public disclosure audit.", *violations]
    else:
        public_df = create_synthetic_public_dataset(seed=seed)
        is_safe, violations = audit_public_dataframe(public_df)
        source_type = "synthetic-fallback"
        notes = ["Protected dataset not supplied; generated the public demonstration dataset."]

    write_public_dataset(public_df, output_path)

    manifest = {
        "dataset_path": str(output_path),
        "source_type": source_type,
        "rows": int(len(public_df)),
        "columns": list(public_df.columns),
        "audit_passed": bool(is_safe),
        "audit_violations": violations,
        "notes": notes,
    }
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create the public distal pancreatectomy dataset.")
    parser.add_argument("--protected-csv", type=Path, default=None, help="Optional protected registry export.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/public/distal_pancreatectomy_public.csv"),
        help="Output CSV path.",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("data/public/distal_pancreatectomy_manifest.json"),
        help="Output manifest path.",
    )
    parser.add_argument("--seed", type=int, default=42, help="Random seed for the synthetic fallback.")
    parser.add_argument(
        "--allow-protected-export",
        action="store_true",
        help="Enable local processing of a governed protected export; never commit the resulting rows.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    manifest = build_public_dataset(
        args.protected_csv,
        args.output,
        args.seed,
        allow_protected_export=args.allow_protected_export,
    )
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
