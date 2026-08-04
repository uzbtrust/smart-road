"""Tests for turning detections into an ASTM D6433 grade.

The dangerous failure is a plausible one: a wrong ground area still yields a
density, a deduct value and a PCI that all look reasonable. So the central test
projects a rectangle of *known* ground size into the image, hands the resulting
box in as a detection, and checks the area that comes back out.
"""
from __future__ import annotations

import math

import pytest

from smartroad.detect.tiled import Detection
from smartroad.geometry.ipm import Camera
from smartroad.pci.from_detections import (CLASS_TO_DISTRESS, inspected_area_m2,
                                           pci_from_detections, quantify)

# Roughly the survey vehicle: 25 mm equivalent on a 1920x1080 frame, 1.95 m up.
CAM = Camera.create(width=1920, height=1080, height_m=1.95,
                    focal_35mm=25.0, horizon_row=150)

NAMES = {0: "longitudinal_transverse_crack", 1: "alligator_crack",
         2: "block_crack", 3: "patching", 4: "pothole",
         5: "weathering_raveling", 6: "lane_shoulder_drop_off",
         7: "marking_manhole"}

NEAR, FAR = 3.0, 12.0


def box_for_ground_rect(x0, x1, z0, z1):
    """Image-space box enclosing a ground rectangle, as the detector would give."""
    us, vs = [], []
    for x in (x0, x1):
        for z in (z0, z1):
            u, v = CAM.pixel_from_ground(x, z)
            us.append(float(u))
            vs.append(float(v))
    return min(us), min(vs), max(us), max(vs)


class TestGroundArea:
    def test_area_of_a_known_rectangle_is_recovered(self):
        """A 2 m x 0.5 m patch on the road must measure ~1 m2.

        Kept shallow in depth on purpose. A box is axis-aligned and the ground
        rectangle projects to a trapezoid, so over a long run of depth the box
        covers noticeably more road than the rectangle does -- that effect is
        measured separately below. Here it is under 5 %, leaving the projection
        itself as the thing under test.
        """
        x1, y1, x2, y2 = box_for_ground_rect(-1.0, 1.0, 5.0, 5.5)
        det = Detection(x1, y1, x2, y2, 0.9, 3)          # patching, an area distress

        quantities, area, _ = quantify([det], CAM, severity="medium",
                                       class_names=NAMES, near_m=NEAR, far_m=FAR)
        assert len(quantities) == 1
        assert quantities[0].amount == pytest.approx(1.0, rel=0.10)

    def test_a_deep_box_over_reports_by_the_predicted_amount(self):
        """Quantifies the bounding-box approximation rather than hiding it.

        The box takes its width from the near edge and holds it for every row.
        A row at distance z therefore stands for `w * z / z_near` metres of
        road instead of `w`, so the reported area is the integral of that,
        which for 2 m over 5..8 m is 7.8 m2 against a true 6.0 m2 -- a 30 %
        over-report. Anything measured off a box, not a mask, carries this.
        """
        x1, y1, x2, y2 = box_for_ground_rect(-1.0, 1.0, 5.0, 8.0)
        det = Detection(x1, y1, x2, y2, 0.9, 3)
        measured = quantify([det], CAM, severity="medium", class_names=NAMES,
                            near_m=NEAR, far_m=FAR)[0][0].amount

        width, z0, z1 = 2.0, 5.0, 8.0
        predicted = width * (z1 ** 2 - z0 ** 2) / (2 * z0)       # 7.8 m2
        assert measured > 6.0, "a box cannot under-report its own trapezoid"
        assert measured == pytest.approx(predicted, rel=0.10)

    def test_area_scales_with_the_square_of_camera_height(self):
        """The dominant error term, stated in the docs -- assert it."""
        x1, y1, x2, y2 = box_for_ground_rect(-1.0, 1.0, 5.0, 8.0)
        det = Detection(x1, y1, x2, y2, 0.9, 3)

        tall = Camera.create(width=1920, height=1080, height_m=1.95 * 1.1,
                             focal_35mm=25.0, horizon_row=150)
        a = quantify([det], CAM, severity="medium", class_names=NAMES,
                     near_m=NEAR, far_m=FAR)[0][0].amount
        b = quantify([det], tall, severity="medium", class_names=NAMES,
                     near_m=NEAR, far_m=FAR)[0][0].amount
        assert b / a == pytest.approx(1.1 ** 2, rel=0.02)

    def test_inspected_area_is_positive_and_finite(self):
        area = inspected_area_m2(CAM, near_m=NEAR, far_m=FAR)
        assert 0 < area < 10_000
        assert math.isfinite(area)


class TestQuantify:
    def test_density_is_amount_over_inspected_area(self):
        x1, y1, x2, y2 = box_for_ground_rect(-1.0, 1.0, 5.0, 8.0)
        det = Detection(x1, y1, x2, y2, 0.9, 3)
        quantities, area, _ = quantify([det], CAM, severity="medium",
                                       class_names=NAMES, near_m=NEAR, far_m=FAR)
        q = quantities[0]
        assert q.density_pct == pytest.approx(q.amount / area * 100)

    def test_markings_are_never_graded(self):
        """Road markings and manholes are not pavement distresses."""
        x1, y1, x2, y2 = box_for_ground_rect(-1.0, 1.0, 5.0, 8.0)
        det = Detection(x1, y1, x2, y2, 0.9, 7)
        quantities, _, excluded = quantify([det], CAM, severity="medium",
                                           class_names=NAMES, near_m=NEAR, far_m=FAR)
        assert quantities == []
        assert excluded["marking_manhole"] == 1

    def test_marking_is_absent_from_the_distress_map(self):
        assert "marking_manhole" not in CLASS_TO_DISTRESS
        assert set(CLASS_TO_DISTRESS) | {"marking_manhole"} == set(NAMES.values())

    def test_a_crack_is_measured_as_length_not_area(self):
        x1, y1, x2, y2 = box_for_ground_rect(-0.1, 0.1, 5.0, 8.0)
        det = Detection(x1, y1, x2, y2, 0.9, 0)          # longitudinal crack
        q = quantify([det], CAM, severity="medium", class_names=NAMES,
                     near_m=NEAR, far_m=FAR)[0][0]
        assert q.unit == "linear"
        assert q.amount == pytest.approx(3.0, rel=0.25)   # ~3 m of crack

    def test_potholes_become_equivalent_counts(self):
        """ASTM X1.17.1.2: a hole is divided by 0.5 m2 to get a count."""
        x1, y1, x2, y2 = box_for_ground_rect(-1.0, 1.0, 5.0, 5.5)    # ~1 m2
        det = Detection(x1, y1, x2, y2, 0.9, 4)
        q = quantify([det], CAM, severity="medium", class_names=NAMES,
                     near_m=NEAR, far_m=FAR)[0][0]
        assert q.unit == "count"
        assert q.amount == pytest.approx(1.0 / 0.5, rel=0.12)

    def test_a_small_pothole_still_counts_as_one(self):
        x1, y1, x2, y2 = box_for_ground_rect(-0.05, 0.05, 5.0, 5.1)   # far under 0.5 m2
        det = Detection(x1, y1, x2, y2, 0.9, 4)
        q = quantify([det], CAM, severity="medium", class_names=NAMES,
                     near_m=NEAR, far_m=FAR)[0][0]
        assert q.amount == 1.0

    def test_detections_of_one_class_are_pooled(self):
        a = Detection(*box_for_ground_rect(-1.0, 0.0, 5.0, 6.0), 0.9, 3)
        b = Detection(*box_for_ground_rect(0.5, 1.5, 6.0, 7.0), 0.8, 3)
        quantities, _, _ = quantify([a, b], CAM, severity="medium",
                                    class_names=NAMES, near_m=NEAR, far_m=FAR)
        assert len(quantities) == 1
        assert quantities[0].detections == 2

    def test_detections_beyond_the_measurable_band_are_dropped(self):
        far = Detection(*box_for_ground_rect(-1.0, 1.0, 60.0, 70.0), 0.9, 3)
        quantities, _, excluded = quantify([far], CAM, severity="medium",
                                           class_names=NAMES, near_m=NEAR, far_m=FAR)
        assert quantities == []
        assert excluded


class TestPci:
    def test_clean_road_scores_100(self):
        r = pci_from_detections([], CAM, severity="medium", class_names=NAMES,
                                near_m=NEAR, far_m=FAR)
        assert r.pci == 100.0
        assert r.rating == "Good"

    def test_severity_lowers_the_score_monotonically(self):
        det = Detection(*box_for_ground_rect(-1.0, 1.0, 5.0, 8.0), 0.9, 1)
        scores = [pci_from_detections([det], CAM, severity=s, class_names=NAMES,
                                      near_m=NEAR, far_m=FAR).pci
                  for s in ("low", "medium", "high")]
        assert scores[0] > scores[1] > scores[2]

    def test_more_distress_lowers_the_score(self):
        small = Detection(*box_for_ground_rect(-0.3, 0.3, 5.0, 5.6), 0.9, 1)
        big = Detection(*box_for_ground_rect(-1.6, 1.6, 4.5, 9.0), 0.9, 1)
        a = pci_from_detections([small], CAM, severity="medium",
                                class_names=NAMES, near_m=NEAR, far_m=FAR)
        b = pci_from_detections([big], CAM, severity="medium",
                                class_names=NAMES, near_m=NEAR, far_m=FAR)
        assert b.pci < a.pci

    def test_pci_is_a_hundred_minus_the_corrected_deduct(self):
        det = Detection(*box_for_ground_rect(-1.0, 1.0, 5.0, 8.0), 0.9, 1)
        r = pci_from_detections([det], CAM, severity="medium", class_names=NAMES,
                                near_m=NEAR, far_m=FAR)
        assert r.pci == pytest.approx(100.0 - r.max_cdv)
        assert 0.0 <= r.pci <= 100.0

    def test_deducts_are_sorted_descending(self):
        dets = [Detection(*box_for_ground_rect(-1.0, 1.0, 5.0, 8.0), 0.9, 1),
                Detection(*box_for_ground_rect(-1.0, 1.0, 8.0, 10.0), 0.9, 3),
                Detection(*box_for_ground_rect(-0.2, 0.2, 5.0, 9.0), 0.9, 0)]
        r = pci_from_detections(dets, CAM, severity="medium", class_names=NAMES,
                                near_m=NEAR, far_m=FAR)
        assert r.deduct_values == sorted(r.deduct_values, reverse=True)

    @pytest.mark.parametrize("bad", ["Low", "severe", "", None])
    def test_rejects_an_unknown_severity(self, bad):
        with pytest.raises(ValueError):
            pci_from_detections([], CAM, severity=bad, class_names=NAMES)

    def test_rejects_a_region_with_no_ground_area(self):
        up = Camera.create(width=1920, height=1080, height_m=1.95,
                           focal_35mm=25.0, pitch_deg=-40)   # aimed at the sky
        with pytest.raises(ValueError):
            pci_from_detections([], up, severity="medium", class_names=NAMES,
                                roi=(0, 0, 1920, 200))
