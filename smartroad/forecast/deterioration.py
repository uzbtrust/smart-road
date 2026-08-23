"""How a PCI falls with age, and what a maintenance treatment buys back.

A single survey is one point. A forecast needs a curve, and a curve cannot be
fitted to one point, so the curve has to come from somewhere else and be said
to. Two sources are carried here, and they disagree by a factor of seven, which
is the most useful thing about having both.

MATHEW & ISAAC (2014), rural roads, Kerala. Their prediction model is

    PCI(t) = PCI_0 - 3.682 * age^1.822 + exp(0.55 * age * CQ)

with CQ a construction quality between 0 and 1. Checked against the fifteen
road stretches of their own case study, it reproduces the published PCI to a
mean absolute error of 0.44 points, worst case 1.17 -- the residual is rounding
in their table. It is a real, verifiable model and its coefficients are for
low-volume rural roads that reach PCI 10 by their sixth year.

SOATALIYEV (2024), republic roads, Tashkent region. The dissertation carries
roughness for four roads at five dates between 2016 and 2022, and a regression
from roughness to PCI fitted separately on each road. Putting the one through
the other gives an observed trajectory:

    A373a  64.2 -> 50.5      -2.42 PCI/year
    4P12   65.5 -> 55.2      -1.77
    4P21   70.1 -> 55.3      -2.49
    M39b   65.0 -> 55.6      -1.52
                      mean   -2.05 PCI/year

Seven times slower than the Kerala curve, which is what one expects of
republic-level roads against low-volume rural ones. Nothing here transfers
between them, and applying the Kerala coefficients to a Tashkent street would
produce a confident number that is wrong by a factor.

WHAT NEITHER GIVES YOU. Both are calibrated on roads whose age and treatment
history were known to their authors. Soataliyev is explicit that for the
Uzbek network at large this is not currently recoverable -- the technical
passports read "no data" where the repair history should be, so which
treatment was applied and what it achieved cannot be established. Until a
street's last resurfacing date is known, `LinearTrend` is the honest model
and the age-based one is a hypothesis.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

#: Mathew & Isaac (2014), equation 8. Verified against their Table 2.
KERALA_A, KERALA_B, KERALA_C = 3.682, 1.822, 0.55

#: The ages their case study covers. Outside this the curve is extrapolation:
#: at age 20 it returns a PCI of about -770.
KERALA_VALID_AGE = (4.9, 6.2)

#: Soataliyev (2024), figure 3.5 through figure 2.9. PCI points lost per year,
#: observed on four Tashkent-region roads over six years.
UZBEK_PCI_PER_YEAR = -2.05
UZBEK_PCI_PER_YEAR_RANGE = (-2.49, -1.52)

#: Figure 2.9: PCI against roughness, five roads, slopes -9.4 to -10.6 and
#: intercepts 93.2 to 97.8. These are the means. Their PCI is ASTM D6433-07
#: over the same nineteen distresses this project grades, so the two are
#: directly comparable rather than merely similarly named.
IRI_TO_PCI_SLOPE, IRI_TO_PCI_INTERCEPT = -10.20, 96.00


#: Mathew & Isaac Table 1: how many PCI points each treatment returns, by the
#: condition it is applied to. Expert opinion collected by Delphi, so these are
#: judgements rather than measurements -- but they are published judgements
#: with a method behind them, which is more than a guess.
#: Keyed by the lower bound of the PCI band.
TREATMENT_GAIN: dict[str, dict[int, float]] = {
    "shoulder_maintenance":  {70: 2,  60: 2,  50: 2,  40: 2,  30: 2,  20: 2,  10: 2,  0: 2},
    "pothole_patching":      {70: 5,  60: 5,  50: 10, 40: 10, 30: 15, 20: 15, 10: 20, 0: 20},
    "patching_slurry_seal":  {70: 10, 60: 10, 50: 25, 40: 25, 30: 35, 20: 35, 10: 45, 0: 45},
    "resurfacing":           {70: 15, 60: 25, 50: 35, 40: 45, 30: 50, 20: 60, 10: 70, 0: 80},
}

#: Above this, Table 1 records no action: the pavement does not need one.
NO_TREATMENT_ABOVE = 80

#: Soataliyev Table 3.1, relative cost in units, Uzbek practice. Ratios rather
#: than currency, so they survive inflation and an exchange rate.
COST_UNITS: dict[str, tuple[float, float]] = {
    "routine_maintenance": (1.0, 5.0),
    "current_repair": (25.0, 40.0),
    "major_repair": (60.0, 100.0),
}


@dataclass(frozen=True)
class Point:
    """One year of a forecast."""

    year: int
    age_years: float
    pci: float
    rating: str
    treatment: str | None = None
    gain: float = 0.0


def pci_from_iri(iri_m_per_km: float) -> float:
    """Roughness to PCI, by the dissertation's regression across five roads."""
    return max(0.0, min(100.0, IRI_TO_PCI_SLOPE * iri_m_per_km + IRI_TO_PCI_INTERCEPT))


def iri_from_pci(pci: float) -> float:
    """The inverse, for reading a target PCI back as a roughness to measure."""
    return (pci - IRI_TO_PCI_INTERCEPT) / IRI_TO_PCI_SLOPE


def kerala_pci(age_years: float, construction_quality: float,
               pci_0: float = 100.0) -> float:
    """Mathew & Isaac's curve. Clamped to 0-100; see KERALA_VALID_AGE."""
    if not 0.0 <= construction_quality <= 1.0:
        raise ValueError(f"construction quality is 0 to 1, got {construction_quality}")
    if age_years < 0:
        raise ValueError(f"age cannot be negative, got {age_years}")
    raw = (pci_0
           - KERALA_A * age_years ** KERALA_B
           + math.exp(KERALA_C * age_years * construction_quality))
    return max(0.0, min(100.0, raw))


def kerala_turning_age(construction_quality: float) -> float:
    """Where the curve stops falling and starts to climb again.

    The exponential term eventually overtakes the power term, so the model is
    not monotonic and a bisection over an arbitrary range walks off the far
    side of the minimum and returns nonsense. Measured, the turn is at age 7.6
    for CQ 1.0 and 20.7 for CQ 0.5 -- by which point the curve has long since
    passed through zero, so it never matters in a real forecast. It matters to
    the inverse, which has to search below it.
    """
    lo, hi = 0.05, 60.0
    for _ in range(200):                  # ternary search on a unimodal dip
        a = lo + (hi - lo) / 3
        b = hi - (hi - lo) / 3
        fa = -KERALA_A * a ** KERALA_B + math.exp(KERALA_C * a * construction_quality)
        fb = -KERALA_A * b ** KERALA_B + math.exp(KERALA_C * b * construction_quality)
        if fa < fb:
            hi = b
        else:
            lo = a
    return (lo + hi) / 2


def kerala_age_for_pci(pci: float, construction_quality: float,
                       pci_0: float = 100.0) -> float:
    """The age at which the curve first falls to `pci`.

    Mathew & Isaac model a treatment by converting the improved PCI back into
    an equivalent age and continuing the same curve from there, so this is what
    makes their treatment effect computable rather than decorative. Figure 3 of
    their paper: PCI 39 at age 5, a slurry seal takes it to 74, and the road
    carries on as though it were 3.2 years old.

    The search is bounded above by the turning age, where the curve stops being
    a deterioration model at all.
    """
    lo, hi = 0.0, kerala_turning_age(construction_quality)
    if kerala_pci(hi, construction_quality, pci_0) > pci:
        return hi                         # never falls this far before turning
    for _ in range(80):                   # monotonic on [0, turning age]
        mid = (lo + hi) / 2
        if kerala_pci(mid, construction_quality, pci_0) > pci:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def treatment_gain(pci: float, treatment: str) -> float:
    """PCI points Table 1 credits `treatment` with, at this condition.

    Zero above PCI 80, where the table records no action: a pavement in that
    state does not need one, and crediting a gain there would let an optimiser
    spend money to no purpose.
    """
    if treatment not in TREATMENT_GAIN:
        raise ValueError(f"unknown treatment {treatment!r}; "
                         f"expected one of {sorted(TREATMENT_GAIN)}")
    if pci > NO_TREATMENT_ABOVE:
        return 0.0
    band = max(b for b in TREATMENT_GAIN[treatment] if pci >= b)
    return float(TREATMENT_GAIN[treatment][band])


def forecast_linear(pci_now: float, years: int, *, start_year: int = 2026,
                    per_year: float = UZBEK_PCI_PER_YEAR) -> list[Point]:
    """Straight-line decline at the rate observed on Tashkent-region roads.

    The honest default where a street's age and last resurfacing are unknown,
    which Soataliyev reports is the normal case for the Uzbek network.
    """
    from smartroad.pci.engine import rate

    out = []
    for i in range(years + 1):
        pci = max(0.0, min(100.0, pci_now + per_year * i))
        out.append(Point(start_year + i, float(i), pci, rate(pci)[0]))
    return out


def forecast_aged(age_now: float, construction_quality: float, years: int, *,
                  start_year: int = 2026, treat_at: float | None = None,
                  treatment: str = "patching_slurry_seal") -> list[Point]:
    """Mathew & Isaac's curve, optionally treating when the PCI falls too far.

    When a treatment fires, the gain from Table 1 is added and the age is reset
    to whatever age the improved PCI corresponds to -- their procedure, not an
    invention here. Deterioration then continues along the same curve.
    """
    from smartroad.pci.engine import rate

    out, age = [], age_now
    for i in range(years + 1):
        pci = kerala_pci(age, construction_quality)
        applied, gain = None, 0.0
        if treat_at is not None and pci < treat_at and i > 0:
            gain = treatment_gain(pci, treatment)
            if gain > 0:
                pci = min(100.0, pci + gain)
                age = kerala_age_for_pci(pci, construction_quality)
                applied = treatment
        out.append(Point(start_year + i, round(age, 2), pci, rate(pci)[0],
                         applied, gain))
        age += 1.0
    return out


def years_until(pci_now: float, threshold: float, *,
                per_year: float = UZBEK_PCI_PER_YEAR) -> float | None:
    """Years before a straight-line decline reaches `threshold`.

    None where it never does, which is what a road already below the threshold
    or a non-negative rate means.
    """
    if per_year >= 0 or pci_now <= threshold:
        return None
    return (pci_now - threshold) / -per_year
