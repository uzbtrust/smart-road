"""Tests for tiled inference.

The failure this guards against is silent: a wrong tile offset still produces
boxes, in plausible places, at plausible sizes. Nothing downstream complains --
the density is simply computed from distresses that are not where the model put
them. So the central test does not check the arithmetic against itself. It
plants a mark at a known place in a large frame, runs a stub detector that finds
exactly that mark inside whatever crop it is handed, and asserts the box comes
back at the coordinates the mark was planted at.
"""
from __future__ import annotations

import numpy as np
import pytest

from smartroad.detect.tiled import (DEFAULT_TILE, Detection, detect_tiled,
                                    merge_detections, road_roi, tile_grid)


class TestTileGrid:
    def test_covers_every_pixel(self):
        w, h, tile = 3840, 2160, 640
        boxes = tile_grid(w, h, tile=tile, overlap=0.2)
        covered = np.zeros((h, w), dtype=bool)
        for x0, y0, x1, y1 in boxes:
            covered[y0:y1, x0:x1] = True
        assert covered.all(), f"{(~covered).sum()} pixels in no tile"

    def test_tiles_stay_inside_the_frame(self):
        w, h = 1000, 700
        for x0, y0, x1, y1 in tile_grid(w, h, tile=640, overlap=0.25):
            assert 0 <= x0 < x1 <= w
            assert 0 <= y0 < y1 <= h

    def test_neighbours_actually_overlap(self):
        boxes = tile_grid(2000, 640, tile=640, overlap=0.2)
        xs = sorted({b[0] for b in boxes})
        assert len(xs) > 1
        # Every step is at most the stride, so consecutive tiles share pixels.
        assert all(b - a <= 640 * 0.8 + 1 for a, b in zip(xs, xs[1:]))

    def test_region_smaller_than_a_tile_gives_one_tile(self):
        assert tile_grid(300, 200, tile=640) == [(0, 0, 300, 200)]

    def test_roi_is_respected(self):
        roi = (100, 500, 900, 1100)
        boxes = tile_grid(1920, 1200, tile=320, overlap=0.2, roi=roi)
        assert boxes
        for x0, y0, x1, y1 in boxes:
            assert x0 >= roi[0] and y0 >= roi[1]
            assert x1 <= roi[2] and y1 <= roi[3]

    def test_covers_the_whole_roi(self):
        roi = (100, 500, 900, 1100)
        boxes = tile_grid(1920, 1200, tile=320, overlap=0.2, roi=roi)
        covered = np.zeros((1200, 1920), dtype=bool)
        for x0, y0, x1, y1 in boxes:
            covered[y0:y1, x0:x1] = True
        assert covered[roi[1]:roi[3], roi[0]:roi[2]].all()

    @pytest.mark.parametrize("kwargs", [
        {"tile": 0}, {"tile": -5}, {"overlap": 1.0}, {"overlap": -0.1},
    ])
    def test_rejects_nonsense(self, kwargs):
        with pytest.raises(ValueError):
            tile_grid(1000, 1000, **kwargs)

    def test_rejects_empty_roi(self):
        with pytest.raises(ValueError):
            tile_grid(1000, 1000, roi=(500, 500, 400, 400))


class TestMerge:
    def test_duplicates_collapse_to_the_most_confident(self):
        a = Detection(10, 10, 50, 50, 0.9, 0)
        b = Detection(12, 11, 51, 52, 0.7, 0)      # same thing, seen twice
        out = merge_detections([a, b], iou_threshold=0.5)
        assert len(out) == 1
        assert out[0].confidence == 0.9

    def test_different_classes_at_the_same_place_both_survive(self):
        """A pothole inside a patch is two true detections, not a duplicate."""
        a = Detection(10, 10, 50, 50, 0.9, 3)
        b = Detection(10, 10, 50, 50, 0.8, 4)
        assert len(merge_detections([a, b])) == 2

    def test_distinct_boxes_are_kept(self):
        a = Detection(0, 0, 40, 40, 0.9, 0)
        b = Detection(200, 200, 240, 240, 0.8, 0)
        assert len(merge_detections([a, b])) == 2

    def test_seam_flag_survives_the_merge(self):
        strong = Detection(10, 10, 50, 50, 0.9, 0, on_seam=False)
        weak = Detection(11, 11, 51, 51, 0.6, 0, on_seam=True)
        out = merge_detections([strong, weak])
        assert len(out) == 1
        assert out[0].on_seam, "a merged box must stay flagged if any source was"

    def test_output_is_confidence_ordered(self):
        dets = [Detection(i * 100, 0, i * 100 + 40, 40, c, 0)
                for i, c in enumerate([0.3, 0.9, 0.6])]
        assert [d.confidence for d in merge_detections(dets)] == [0.9, 0.6, 0.3]

    def test_rejects_bad_threshold(self):
        with pytest.raises(ValueError):
            merge_detections([Detection(0, 0, 1, 1, 0.5, 0)], iou_threshold=0)


class _Box:
    def __init__(self, arr):
        self._arr = np.asarray(arr, dtype=float)

    def cpu(self):
        return self

    def numpy(self):
        return self._arr


class _Boxes:
    def __init__(self, xyxy, conf, cls):
        self.xyxy, self.conf, self.cls = _Box(xyxy), _Box(conf), _Box(cls)

    def __len__(self):
        return len(self.xyxy.numpy())


class _Result:
    def __init__(self, boxes):
        self.boxes = boxes


class MarkFinder:
    """Stub detector: reports the bounding box of non-zero pixels in each crop.

    Stands in for the network so the test measures the tiling, not the model.
    """

    def predict(self, crops, **kwargs):
        results = []
        for crop in crops:
            ys, xs = np.nonzero(crop.max(axis=2))
            if len(xs) == 0:
                results.append(_Result(_Boxes(np.empty((0, 4)), [], [])))
                continue
            box = [[xs.min(), ys.min(), xs.max() + 1, ys.max() + 1]]
            results.append(_Result(_Boxes(box, [0.9], [0])))
        return results


class TestDetectTiled:
    def test_box_comes_back_where_the_mark_was_planted(self):
        frame = np.zeros((2160, 3840, 3), dtype=np.uint8)
        x0, y0, x1, y1 = 2500, 1500, 2560, 1530
        frame[y0:y1, x0:x1] = 255

        dets = detect_tiled(MarkFinder(), frame, tile=DEFAULT_TILE, overlap=0.2)

        assert dets, "the mark was not found at all"
        best = max(dets, key=lambda d: d.area)
        assert best.x1 == pytest.approx(x0, abs=2)
        assert best.y1 == pytest.approx(y0, abs=2)
        assert best.x2 == pytest.approx(x1, abs=2)
        assert best.y2 == pytest.approx(y1, abs=2)

    def test_mark_on_a_tile_seam_is_still_found_whole(self):
        """The reason overlap exists: a distress astride a seam."""
        frame = np.zeros((1280, 1280, 3), dtype=np.uint8)
        # A stride of 512 puts a seam at x=512; straddle it.
        x0, x1 = 500, 530
        frame[600:610, x0:x1] = 255

        dets = detect_tiled(MarkFinder(), frame, tile=640, overlap=0.2)
        widest = max(dets, key=lambda d: d.width)
        assert widest.width == pytest.approx(x1 - x0, abs=2), (
            "overlap should let one tile see the whole mark")

    def test_roi_excludes_everything_above_it(self):
        frame = np.zeros((1000, 1000, 3), dtype=np.uint8)
        frame[100:120, 100:120] = 255          # sky: must be ignored
        dets = detect_tiled(MarkFinder(), frame, tile=320, overlap=0.2,
                            roi=(0, 500, 1000, 1000))
        assert dets == []

    def test_class_filter_drops_untrained_heads(self):
        frame = np.zeros((640, 640, 3), dtype=np.uint8)
        frame[100:150, 100:150] = 255
        assert detect_tiled(MarkFinder(), frame, tile=640, classes=[1, 2]) == []
        assert detect_tiled(MarkFinder(), frame, tile=640, classes=[0])

    def test_rejects_non_image(self):
        with pytest.raises(ValueError):
            detect_tiled(MarkFinder(), np.zeros((10, 10)))


class TestRoadRoi:
    def test_keeps_the_bottom_of_the_frame(self):
        assert road_roi(3840, 2160, top_fraction=0.45) == (0, 972, 3840, 2160)

    def test_rejects_bad_fraction(self):
        with pytest.raises(ValueError):
            road_roi(100, 100, top_fraction=1.0)
