"""ASTM D6433 Pavement Condition Index.

Implements Sections 9-11 of ASTM D6433: distress quantities become densities,
densities become deduct values via the published curves, the deduct values are
combined through the iterative corrected-deduct-value procedure, and

    PCI = 100 - max(CDV)

Reference implementation and curve digitisation: the MIT-licensed
`brandnewbox/pavement_condition_index` Ruby gem. Verified against the worked
example in ASTM D6433-07 Fig. 4/6 (PCI = 49) -- see tests/test_pci.py.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Iterable, Literal, Sequence

from .astm import area_to_imperial, quantity_to_imperial, unit_of
from .curves import CDV_CURVES, DEDUCT_CURVES

Severity = Literal["low", "medium", "high"]
PavementType = Literal["asphalt", "concrete"]
Units = Literal["metric", "imperial"]

#: ASTM D6433 Fig. 1 condition rating scale, highest band first. The bands share
#: their endpoints in the standard (e.g. 85 is both "Good" and "Satisfactory");
#: testing from the top resolves each boundary to the better rating.
RATING_SCALE: tuple[tuple[float, str, str], ...] = (
    (85.0, "Good", "#0f7d1d"),
    (70.0, "Satisfactory", "#1ec734"),
    (55.0, "Fair", "#fefb4a"),
    (40.0, "Poor", "#fc2e1f"),
    (25.0, "Very Poor", "#a81a10"),
    (10.0, "Serious", "#690d07"),
    (0.0, "Failed", "#979797"),
)

#: Deduct values at or below this are treated as negligible by the CDV procedure.
DEDUCT_FLOOR = 2.0
#: ASTM D6433 9.5.3 caps the number of deducts that may be counted.
MAX_DEDUCTS = 10


def _polynomial(coefficients: Sequence[float], x: float) -> float:
    return sum(c * x**i for i, c in enumerate(coefficients))


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def rate(pci: float) -> tuple[str, str]:
    """Map a PCI score to its ASTM D6433 verbal rating and suggested colour."""
    if not 0.0 <= pci <= 100.0:
        raise ValueError(f"PCI must be within 0..100, got {pci}")
    for threshold, label, colour in RATING_SCALE:
        if pci >= threshold:
            return label, colour
    raise AssertionError("unreachable: RATING_SCALE must cover down to 0")


def deduct_value(
    distress: str,
    severity: Severity,
    density_pct: float,
    pavement_type: PavementType = "asphalt",
) -> float:
    """Deduct value for one distress type at one severity and density.

    `density_pct` is a percentage (0-100), not a fraction.
    """
    try:
        curve = DEDUCT_CURVES[pavement_type][distress]
    except KeyError:
        known = ", ".join(sorted(DEDUCT_CURVES[pavement_type]))
        raise KeyError(f"unknown {pavement_type} distress {distress!r}; expected one of: {known}") from None
    if severity not in curve["coefficients"]:
        raise KeyError(f"unknown severity {severity!r} for {distress!r}")
    if density_pct < 0:
        raise ValueError(f"density must be non-negative, got {density_pct}")
    if density_pct == 0:
        return 0.0

    # Clamp into the range the curve was digitised over before taking the log:
    # the polynomial is only meaningful inside the printed chart's extent.
    d = _clamp(density_pct, curve["valid_min"], curve["valid_max"])
    x = math.log10(d) if curve["chart_type"] == "log" else d
    return _clamp(_polynomial(curve["coefficients"][severity], x), 0.0, 100.0)


def corrected_deduct_value(
    total_deduct: float, q: int, pavement_type: PavementType = "asphalt"
) -> float:
    """Read the corrected deduct value off the q-curve (ASTM D6433 Fig. X3.26)."""
    if not 1 <= q <= MAX_DEDUCTS:
        raise ValueError(f"q must be within 1..{MAX_DEDUCTS}, got {q}")
    coefficients = CDV_CURVES[pavement_type]["coefficients"][f"q{q}"]
    return _clamp(_polynomial(coefficients, _clamp(total_deduct, 0.0, 200.0)), 0.0, 100.0)


def allowable_deduct_count(highest_deduct: float) -> float:
    """m = 1 + (9/98)(100 - HDV), capped at 10 (ASTM D6433 Eq. 4).

    Returned unrounded: the fractional part scales the last deduct that is used.
    """
    return min(1.0 + (9.0 / 98.0) * (100.0 - highest_deduct), float(MAX_DEDUCTS))


@dataclass(frozen=True)
class Distress:
    """One recorded distress occurrence within a sample unit.

    `quantity` is in the unit ASTM D6433 prescribes for this distress type --
    surface area, linear extent, or a count of potholes -- expressed in the
    unit system declared on the owning :class:`SampleUnit`.
    """

    type: str
    severity: Severity
    quantity: float

    def __post_init__(self) -> None:
        if self.quantity < 0:
            raise ValueError(f"quantity must be non-negative, got {self.quantity}")
        if self.severity not in ("low", "medium", "high"):
            raise ValueError(f"severity must be low/medium/high, got {self.severity!r}")


@dataclass
class SampleUnitResult:
    pci: float
    rating: str
    colour: str
    max_cdv: float
    highest_deduct: float
    allowable_deducts: float
    q: int
    deduct_values: list[float] = field(default_factory=list)
    densities: dict[tuple[str, str], float] = field(default_factory=dict)
    iterations: list[dict] = field(default_factory=list)

    def summary(self) -> str:
        return f"PCI {self.pci:.1f} ({self.rating}), max CDV {self.max_cdv:.1f} from q={self.q}"


class SampleUnit:
    """A pavement sample unit and the distresses recorded on it.

    `area` is the surveyed area -- m2 when ``units="metric"``, square feet when
    ``units="imperial"``. ASTM's standard asphalt sample unit is 2500 +/- 1000
    sq ft (225 +/- 90 m2).

    Quantities are converted to inch-pound units internally, because that is
    what the deduct curves were drawn in. This is not cosmetic: densities of
    linear and count distresses change value with the unit system, so feeding
    metres straight into the curves overstates a pothole density by 10.76x.
    See :mod:`smartroad.pci.astm`.

    For jointed concrete pass the slab count as `area`, since PCC densities are
    expressed per slab; unit conversion does not apply there.
    """

    def __init__(
        self,
        area: float,
        distresses: Iterable[Distress] = (),
        pavement_type: PavementType = "asphalt",
        units: Units = "metric",
        identifier: str | None = None,
    ) -> None:
        if area <= 0:
            raise ValueError(f"area must be positive, got {area}")
        if units not in ("metric", "imperial"):
            raise ValueError(f"units must be 'metric' or 'imperial', got {units!r}")
        self.area = float(area)
        self.pavement_type: PavementType = pavement_type
        self.units: Units = units
        self.identifier = identifier
        self.distresses: list[Distress] = list(distresses)

    def _imperial_area(self) -> float:
        if self.pavement_type == "concrete" or self.units == "imperial":
            return self.area
        return area_to_imperial(self.area)

    def _imperial_quantity(self, d: Distress) -> float:
        if self.pavement_type == "concrete" or self.units == "imperial":
            return d.quantity
        return quantity_to_imperial(d.quantity, d.type)

    def densities(self) -> dict[tuple[str, Severity], float]:
        """Percent density per (distress type, severity), summing repeats first.

        ASTM 9.1-9.2: quantities of the same type *and* severity are totalled
        before the density is taken, so five separate 4 m2 patches of low-severity
        alligator cracking deduct as one 20 m2 occurrence rather than five small ones.
        """
        area = self._imperial_area()
        totals: dict[tuple[str, Severity], float] = {}
        for d in self.distresses:
            key = (d.type, d.severity)
            totals[key] = totals.get(key, 0.0) + self._imperial_quantity(d)
        return {k: v / area * 100.0 for k, v in totals.items()}

    def unit_of(self, distress: str) -> str:
        """Measurement unit ASTM prescribes for `distress` ('area'/'linear'/'count')."""
        return unit_of(distress)

    def evaluate(self) -> SampleUnitResult:
        densities = self.densities()
        if not densities:
            # A sample unit with nothing recorded on it is undamaged.
            return SampleUnitResult(
                pci=100.0, rating=rate(100.0)[0], colour=rate(100.0)[1],
                max_cdv=0.0, highest_deduct=0.0,
                allowable_deducts=allowable_deduct_count(0.0), q=0,
            )

        all_deducts = sorted(
            (
                deduct_value(dtype, sev, density, self.pavement_type)
                for (dtype, sev), density in densities.items()
            ),
            reverse=True,
        )[:MAX_DEDUCTS]

        highest = all_deducts[0]
        m = allowable_deduct_count(highest)

        # ASTM 9.5.4: keep the m largest deducts. m is fractional, so the last
        # one counted is scaled by the fractional part rather than dropped.
        whole = int(m)
        deducts = all_deducts[:whole]
        remainder = m - whole
        if remainder > 0 and len(all_deducts) > whole:
            deducts.append(all_deducts[whole] * remainder)

        q = sum(1 for dv in deducts if dv > DEDUCT_FLOOR)
        if q <= 1:
            # ASTM 9.5.1: with none or only one deduct above 2.0 the correction
            # curves are skipped and the total deduct value is used as the CDV.
            # (The Ruby reference returns PCI 100 when q == 0, dropping the
            # deducts entirely; that contradicts the standard, so we differ here.)
            max_cdv = _clamp(sum(deducts), 0.0, 100.0)
            pci = 100.0 - max_cdv
            label, colour = rate(pci)
            return SampleUnitResult(
                pci=pci, rating=label, colour=colour, max_cdv=max_cdv,
                highest_deduct=highest, allowable_deducts=m, q=q,
                deduct_values=deducts, densities=dict(densities),
            )

        # ASTM 9.5.5: progressively reduce the deducts above 2.0 down to 2.0,
        # recomputing the CDV at each step. The largest CDV seen wins.
        iterations: list[dict] = []
        for qi in range(q, 0, -1):
            adjusted = deducts[:qi] + [min(dv, DEDUCT_FLOOR) for dv in deducts[qi:]]
            total = sum(adjusted)
            cdv = corrected_deduct_value(total, qi, self.pavement_type)
            iterations.append({"q": qi, "total_deduct": total, "cdv": cdv, "deducts": adjusted})

        best = max(iterations, key=lambda it: it["cdv"])
        max_cdv = best["cdv"]
        pci = _clamp(100.0 - max_cdv, 0.0, 100.0)
        label, colour = rate(pci)
        return SampleUnitResult(
            pci=pci, rating=label, colour=colour, max_cdv=max_cdv,
            highest_deduct=highest, allowable_deducts=m, q=best["q"],
            deduct_values=deducts, densities=dict(densities), iterations=iterations,
        )


def section_pci(units: Sequence[SampleUnit]) -> float:
    """Area-weighted PCI of a pavement section (ASTM D6433 Eq. 5).

    Mixing unit systems across sample units is rejected rather than silently
    weighted wrong.
    """
    units = list(units)
    if not units:
        raise ValueError("a section needs at least one sample unit")
    if len({u.units for u in units}) > 1:
        raise ValueError("all sample units in a section must use the same unit system")
    total_area = sum(u.area for u in units)
    return sum(u.evaluate().pci * u.area for u in units) / total_area
