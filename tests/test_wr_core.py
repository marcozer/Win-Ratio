from __future__ import annotations

import pandas as pd

from winratio import MultiArmWinRatioConfig, WinRatioConfig, WinRatioOutcome, compute_win_ratio, compute_win_ratio_multi_arm


def test_hierarchical_resolution_prefers_higher_priority_outcome() -> None:
    df = pd.DataFrame(
        {
            "group": ["A", "B"],
            "mort90": [0, 0],
            "major_comp": [0, 1],
            "los_days": [12, 8],
        }
    )
    cfg = WinRatioConfig(
        group_col="group",
        arm_a="A",
        arm_b="B",
        outcomes=[
            WinRatioOutcome("Mortality", "mort90", "binary", "lower"),
            WinRatioOutcome("Major complication", "major_comp", "binary", "lower"),
            WinRatioOutcome("Length of stay", "los_days", "continuous", "lower"),
        ],
    )
    overall = compute_win_ratio(df, cfg)["overall"]
    assert overall["wins"] == 1
    assert overall["losses"] == 0


def test_missing_value_policy_can_force_loss() -> None:
    df = pd.DataFrame({"group": ["A", "B"], "endpoint": [None, 0]})
    cfg = WinRatioConfig(
        group_col="group",
        arm_a="A",
        arm_b="B",
        outcomes=[WinRatioOutcome("Endpoint", "endpoint", "binary", "lower", missing_is="loss")],
    )
    overall = compute_win_ratio(df, cfg)["overall"]
    assert overall["losses"] == 1


def test_los_tolerance_mode_respects_one_day_ties() -> None:
    df = pd.DataFrame({"group": ["A", "B"], "los": [8, 7.4]})
    cfg = WinRatioConfig(
        group_col="group",
        arm_a="A",
        arm_b="B",
        outcomes=[
            WinRatioOutcome(
                "LOS",
                "los",
                "continuous",
                "lower",
                los_tolerance_mode="tolerance_1day",
            )
        ],
    )
    overall = compute_win_ratio(df, cfg)["overall"]
    assert overall["ties"] == 1


def test_multi_arm_returns_all_pairwise_comparisons() -> None:
    df = pd.DataFrame(
        {
            "arm": ["A", "B", "C"],
            "mort90": [0, 1, 0],
        }
    )
    cfg = MultiArmWinRatioConfig(
        group_col="arm",
        arms=["A", "B", "C"],
        outcomes=[WinRatioOutcome("Mortality", "mort90", "binary", "lower")],
    )
    result = compute_win_ratio_multi_arm(df, cfg)
    assert len(result["comparisons"]) == 3
