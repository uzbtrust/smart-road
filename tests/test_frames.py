"""Tests for georeferencing sampled frames.

Everything here is built in the test rather than read from SURVEY/, so the suite
still means something in a checkout that carries no footage. The container for
`video_start_time` is sixteen hand-written bytes of atom header, which is enough
of an MP4 for the parser and needs no ffmpeg.
"""
from __future__ import annotations

import datetime as _dt
import struct

import pytest

from smartroad.survey.frames import (EDGE_TOLERANCE_S, MIN_STEP_M, Track,
                                     TrackPoint, frame_spacing_m, haversine_m,
                                     read_gpx, video_start_time)

# A degree of latitude is about 111 km; these two are 0.001 deg apart.
LAT, LON = 41.27, 69.2875


def _gpx(path, fixes):
    """fixes: [(seconds_from_start, lat, lon)]"""
    base = _dt.datetime(2026, 8, 3, 11, 38, 0, tzinfo=_dt.timezone.utc)
    pts = "".join(
        f'<trkpt lat="{lat}" lon="{lon}"><ele>380</ele>'
        f'<time>{(base + _dt.timedelta(seconds=s)).isoformat().replace("+00:00", "Z")}</time>'
        f'</trkpt>'
        for s, lat, lon in fixes)
    path.write_text(
        '<?xml version="1.0"?>'
        '<gpx xmlns="http://www.topografix.com/GPX/1/1" version="1.1">'
        f'<trk><trkseg>{pts}</trkseg></trk></gpx>')
    return path


def test_haversine_matches_a_known_separation():
    # One thousandth of a degree of latitude is 111.19 m on a sphere.
    d = haversine_m(LAT, LON, LAT + 0.001, LON)
    assert d == pytest.approx(111.19, abs=0.5)


def test_haversine_is_symmetric_and_zero_on_itself():
    assert haversine_m(LAT, LON, LAT, LON) == 0.0
    assert haversine_m(LAT, LON, LAT + 0.01, LON + 0.01) == \
        pytest.approx(haversine_m(LAT + 0.01, LON + 0.01, LAT, LON))


def test_chainage_accumulates_along_the_track(tmp_path):
    pts = read_gpx(_gpx(tmp_path / "t.gpx",
                        [(0, LAT, LON), (10, LAT + 0.001, LON),
                         (20, LAT + 0.002, LON)]))
    assert pts[0].chainage_m == 0.0
    assert pts[1].chainage_m == pytest.approx(111.19, abs=0.5)
    assert pts[2].chainage_m == pytest.approx(222.4, abs=1.0)


def test_gps_jitter_below_the_step_threshold_adds_no_distance(tmp_path):
    """A vehicle stopped at a light must not accumulate phantom metres."""
    wander = 0.000002          # ~0.2 m, well under MIN_STEP_M
    pts = read_gpx(_gpx(tmp_path / "t.gpx",
                        [(s, LAT + wander * s, LON) for s in range(30)]))
    assert pts[-1].chainage_m == 0.0
    assert MIN_STEP_M > 0.2


def test_points_without_a_time_are_dropped_not_guessed(tmp_path):
    p = tmp_path / "t.gpx"
    p.write_text(
        '<?xml version="1.0"?>'
        '<gpx xmlns="http://www.topografix.com/GPX/1/1" version="1.1"><trk><trkseg>'
        f'<trkpt lat="{LAT}" lon="{LON}"><time>2026-08-03T11:38:00Z</time></trkpt>'
        f'<trkpt lat="{LAT + 0.001}" lon="{LON}"></trkpt>'
        f'<trkpt lat="{LAT + 0.002}" lon="{LON}"><time>2026-08-03T11:38:20Z</time></trkpt>'
        '</trkseg></trk></gpx>')
    assert len(read_gpx(p)) == 2


def test_a_track_with_one_fix_is_not_a_track(tmp_path):
    with pytest.raises(ValueError):
        Track(read_gpx(_gpx(tmp_path / "t.gpx", [(0, LAT, LON)])))


# ---------------------------------------------------------------- interpolation

@pytest.fixture
def track(tmp_path):
    """Three fixes, ten seconds and ~111 m apart."""
    return Track(read_gpx(_gpx(tmp_path / "t.gpx",
                               [(0, LAT, LON), (10, LAT + 0.001, LON),
                                (20, LAT + 0.002, LON)])))


def test_interpolates_halfway_between_two_fixes(track):
    half = track.start + _dt.timedelta(seconds=5)
    lat, lon, chainage, _ = track.at(half)
    assert lat == pytest.approx(LAT + 0.0005, abs=1e-7)
    assert lon == pytest.approx(LON, abs=1e-7)
    assert chainage == pytest.approx(55.6, abs=1.0)


def test_returns_the_endpoints_exactly(track):
    assert track.at(track.start)[2] == 0.0
    assert track.at(track.end)[2] == pytest.approx(track.length_m)


def test_clamps_just_outside_the_track(track):
    """Recording usually starts a moment before the tracker's next sample."""
    early = track.start - _dt.timedelta(seconds=EDGE_TOLERANCE_S / 2)
    assert track.at(early)[2] == 0.0


def test_refuses_a_time_far_outside_the_track(track):
    """Clamping this would put real distress at the wrong end of the street."""
    with pytest.raises(ValueError, match="before the track"):
        track.at(track.start - _dt.timedelta(seconds=EDGE_TOLERANCE_S + 60))
    with pytest.raises(ValueError, match="after the track"):
        track.at(track.end + _dt.timedelta(seconds=EDGE_TOLERANCE_S + 60))


def test_speed_is_distance_over_time(track):
    # 111 m in 10 s.
    _, _, _, speed = track.at(track.start + _dt.timedelta(seconds=5))
    assert speed == pytest.approx(11.1, abs=0.3)


def test_length_and_duration_describe_the_whole_track(track):
    assert track.length_m == pytest.approx(222.4, abs=1.0)
    assert track.duration_s == 20.0


# ------------------------------------------------------------------- container

def _mp4(path, seconds_since_1904, version=0):
    """The smallest container this parser will accept: ftyp + moov/mvhd."""
    if version == 1:
        payload = b"\x01\x00\x00\x00" + struct.pack(">Q", seconds_since_1904) + b"\x00" * 20
    else:
        payload = b"\x00\x00\x00\x00" + struct.pack(">I", seconds_since_1904) + b"\x00" * 12
    mvhd = struct.pack(">I4s", 8 + len(payload), b"mvhd") + payload
    moov = struct.pack(">I4s", 8 + len(mvhd), b"moov") + mvhd
    ftyp = struct.pack(">I4s", 16, b"ftyp") + b"isom" + b"\x00" * 4
    path.write_bytes(ftyp + moov)
    return path


def test_reads_the_creation_time_out_of_mvhd(tmp_path):
    # 2026-08-03T11:38:01Z, the stamp on the Yangizamon forward pass.
    want = _dt.datetime(2026, 8, 3, 11, 38, 1, tzinfo=_dt.timezone.utc)
    secs = int((want - _dt.datetime(1904, 1, 1, tzinfo=_dt.timezone.utc)).total_seconds())
    assert video_start_time(_mp4(tmp_path / "a.mov", secs)) == want


def test_reads_the_64_bit_form_too(tmp_path):
    want = _dt.datetime(2026, 8, 3, 11, 38, 1, tzinfo=_dt.timezone.utc)
    secs = int((want - _dt.datetime(1904, 1, 1, tzinfo=_dt.timezone.utc)).total_seconds())
    assert video_start_time(_mp4(tmp_path / "b.mov", secs, version=1)) == want


def test_a_container_with_no_clock_fails_rather_than_landing_in_1904(tmp_path):
    with pytest.raises(ValueError, match="no creation time"):
        video_start_time(_mp4(tmp_path / "c.mov", 0))


def test_a_file_that_is_not_a_container_fails(tmp_path):
    p = tmp_path / "d.mov"
    p.write_bytes(b"not an atom tree at all, just bytes on disk")
    with pytest.raises(ValueError, match="no mvhd"):
        video_start_time(p)


# --------------------------------------------------------------------- spacing

def test_frame_spacing_is_the_gap_between_consecutive_frames():
    from smartroad.survey.frames import GeoFrame
    base = _dt.datetime(2026, 8, 3, 11, 38, tzinfo=_dt.timezone.utc)
    frames = [GeoFrame(float(i), base, LAT, LON, i * 6.5, 6.5) for i in range(4)]
    assert frame_spacing_m(frames) == pytest.approx([6.5, 6.5, 6.5])
    assert frame_spacing_m(frames[:1]) == []


# ------------------------------------------------------- end to end, needs ffmpeg

needs_ffmpeg = pytest.mark.skipif(
    __import__("shutil").which("ffmpeg") is None, reason="ffmpeg not installed")

CLIP_START = _dt.datetime(2026, 8, 3, 11, 38, 0, tzinfo=_dt.timezone.utc)


@pytest.fixture
def clip(tmp_path):
    """Six seconds of test pattern, stamped so mvhd carries a real clock.

    ffmpeg leaves the creation time at zero unless asked, and the parser refuses
    that rather than placing every frame in 1904 -- which is the behaviour under
    test elsewhere in this file, so here it has to be given a time.
    """
    import subprocess
    out = tmp_path / "clip.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
                    "-i", "testsrc=size=320x240:rate=30:duration=6",
                    "-pix_fmt", "yuv420p", "-metadata",
                    f"creation_time={CLIP_START.isoformat().replace('+00:00', 'Z')}",
                    str(out)], check=True)
    return out


@needs_ffmpeg
def test_places_every_sampled_frame_on_the_track(tmp_path, clip):
    from smartroad.survey.frames import locate_frames
    gpx = _gpx(tmp_path / "t.gpx",
               [(s, LAT + 0.0001 * s, LON) for s in range(0, 30, 5)])
    frames = locate_frames(clip, gpx, every_s=1.0)
    assert len(frames) == 6
    # video.frame_times starts half an interval in, deliberately: frame zero is
    # often still auto-exposing. The wall clock has to carry that same offset.
    assert [f.t_s for f in frames] == pytest.approx([0.5, 1.5, 2.5, 3.5, 4.5, 5.5])
    assert frames[0].time == CLIP_START + _dt.timedelta(seconds=0.5)
    # Chainage only ever increases along a track driven in one direction.
    chainages = [f.chainage_m for f in frames]
    assert chainages == sorted(chainages)


@needs_ffmpeg
def test_refuses_when_the_clocks_do_not_overlap(tmp_path, clip):
    """A six-second clip and a track an hour away must not be joined."""
    from smartroad.survey.frames import locate_frames
    gpx = _gpx(tmp_path / "t.gpx", [(0, LAT, LON), (10, LAT + 0.001, LON)])
    with pytest.raises(ValueError, match="do not overlap"):
        locate_frames(clip, gpx, every_s=1.0, offset_s=-3600.0)


@needs_ffmpeg
def test_offset_corrects_a_container_stamped_at_the_wrong_moment(tmp_path, clip):
    """The escape hatch for cameras that stamp the end of the recording."""
    from smartroad.survey.frames import locate_frames
    # Track sits an hour later; the offset is what brings the clip onto it.
    late = [(3600 + s, LAT + 0.0001 * s, LON) for s in range(0, 30, 5)]
    gpx = _gpx(tmp_path / "t.gpx", late)
    with pytest.raises(ValueError, match="do not overlap"):
        locate_frames(clip, gpx, every_s=1.0)
    frames = locate_frames(clip, gpx, every_s=1.0, offset_s=3600.0)
    assert len(frames) == 6
