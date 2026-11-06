"""Tests for the batch tool's per-second sheet and its copy of the app's maths."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("openpyxl")

import batch_pci as bp
from smartroad.detect.tiled import Detection
from smartroad.pci.engine import deduct_value
from smartroad.pci.from_detections import pci_from_detections

S = bp.Settings()
CAM = bp.make_camera(1280, 720, S)
ROI = bp.road_roi(1280, 720, top_fraction=S.sky)
NAMES = {4: "pothole"}


def _frame(i: int, t: float, dets=()) -> bp.FrameResult:
    return bp.FrameResult(i, t, (1280, 720), list(dets),
                          bp.grade_frame(list(dets), CAM, ROI, NAMES, S))


def _video(times, **kw) -> bp.VideoResult:
    v = bp.VideoResult(path=Path("clip.mp4"), label="clip.mp4", status="OK", **kw)
    v.frames = [_frame(i, t) for i, t in enumerate(times, 1)]
    return v


def test_one_row_per_second_at_one_frame_a_second():
    rows = list(bp._per_second_rows([_video([0.5, 1.5, 2.5])], S))
    assert [r[1] for r in rows] == [0, 1, 2]
    assert [r[3] for r in rows] == [0.5, 1.5, 2.5]
    assert all(r[4].value == 100.0 for r in rows)       # no detections


def test_unsampled_seconds_are_listed_empty_not_invented():
    s = bp.Settings(every_s=2.0)
    rows = list(bp._per_second_rows([_video([1.0, 3.0])], s))
    assert [r[1] for r in rows] == [0, 1, 2, 3]
    gaps = [r for r in rows if r[4] is None]
    assert [r[1] for r in gaps] == [0, 2]
    assert all(r[-1] == "not sampled at this interval" for r in gaps)


def test_pothole_deduct_matches_the_grade():
    """deducts_by_distress must pair each distress with the deduct the PCI used."""
    u0, v0 = CAM.pixel_from_ground(-0.1, 5.0)
    u1, v1 = CAM.pixel_from_ground(0.1, 5.2)
    det = Detection(min(u0, u1), min(v0, v1), max(u0, u1), max(v0, v1), 0.9, 4)
    a = pci_from_detections([det], CAM, severity="medium", class_names=NAMES,
                            roi=ROI, near_m=bp.NEAR_M, far_m=S.far_m)
    pairs = bp.deducts_by_distress(a)
    assert [dv for _, dv in pairs] == pytest.approx(a.deduct_values)


def test_whole_frame_detection_gets_bgr():
    seen = []

    class Box:
        def __init__(self):
            self.boxes = []

    class Model:
        def predict(self, frame, **kw):
            seen.append(frame)
            return [Box()]

    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    frame[..., 0] = 200                                  # red, in RGB
    bp.detect(Model(), frame, bp.Settings(tiled=False), "cpu")
    assert (seen[0][..., 2] == 200).all() and (seen[0][..., 0] == 0).all()


def test_workbook_has_the_per_second_sheet(tmp_path):
    from openpyxl import load_workbook

    out = bp.write_workbook(tmp_path / "b.xlsx", [_video([0.5, 1.5])], S, {}, NAMES,
                            per_second=True)
    wb = load_workbook(out)
    assert "Per second" in wb.sheetnames
    assert wb["Per second"].max_row == 3                 # header + two seconds
    assert "Per second" not in load_workbook(
        bp.write_workbook(tmp_path / "c.xlsx", [_video([0.5])], S, {}, NAMES)).sheetnames
