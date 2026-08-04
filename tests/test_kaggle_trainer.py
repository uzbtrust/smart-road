"""Tests for the Kaggle training launcher's pure logic.

The training itself needs a GPU, but the parts that decide *what* gets run are
plain functions and are exactly where a silent mistake is expensive: a wrong
data.yaml path or a job accidentally pinned to the same card would waste hours
of a limited weekly GPU quota before anyone noticed.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

spec = importlib.util.spec_from_file_location("train_detector", ROOT / "kaggle" / "train_detector.py")
train_detector = importlib.util.module_from_spec(spec)
sys.modules["train_detector"] = train_detector
spec.loader.exec_module(train_detector)


class TestJobConfiguration:
    def test_one_job_per_gpu(self):
        gpus = [j["gpu"] for j in train_detector.JOBS]
        assert sorted(gpus) == [0, 1], "both T4s must be used, exactly once each"

    def test_jobs_are_heterogeneous(self):
        """Ensembling identical models buys far less than mixing them."""
        signatures = {(j["model"], j["imgsz"]) for j in train_detector.JOBS}
        assert len(signatures) == len(train_detector.JOBS)

    def test_job_names_unique(self):
        names = [j["name"] for j in train_detector.JOBS]
        assert len(set(names)) == len(names)

    def test_batch_sizes_fit_a_16gb_t4(self):
        """Activation memory per step must leave headroom on a 16 GB T4.

        Pixels per step alone is not the quantity that OOMs: a yolo11s step and
        a yolo11x step of the same shape differ severalfold in activations. The
        weights below are the models' relative widths, so the product tracks
        activation memory rather than image area.

        The scale factor is measured, not guessed. Our own yolo11l run at 640
        with batch 32 reported 19.6 GB on a 32 GB card, which is
        32 * 640^2 * 1.3 = 17.0e6 weighted pixels, i.e. ~1.15 GB per 1e6. A T4
        holds 16 GB; budgeting 14 GB for activations gives the ceiling below.
        """
        weight = {"yolo11n": 0.25, "yolo11s": 0.5, "yolo11m": 1.0,
                  "yolo11l": 1.3, "yolo11x": 2.0}
        gb_per_unit = 19.6 / 17.0e6
        budget_units = 14.0 / gb_per_unit

        for job in train_detector.JOBS:
            size = Path(job["model"]).stem
            assert size in weight, f"unknown model size {size!r}"
            units = job["batch"] * job["imgsz"] ** 2 * weight[size]
            assert units <= budget_units, (
                f"{job['name']} needs ~{units * gb_per_unit:.1f} GB of activations, "
                f"over the 14 GB budgeted on a 16 GB T4"
            )


class TestCommandBuilding:
    @pytest.fixture
    def cmd(self, tmp_path):
        job = train_detector.JOBS[0]
        return " ".join(
            train_detector.build_command(job, tmp_path / "data.yaml", 5.0, 200, 15, 1337)
        )

    def test_uses_device_zero_within_the_pinned_gpu(self, cmd):
        """CUDA_VISIBLE_DEVICES renumbers the card, so the job always sees 0."""
        assert "device=0" in cmd

    def test_amp_enabled(self, cmd):
        assert "amp=True" in cmd

    def test_time_budget_passed(self, cmd):
        assert "time=5.0" in cmd

    def test_copy_paste_enabled_for_rare_classes(self, cmd):
        assert "copy_paste=" in cmd

    def test_writes_into_kaggle_working(self, cmd):
        assert "/kaggle/working/runs" in cmd

    def test_each_job_gets_its_own_run_name(self, tmp_path):
        names = {
            train_detector.build_command(j, tmp_path / "d.yaml", 5.0, 200, 15, 1)[-1].split("name=")[1]
            for j in train_detector.JOBS
        }
        assert len(names) == len(train_detector.JOBS)


class TestDataYamlRewriting:
    def test_path_is_repointed_at_the_mounted_copy(self, tmp_path, monkeypatch):
        monkeypatch.setattr(train_detector, "WORKING", tmp_path / "working")
        (tmp_path / "working").mkdir()
        mounted = tmp_path / "input" / "smartroad-yolo"
        mounted.mkdir(parents=True)
        src = mounted / "data.yaml"
        src.write_text(
            "path: /Users/someone/Desktop/Smart Road/DATA/yolo_upload\n"
            "train: images/train\nval: images/val\nnc: 8\nnames:\n  0: crack\n"
        )

        out = train_detector.rewrite_paths(src)
        text = out.read_text()
        assert f"path: {mounted}" in text
        assert "/Users/someone" not in text, "the local absolute path must not survive"
        # everything else must be carried through untouched
        assert "train: images/train" in text
        assert "val: images/val" in text
        assert "nc: 8" in text
        assert "  0: crack" in text

    def test_missing_data_yaml_is_fatal(self):
        with pytest.raises(SystemExit):
            train_detector.find_data_yaml("/definitely/not/here/data.yaml")

    def test_explicit_path_wins(self, tmp_path):
        p = tmp_path / "data.yaml"
        p.write_text("path: x\n")
        assert train_detector.find_data_yaml(str(p)) == p
