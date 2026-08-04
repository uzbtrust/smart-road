"""Turn detector output into an ASTM D6433 PCI for the road surface in view.

This is the join between the two halves of the project. The detector says
*what* and *where in the image*; ASTM needs *how much*, as a percentage of the
inspected area, in the units its curves were drawn in. Getting from one to the
other is where the assumptions live, so they are all in this module and all
stated.

What is assumed, and what each assumption costs
-----------------------------------------------
*Ground area comes from inverse perspective mapping.* Every detection's area is
integrated over its rows rather than taken at its centre, because a box 200 px
tall spans a large change in scale. Area goes as the square of the camera
height, so a 10 % error in that measurement is a 21 % error in every density and
therefore in the deduct value.

*Severity is not predicted.* The detector has no severity head — the training
data carried no consistent L/M/H labels. A severity has to be supplied, and the
resulting PCI is only as good as that choice. `pci_from_detections` takes it as
an argument with no default hidden inside, so the caller cannot forget.

*A bounding box is not the distress.* A diagonal crack fills a small fraction of
its box. For linear distresses the box diagonal is used as the length rather
than its area, which is closer but still an estimate. For area distresses the
box area is used directly and will over-report.

*One frame is not a sample unit.* ASTM's asphalt sample unit is 2500 ± 1000 sq
ft (232 ± 93 m²); a single frame usually sees less. The result is therefore a
reading for the visible surface, useful for comparison across frames, not a
certified sample-unit PCI. Aggregating frames into real sample units needs
frame-to-frame deduplication, which is a survey-level concern, not this one.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Sequence

import numpy as np

from ..geometry.ipm import Camera
from .astm import unit_of
from .engine import DEDUCT_FLOOR, MAX_DEDUCTS, allowable_deduct_count, \
    corrected_deduct_value, deduct_value, rate
from .from_survey import SQ_M_PER_EQUIVALENT_POTHOLE, imperial_density

#: Detector class name -> ASTM D6433 distress key. `marking_manhole` has no
#: entry: road markings and manhole covers are not pavement distresses. They are
#: detected because they are the things most often mistaken for one, and they
#: are excluded here rather than quietly inflating the deduct total.
CLASS_TO_DISTRESS: dict[str, str] = {
    "longitudinal_transverse_crack": "longitudinal_transverse_cracking",
    "alligator_crack": "alligator_cracking",
    "block_crack": "block_cracking",
    "patching": "patching_and_utility_cut_patching",
    "pothole": "potholes",
    "weathering_raveling": "weathering",
    "lane_shoulder_drop_off": "lane_shoulder_drop_off",
}


@dataclass(frozen=True)
class Quantity:
    """How much of one distress was seen, in metric units."""

    distress: str
    severity: str
    amount: float            # m2, m, or a count of equivalent potholes
    unit: str                # "area" | "linear" | "count"
    density_pct: float
    detections: int

    @property
    def label(self) -> str:
        return f"{self.distress} ({self.severity})"


@dataclass(frozen=True)
class FrameAssessment:
    pci: float
    rating: str
    max_cdv: float
    q: int
    inspected_area_m2: float
    quantities: list[Quantity]
    deduct_values: list[float]
    excluded: dict[str, int]

    def summary(self) -> str:
        return (f"PCI {self.pci:.1f} ({self.rating}) over "
                f"{self.inspected_area_m2:.0f} m2, max CDV {self.max_cdv:.1f} from q={self.q}")


def _box_ground_area_m2(cam: Camera, x1: float, y1: float, x2: float, y2: float,
                        near_m: float, far_m: float) -> float:
    """Ground area of an image-space box, integrating scale down its rows."""
    row_far, row_near = cam.usable_row_range(near_m, far_m)
    lo = max(y1, row_far)
    hi = min(y2, row_near)
    if hi <= lo:
        return 0.0
    rows = np.arange(math.floor(lo), math.ceil(hi), dtype=float)
    if rows.size == 0:
        return 0.0
    per_row = np.nan_to_num(cam.pixel_area_m2(rows), nan=0.0, posinf=0.0)
    return float(per_row.sum() * max(0.0, x2 - x1))


def _box_ground_length_m(cam: Camera, x1: float, y1: float, x2: float, y2: float,
                         near_m: float, far_m: float) -> float:
    """Ground length of a box's diagonal -- the usual stand-in for a crack."""
    row_far, row_near = cam.usable_row_range(near_m, far_m)
    ya = min(max(y1, row_far), row_near)
    yb = min(max(y2, row_far), row_near)
    if yb <= ya:
        return 0.0
    (xa, za), (xb, zb) = (cam.ground_from_pixel(x1, ya), cam.ground_from_pixel(x2, yb))
    if not all(np.isfinite(v) for v in (xa, za, xb, zb)):
        return 0.0
    return float(math.hypot(float(xb) - float(xa), float(zb) - float(za)))


def inspected_area_m2(cam: Camera, roi: tuple[int, int, int, int] | None = None,
                      near_m: float = 3.0, far_m: float = 15.0) -> float:
    """Ground area of the region the detector actually searched."""
    x0, y0, x1, y1 = roi if roi else (0, 0, cam.width, cam.height)
    return _box_ground_area_m2(cam, x0, y0, x1, y1, near_m, far_m)


def quantify(detections: Sequence, camera: Camera, *, severity: str,
             class_names: dict[int, str], roi: tuple[int, int, int, int] | None = None,
             near_m: float = 3.0, far_m: float = 15.0) -> tuple[list[Quantity], float, dict[str, int]]:
    """Group detections into per-distress metric quantities and densities.

    Returns the quantities, the inspected ground area, and a count of what was
    excluded and why -- an empty exclusion report and a full one produce very
    different PCIs, so the caller should be able to see it.
    """
    area_m2 = inspected_area_m2(camera, roi, near_m, far_m)
    if area_m2 <= 0:
        raise ValueError("the inspected region has no ground area; check camera pitch and roi")

    totals: dict[str, float] = {}
    counts: dict[str, int] = {}
    excluded: dict[str, int] = {}

    for det in detections:
        name = class_names.get(det.class_id, str(det.class_id))
        distress = CLASS_TO_DISTRESS.get(name)
        if distress is None:
            excluded[name] = excluded.get(name, 0) + 1
            continue

        unit = unit_of(distress)
        if unit == "linear":
            amount = _box_ground_length_m(camera, det.x1, det.y1, det.x2, det.y2, near_m, far_m)
        else:
            amount = _box_ground_area_m2(camera, det.x1, det.y1, det.x2, det.y2, near_m, far_m)
        if amount <= 0:
            excluded["outside measurable band"] = excluded.get("outside measurable band", 0) + 1
            continue
        if unit == "count":
            # ASTM X1.17.1.2: a large pothole counts as several.
            amount = max(1.0, amount / SQ_M_PER_EQUIVALENT_POTHOLE)

        totals[distress] = totals.get(distress, 0.0) + amount
        counts[distress] = counts.get(distress, 0) + 1

    quantities = [
        Quantity(distress=d, severity=severity, amount=a, unit=unit_of(d),
                 density_pct=a / area_m2 * 100.0, detections=counts[d])
        for d, a in sorted(totals.items())
    ]
    return quantities, area_m2, excluded


def pci_from_detections(detections: Sequence, camera: Camera, *, severity: str,
                        class_names: dict[int, str],
                        roi: tuple[int, int, int, int] | None = None,
                        near_m: float = 3.0, far_m: float = 15.0) -> FrameAssessment:
    """PCI for the road surface visible in one frame.

    `severity` applies to every detection, because the detector does not predict
    it. Run it at "low" and at "high" to see the range the answer really sits in.
    """
    if severity not in ("low", "medium", "high"):
        raise ValueError(f"severity must be low, medium or high, got {severity!r}")

    quantities, area_m2, excluded = quantify(
        detections, camera, severity=severity, class_names=class_names,
        roi=roi, near_m=near_m, far_m=far_m)

    deducts = sorted(
        (deduct_value(q.distress, q.severity, imperial_density(q.density_pct, q.distress))
         for q in quantities if q.density_pct > 0),
        reverse=True,
    )[:MAX_DEDUCTS]

    if not deducts:
        return FrameAssessment(100.0, rate(100.0)[0], 0.0, 0, area_m2,
                               quantities, [], excluded)

    m = allowable_deduct_count(deducts[0])
    whole = int(m)
    kept = deducts[:whole]
    if m - whole > 0 and len(deducts) > whole:
        kept.append(deducts[whole] * (m - whole))

    q = sum(1 for dv in kept if dv > DEDUCT_FLOOR)
    if q <= 1:
        cdv = min(sum(kept), 100.0)
    else:
        cdv = max(
            corrected_deduct_value(sum(kept[:qi] + [min(d, DEDUCT_FLOOR) for d in kept[qi:]]), qi)
            for qi in range(1, q + 1)
        )
    pci = max(0.0, 100.0 - cdv)
    return FrameAssessment(pci, rate(pci)[0], cdv, q, area_m2, quantities, deducts, excluded)
