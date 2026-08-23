"""Tests for slicing a drive into non-overlapping road sections.

The property under test throughout is that slices tile the road: they never
overlap, so quantities may be summed, and they never silently close a gap the
vehicle actually left unmeasured.
"""
from __future__ import annotations

import datetime as _dt

import pytest

from smartroad.survey.frames import GeoFrame
from smartroad.survey.sections import (MIN_SLICE_M, FrameWindow, assess_sections,
                                       coverage_report, effective_band,
                                       disjoint_windows, split_into_sections)

BASE = _dt.datetime(2026, 8, 3, 11, 38, tzinfo=_dt.timezone.utc)
NEAR, FAR = 3.0, 15.0


def frames(*chainages: float) -> list[GeoFrame]:
    return [GeoFrame(float(i), BASE + _dt.timedelta(seconds=i),
                     41.27, 69.2875, c, 6.5)
            for i, c in enumerate(chainages)]


# ------------------------------------------------------------------ tiling

def test_the_first_frame_keeps_its_whole_band():
    w = disjoint_windows(frames(0.0), near_m=NEAR, far_m=FAR)
    assert len(w) == 1
    assert (w[0].start_m, w[0].end_m) == (3.0, 15.0)
    assert w[0].length_m == 12.0
    assert w[0].near_m == NEAR


def test_each_later_frame_contributes_the_distance_travelled():
    """This is the whole point: no metre of road belongs to two frames."""
    w = disjoint_windows(frames(0.0, 6.3, 12.6), near_m=NEAR, far_m=FAR)
    assert [round(x.length_m, 3) for x in w] == [12.0, 6.3, 6.3]
    assert [round(x.start_m, 2) for x in w] == [3.0, 15.0, 21.3]
    assert [round(x.end_m, 2) for x in w] == [15.0, 21.3, 27.6]


def test_slices_never_overlap():
    w = disjoint_windows(frames(*[i * 6.3 for i in range(40)]))
    for a, b in zip(w, w[1:]):
        assert b.start_m >= a.end_m - 1e-9


def test_trimming_is_expressed_as_a_larger_near_distance():
    """quantify() clips by near_m, so the trim has to arrive that way."""
    w = disjoint_windows(frames(0.0, 6.3), near_m=NEAR, far_m=FAR)
    # Frame 1 starts where frame 0 stopped: 15.0 m of chainage, 8.7 m ahead.
    assert w[1].near_m == pytest.approx(8.7)
    assert w[1].far_m == FAR
    assert w[1].frame.chainage_m + w[1].near_m == pytest.approx(w[1].start_m)


def test_a_frame_inside_what_came_before_is_dropped():
    """A vehicle stopped at a light produces frames that add no new road."""
    w = disjoint_windows(frames(0.0, 0.1, 0.2, 6.3), near_m=NEAR, far_m=FAR)
    assert len(w) == 2
    assert [round(x.start_m, 2) for x in w] == [3.0, 15.0]


def test_frames_arriving_out_of_order_are_sorted_first():
    a = disjoint_windows(frames(0.0, 6.3, 12.6))
    b = disjoint_windows(frames(12.6, 0.0, 6.3))
    assert [(round(w.start_m, 3), round(w.end_m, 3)) for w in a] == \
           [(round(w.start_m, 3), round(w.end_m, 3)) for w in b]


def test_a_gap_is_left_open_rather_than_closed():
    """Outrun the band and the road between really was not measured."""
    w = disjoint_windows(frames(0.0, 40.0), near_m=NEAR, far_m=FAR)
    assert w[0].end_m == 15.0
    assert w[1].start_m == 43.0          # not pulled back to 15.0
    assert coverage_report(w)["largest_gap_m"] == pytest.approx(28.0)


def test_near_must_be_inside_far():
    with pytest.raises(ValueError, match="near < far"):
        disjoint_windows(frames(0.0), near_m=15.0, far_m=3.0)


def test_no_frames_no_windows():
    assert disjoint_windows([]) == []


# ---------------------------------------------------------------- sectioning

def test_sections_are_cut_at_multiples_of_the_length():
    """Fixed boundaries let two surveys of one street be compared directly."""
    w = disjoint_windows(frames(*[i * 6.0 for i in range(30)]))
    secs = split_into_sections(w, section_m=50.0, start_m=0.0)
    assert [s.start_m for s in secs[:4]] == [0.0, 50.0, 100.0, 150.0]
    assert all(s.index == i for i, s in enumerate(secs))


def test_a_frame_spanning_a_boundary_is_split_across_it():
    """Not assigned whole to whichever side its midpoint lands on."""
    w = disjoint_windows(frames(0.0), near_m=NEAR, far_m=FAR)   # [3, 15]
    secs = split_into_sections(w, section_m=10.0, start_m=0.0, end_m=20.0)
    assert [round(s.covered_m, 3) for s in secs] == [7.0, 5.0]
    assert sum(s.covered_m for s in secs) == pytest.approx(w[0].length_m)


def test_a_split_frame_keeps_a_consistent_near_and_far():
    w = disjoint_windows(frames(0.0), near_m=NEAR, far_m=FAR)
    first = split_into_sections(w, section_m=10.0, start_m=0.0, end_m=20.0)[0]
    piece = first.windows[0]
    c = piece.frame.chainage_m
    assert c + piece.near_m == pytest.approx(piece.start_m)
    assert c + piece.far_m == pytest.approx(piece.end_m)
    assert piece.near_m == pytest.approx(3.0)
    assert piece.far_m == pytest.approx(10.0)


def test_covered_never_exceeds_the_section_length():
    w = disjoint_windows(frames(*[i * 6.3 for i in range(60)]))
    for s in split_into_sections(w, section_m=100.0):
        assert s.covered_m <= s.length_m + 1e-9
        assert 0.0 <= s.coverage_fraction <= 1.0


def test_coverage_fraction_reports_a_partly_measured_section():
    """A third of a section measured is a third of a sample, and must say so."""
    w = disjoint_windows(frames(0.0), near_m=NEAR, far_m=FAR)   # 12 m of road
    only = split_into_sections(w, section_m=36.0, start_m=3.0, end_m=39.0)[0]
    assert only.coverage_fraction == pytest.approx(1 / 3, abs=0.01)
    assert only.gaps_m == pytest.approx(24.0, abs=0.1)


def test_slivers_below_the_minimum_are_not_kept():
    w = [FrameWindow(frames(0.0)[0], 3.0, 15.0, 3.0, 15.0)]
    # A boundary a hair above 3.0 leaves a sliver on the low side.
    secs = split_into_sections(w, section_m=0.1 + MIN_SLICE_M / 2,
                               start_m=3.0, end_m=3.0 + MIN_SLICE_M / 2)
    assert all(len(s) == 0 for s in secs)


def test_section_length_must_be_positive():
    w = disjoint_windows(frames(0.0))
    with pytest.raises(ValueError, match="must be positive"):
        split_into_sections(w, section_m=0.0)


def test_no_windows_no_sections():
    assert split_into_sections([], section_m=100.0) == []


# ------------------------------------------------------------------ coverage

def test_coverage_report_adds_up():
    w = disjoint_windows(frames(*[i * 6.3 for i in range(20)]))
    rep = coverage_report(w)
    assert rep["covered_m"] + rep["gap_m"] == pytest.approx(rep["span_m"])
    assert rep["coverage_fraction"] == pytest.approx(1.0)
    assert rep["largest_gap_m"] == 0.0


def test_coverage_report_on_nothing_is_zero_not_an_error():
    assert coverage_report([])["span_m"] == 0.0


# ------------------------------------------------------------------- grading

@pytest.fixture
def camera():
    from smartroad.geometry.ipm import Camera
    return Camera.create(width=1920, height=1080, height_m=1.70,
                         focal_35mm=25.0, horizon_row=0.139 * 1080)


NAMES = {0: "alligator_crack", 1: "longitudinal_transverse_crack"}


def _det(cls=0, box=(800, 700, 1100, 900)):
    from smartroad.detect.tiled import Detection
    x1, y1, x2, y2 = box
    return Detection(x1, y1, x2, y2, 0.8, cls)


def test_a_section_with_no_distress_scores_100(camera):
    w = disjoint_windows(frames(0.0, 6.3))
    secs = split_into_sections(w, section_m=100.0)
    got = assess_sections(secs, {}, camera, severity="medium", class_names=NAMES)
    assert got[0].pci == 100.0
    assert got[0].rating == "Good"


def test_density_is_over_the_area_the_section_actually_inspected(camera):
    """Not the nominal band -- the trimmed slices that were really measured."""
    w = disjoint_windows(frames(0.0, 6.3, 12.6))
    secs = split_into_sections(w, section_m=100.0)
    by_frame = {f.t_s: [_det()] for f in [x.frame for x in w]}
    got = assess_sections(secs, by_frame, camera, severity="medium",
                          class_names=NAMES)[0]
    assert got.inspected_area_m2 > 0
    assert got.quantities
    q = got.quantities[0]
    assert q.density_pct == pytest.approx(q.amount / got.inspected_area_m2 * 100.0)


def test_the_same_distress_seen_twice_is_not_counted_twice(camera):
    """A frame wholly inside its predecessor adds no area and no quantity."""
    from smartroad.survey.frames import GeoFrame
    moving = frames(0.0, 6.3)
    stopped = moving + [GeoFrame(2.0, BASE, 41.27, 69.2875, 6.4, 0.0)]

    def graded(fs):
        w = disjoint_windows(fs)
        secs = split_into_sections(w, section_m=100.0)
        by_frame = {f.t_s: [_det()] for f in fs}
        return assess_sections(secs, by_frame, camera, severity="medium",
                               class_names=NAMES)[0]

    a, b = graded(moving), graded(stopped)
    assert b.inspected_area_m2 == pytest.approx(a.inspected_area_m2, rel=0.02)
    assert b.pci == pytest.approx(a.pci, abs=0.5)


def test_severity_moves_the_score_the_way_astm_says(camera):
    w = disjoint_windows(frames(0.0, 6.3))
    secs = split_into_sections(w, section_m=100.0)
    by_frame = {x.frame.t_s: [_det()] for x in w}
    scores = [assess_sections(secs, by_frame, camera, severity=s,
                              class_names=NAMES)[0].pci
              for s in ("low", "medium", "high")]
    assert scores[0] >= scores[1] >= scores[2]


def test_unknown_classes_are_reported_not_silently_dropped(camera):
    w = disjoint_windows(frames(0.0))
    secs = split_into_sections(w, section_m=100.0)
    by_frame = {w[0].frame.t_s: [_det(cls=99)]}
    got = assess_sections(secs, by_frame, camera, severity="medium",
                          class_names={99: "not_a_distress"})[0]
    assert got.excluded
    assert got.pci == 100.0


def test_summary_names_the_chainage_and_the_coverage(camera):
    w = disjoint_windows(frames(0.0, 6.3))
    secs = split_into_sections(w, section_m=100.0)
    got = assess_sections(secs, {}, camera, severity="medium", class_names=NAMES)[0]
    assert "m: PCI" in got.summary and "% measured" in got.summary


def test_a_slice_outside_the_searched_region_is_dropped_not_fatal(camera):
    """The sky cut-off ends the searched band around 6.8 m on 16:9 footage.

    Trimming pushes later frames past that, so their slices are real road the
    detector never examined. Those must be counted and skipped, not allowed to
    abort the section they sit in.
    """
    from smartroad.detect.tiled import road_roi
    roi = road_roi(camera.width, camera.height, top_fraction=0.45)
    w = disjoint_windows(frames(0.0, 6.3), near_m=3.0, far_m=15.0)
    assert w[1].near_m > 8.0                       # beyond what the ROI sees
    secs = split_into_sections(w, section_m=100.0)
    got = assess_sections(secs, {}, camera, severity="medium",
                          class_names=NAMES, roi=roi)
    assert got
    assert any("slice outside the searched region" in a.excluded for a in got)


# ------------------------------------------------------------ effective band

def test_the_roi_and_not_far_m_decides_how_far_a_frame_sees(camera):
    """far_m is a request. The sky cut-off is what answers it."""
    from smartroad.detect.tiled import road_roi
    roi = road_roi(camera.width, camera.height, top_fraction=0.45)
    near, far = effective_band(camera, roi, near_m=3.0, far_m=15.0)
    assert near == pytest.approx(3.0, abs=0.01)
    assert far < 15.0                       # the request is not granted
    assert far == pytest.approx(6.8, abs=0.3)


def test_lowering_the_sky_cut_off_lets_the_band_reach_further(camera):
    from smartroad.detect.tiled import road_roi
    reach = [effective_band(camera,
                            road_roi(camera.width, camera.height, top_fraction=tf),
                            3.0, 15.0)[1]
             for tf in (0.45, 0.35, 0.25)]
    assert reach == sorted(reach)
    assert reach[-1] == pytest.approx(15.0, abs=0.1)   # request finally met


def test_without_a_roi_the_band_is_what_was_asked_for(camera):
    near, far = effective_band(camera, None, near_m=3.0, far_m=15.0)
    assert (near, far) == (pytest.approx(3.0, abs=0.01), pytest.approx(15.0, abs=0.01))


def test_a_band_the_roi_excludes_entirely_is_empty_not_negative(camera):
    """Asking to measure beyond the searched region measures nothing."""
    # An ROI covering only the bottom rows sees only very near ground.
    roi = (0, camera.height - 5, camera.width, camera.height)
    near, far = effective_band(camera, roi, near_m=12.0, far_m=15.0)
    assert (near, far) == (0.0, 0.0)


def test_tiling_the_effective_band_reports_the_gaps_it_leaves(camera):
    """At 6.3 m between frames a 3.8 m band cannot cover the road."""
    from smartroad.detect.tiled import road_roi
    roi = road_roi(camera.width, camera.height, top_fraction=0.45)
    near, far = effective_band(camera, roi, 3.0, 15.0)
    w = disjoint_windows(frames(*[i * 6.3 for i in range(20)]),
                         near_m=near, far_m=far)
    rep = coverage_report(w)
    assert rep["coverage_fraction"] < 0.7
    assert rep["largest_gap_m"] > 2.0
