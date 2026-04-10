from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from winratio import WinRatioConfig, WinRatioOutcome, bootstrap_win_ratio, compute_win_ratio


def main() -> None:
    df = pd.DataFrame(
        {
            "group": ["A", "A", "A", "B", "B", "B"],
            "mort90": [0, 0, 0, 1, 0, 0],
            "major_comp": [0, 1, 0, 1, 1, 0],
            "los_days": [7, 9, 6, 11, 10, 8],
        }
    )
    cfg = WinRatioConfig(
        group_col="group",
        arm_a="A",
        arm_b="B",
        outcomes=[
            WinRatioOutcome("Mortality", "mort90", "binary", "lower"),
            WinRatioOutcome("Major complications", "major_comp", "binary", "lower"),
            WinRatioOutcome("Length of stay", "los_days", "continuous", "lower"),
        ],
    )

    result = compute_win_ratio(df, cfg)["overall"]
    boot = bootstrap_win_ratio(df, cfg, n_boot=200, seed=7)

    print("Win ratio:", result["wr"])
    print("Bootstrap CI:", boot["ci"])


if __name__ == "__main__":
    main()
