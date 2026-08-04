"""Tests for video sampling.

Built against a clip generated here rather than a fixture on disk, so the suite
still means something in a checkout that does not carry survey footage. Skips
cleanly where ffmpeg is absent.
"""
from __future__ import annotations

import shutil
import subprocess

import pytest

from smartroad.survey.video import (extract_frames, frame_times, probe_video)

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None
                                or shutil.which("ffprobe") is None,
                                reason="ffmpeg not installed")

WIDTH, HEIGHT, FPS, SECONDS = 320, 240, 30, 6


@pytest.fixture(scope="module")
def clip(tmp_path_factory):
    """A synthetic clip of known dimensions, frame rate and length."""
    path = tmp_path_factory.mktemp("video") / "clip.mp4"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-f", "lavfi",
         "-i", f"testsrc=size={WIDTH}x{HEIGHT}:rate={FPS}:duration={SECONDS}",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-y", str(path)],
        check=True, capture_output=True)
    return path


class TestProbe:
    def test_reads_the_dimensions_and_rate(self, clip):
        info = probe_video(clip)
        assert (info.width, info.height) == (WIDTH, HEIGHT)
        assert info.fps == pytest.approx(FPS, abs=0.1)
        assert info.duration_s == pytest.approx(SECONDS, abs=0.2)
        assert info.n_frames == pytest.approx(FPS * SECONDS, rel=0.05)

    def test_missing_file_is_an_error(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            probe_video(tmp_path / "nope.mp4")

    def test_label_is_human_readable(self, clip):
        assert "320x240" in probe_video(clip).label


class TestFrameTimes:
    def test_one_per_interval(self, clip):
        info = probe_video(clip)
        times = frame_times(info, every_s=1.0)
        assert len(times) == SECONDS
        assert all(0 <= t < info.duration_s for t in times)

    def test_starts_half_an_interval_in(self, clip):
        """Frame zero on dashcam footage is often still auto-exposing."""
        assert frame_times(probe_video(clip), every_s=2.0)[0] == pytest.approx(1.0)

    def test_spacing_is_the_interval(self, clip):
        t = frame_times(probe_video(clip), every_s=1.5)
        gaps = [b - a for a, b in zip(t, t[1:])]
        assert all(g == pytest.approx(1.5) for g in gaps)

    def test_max_frames_caps_the_list(self, clip):
        assert len(frame_times(probe_video(clip), every_s=0.5, max_frames=4)) == 4

    def test_rejects_a_nonpositive_interval(self, clip):
        with pytest.raises(ValueError):
            frame_times(probe_video(clip), every_s=0)


class TestExtract:
    def test_one_file_per_sample(self, clip, tmp_path):
        got = extract_frames(clip, every_s=1.0, out_dir=tmp_path / "f")
        assert len(got) == SECONDS
        assert all(p.is_file() and p.stat().st_size > 0 for _, p in got)

    def test_times_ascend(self, clip, tmp_path):
        times = [t for t, _ in extract_frames(clip, every_s=1.0, out_dir=tmp_path / "f")]
        assert times == sorted(times)

    def test_max_frames_is_honoured(self, clip, tmp_path):
        assert len(extract_frames(clip, every_s=0.5, max_frames=3,
                                  out_dir=tmp_path / "f")) == 3

    def test_long_side_rescales(self, clip, tmp_path):
        from PIL import Image

        got = extract_frames(clip, every_s=2.0, long_side=160, out_dir=tmp_path / "f")
        with Image.open(got[0][1]) as im:
            assert max(im.size) == 160

    def test_frames_keep_the_source_size_by_default(self, clip, tmp_path):
        from PIL import Image

        got = extract_frames(clip, every_s=2.0, out_dir=tmp_path / "f")
        with Image.open(got[0][1]) as im:
            assert im.size == (WIDTH, HEIGHT)
