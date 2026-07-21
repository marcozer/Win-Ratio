from __future__ import annotations

import json
from pathlib import Path

import pytest

from studies.distal_pancreatectomy.export_public_data import build_public_dataset
from studies.distal_pancreatectomy.preprocess import audit_public_dataframe, create_synthetic_public_dataset
from studies.distal_pancreatectomy.run_public_analysis import main as run_public_analysis_main


def test_public_dataset_audit_rejects_free_text_column() -> None:
    df = create_synthetic_public_dataset(n=10, seed=1)
    df["operative_comment"] = "too much detail for public release"
    is_safe, violations = audit_public_dataframe(df)
    assert not is_safe
    assert any("forbidden column name" in item or "possible free-text" in item for item in violations)


def test_build_public_dataset_writes_manifest(tmp_path: Path) -> None:
    output = tmp_path / "public.csv"
    manifest = build_public_dataset(protected_csv=None, output_path=output, seed=5)
    assert output.exists()
    assert manifest["source_type"] == "synthetic-fallback"
    assert manifest["audit_passed"] is True


def test_protected_export_requires_explicit_local_flag(tmp_path: Path) -> None:
    protected = tmp_path / "protected.csv"
    protected.write_text("CENTRE,ANNEE\nA,2020\n")
    with pytest.raises(ValueError, match="disabled by default"):
        build_public_dataset(protected_csv=protected, output_path=tmp_path / "public.csv", seed=5)


def test_public_analysis_script_creates_outputs(tmp_path: Path, monkeypatch) -> None:
    dataset_path = tmp_path / "public.csv"
    manifest = build_public_dataset(protected_csv=None, output_path=dataset_path, seed=7)
    assert manifest["audit_passed"] is True

    config_path = Path("studies/distal_pancreatectomy/config/primary_analysis.yaml")
    output_dir = tmp_path / "results"
    monkeypatch.setattr(
        "sys.argv",
        [
            "run_public_analysis",
            "--dataset",
            str(dataset_path),
            "--config",
            str(config_path),
            "--output-dir",
            str(output_dir),
            "--n-boot",
            "50",
        ],
    )
    run_public_analysis_main()
    assert (output_dir / "win_ratio_summary.json").exists()
    assert (output_dir / "reproducibility_manifest.json").exists()
    assert (output_dir / "matched_risk_differences.csv").exists()
    assert (output_dir / "hierarchy_sensitivities.csv").exists()
    assert (output_dir / "binary_benchmarks.csv").exists()
    assert (output_dir / "win_ratio_overview.svg").exists()
    summary = json.loads((output_dir / "win_ratio_summary.json").read_text())
    assert summary["analysis_version"] == "v21"
    assert "primary_assigned_pairs" in summary
    assert "matched_sample_all_pair_gpc" in summary
    assert "overlap_weighted_gpc" in summary
