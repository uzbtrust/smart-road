"""Tests for parsing Ultralytics training output.

The per-class table is the number that will be shown to a pavement engineer, so
the parser has to be right about which validation block it read and has to keep
class names attached to the correct row.
"""
from __future__ import annotations

import textwrap

import pytest

from smartroad.report.parse_results import load_run, parse_curve, parse_log

# Ultralytics prints colour codes and a header before the table; both are here
# on purpose so the parser is exercised against realistic input.
LOG = textwrap.dedent("""\
    Ultralytics 8.3.155 🚀 Python-3.12.0 torch-2.6.0 CUDA:0 (Tesla T4, 15360MiB)
    \x1b[34m\x1b[1mtrain: \x1b[0mScanning labels/train... 40994 images
                     Class     Images  Instances      Box(P          R      mAP50  mAP50-95)
                       all       3550       9680      0.512      0.401      0.418      0.201
    longitudinal_transverse_crack    2100       4971      0.602      0.510      0.545      0.263
               alligator_crack        800       1533      0.571      0.488      0.512      0.249
                   block_crack          2          2          0          0          0          0
                      patching        600        823      0.498      0.402      0.431      0.221
                       pothole        520        792      0.611      0.523      0.560      0.289
           weathering_raveling        150        175      0.402      0.301      0.312      0.140
        lane_shoulder_drop_off         30         38      0.201      0.105      0.098      0.041
               marking_manhole        900       1346      0.703      0.622      0.671      0.401
    Speed: 0.2ms preprocess
    """)

# A later, better block must win over an earlier one.
LOG_TWO_BLOCKS = textwrap.dedent("""\
                       all       3550       9680      0.100      0.100      0.100      0.050
                       pothole      520        792      0.100      0.100      0.100      0.050
                       all       3550       9680      0.512      0.401      0.418      0.201
                       pothole      520        792      0.611      0.523      0.560      0.289
    """)

CSV = textwrap.dedent("""\
    epoch,train/box_loss,train/cls_loss,metrics/precision(B),metrics/recall(B),metrics/mAP50(B),metrics/mAP50-95(B)
    1,2.11,3.02,0.201,0.150,0.120,0.050
    2,1.85,2.44,0.310,0.240,0.220,0.099
    3,1.70,2.10,0.512,0.401,0.418,0.201
    """)


@pytest.fixture
def run(tmp_path):
    run_dir = tmp_path / "runs" / "yolo11s_640"
    run_dir.mkdir(parents=True)
    (run_dir / "results.csv").write_text(CSV)
    log = tmp_path / "yolo11s_640.log"
    log.write_text(LOG)
    return load_run(run_dir, log)


class TestParseLog:
    def test_finds_every_row(self, tmp_path):
        p = tmp_path / "l.log"
        p.write_text(LOG)
        rows = parse_log(p)
        assert len(rows) == 9  # all + 8 classes

    def test_class_names_stay_with_their_numbers(self, tmp_path):
        p = tmp_path / "l.log"
        p.write_text(LOG)
        by_name = {c.name: c for c in parse_log(p)}
        assert by_name["pothole"].map50 == pytest.approx(0.560)
        assert by_name["pothole"].instances == 792
        assert by_name["marking_manhole"].map50 == pytest.approx(0.671)
        assert by_name["longitudinal_transverse_crack"].precision == pytest.approx(0.602)

    def test_strips_ansi_colour_codes(self, tmp_path):
        p = tmp_path / "l.log"
        p.write_text(LOG)
        assert all("\x1b" not in c.name for c in parse_log(p))

    def test_zeroed_class_is_kept_not_dropped(self, tmp_path):
        """block_crack scoring 0 is the finding, not noise to filter out."""
        p = tmp_path / "l.log"
        p.write_text(LOG)
        block = next(c for c in parse_log(p) if c.name == "block_crack")
        assert block.map50 == 0.0
        assert block.instances == 2

    def test_later_validation_block_wins(self, tmp_path):
        p = tmp_path / "l.log"
        p.write_text(LOG_TWO_BLOCKS)
        by_name = {c.name: c for c in parse_log(p)}
        assert by_name["all"].map50 == pytest.approx(0.418)
        assert by_name["pothole"].map50 == pytest.approx(0.560)

    def test_no_table_yields_nothing(self, tmp_path):
        p = tmp_path / "l.log"
        p.write_text("Traceback (most recent call last):\nRuntimeError: CUDA OOM\n")
        assert parse_log(p) == []


class TestParseCurve:
    def test_reads_every_epoch(self, tmp_path):
        p = tmp_path / "results.csv"
        p.write_text(CSV)
        curve = parse_curve(p)
        assert [r["epoch"] for r in curve] == [1, 2, 3]

    def test_metrics_are_numeric(self, tmp_path):
        p = tmp_path / "results.csv"
        p.write_text(CSV)
        last = parse_curve(p)[-1]
        assert last["map50"] == pytest.approx(0.418)
        assert last["map50_95"] == pytest.approx(0.201)
        assert last["box_loss"] == pytest.approx(1.70)

    def test_missing_column_defaults_rather_than_raising(self, tmp_path):
        p = tmp_path / "results.csv"
        p.write_text("epoch,metrics/mAP50(B)\n1,0.3\n")
        assert parse_curve(p)[0]["recall"] == 0.0


class TestLoadRun:
    def test_combines_both_sources(self, run):
        assert run.name == "yolo11s_640"
        assert run.epochs == 3
        assert len(run.per_class) == 8

    def test_overall_row_is_separated_from_classes(self, run):
        assert run.overall.map50 == pytest.approx(0.418)
        assert "all" not in {c.name for c in run.per_class}

    def test_survives_a_missing_log(self, tmp_path):
        run_dir = tmp_path / "runs" / "x"
        run_dir.mkdir(parents=True)
        (run_dir / "results.csv").write_text(CSV)
        r = load_run(run_dir, None)
        assert r.epochs == 3
        assert r.classes == []
        assert r.overall is None
