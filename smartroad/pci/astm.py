"""ASTM D6433 asphalt distress catalogue: numbers, measurement units, severities.

The measurement unit matters for more than bookkeeping. A density is
`quantity / area`, so it is only dimensionless for area-type distresses. For a
linear distress the density carries units of 1/length, and for potholes it is a
count per unit area -- both change value when you switch between feet and metres:

    edge cracking   130 ft / 2500 ft2  = 5.20 %      (ASTM Fig. 4)
                   39.6 m  /  232.3 m2 = 17.06 %     -- 3.28x larger
    potholes          1    / 2500 ft2  = 0.04 %
                      1    /  232.3 m2 = 0.43 %      -- 10.76x larger

ASTM D6433 states the inch-pound values are the standard and the SI values are
"for information only", and the deduct curves were digitised from charts drawn
in those inch-pound units. So quantities must reach the curves as feet, square
feet and counts, whatever the survey recorded them in.
"""
from __future__ import annotations

from typing import Literal

Unit = Literal["area", "linear", "count"]

SQ_M_PER_SQ_FT = 0.09290304
M_PER_FT = 0.3048

#: distress key -> (ASTM D6433 distress number, measurement unit)
#:
#: Units are taken from Appendix X1 ("How to Measure" for each distress).
#: `weathering` and `raveling` share ASTM number 19; the digitised curve set
#: keeps them apart, so both appear here.
ASPHALT_DISTRESSES: dict[str, tuple[int, Unit]] = {
    "alligator_cracking": (1, "area"),
    "bleeding": (2, "area"),
    "block_cracking": (3, "area"),
    "bumps_and_sags": (4, "linear"),
    "corrugation": (5, "area"),
    "depression": (6, "area"),
    "edge_cracking": (7, "linear"),
    "joint_reflection_cracking": (8, "linear"),
    "lane_shoulder_drop_off": (9, "linear"),
    "longitudinal_transverse_cracking": (10, "linear"),
    "patching_and_utility_cut_patching": (11, "area"),
    "polished_aggregate": (12, "area"),
    "potholes": (13, "count"),
    "railroad_crossing": (14, "area"),
    "rutting": (15, "area"),
    "shoving": (16, "area"),
    "slippage_cracking": (17, "area"),
    "swell": (18, "area"),
    "weathering": (19, "area"),
    "raveling": (19, "area"),
}

SEVERITIES = ("low", "medium", "high")

#: ASTM's standard asphalt sample unit, 2500 +/- 1000 sq ft (Section 2.1.7).
SAMPLE_UNIT_SQ_FT = 2500.0
SAMPLE_UNIT_SQ_M = SAMPLE_UNIT_SQ_FT * SQ_M_PER_SQ_FT          # ~232.3
SAMPLE_UNIT_TOLERANCE_SQ_M = 1000.0 * SQ_M_PER_SQ_FT           # ~92.9


def unit_of(distress: str) -> Unit:
    try:
        return ASPHALT_DISTRESSES[distress][1]
    except KeyError:
        known = ", ".join(sorted(ASPHALT_DISTRESSES))
        raise KeyError(f"unknown asphalt distress {distress!r}; expected one of: {known}") from None


def number_of(distress: str) -> int:
    return ASPHALT_DISTRESSES[distress][0]


def quantity_to_imperial(quantity: float, distress: str) -> float:
    """Convert a metric quantity (m2 / m / count) to the curves' units (ft2 / ft / count)."""
    unit = unit_of(distress)
    if unit == "area":
        return quantity / SQ_M_PER_SQ_FT
    if unit == "linear":
        return quantity / M_PER_FT
    return quantity


def area_to_imperial(area_sq_m: float) -> float:
    """Convert a sample-unit area in m2 to square feet."""
    return area_sq_m / SQ_M_PER_SQ_FT
