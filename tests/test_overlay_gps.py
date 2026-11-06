"""Tests for reading coordinates a dashcam printed on its frames."""
from __future__ import annotations

import pytest

from smartroad.survey.embedded_gps import Fix
from smartroad.survey.overlay_gps import (available, drop_misreads,
                                          parse_overlay_text, track_from_overlay)


@pytest.mark.parametrize("text, expected", [
    # What RapidOCR returned for a Viofo A129 Plus frame: spaces read as dots.
    ("84.KM/H S12.035136.E13.955326 ROBOREDO V10F0A129PIus", (-12.035136, 13.955326)),
    ("84 KM/H S12.035136 E13.955326", (-12.035136, 13.955326)),
    ("N:41.3111 E:69.2797", (41.3111, 69.2797)),
    ("N41.311100 W069.279700", (41.3111, -69.2797)),
    ("E13.955326 S12.035136", (-12.035136, 13.955326)),
    ("12.035136S 13.955326E", (-12.035136, 13.955326)),
    ("12.035136°S, 13.955326°E", (-12.035136, 13.955326)),
    ("LAT: -12.035136 LON: 13.955326", (-12.035136, 13.955326)),
    ("-12.035136, 13.955326", (-12.035136, 13.955326)),
])
def test_camera_formats(text, expected):
    assert parse_overlay_text(text) == pytest.approx(expected)


@pytest.mark.parametrize("text", [
    "15-03-2025 10:56:44",            # date and time
    "84 KM/H",                        # speed
    "S12.03 E13.95",                  # too few decimals to be a position
    "N0.0000 E0.0000",                # what a receiver writes before a fix
    "VIOFO A129 Plus 33-26-HU",
    "",
])
def test_text_without_coordinates(text):
    assert parse_overlay_text(text) is None


def test_hemisphere_letters_set_the_sign():
    """S and W are negative: dropping them moves a road to another continent."""
    lat, lon = parse_overlay_text("S12.035136 W13.955326")
    assert lat < 0 and lon < 0


def _line(n, misread_at=None):
    """A drive south at about 11 m/s, one fix a second."""
    fixes = [Fix(t + 0.5, -12.035136 - t * 0.0001, 13.955326) for t in range(n)]
    if misread_at is not None:
        f = fixes[misread_at]                       # 12.035 -> 12.085: 5.5 km off
        fixes[misread_at] = Fix(f.t_s, f.lat - 0.05, f.lon)
    return fixes


def test_a_misread_digit_is_dropped():
    kept = drop_misreads(_line(10, misread_at=4))
    assert len(kept) == 9
    assert all(abs(f.lat + 12.0355) < 0.001 for f in kept)


def test_a_misread_at_either_end_is_dropped():
    assert len(drop_misreads(_line(6, misread_at=0))) == 5
    assert len(drop_misreads(_line(6, misread_at=5))) == 5


def test_a_clean_drive_is_kept_whole():
    assert len(drop_misreads(_line(10))) == 10


def test_track_reports_how_much_was_read():
    track = track_from_overlay(_line(8, misread_at=3), frames_read=10)
    assert len(track.fixes) == 7
    assert "7 of 10 frames" in track.source and "1 misread dropped" in track.source
    # The dropped frame is placed between its neighbours.
    assert track.at(3.5).lat == pytest.approx(-12.035136 - 3 * 0.0001)


def test_no_fixes_no_track():
    assert track_from_overlay([], frames_read=5) is None


@pytest.mark.skipif(not available(), reason="rapidocr_onnxruntime is not installed")
def test_ocr_reads_a_rendered_strip():
    import cv2
    import numpy as np
    from PIL import Image

    from smartroad.survey.overlay_gps import OverlayReader

    frame = np.full((720, 1280, 3), 90, dtype=np.uint8)
    cv2.rectangle(frame, (0, 686), (1280, 720), (0, 0, 0), -1)
    cv2.putText(frame, "84 KM/H S12.035136 E13.955326   15-03-2025 10:56:44",
                (20, 710), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA)
    found = OverlayReader().read(Image.fromarray(frame))
    assert found == pytest.approx((-12.035136, 13.955326))
