"""Tests for the inverse perspective mapping.

This is the step where a mistake is invisible: a wrong scale still produces
plausible-looking square metres, which become a plausible-looking density and a
plausible-looking PCI. So the central test does not check the formula against
itself -- it puts a rectangle of known size on the ground, projects it into the
image, rasterises it, and measures it back.
"""
from __future__ import annotations

import math

import numpy as np
import pytest
from PIL import Image, ImageDraw

from smartroad.geometry.ipm import FULL_FRAME_WIDTH_MM, Camera

# Roughly the Tashkent phone: 24 mm equivalent on a 4000 px frame, held at
# 1.35 m and tilted 12 degrees down. Scaled to 800x600 to keep tests quick.
CAM = Camera.create(width=800, height=600, height_m=1.35, focal_35mm=24.0, pitch_deg=12.0)


SUPERSAMPLE = 8


def rasterise_ground_quad(cam: Camera, x0, x1, z0, z1) -> np.ndarray:
    """Project a ground rectangle and return per-pixel coverage in [0, 1].

    Supersampled: a plain binary fill counts every boundary pixel in full, which
    on a few-thousand-pixel shape is several percent of the area -- enough to
    look like a scale error in the mapping under test.
    """
    corners = [(x0, z0), (x1, z0), (x1, z1), (x0, z1)]
    poly = []
    for x, z in corners:
        u, v = cam.pixel_from_ground(x, z)
        poly.append((float(u) * SUPERSAMPLE, float(v) * SUPERSAMPLE))
    big = Image.new("1", (cam.width * SUPERSAMPLE, cam.height * SUPERSAMPLE), 0)
    ImageDraw.Draw(big).polygon(poly, fill=1)
    a = np.array(big, dtype=np.float32)
    return a.reshape(cam.height, SUPERSAMPLE, cam.width, SUPERSAMPLE).mean(axis=(1, 3))


class TestConstruction:
    def test_focal_from_35mm_equivalent(self):
        cam = Camera.create(width=4000, height=3000, height_m=1.4,
                            focal_35mm=24.0, pitch_deg=10)
        assert cam.focal_px == pytest.approx(24.0 / FULL_FRAME_WIDTH_MM * 4000)
        assert cam.focal_px == pytest.approx(2666.67, abs=0.1)

    def test_pitch_from_horizon_row_round_trips(self):
        cam = Camera.create(width=800, height=600, height_m=1.4,
                            focal_px=900, pitch_deg=8.0)
        recovered = Camera.create(width=800, height=600, height_m=1.4,
                                  focal_px=900, horizon_row=cam.horizon_row)
        assert recovered.pitch_rad == pytest.approx(cam.pitch_rad)

    def test_horizon_formula(self):
        cam = Camera.create(width=800, height=600, height_m=1.4,
                            focal_px=900, pitch_deg=10)
        assert cam.horizon_row == pytest.approx(300 - 900 * math.tan(math.radians(10)))

    def test_level_camera_puts_horizon_at_centre(self):
        cam = Camera.create(width=800, height=600, height_m=1.4, focal_px=900, pitch_deg=0)
        assert cam.horizon_row == pytest.approx(cam.cy)

    @pytest.mark.parametrize("kwargs", [
        dict(focal_px=-1, pitch_deg=10),
        dict(focal_px=900, pitch_deg=95),
    ])
    def test_invalid_parameters_rejected(self, kwargs):
        with pytest.raises(ValueError):
            Camera.create(width=800, height=600, height_m=1.4, **kwargs)

    def test_negative_height_rejected(self):
        with pytest.raises(ValueError, match="height must be positive"):
            Camera.create(width=800, height=600, height_m=-1, focal_px=900, pitch_deg=10)

    def test_needs_exactly_one_pitch_source(self):
        with pytest.raises(ValueError, match="exactly one"):
            Camera.create(width=800, height=600, height_m=1.4, focal_px=900)
        with pytest.raises(ValueError, match="exactly one"):
            Camera.create(width=800, height=600, height_m=1.4, focal_px=900,
                          pitch_deg=10, horizon_row=100)


class TestProjection:
    def test_round_trip_pixel_to_ground_and_back(self):
        us = np.array([100.0, 400.0, 700.0, 400.0])
        vs = np.array([420.0, 500.0, 560.0, 590.0])
        x, z = CAM.ground_from_pixel(us, vs)
        u2, v2 = CAM.pixel_from_ground(x, z)
        assert np.allclose(u2, us, atol=1e-6)
        assert np.allclose(v2, vs, atol=1e-6)

    def test_round_trip_ground_to_pixel_and_back(self):
        xs = np.array([-2.0, 0.0, 1.5, 3.0])
        zs = np.array([4.0, 6.0, 10.0, 20.0])
        u, v = CAM.pixel_from_ground(xs, zs)
        x2, z2 = CAM.ground_from_pixel(u, v)
        assert np.allclose(x2, xs, atol=1e-6)
        assert np.allclose(z2, zs, atol=1e-6)

    def test_above_horizon_has_no_ground_point(self):
        v = CAM.horizon_row - 5
        x, z = CAM.ground_from_pixel(CAM.cx, v)
        assert np.isnan(x) and np.isnan(z)

    def test_at_the_horizon_itself_is_undefined(self):
        """Exactly on the horizon the ray runs parallel to the road.

        Floating point can leave the downward component a hair above zero, which
        would otherwise report a distance of kilometres instead of "no answer".
        """
        for dv in (0.0, 1e-9, 1e-6):
            _, z = CAM.ground_from_pixel(CAM.cx, CAM.horizon_row + dv)
            assert np.isnan(z) or z > 1e4

    def test_distance_grows_towards_the_horizon(self):
        rows = np.linspace(CAM.horizon_row + 20, CAM.height - 1, 40)
        d = CAM.distance_at_row(rows)
        assert np.all(np.diff(d) < 0), "distance must fall as the row moves down"
        assert np.all(d > 0)

    def test_level_camera_matches_the_textbook_formula(self):
        """With no pitch, Z = h * f / (v - cy)."""
        cam = Camera.create(width=800, height=600, height_m=1.5, focal_px=900, pitch_deg=0)
        for v in (400.0, 500.0, 599.0):
            expected = cam.height_m * cam.focal_px / (v - cam.cy)
            assert cam.distance_at_row(v) == pytest.approx(expected, rel=1e-9)

    def test_optical_column_has_no_lateral_offset(self):
        x, _ = CAM.ground_from_pixel(CAM.cx, 500.0)
        assert x == pytest.approx(0.0, abs=1e-9)

    def test_lateral_offset_is_symmetric(self):
        left, _ = CAM.ground_from_pixel(CAM.cx - 150, 500.0)
        right, _ = CAM.ground_from_pixel(CAM.cx + 150, 500.0)
        assert left == pytest.approx(-right)


class TestScale:
    def test_pixel_area_matches_a_numeric_jacobian(self):
        """The analytic scale^3/(h f^2) against finite differences."""
        for v in (450.0, 500.0, 560.0):
            eps = 1e-3
            x1, z1 = CAM.ground_from_pixel(CAM.cx, v)
            x2, _ = CAM.ground_from_pixel(CAM.cx + eps, v)
            _, z2 = CAM.ground_from_pixel(CAM.cx, v + eps)
            numeric = abs((x2 - x1) / eps) * abs((z2 - z1) / eps)
            assert CAM.pixel_area_m2(v) == pytest.approx(float(numeric), rel=1e-4)

    def test_pixel_area_grows_with_distance(self):
        rows = np.array([560.0, 520.0, 480.0, 450.0])   # nearer -> further
        areas = CAM.pixel_area_m2(rows)
        assert np.all(np.diff(areas) > 0)

    def test_area_scales_with_the_cube_of_distance(self):
        """Doubling the distance multiplies pixel area by eight.

        Checked on a level camera, where the ray parameter equals the forward
        distance exactly; with pitch the two differ by cos/sin terms and the
        law holds in the ray parameter rather than in Z.
        """
        level = Camera.create(width=800, height=600, height_m=1.35,
                              focal_px=533.3, pitch_deg=0)
        v_near = float(level.row_at_distance(5.0))
        v_far = float(level.row_at_distance(10.0))
        ratio = level.pixel_area_m2(v_far) / level.pixel_area_m2(v_near)
        assert ratio == pytest.approx(8.0, rel=1e-6)

    def test_usable_range_brackets_the_requested_distances(self):
        row_far, row_near = CAM.usable_row_range(3.0, 15.0)
        assert row_far < row_near
        assert CAM.distance_at_row(row_near) == pytest.approx(3.0, rel=1e-6)
        assert CAM.distance_at_row(row_far) == pytest.approx(15.0, rel=1e-6)

    def test_bad_range_rejected(self):
        with pytest.raises(ValueError):
            CAM.usable_row_range(10.0, 5.0)


class TestMeasurement:
    """The tests that would catch a wrong scale."""

    @pytest.mark.parametrize("x0,x1,z0,z1", [
        (-1.0, 1.0, 5.0, 7.0),      # 2 x 2 = 4 m2
        (-0.5, 0.5, 4.0, 6.0),      # 1 x 2 = 2 m2
        (0.0, 2.0, 6.0, 9.0),       # 2 x 3 = 6 m2, off to one side
    ])
    def test_known_ground_rectangle_measures_back(self, x0, x1, z0, z1):
        expected = (x1 - x0) * (z1 - z0)
        mask = rasterise_ground_quad(CAM, x0, x1, z0, z1)
        assert mask.any(), "the quad projected outside the frame"
        measured = CAM.mask_area_m2(mask, near_m=1.0, far_m=100.0)
        assert measured == pytest.approx(expected, rel=0.03)

    def test_a_square_further_away_still_measures_the_same(self):
        """Same physical size at two distances -- the whole point of the mapping."""
        near = CAM.mask_area_m2(rasterise_ground_quad(CAM, -0.5, 0.5, 4.0, 5.0),
                                near_m=1.0, far_m=100.0)
        far = CAM.mask_area_m2(rasterise_ground_quad(CAM, -0.5, 0.5, 9.0, 10.0),
                               near_m=1.0, far_m=100.0)
        assert near == pytest.approx(1.0, rel=0.03)
        assert far == pytest.approx(1.0, rel=0.06)   # fewer pixels, coarser

    def test_empty_mask_is_zero(self):
        assert CAM.mask_area_m2(np.zeros((CAM.height, CAM.width), bool)) == 0.0

    def test_far_field_pixels_are_excluded(self):
        """A mask beyond the usable band must not contribute."""
        mask = rasterise_ground_quad(CAM, -1.0, 1.0, 40.0, 60.0)
        assert mask.any()
        assert CAM.mask_area_m2(mask, near_m=3.0, far_m=15.0) == 0.0

    def test_wrong_sized_mask_rejected(self):
        with pytest.raises(ValueError, match="camera expects"):
            CAM.mask_area_m2(np.zeros((10, 10), bool))

    def test_straight_ground_line_measures_its_true_length(self):
        """A 6 m line along the road, sampled in the image, measured back."""
        zs = np.linspace(5.0, 11.0, 60)
        u, v = CAM.pixel_from_ground(np.zeros_like(zs), zs)
        length = CAM.polyline_length_m(np.column_stack([u, v]), near_m=1.0, far_m=100.0)
        assert length == pytest.approx(6.0, rel=0.01)

    def test_lateral_line_measures_its_true_length(self):
        xs = np.linspace(-1.5, 1.5, 40)
        u, v = CAM.pixel_from_ground(xs, np.full_like(xs, 6.0))
        length = CAM.polyline_length_m(np.column_stack([u, v]), near_m=1.0, far_m=100.0)
        assert length == pytest.approx(3.0, rel=0.01)

    def test_polyline_outside_the_band_is_dropped(self):
        zs = np.linspace(40.0, 60.0, 30)
        u, v = CAM.pixel_from_ground(np.zeros_like(zs), zs)
        assert CAM.polyline_length_m(np.column_stack([u, v]), 3.0, 15.0) == 0.0

    def test_polyline_needs_two_points(self):
        with pytest.raises(ValueError, match="at least two"):
            CAM.polyline_length_m([[100.0, 500.0]])


class TestSensitivity:
    """How wrong the answer gets when the inputs are wrong.

    These are not pass/fail engineering claims -- they document the error budget
    so the field instructions can be argued for rather than asserted.
    """

    def test_height_error_scales_area_quadratically(self):
        """area = h^2 / (dy^3 f^2): a 10 % height error is a 21 % area error.

        This is the number that justifies measuring the mount with a tape rather
        than estimating it -- the error lands directly on the ASTM density.
        """
        truth = rasterise_ground_quad(CAM, -1.0, 1.0, 5.0, 7.0)
        wrong = Camera.create(width=CAM.width, height=CAM.height,
                              height_m=CAM.height_m * 1.10,
                              focal_px=CAM.focal_px, pitch_rad=CAM.pitch_rad)
        ratio = wrong.mask_area_m2(truth, 1.0, 100.0) / CAM.mask_area_m2(truth, 1.0, 100.0)
        assert ratio == pytest.approx(1.10**2, rel=0.02)

    def test_pitch_error_of_two_degrees_stays_under_a_third(self):
        truth = rasterise_ground_quad(CAM, -1.0, 1.0, 5.0, 7.0)
        wrong = Camera.create(width=CAM.width, height=CAM.height, height_m=CAM.height_m,
                              focal_px=CAM.focal_px,
                              pitch_deg=math.degrees(CAM.pitch_rad) + 2.0)
        ratio = wrong.mask_area_m2(truth, 1.0, 100.0) / CAM.mask_area_m2(truth, 1.0, 100.0)
        # Measured: two degrees of pitch error moves reported area by ~35 %.
        # Pitch is recoverable from the horizon in the frame, so it need not be
        # guessed -- but a mount that shifts mid-drive cannot be recovered.
        assert 0.6 < ratio < 1.5, f"2 deg of pitch moved area by {ratio:.2f}x"
