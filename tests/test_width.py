"""Tests for crack-width measurement.

Cracks are drawn at a known pixel width, so the measurement is checked against
a truth rather than against itself.
"""
from __future__ import annotations

import numpy as np
import pytest

from smartroad.geometry.ipm import Camera
from smartroad.measure.width import (KERNEL_MM, LOW_MEDIUM_MM, MEDIUM_HIGH_MM,
                                     MIN_ELONGATION, MIN_PX_ACROSS, RIBBON_RATIO_MIN,
                                     WIDTH_GRADED, CrackWidth, measure_width,
                                     reliable_distance_m, segment_crack,
                                     severity_from_width)

H, W = 1080, 1920
KERNEL = 61


@pytest.fixture
def camera():
    return Camera.create(width=W, height=H, height_m=1.70, focal_35mm=25.0,
                         horizon_row=0.139 * H)


def asphalt(h=200, w=400, grey=140, noise=6, seed=0):
    rng = np.random.default_rng(seed)
    img = np.full((h, w), grey, dtype=np.int16)
    img += rng.integers(-noise, noise + 1, size=(h, w))
    return np.clip(img, 0, 255).astype(np.uint8)


def with_crack(width_px, *, h=200, w=400, dark=40, seed=0):
    """A dark vertical band of exactly `width_px` on noisy asphalt."""
    img = asphalt(h, w, seed=seed)
    start = w // 2 - width_px // 2          # exactly width_px columns, no rounding
    img[:, start:start + width_px] = dark
    return np.stack([img] * 3, axis=-1)


# ------------------------------------------------------------- segmentation

@pytest.mark.parametrize("drawn", [3, 9, 20, 40])
def test_recovers_the_width_that_was_drawn(drawn):
    mask = segment_crack(with_crack(drawn), KERNEL)
    assert mask.sum() == pytest.approx(drawn * 200, rel=0.1)


@pytest.mark.parametrize("seed", [0, 5, 7])
def test_bare_asphalt_is_refused_because_it_is_not_a_ribbon(seed):
    """Otsu's split of noise reads 88 px wide by area/length and 4.4 px by
    distance transform. A real crack cannot disagree with itself like that."""
    assert not segment_crack(np.stack([asphalt(seed=seed)] * 3, axis=-1), KERNEL).any()


def test_a_round_blob_is_still_refused():
    img = asphalt()
    img[80:130, 175:225] = 30
    assert not segment_crack(np.stack([img] * 3, axis=-1), KERNEL).any()


def test_a_crack_wider_than_the_kernel_is_erased_by_the_operator():
    """Why KERNEL_MM is sized from geometry rather than fixed."""
    wide = with_crack(20)
    assert not segment_crack(wide, kernel_px=15).any()     # kernel too small
    assert segment_crack(wide, KERNEL).any()               # kernel large enough


def test_shading_across_the_patch_does_not_become_the_crack():
    img = with_crack(9)
    gradient = np.linspace(0, 70, img.shape[1]).astype(np.int16)
    shaded = np.clip(img.astype(np.int16) - gradient[None, :, None], 0,
                     255).astype(np.uint8)
    cols = np.nonzero(segment_crack(shaded, KERNEL).any(axis=0))[0]
    assert 180 <= cols.mean() <= 220


def test_an_empty_patch_is_handled_rather_than_raising():
    assert segment_crack(np.zeros((0, 0), dtype=np.uint8), KERNEL).size == 0


# --------------------------------------------------------------- measurement

def _frame_with_crack(camera, distance_m, width_px, dark=40):
    """Full-frame asphalt with a crack at a known distance, and its box."""
    row = int(camera.row_at_distance(distance_m))
    img = np.stack([asphalt(H, W, seed=3)] * 3, axis=-1)
    x0, half = W // 2, width_px // 2
    top, bottom = row - 60, row + 60
    img[top:bottom, x0 - half:x0 - half + width_px] = dark
    return img, (x0 - half - 20, top, x0 - half + width_px + 20, bottom)


def test_measures_a_crack_in_millimetres_on_the_road(camera):
    img, box = _frame_with_crack(camera, 3.5, 9)
    got = measure_width(img, box, camera)
    assert got is not None
    # 9 px at 2.88 mm/px is about 26 mm.
    assert got.mean_mm == pytest.approx(9 * got.mm_per_px, rel=0.25)
    assert got.mm_per_px == pytest.approx(2.88, abs=0.15)
    assert got.distance_m == pytest.approx(3.5, abs=0.2)


def test_the_same_crack_further_away_measures_the_same_width(camera):
    """The whole point of the geometry: millimetres, not pixels."""
    near_img, near_box = _frame_with_crack(camera, 3.5, 10)
    far_img, far_box = _frame_with_crack(camera, 7.0, 5)   # half the pixels
    near = measure_width(near_img, near_box, camera)
    far = measure_width(far_img, far_box, camera)
    assert near and far
    assert far.mean_mm == pytest.approx(near.mean_mm, rel=0.3)
    assert far.px_across < near.px_across


def test_a_box_with_no_crack_in_it_measures_nothing(camera):
    img = np.stack([asphalt(H, W, seed=5)] * 3, axis=-1)
    assert measure_width(img, (900, 800, 1000, 900), camera) is None


def test_a_box_above_the_horizon_is_refused(camera):
    img = np.stack([asphalt(H, W, seed=5)] * 3, axis=-1)
    assert measure_width(img, (900, 0, 1000, 40), camera) is None


def test_a_box_with_no_pixels_in_it_is_refused(camera):
    img = np.stack([asphalt(H, W, seed=5)] * 3, axis=-1)
    # Padding cannot rescue a box that is off the frame entirely.
    assert measure_width(img, (W + 10, 800, W + 20, 900), camera, pad_px=0) is None
    assert measure_width(img, (900, 800, 900, 800), camera, pad_px=0) is None


# ------------------------------------------------------------------ severity

def _width(mm, px=6.0):
    return CrackWidth(mean_mm=mm, max_mm=mm * 1.4, length_px=200.0,
                      px_across=px, mm_per_px=mm / px if px else 1.0,
                      distance_m=3.5)


@pytest.mark.parametrize("mm,want", [(4.0, "low"), (9.9, "low"), (10.0, "medium"),
                                     (40.0, "medium"), (75.0, "medium"),
                                     (90.0, "high")])
def test_astm_width_boundaries(mm, want):
    assert severity_from_width("longitudinal_transverse_cracking", _width(mm)) == want


def test_alligator_is_graded_by_pattern_so_width_refuses_it():
    """Handing it a width would invent a criterion the standard does not use."""
    assert "alligator_cracking" not in WIDTH_GRADED
    assert severity_from_width("alligator_cracking", _width(40.0)) is None
    assert severity_from_width("potholes", _width(40.0)) is None


def test_too_few_pixels_across_refuses_rather_than_guessing():
    thin = _width(12.0, px=MIN_PX_ACROSS - 0.5)
    assert not thin.reliable
    assert severity_from_width("longitudinal_transverse_cracking", thin) is None


def test_reliable_distance_is_further_at_higher_resolution():
    hd = Camera.create(width=1920, height=1080, height_m=1.70, focal_35mm=25.0,
                       horizon_row=0.139 * 1080)
    uhd = Camera.create(width=3840, height=2160, height_m=1.70, focal_35mm=25.0,
                        horizon_row=0.139 * 2160)
    assert reliable_distance_m(hd) == pytest.approx(4.1, abs=0.3)
    assert reliable_distance_m(uhd) == pytest.approx(8.8, abs=0.4)
    assert reliable_distance_m(uhd) > 2 * reliable_distance_m(hd) - 0.5


def test_the_unreliable_flag_shows_up_in_the_text():
    assert "unreliable" in str(_width(12.0, px=1.0))
    assert "unreliable" not in str(_width(12.0, px=6.0))


def test_the_two_width_estimators_agree_on_a_real_ribbon():
    """The gate's premise, asserted directly."""
    import cv2
    from smartroad.measure.width import _length_px
    for drawn in (3, 9, 20, 40):
        mask = segment_crack(with_crack(drawn), KERNEL)
        area, length = float(mask.sum()), _length_px(mask)
        mean_px = area / length
        max_px = float(cv2.distanceTransform(mask.astype(np.uint8),
                                             cv2.DIST_L2, 5).max()) * 2.0
        assert max_px / mean_px >= RIBBON_RATIO_MIN
        assert mean_px == pytest.approx(drawn, rel=0.15)
