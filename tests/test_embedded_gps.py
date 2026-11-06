"""Tests for reading the GPS a camera recorded into its own video."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from smartroad.survey.embedded_gps import (MAX_GAP_S, Fix, GpsTrack, exiftool,
                                           parse_exiftool_json, parse_srt,
                                           read_embedded_gps)

LAT, LON = 41.3111, 69.2797
SAMPLE = Path(__file__).resolve().parents[1] / "samples" / "yangizamon_15s.mp4"


def _exiftool_record(docs: list[dict], main: dict | None = None) -> list[dict]:
    """What ``exiftool -j -n -ee -G3`` prints: one object, groups as prefixes."""
    rec = {"SourceFile": "clip.mp4"}
    for k, v in (main or {}).items():
        rec[f"Main:{k}"] = v
    for i, doc in enumerate(docs, 1):
        for k, v in doc.items():
            rec[f"Doc{i}:{k}"] = v
    return [rec]


class TestExiftoolOutput:
    def test_timed_samples_become_a_track_in_video_time(self):
        track = parse_exiftool_json(_exiftool_record([
            {"SampleTime": 1.001, "GPSLatitude": LAT + 0.0001, "GPSLongitude": LON},
            {"SampleTime": 0.0, "GPSLatitude": LAT, "GPSLongitude": LON,
             "GPSDateTime": "2026:08:03 11:38:01.000Z"},
        ], main={"GPSLatitude": 1.0, "GPSLongitude": 1.0}))
        assert [f.t_s for f in track.fixes] == [0.0, 1.001]       # sorted
        assert "timed by the video" in track.source
        assert track.fixes[0].utc == "2026:08:03 11:38:01.000Z"

    def test_position_is_interpolated_between_fixes(self):
        track = GpsTrack((Fix(0.0, LAT, LON), Fix(2.0, LAT + 0.002, LON + 0.002)), "t")
        mid = track.at(1.0)
        assert mid.lat == pytest.approx(LAT + 0.001)
        assert mid.lon == pytest.approx(LON + 0.001)

    def test_no_position_across_a_long_gap(self):
        """A tunnel is not a straight line between its two ends."""
        track = GpsTrack((Fix(0.0, LAT, LON), Fix(MAX_GAP_S + 5, LAT + 0.01, LON)), "t")
        assert track.at(MAX_GAP_S / 2) is None

    def test_no_position_far_outside_the_track(self):
        track = GpsTrack((Fix(5.0, LAT, LON), Fix(6.0, LAT, LON)), "t")
        assert track.at(4.0) is not None          # first fix arrives a moment late
        assert track.at(0.5) is None
        assert track.at(30.0) is None

    def test_clock_only_samples_are_timed_from_the_first_fix(self):
        track = parse_exiftool_json(_exiftool_record([
            {"GPSDateTime": "2026:08:03 11:38:02Z", "GPSLatitude": LAT, "GPSLongitude": LON},
            {"GPSDateTime": "2026:08:03 11:38:03.5Z", "GPSLatitude": LAT, "GPSLongitude": LON},
        ]))
        assert [f.t_s for f in track.fixes] == [0.0, 1.5]
        assert "first fix" in track.source

    def test_a_single_location_covers_the_whole_clip(self):
        track = parse_exiftool_json(_exiftool_record([], main={
            "GPSLatitude": LAT, "GPSLongitude": LON}))
        assert track.static
        assert track.at(123.0).lat == LAT

    def test_zero_zero_is_no_fix(self):
        assert parse_exiftool_json(_exiftool_record([
            {"SampleTime": 0.0, "GPSLatitude": 0, "GPSLongitude": 0}])) is None

    def test_nothing_found(self):
        assert parse_exiftool_json([{"SourceFile": "clip.mp4"}]) is None
        assert parse_exiftool_json([]) is None


DJI_SRT = """1
00:00:00,000 --> 00:00:00,033
<font size="28">FrameCnt: 1, DiffTime: 33ms
2026-08-03 11:38:01.000
[iso: 100] [shutter: 1/500.0] [fnum: 2.8] [latitude: 41.311100] [longitude: 69.279700] [rel_alt: 1.700 abs_alt: 450.000] </font>

2
00:00:01,000 --> 00:00:01,033
<font size="28">FrameCnt: 31, DiffTime: 33ms
[latitude: 41.311200] [longitude: 69.279800] [rel_alt: 1.700 abs_alt: 450.000] </font>
"""

OLD_DJI_SRT = """1
00:00:00,000 --> 00:00:01,000
HOME(69.2790,41.3100) 2016.08.03 11:38:01
GPS(69.2797,41.3111,19) BAROMETER:1.7
"""


class TestSidecarSrt:
    def test_dji_latitude_longitude_tags(self):
        track = parse_srt(DJI_SRT)
        assert [(f.t_s, f.lat, f.lon) for f in track.fixes] == [
            (0.0, 41.3111, 69.2797), (1.0, 41.3112, 69.2798)]

    def test_old_firmware_writes_longitude_first(self):
        fix = parse_srt(OLD_DJI_SRT).fixes[0]
        assert (fix.lat, fix.lon) == (41.3111, 69.2797)

    def test_subtitles_without_coordinates(self):
        assert parse_srt("1\n00:00:00,000 --> 00:00:01,000\nhello\n") is None


def _clip(tmp_path: Path, **metadata) -> Path:
    if not SAMPLE.exists() or not shutil.which("ffmpeg"):
        pytest.skip("needs ffmpeg and the bundled sample clip")
    out = tmp_path / "clip.mp4"
    args = ["ffmpeg", "-v", "error", "-y", "-i", str(SAMPLE), "-t", "3", "-c", "copy"]
    for k, v in metadata.items():
        args += ["-metadata", f"{k}={v}", "-movflags", "use_metadata_tags"]
    subprocess.run([*args, str(out)], check=True)
    return out


def test_sidecar_srt_beside_a_real_video(tmp_path):
    video = _clip(tmp_path)
    video.with_suffix(".SRT").write_text(DJI_SRT)
    track = read_embedded_gps(video)
    assert track is not None and len(track.fixes) == 2
    assert "clip.SRT" in track.source


def test_phone_location_through_exiftool(tmp_path):
    if not exiftool():
        pytest.skip("ExifTool is not installed")
    video = _clip(tmp_path, location=f"+{LAT:.4f}+0{LON:.4f}/")
    track = read_embedded_gps(video)
    assert track is not None and track.static
    assert track.fixes[0].lat == pytest.approx(LAT, abs=1e-4)
    assert track.fixes[0].lon == pytest.approx(LON, abs=1e-4)


def test_no_gps_at_all(tmp_path):
    if not exiftool():
        pytest.skip("ExifTool is not installed")
    assert read_embedded_gps(_clip(tmp_path)) is None
