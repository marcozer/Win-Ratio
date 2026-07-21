from __future__ import annotations

import math
from typing import Any, Dict

import numpy as np


def logwr_wald_ci(
    wins: int,
    losses: int,
    alpha: float = 0.05,
) -> Dict[str, Any]:
    """Approximate Wald CI for WR using log(W R) normal approximation.

    Assumes (wins, losses) behave like independent Poisson counts:
      var(log(W/L)) ≈ 1/W + 1/L

    This is commonly used as a quick analytic CI; bootstrap remains preferred.
    """
    wins = int(wins)
    losses = int(losses)
    if wins <= 0 or losses <= 0:
        return {
            "wr": np.nan,
            "ci": (np.nan, np.nan),
            "se_logwr": np.nan,
            "method": "wald_logwr",
        }

    wr = wins / losses
    logwr = np.log(wr)
    se = float(np.sqrt(1.0 / wins + 1.0 / losses))

    # Normal quantile (avoid scipy dependency here)
    # For alpha=0.05, z≈1.95996; use an approximation for general alpha.
    z = _norm_ppf(1 - alpha / 2)
    lo = float(np.exp(logwr - z * se))
    hi = float(np.exp(logwr + z * se))
    return {"wr": float(wr), "ci": (lo, hi), "se_logwr": se, "method": "wald_logwr"}


def logwr_wald_p_value(wins: int, losses: int, null_wr: float = 1.0) -> float:
    """Two-sided Wald p-value for H0: WR = null_wr using log scale."""
    wins = int(wins)
    losses = int(losses)
    if wins <= 0 or losses <= 0 or null_wr <= 0:
        return float("nan")
    wr = wins / losses
    se = float(np.sqrt(1.0 / wins + 1.0 / losses))
    if se <= 0:
        return float("nan")
    z = (np.log(wr) - np.log(null_wr)) / se
    # two-sided
    p = 2.0 * (1.0 - _norm_cdf(abs(float(z))))
    return float(p)


def _norm_cdf(x: float) -> float:
    """Standard normal CDF via error function."""
    return float(0.5 * (1.0 + math.erf(x / np.sqrt(2.0))))


def compute_e_value(rr: float) -> Dict[str, Any]:
    """Compute E-value for sensitivity to unmeasured confounding.

    The E-value quantifies the minimum strength of association (on the RR scale)
    that an unmeasured confounder would need to have with both exposure and outcome
    to fully explain away the observed effect (VanderWeele & Ding, 2017).

    Formula: E = RR + sqrt(RR × (RR - 1))

    Parameters
    ----------
    rr : float
        The observed effect estimate (Win Ratio, Risk Ratio, etc.)
        Values < 1 are converted to 1/RR for calculation.

    Returns
    -------
    Dict with:
        - e_value: The E-value for the point estimate
        - rr_used: The RR used (original or inverted if < 1)
        - interpretation: Text interpretation of the E-value
    """
    if rr is None or not np.isfinite(rr) or rr <= 0:
        return {
            "e_value": np.nan,
            "rr_used": np.nan,
            "interpretation": "Cannot compute E-value for invalid RR",
        }

    # For protective effects (RR < 1), use 1/RR
    rr_calc = rr if rr >= 1 else 1 / rr

    # E-value formula
    e_value = float(rr_calc + np.sqrt(rr_calc * (rr_calc - 1)))

    # Interpretation
    if e_value < 1.5:
        strength = "weak"
    elif e_value < 2.0:
        strength = "moderate"
    elif e_value < 3.0:
        strength = "moderately strong"
    else:
        strength = "strong"

    interpretation = (
        f"An unmeasured confounder would need to have an RR of {e_value:.2f} "
        f"with both the exposure and outcome to fully explain away the observed effect. "
        f"This represents a {strength} level of robustness to unmeasured confounding."
    )

    return {
        "e_value": e_value,
        "rr_used": float(rr_calc),
        "interpretation": interpretation,
    }


def compute_e_value_for_ci(rr: float, ci_lower: float, ci_upper: float) -> Dict[str, Any]:
    """Compute E-values for both point estimate and confidence interval limit.

    Parameters
    ----------
    rr : float
        Point estimate (Win Ratio)
    ci_lower : float
        Lower bound of confidence interval
    ci_upper : float
        Upper bound of confidence interval

    Returns
    -------
    Dict with:
        - e_value_point: E-value for point estimate
        - e_value_ci: E-value for the CI limit closest to null (1.0)
        - ci_limit_used: Which CI limit was used ('lower' or 'upper')
        - interpretation: Text interpretation
    """
    e_point = compute_e_value(rr)

    # For the CI, use the limit closest to null (1.0)
    if rr >= 1:
        ci_limit = ci_lower
        limit_used = "lower"
    else:
        ci_limit = ci_upper
        limit_used = "upper"

    e_ci = compute_e_value(ci_limit) if ci_limit is not None and np.isfinite(ci_limit) else {"e_value": np.nan}

    # If CI crosses null, E-value for CI is 1.0
    if ci_lower is not None and ci_upper is not None and ci_lower <= 1.0 <= ci_upper:
        e_ci_value = 1.0
        interpretation = (
            f"E-value for point estimate: {e_point['e_value']:.2f}. "
            f"However, the 95% CI includes the null, so E-value for CI = 1.0 "
            f"(any unmeasured confounder could explain away the effect)."
        )
    else:
        e_ci_value = e_ci.get("e_value", np.nan)
        interpretation = (
            f"E-value for point estimate: {e_point['e_value']:.2f}. "
            f"E-value for 95% CI {limit_used} limit: {e_ci_value:.2f}. "
            f"An unmeasured confounder would need an RR >= {e_ci_value:.2f} with both "
            f"exposure and outcome to move the CI to include the null."
        )

    return {
        "e_value_point": e_point["e_value"],
        "e_value_ci": float(e_ci_value),
        "ci_limit_used": limit_used,
        "rr_point": float(rr),
        "rr_ci_limit": float(ci_limit) if ci_limit is not None else np.nan,
        "interpretation": interpretation,
    }


def _norm_ppf(p: float) -> float:
    """Inverse CDF for standard normal using a rational approximation (Acklam)."""
    # https://web.archive.org/web/20150910044729/http://home.online.no/~pjacklam/notes/invnorm/
    if p <= 0.0 or p >= 1.0:
        raise ValueError("p must be in (0,1)")

    # Coefficients in rational approximations
    a = [
        -3.969683028665376e+01,
        2.209460984245205e+02,
        -2.759285104469687e+02,
        1.383577518672690e+02,
        -3.066479806614716e+01,
        2.506628277459239e+00,
    ]
    b = [
        -5.447609879822406e+01,
        1.615858368580409e+02,
        -1.556989798598866e+02,
        6.680131188771972e+01,
        -1.328068155288572e+01,
    ]
    c = [
        -7.784894002430293e-03,
        -3.223964580411365e-01,
        -2.400758277161838e+00,
        -2.549732539343734e+00,
        4.374664141464968e+00,
        2.938163982698783e+00,
    ]
    d = [
        7.784695709041462e-03,
        3.224671290700398e-01,
        2.445134137142996e+00,
        3.754408661907416e+00,
    ]

    plow = 0.02425
    phigh = 1 - plow

    if p < plow:
        q = np.sqrt(-2 * np.log(p))
        num = (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5])
        den = ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
        return float(num / den)
    if p > phigh:
        q = np.sqrt(-2 * np.log(1 - p))
        num = (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5])
        den = ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
        return float(-(num / den))

    q = p - 0.5
    r = q * q
    num = (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q
    den = (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1)
    return float(num / den)
