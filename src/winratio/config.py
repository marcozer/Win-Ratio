from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional, Sequence, Tuple

Direction = Literal["higher", "lower"]
OutcomeKind = Literal["binary", "ordinal", "continuous"]
LostToleranceMode = Literal["exact", "tolerance_1day", "threshold_based"]
MissingValuePolicy = Literal["tie", "loss", "win"]
PairStrategy = Literal["all_pairs", "matched"]


@dataclass
class WinRatioOutcome:
    """Definition of one ordered outcome within a hierarchical win-ratio comparison."""

    name: str
    column: str
    kind: OutcomeKind
    direction: Direction
    tie_tol: float = 0.0
    missing_is: MissingValuePolicy = "tie"
    los_tolerance_mode: LostToleranceMode = "exact"
    los_threshold: Optional[float] = None
    cutpoints: Optional[Tuple[float, ...]] = None
    terminal: bool = False
    terminal_value: Any = 1

    def __post_init__(self) -> None:
        if self.kind not in {"binary", "ordinal", "continuous"}:
            raise ValueError("kind must be 'binary', 'ordinal', or 'continuous'")
        if self.direction not in {"higher", "lower"}:
            raise ValueError("direction must be 'higher' or 'lower'")
        if self.missing_is not in {"tie", "loss", "win"}:
            raise ValueError("missing_is must be 'tie', 'loss', or 'win'")
        if self.tie_tol < 0:
            raise ValueError("tie_tol must be nonnegative")
        if self.cutpoints is not None:
            self.cutpoints = tuple(float(value) for value in self.cutpoints)
            if tuple(sorted(self.cutpoints)) != self.cutpoints:
                raise ValueError("cutpoints must be sorted in ascending order")
            if len(set(self.cutpoints)) != len(self.cutpoints):
                raise ValueError("cutpoints must be unique")
            if self.kind == "binary":
                raise ValueError("cutpoints are only valid for ordinal or continuous outcomes")

    @classmethod
    def binary(
        cls,
        column: str,
        *,
        name: Optional[str] = None,
        favorable: Direction = "lower",
        terminal: bool = False,
        terminal_value: Any = 1,
        missing_is: MissingValuePolicy = "tie",
    ) -> "WinRatioOutcome":
        """Build a binary tier; by convention 1 denotes the event."""

        return cls(
            name=name or column,
            column=column,
            kind="binary",
            direction=favorable,
            missing_is=missing_is,
            terminal=terminal,
            terminal_value=terminal_value,
        )

    @classmethod
    def ordinal(
        cls,
        column: str,
        *,
        name: Optional[str] = None,
        favorable: Direction = "lower",
        cutpoints: Optional[Sequence[float]] = None,
        missing_is: MissingValuePolicy = "tie",
    ) -> "WinRatioOutcome":
        """Build an ordered tier, optionally categorizing values at cut points."""

        return cls(
            name=name or column,
            column=column,
            kind="ordinal",
            direction=favorable,
            cutpoints=tuple(cutpoints) if cutpoints is not None else None,
            missing_is=missing_is,
        )

    @classmethod
    def continuous(
        cls,
        column: str,
        *,
        name: Optional[str] = None,
        favorable: Direction = "lower",
        margin: float = 0.0,
        cutpoints: Optional[Sequence[float]] = None,
        missing_is: MissingValuePolicy = "tie",
    ) -> "WinRatioOutcome":
        """Build a continuous tier with an optional clinical tie margin."""

        return cls(
            name=name or column,
            column=column,
            kind="continuous",
            direction=favorable,
            tie_tol=margin,
            cutpoints=tuple(cutpoints) if cutpoints is not None else None,
            missing_is=missing_is,
        )


@dataclass
class WinRatioConfig:
    """Configuration for a two-arm win-ratio analysis."""

    group_col: str
    arm_a: Any
    arm_b: Any
    outcomes: List[WinRatioOutcome] = field(default_factory=list)
    strata: Optional[List[str]] = None
    id_col: Optional[str] = None
    pair_strategy: PairStrategy = "all_pairs"
    pair_id: Optional[str] = None


@dataclass
class MultiArmWinRatioConfig:
    """Configuration for pairwise win-ratio comparisons across multiple arms."""

    group_col: str
    arms: List[str]
    arm_labels: Dict[str, str] = field(default_factory=dict)
    reference_arm: Optional[str] = None
    outcomes: List[WinRatioOutcome] = field(default_factory=list)
    strata: Optional[List[str]] = None
    id_col: Optional[str] = None
    pair_strategy: PairStrategy = "all_pairs"
    pair_id: Optional[str] = None
    comparison_pairs: Optional[List[Tuple[str, str]]] = None


def _parse_outcome(values: Dict[str, Any]) -> WinRatioOutcome:
    return WinRatioOutcome(
        name=values["name"],
        column=values["column"],
        kind=values["kind"],
        direction=values["direction"],
        tie_tol=values.get("tie_tol", 0.0),
        missing_is=values.get("missing_is", "tie"),
        los_tolerance_mode=values.get("los_tolerance_mode", "exact"),
        los_threshold=values.get("los_threshold"),
        cutpoints=tuple(values["cutpoints"]) if values.get("cutpoints") is not None else None,
        terminal=bool(values.get("terminal", False)),
        terminal_value=values.get("terminal_value", 1),
    )


def config_from_dict(values: Dict[str, Any]) -> WinRatioConfig:
    """Create a two-arm configuration from a Python mapping."""

    return WinRatioConfig(
        group_col=values["group_col"],
        arm_a=values["arm_a"],
        arm_b=values["arm_b"],
        outcomes=[_parse_outcome(item) for item in values.get("outcomes", [])],
        strata=values.get("strata"),
        id_col=values.get("id_col"),
        pair_strategy=values.get("pair_strategy", "all_pairs"),
        pair_id=values.get("pair_id"),
    )


def multi_arm_config_from_dict(values: Dict[str, Any]) -> MultiArmWinRatioConfig:
    """Create a multi-arm configuration from a Python mapping."""

    comparison_pairs = None
    if values.get("comparison_pairs"):
        comparison_pairs = [tuple(item) for item in values["comparison_pairs"]]

    return MultiArmWinRatioConfig(
        group_col=values["group_col"],
        arms=list(values["arms"]),
        arm_labels=dict(values.get("arm_labels", {})),
        reference_arm=values.get("reference_arm"),
        outcomes=[_parse_outcome(item) for item in values.get("outcomes", [])],
        strata=values.get("strata"),
        id_col=values.get("id_col"),
        pair_strategy=values.get("pair_strategy", "all_pairs"),
        pair_id=values.get("pair_id"),
        comparison_pairs=comparison_pairs,
    )
