"""Turn a drive into road sections without counting the same asphalt twice.

`video.py` grades frames and says plainly that their densities must never be
summed: at one sample per second the frames are closer together than the band
each one measures, so a crack lying in the overlap is counted once per frame
that sees it. `frames.py` supplies the missing piece, a chainage in metres for
every frame. This module uses it to give each frame a slice of road that no
other frame owns, and then bins those slices into sections.

THE DEDUPLICATION. A frame placed at chainage c measures the band between
`near_m` and `far_m` ahead of the camera, which is the road from c+near to
c+far. Sorted by chainage, each frame's slice is trimmed to start where the
previous one stopped:

    frame 0 at   0.0 m  ->  [ 3.0, 15.0]   12.0 m of road
    frame 1 at   6.3 m  ->  [15.0, 21.3]    6.3 m   (trimmed from 9.3)
    frame 2 at  12.6 m  ->  [21.3, 27.6]    6.3 m

After the first, every frame contributes exactly the distance travelled since
the last one, and the slices tile the road end to end with no gaps and no
overlaps. Where the vehicle moved further than the band is deep, the slices
stop touching and the gap is real -- unmeasured road, reported rather than
interpolated over, because a density computed against an area that was never
looked at is not a density.

Trimming is expressed as a larger `near_m` for that frame, which is all the
existing geometry needs: `_box_ground_area_m2` and `_box_ground_length_m` both
clip to `usable_row_range(near_m, far_m)`, so passing the trimmed band shrinks
the inspected area and every distress quantity in step, with no second code
path to keep in agreement.

WHAT THIS STILL DOES NOT FIX. Potholes are counted, not measured, and ASTM
floors a partial one at a single pothole. A pothole straddling the line between
two slices therefore counts once on each side. Area and linear distresses --
alligator, block, longitudinal, which are the bulk of what the detector finds
-- are clipped by geometry and do not have this problem. Fixing the count case
needs detections tracked between frames, which is a different piece of work.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from smartroad.survey.frames import GeoFrame

#: Below this a slice is too thin to carry a useful density; it is dropped and
#: reported. A frame worth less than a hand's width of road is noise.
MIN_SLICE_M = 0.25


@dataclass(frozen=True)
class FrameWindow:
    """One frame's exclusive slice of the road, in chainage and in camera terms."""

    frame: GeoFrame
    near_m: float          #: trimmed near distance, to pass back to quantify()
    far_m: float
    start_m: float         #: chainage of the near edge
    end_m: float           #: chainage of the far edge

    @property
    def length_m(self) -> float:
        return self.end_m - self.start_m

    def clipped_to(self, start_m: float, end_m: float) -> "FrameWindow | None":
        """This slice restricted to a chainage interval, or None if disjoint.

        A frame that straddles a section boundary contributes its near part to
        one section and its far part to the next, rather than landing wholly in
        whichever section its midpoint happens to fall in.
        """
        lo, hi = max(self.start_m, start_m), min(self.end_m, end_m)
        if hi - lo < MIN_SLICE_M:
            return None
        c = self.frame.chainage_m
        return FrameWindow(self.frame, lo - c, hi - c, lo, hi)


def effective_band(camera, roi: tuple[int, int, int, int] | None = None,
                   near_m: float = 3.0, far_m: float = 15.0) -> tuple[float, float]:
    """The distances a frame really measures, after the ROI has had its say.

    `far_m` is a request, not a result. The detector only searches inside the
    region of interest, and the sky cut-off puts the top of that region well
    below the horizon -- on 16:9 drive footage at the default cut-off of 0.45,
    row 324 of 720 is 6.8 m away, so asking for 15 m measures nothing beyond
    6.8 m and the extra is silently discarded by the row clipping in
    `_box_ground_area_m2`.

    Getting this right matters for tiling: at 6.3 m between frames a nominal
    3-15 m band looks like a 12 m overlap to remove, while the real 2.2-6.8 m
    band is 4.6 m deep and leaves 1.7 m of road between frames unmeasured. One
    of those stories is true and it is not the one the parameters suggest.
    """
    top = roi[1] if roi else 0
    bottom = (roi[3] if roi else camera.height) - 1
    row_far = max(float(top), camera.row_at_distance(far_m))
    row_near = min(float(bottom), camera.row_at_distance(near_m))
    if row_near <= row_far:
        return (0.0, 0.0)
    return (float(camera.distance_at_row(row_near)),
            float(camera.distance_at_row(row_far)))


def disjoint_windows(frames: list[GeoFrame], *, near_m: float = 3.0,
                     far_m: float = 15.0) -> list[FrameWindow]:
    """Give every frame a slice of road that no other frame owns."""
    if not 0 < near_m < far_m:
        raise ValueError(f"need 0 < near < far, got {near_m}, {far_m}")

    windows: list[FrameWindow] = []
    reached = -math.inf
    for frame in sorted(frames, key=lambda f: f.chainage_m):
        raw_start = frame.chainage_m + near_m
        raw_end = frame.chainage_m + far_m
        start = max(raw_start, reached)
        if raw_end - start < MIN_SLICE_M:
            continue                      # wholly inside what came before
        windows.append(FrameWindow(frame, start - frame.chainage_m, far_m,
                                   start, raw_end))
        reached = raw_end
    return windows


@dataclass(frozen=True)
class Section:
    """A stretch of road and the frame slices that measured it."""

    index: int
    start_m: float
    end_m: float
    windows: list[FrameWindow]

    @property
    def length_m(self) -> float:
        return self.end_m - self.start_m

    @property
    def covered_m(self) -> float:
        """Road actually measured. Slices are disjoint, so this is a plain sum."""
        return sum(w.length_m for w in self.windows)

    @property
    def coverage_fraction(self) -> float:
        return 0.0 if self.length_m <= 0 else self.covered_m / self.length_m

    @property
    def gaps_m(self) -> float:
        return max(0.0, self.length_m - self.covered_m)

    def __len__(self) -> int:
        return len(self.windows)


def split_into_sections(windows: list[FrameWindow], *, section_m: float,
                        start_m: float | None = None,
                        end_m: float | None = None) -> list[Section]:
    """Cut the measured road into fixed-length sections.

    Boundaries are at multiples of `section_m` from `start_m`, so two surveys of
    the same street cut at the same places and can be compared section by
    section. A frame spanning a boundary is split across it.

    The final section is whatever is left and is usually short; its
    `coverage_fraction` says how much of it was measured, which matters more
    than its length -- ASTM's densities are per unit area inspected, and a
    section measured a third of the way along is a third of a sample.
    """
    if section_m <= 0:
        raise ValueError(f"section_m must be positive, got {section_m}")
    if not windows:
        return []

    lo = min(w.start_m for w in windows) if start_m is None else start_m
    hi = max(w.end_m for w in windows) if end_m is None else end_m
    if hi <= lo:
        return []

    sections: list[Section] = []
    count = math.ceil((hi - lo) / section_m)
    for i in range(count):
        s = lo + i * section_m
        e = min(s + section_m, hi)
        inside = [c for c in (w.clipped_to(s, e) for w in windows) if c is not None]
        sections.append(Section(i, s, e, inside))
    return sections


def coverage_report(windows: list[FrameWindow]) -> dict[str, float]:
    """How much road the drive actually measured, and where it did not.

    `span_m` is end to end; `covered_m` excludes the gaps where the vehicle
    outran its own measuring band. The difference is road nobody looked at, and
    it belongs in a report rather than being averaged away.
    """
    if not windows:
        return {"span_m": 0.0, "covered_m": 0.0, "gap_m": 0.0,
                "coverage_fraction": 0.0, "largest_gap_m": 0.0}

    ordered = sorted(windows, key=lambda w: w.start_m)
    span = ordered[-1].end_m - ordered[0].start_m
    covered = sum(w.length_m for w in ordered)
    largest = max((b.start_m - a.end_m for a, b in zip(ordered, ordered[1:])),
                  default=0.0)
    return {"span_m": span, "covered_m": covered,
            "gap_m": max(0.0, span - covered),
            "coverage_fraction": covered / span if span > 0 else 0.0,
            "largest_gap_m": max(0.0, largest)}


@dataclass(frozen=True)
class SectionAssessment:
    """A graded road section."""

    section: "Section"
    pci: float
    rating: str
    max_cdv: float
    q: int
    inspected_area_m2: float
    quantities: list
    deduct_values: list[float]
    excluded: dict[str, int]

    @property
    def summary(self) -> str:
        s = self.section
        return (f"{s.start_m:.0f}-{s.end_m:.0f} m: PCI {self.pci:.1f} "
                f"({self.rating}) over {self.inspected_area_m2:.0f} m2 from "
                f"{len(s)} frames, {s.coverage_fraction * 100:.0f}% measured")


def assess_sections(sections: list["Section"], detections_by_frame, camera, *,
                    severity: str, class_names: dict[int, str],
                    roi: tuple[int, int, int, int] | None = None
                    ) -> list[SectionAssessment]:
    """Grade each section from the frames that measured it.

    `detections_by_frame` maps a frame's `t_s` to its detections.

    Quantities are summed across the section's slices and divided by the total
    area those slices inspected, which is the density ASTM asks for -- amount
    per unit area actually looked at. Averaging the frames' own PCIs instead
    would be wrong twice over: PCI is not linear in density, and a frame that
    measured two metres would weigh the same as one that measured twelve.
    """
    from smartroad.pci.from_detections import (Quantity, inspected_area_m2,
                                               pci_from_quantities, quantify)

    out: list[SectionAssessment] = []
    for section in sections:
        totals: dict[tuple[str, str], float] = {}
        counts: dict[tuple[str, str], int] = {}
        units: dict[str, str] = {}
        area = 0.0
        excluded: dict[str, int] = {}

        for window in section.windows:
            # A trimmed slice can land wholly outside the searched region: the
            # sky cut-off puts the top of the ROI around 6.8 m out on 16:9
            # footage, so a slice starting at 8.7 m is real road that the
            # detector never looked at. quantify() refuses a band with no
            # ground area rather than dividing by it, so such a slice is
            # dropped and counted here instead of aborting its whole section.
            # See effective_band() for why far_m alone does not tell you this.
            if inspected_area_m2(camera, roi, window.near_m, window.far_m) <= 0:
                excluded["slice outside the searched region"] = \
                    excluded.get("slice outside the searched region", 0) + 1
                continue
            dets = detections_by_frame.get(window.frame.t_s, ())
            quantities, slice_area, slice_excluded = quantify(
                dets, camera, severity=severity, class_names=class_names,
                roi=roi, near_m=window.near_m, far_m=window.far_m)
            area += slice_area
            for name, n in slice_excluded.items():
                excluded[name] = excluded.get(name, 0) + n
            for q in quantities:
                key = (q.distress, q.severity)
                totals[key] = totals.get(key, 0.0) + q.amount
                counts[key] = counts.get(key, 0) + q.detections
                units[q.distress] = q.unit

        merged = [
            Quantity(distress=d, severity=sev, amount=a, unit=units[d],
                     density_pct=(a / area * 100.0) if area > 0 else 0.0,
                     detections=counts[(d, sev)])
            for (d, sev), a in sorted(totals.items())
        ]
        graded = pci_from_quantities(merged, area, excluded)
        out.append(SectionAssessment(section, graded.pci, graded.rating,
                                     graded.max_cdv, graded.q, area, merged,
                                     graded.deduct_values, graded.excluded))
    return out
