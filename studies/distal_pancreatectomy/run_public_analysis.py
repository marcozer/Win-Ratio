from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict

import matplotlib.pyplot as plt
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from winratio import (
    WinRatioConfig,
    bootstrap_win_ratio,
    bootstrap_win_ratio_matched,
    compute_win_ratio,
    config_from_dict,
    propensity_match,
    summarize_component_outcomes,
    summarize_wr_metrics_from_overall,
)


def load_config(path: Path) -> Dict[str, Any]:
    return yaml.safe_load(path.read_text())


def run_all_pairs(df: pd.DataFrame, config_dict: Dict[str, Any], n_boot: int, seed: int) -> Dict[str, Any]:
    cfg = config_from_dict(config_dict)
    point = compute_win_ratio(df, cfg)["overall"]
    boot = bootstrap_win_ratio(df, cfg, n_boot=n_boot, seed=seed)
    components = summarize_component_outcomes(df, cfg)
    metrics = summarize_wr_metrics_from_overall(point)
    return {"config": cfg, "point": point, "bootstrap": boot, "components": components, "metrics": metrics}


def run_matched(df: pd.DataFrame, config_dict: Dict[str, Any], matching_dict: Dict[str, Any], n_boot: int, seed: int) -> Dict[str, Any]:
    matching = propensity_match(
        df,
        treat_col=config_dict["group_col"],
        treated_value=config_dict["arm_a"],
        covariates=matching_dict.get("covariates"),
        exact_cols=matching_dict.get("exact_cols"),
        caliper=matching_dict.get("caliper"),
        method=matching_dict.get("method", "optimal"),
        trim_common_support=matching_dict.get("trim_common_support", True),
        random_state=seed,
    )

    matched_cfg = WinRatioConfig(
        group_col=config_dict["group_col"],
        arm_a=config_dict["arm_a"],
        arm_b=config_dict["arm_b"],
        outcomes=config_from_dict(config_dict).outcomes,
        pair_strategy="matched",
        pair_id="PAIR_ID",
    )
    point = compute_win_ratio(matching.matched_df, matched_cfg)["overall"]
    boot = bootstrap_win_ratio_matched(matching.matched_df, matched_cfg, n_boot=n_boot, seed=seed)
    metrics = summarize_wr_metrics_from_overall(point)
    return {"matching": matching, "config": matched_cfg, "point": point, "bootstrap": boot, "metrics": metrics}


def plot_summary(all_pairs: Dict[str, Any], matched: Dict[str, Any], output_path: Path) -> None:
    labels = ["All pairs", "Matched"]
    wr_values = [all_pairs["point"]["wr"], matched["point"]["wr"]]
    ci_lows = [all_pairs["bootstrap"]["ci"][0], matched["bootstrap"]["ci"][0]]
    ci_highs = [all_pairs["bootstrap"]["ci"][1], matched["bootstrap"]["ci"][1]]
    yerr = [
        [wr - low if pd.notna(low) else 0.0 for wr, low in zip(wr_values, ci_lows)],
        [high - wr if pd.notna(high) else 0.0 for wr, high in zip(wr_values, ci_highs)],
    ]

    fig, ax = plt.subplots(figsize=(6.5, 4.0))
    ax.errorbar(labels, wr_values, yerr=yerr, fmt="o", color="#0B5D7A", ecolor="#7F8C8D", capsize=4, linewidth=1.5)
    ax.axhline(1.0, color="#B03A2E", linestyle="--", linewidth=1.0)
    ax.set_ylabel("Win ratio")
    ax.set_title("Public reproduction summary")
    ax.set_ylim(bottom=0)
    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=200)
    plt.close(fig)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the public distal pancreatectomy analysis.")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path("data/public/distal_pancreatectomy_public.csv"),
        help="Public dataset path.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("studies/distal_pancreatectomy/config/primary_analysis.yaml"),
        help="Analysis configuration YAML.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("results/public"),
        help="Directory for public outputs.",
    )
    parser.add_argument("--n-boot", type=int, default=400, help="Bootstrap replicates.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    config = load_config(args.config)
    df = pd.read_csv(args.dataset)

    all_pairs = run_all_pairs(df, config["all_pairs"], n_boot=args.n_boot, seed=args.seed)
    matched = run_matched(df, config["all_pairs"], config["matching"], n_boot=args.n_boot, seed=args.seed)

    summary_payload = {
        "study_name": config["study_name"],
        "dataset_path": str(args.dataset),
        "all_pairs": {
            "point": all_pairs["point"],
            "bootstrap": all_pairs["bootstrap"],
        },
        "matched": {
            "point": matched["point"],
            "bootstrap": matched["bootstrap"],
            "pairs": matched["matching"].pairs,
        },
    }
    (args.output_dir / "win_ratio_summary.json").write_text(json.dumps(summary_payload, indent=2))
    all_pairs["components"].to_csv(args.output_dir / "component_outcomes.csv", index=False)
    all_pairs["metrics"].to_csv(args.output_dir / "all_pairs_metrics.csv", index=False)
    matched["metrics"].to_csv(args.output_dir / "matched_metrics.csv", index=False)

    manifest = {
        "public_dataset": str(args.dataset),
        "config": str(args.config),
        "reproducible_with_public_data": [
            "results/public/win_ratio_summary.json",
            "results/public/component_outcomes.csv",
            "results/public/all_pairs_metrics.csv",
            "results/public/matched_metrics.csv",
            "results/public/win_ratio_overview.png",
        ],
        "protected_only_outputs": [],
        "dataset_type": "synthetic-fallback",
        "notes": [
            "The committed public dataset is synthetic and preserves only the public analysis schema.",
            "Protected source data are intentionally excluded from this repository.",
        ],
    }
    (args.output_dir / "reproducibility_manifest.json").write_text(json.dumps(manifest, indent=2))
    plot_summary(all_pairs, matched, args.output_dir / "win_ratio_overview.png")


if __name__ == "__main__":
    main()
