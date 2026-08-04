"""Integrity checks for the merged YOLO dataset.

A detection dataset fails quietly: mismatched labels, boxes off the edge of the
frame or a class index that does not exist all train happily and only show up as
a disappointing mAP. These assert the invariants instead.

Skipped when DATA/yolo has not been built yet (smartroad/data/build_yolo.py).
"""
from __future__ import annotations

import collections
import random
from pathlib import Path

import pytest

from smartroad.data.build_yolo import ASTM_TO_CLASS, CLASSES, NAME_TO_ID

ROOT = Path(__file__).resolve().parents[1]
YOLO = ROOT / "DATA" / "yolo"

pytestmark = pytest.mark.skipif(
    not (YOLO / "data.yaml").exists(),
    reason="run smartroad/data/build_yolo.py first",
)


def _pairs(split: str):
    images = sorted((YOLO / "images" / split).iterdir())
    return [(img, YOLO / "labels" / split / f"{img.stem}.txt") for img in images]


def _labels(split: str):
    for _, lab in _pairs(split):
        for line in lab.read_text().strip().splitlines():
            parts = line.split()
            yield lab, int(parts[0]), tuple(float(v) for v in parts[1:])


@pytest.fixture(scope="module")
def splits():
    return {s: _pairs(s) for s in ("train", "val")}


class TestStructure:
    def test_both_splits_populated(self, splits):
        assert len(splits["train"]) > 1000
        assert len(splits["val"]) > 100

    def test_every_image_has_a_label(self, splits):
        for split, pairs in splits.items():
            missing = [i.name for i, l in pairs if not l.exists()]
            assert not missing, f"{split}: {len(missing)} images without labels, e.g. {missing[:3]}"

    def test_every_label_has_an_image(self):
        for split in ("train", "val"):
            stems = {p.stem for p in (YOLO / "images" / split).iterdir()}
            orphans = [l.name for l in (YOLO / "labels" / split).iterdir() if l.stem not in stems]
            assert not orphans, f"{split}: {len(orphans)} orphan labels, e.g. {orphans[:3]}"

    def test_images_resolve(self, splits):
        """Symlinked images must point at something that still exists."""
        for split, pairs in splits.items():
            broken = [i.name for i, _ in pairs if not i.exists()]
            assert not broken, f"{split}: {len(broken)} broken images, e.g. {broken[:3]}"

    def test_no_empty_labels(self, splits):
        for split, pairs in splits.items():
            empty = [l.name for _, l in pairs if not l.read_text().strip()]
            assert not empty, f"{split}: {len(empty)} empty label files"


class TestLabelValues:
    def test_class_ids_in_range(self):
        for split in ("train", "val"):
            for lab, cls, _ in _labels(split):
                assert 0 <= cls < len(CLASSES), f"{lab.name}: class {cls} out of range"

    def test_coordinates_normalised(self):
        for split in ("train", "val"):
            for lab, _, (cx, cy, w, h) in _labels(split):
                assert 0.0 <= cx <= 1.0 and 0.0 <= cy <= 1.0, f"{lab.name}: centre off frame"
                assert 0.0 < w <= 1.0 and 0.0 < h <= 1.0, f"{lab.name}: bad size {w}x{h}"

    def test_boxes_stay_inside_the_frame(self):
        """A box extending past the edge means the clip in _to_yolo failed."""
        for split in ("train", "val"):
            for lab, _, (cx, cy, w, h) in _labels(split):
                assert cx - w / 2 >= -1e-6, f"{lab.name}: box crosses left edge"
                assert cy - h / 2 >= -1e-6, f"{lab.name}: box crosses top edge"
                assert cx + w / 2 <= 1 + 1e-6, f"{lab.name}: box crosses right edge"
                assert cy + h / 2 <= 1 + 1e-6, f"{lab.name}: box crosses bottom edge"


class TestSplitHygiene:
    def test_no_image_in_both_splits(self, splits):
        train = {i.stem for i, _ in splits["train"]}
        val = {i.stem for i, _ in splits["val"]}
        assert not (train & val), f"{len(train & val)} images leak across the split"

    def test_val_covers_every_source_except_train_only(self, splits):
        sources = {i.name.split("__")[0] for i, _ in splits["val"]}
        assert {"rdd2022", "attain_tehran", "svrdd_streetview"} <= sources

    def test_rdd2018_is_train_only(self, splits):
        """Pinned deliberately: it may share scenes with the RDD2022 Japan subset."""
        val_sources = {i.name.split("__")[0] for i, _ in splits["val"]}
        assert "rdd2018_japan" not in val_sources

    def test_val_fraction_is_roughly_ten_percent(self, splits):
        ratio = len(splits["val"]) / (len(splits["train"]) + len(splits["val"]))
        assert 0.05 < ratio < 0.15


class TestTaxonomy:
    def test_class_list_matches_data_yaml(self):
        text = (YOLO / "data.yaml").read_text()
        assert f"nc: {len(CLASSES)}" in text
        for i, (name, _) in enumerate(CLASSES):
            assert f"  {i}: {name}" in text

    def test_every_mapped_astm_class_has_an_id(self):
        for name in ASTM_TO_CLASS.values():
            assert name in NAME_TO_ID

    def test_pci_classes_reference_real_astm_distresses(self):
        from smartroad.pci.astm import ASPHALT_DISTRESSES

        for name, astm_key in CLASSES:
            if astm_key is not None:
                assert astm_key in ASPHALT_DISTRESSES, f"{name} -> unknown ASTM key {astm_key}"

    def test_marking_manhole_is_not_a_pci_distress(self):
        """It must stay unmapped, or faded paint would deduct from the score."""
        assert dict(CLASSES)["marking_manhole"] is None


class TestClassBalance:
    def test_every_class_present_in_train(self, splits):
        counts = collections.Counter()
        for _, cls, _ in _labels("train"):
            counts[cls] += 1
        missing = [n for i, (n, _) in enumerate(CLASSES) if counts[i] == 0]
        assert not missing, f"classes with no training data: {missing}"

    def test_block_crack_scarcity_is_visible(self, splits):
        """block_crack is the professor's dominant Tashkent distress and we have
        almost none of it. Pinned so the shortage cannot be forgotten -- delete
        this test once QOPLAMA block-cracking boxes are added."""
        counts = collections.Counter()
        for _, cls, _ in _labels("train"):
            counts[cls] += 1
        assert counts[NAME_TO_ID["block_crack"]] < 500, (
            "block_crack now has real data -- update the training plan and drop this test"
        )
