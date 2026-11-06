"""Read the GPS track a camera recorded inside its own video file.

`frames.py` places frames on a separately recorded GPX track, which needs two
clocks to agree. Many cameras make that unnecessary: GoPro writes GPS into a
GPMF track, DJI into its metadata stream or a sidecar .SRT, Novatek-based
dashcams into ``freeGPS`` boxes, Garmin, Insta360, BlackVue, Nextbase and Sony
into formats of their own, and a phone writes at least one location for the
clip. Each fix carries its time *in the video*, so a frame's position is a
lookup, with no synchronisation to get wrong.

READING. There are dozens of these formats and each brand has several, so
parsing is left to ExifTool, which decodes nearly all of them and is
maintained as cameras change. It is found on the PATH, or through the
``SMARTROAD_EXIFTOOL`` environment variable. The one format read here
directly is DJI's sidecar subtitle file, ``clip.SRT`` beside ``clip.MP4``,
because it is plain text and ExifTool does not look beside the video for it.

WHAT A COORDINATE MEANS. It is where the *camera* was. The road that was
graded lies 3 to 15 m ahead of it, and consumer GPS is good to 3-5 m, so a
coordinate locates a frame's stretch of road, not a single crack in it.

TIME. ExifTool gives each sample a ``SampleTime``, seconds from the start of
the video. A few formats carry only a wall-clock ``GPSDateTime``; those are
timed from the first fix, which assumes the recording and the GPS log began
together, and the track says so in its `source`.
"""
from __future__ import annotations

import bisect
import datetime as _dt
import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

#: How far outside the recorded fixes a frame may be and still get the nearest
#: one. Cameras often take a second or two to get their first fix.
EDGE_TOLERANCE_S = 3.0

#: The longest gap between two fixes that is interpolated across. Longer than
#: this, the receiver lost its fix (a tunnel, an underpass) and a straight line
#: between the two ends would put frames somewhere the vehicle never was.
MAX_GAP_S = 10.0

#: Seconds allowed for ExifTool to read one video.
EXIFTOOL_TIMEOUT_S = 300


@dataclass(frozen=True)
class Fix:
    t_s: float                      #: seconds into the video
    lat: float
    lon: float
    utc: str | None = None          #: the receiver's own timestamp, as written


@dataclass(frozen=True)
class GpsTrack:
    fixes: tuple[Fix, ...]
    source: str                     #: where the fixes came from, for the workbook

    @property
    def static(self) -> bool:
        """One location for the whole clip, as phones write it."""
        return len(self.fixes) == 1

    def at(self, t_s: float) -> Fix | None:
        """Position at `t_s` seconds into the video, or None if not known.

        Linear between the fixes either side. Outside the track by more than
        `EDGE_TOLERANCE_S`, or inside a gap longer than `MAX_GAP_S`, there is
        no position: a blank cell is honest, a guessed one is not.
        """
        fixes = self.fixes
        if self.static:
            return fixes[0]
        times = [f.t_s for f in fixes]
        i = bisect.bisect_left(times, t_s)
        if i == 0:
            return fixes[0] if times[0] - t_s <= EDGE_TOLERANCE_S else None
        if i == len(fixes):
            return fixes[-1] if t_s - times[-1] <= EDGE_TOLERANCE_S else None
        a, b = fixes[i - 1], fixes[i]
        span = b.t_s - a.t_s
        if span > MAX_GAP_S:
            return None
        f = 0.0 if span <= 0 else (t_s - a.t_s) / span
        nearer = a if f < 0.5 else b
        return Fix(t_s, a.lat + (b.lat - a.lat) * f, a.lon + (b.lon - a.lon) * f,
                   nearer.utc)


def exiftool() -> str | None:
    """The ExifTool command, or None if it is not installed."""
    configured = os.environ.get("SMARTROAD_EXIFTOOL")
    if configured:
        return configured
    return shutil.which("exiftool")


def exiftool_version() -> str | None:
    exe = exiftool()
    if not exe:
        return None
    try:
        out = subprocess.run([exe, "-ver"], capture_output=True, text=True,
                             timeout=30, check=True)
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() or None


def _valid(lat, lon) -> bool:
    if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
        return False
    # 0,0 is what many receivers write before they have a fix.
    return -90 <= lat <= 90 and -180 <= lon <= 180 and not (lat == 0 and lon == 0)


def _utc_seconds(text: str) -> float | None:
    """Seconds since the epoch for ExifTool's ``YYYY:MM:DD HH:MM:SS[.fff]Z``."""
    m = re.match(r"(\d{4}):(\d\d):(\d\d) (\d\d):(\d\d):(\d\d(?:\.\d+)?)", text or "")
    if not m:
        return None
    y, mo, d, h, mi = (int(x) for x in m.groups()[:5])
    sec = float(m.group(6))
    stamp = _dt.datetime(y, mo, d, h, mi, tzinfo=_dt.timezone.utc)
    return stamp.timestamp() + sec


def parse_exiftool_json(records: list[dict]) -> GpsTrack | None:
    """Turn ``exiftool -j -n -ee -G3`` output into a track.

    With ``-G3`` each embedded sample is its own group, ``Doc1``, ``Doc2``...,
    and the file's own tags are in ``Main``. Timed samples win; a lone ``Main``
    location is the fallback, because a GoPro also writes one there.
    """
    if not records:
        return None
    rec = records[0]
    docs: dict[str, dict[str, object]] = {}
    for key, value in rec.items():
        group, _, tag = key.partition(":")
        if tag:
            docs.setdefault(group, {})[tag] = value

    timed: list[Fix] = []
    by_clock: list[tuple[float, Fix]] = []
    for group, tags in docs.items():
        if not group.startswith("Doc"):
            continue
        lat, lon = tags.get("GPSLatitude"), tags.get("GPSLongitude")
        if not _valid(lat, lon):
            continue
        utc = tags.get("GPSDateTime")
        utc = str(utc) if utc is not None else None
        t = tags.get("SampleTime")
        if isinstance(t, (int, float)):
            timed.append(Fix(float(t), float(lat), float(lon), utc))
        elif utc and (secs := _utc_seconds(utc)) is not None:
            by_clock.append((secs, Fix(0.0, float(lat), float(lon), utc)))

    if timed:
        return GpsTrack(_dedupe(timed), "embedded track, timed by the video")
    if by_clock:
        start = min(s for s, _ in by_clock)
        fixes = [Fix(s - start, f.lat, f.lon, f.utc) for s, f in by_clock]
        return GpsTrack(_dedupe(fixes),
                        "embedded track, timed from its first fix (assumes the "
                        "GPS log and the recording began together)")

    main = docs.get("Main", {})
    lat, lon = main.get("GPSLatitude"), main.get("GPSLongitude")
    if _valid(lat, lon):
        return GpsTrack((Fix(0.0, float(lat), float(lon)),),
                        "one location for the whole clip (no track in the file)")
    return None


def _dedupe(fixes: list[Fix]) -> tuple[Fix, ...]:
    """Sorted by time, one fix per time."""
    out: dict[float, Fix] = {}
    for f in sorted(fixes, key=lambda f: f.t_s):
        out.setdefault(round(f.t_s, 3), f)
    return tuple(out.values())


def read_with_exiftool(path: Path) -> GpsTrack | None:
    exe = exiftool()
    if not exe:
        return None
    cmd = [exe, "-j", "-n", "-ee", "-G3", "-api", "LargeFileSupport=1",
           "-GPSLatitude", "-GPSLongitude", "-GPSDateTime", "-SampleTime", str(path)]
    out = subprocess.run(cmd, capture_output=True, text=True,
                         timeout=EXIFTOOL_TIMEOUT_S)
    if not out.stdout.strip():
        if out.returncode:
            raise RuntimeError(f"exiftool failed on {path.name}: {out.stderr.strip()[:200]}")
        return None
    return parse_exiftool_json(json.loads(out.stdout))


# ───────────────────────────────────────────── DJI sidecar subtitles

_SRT_TIME = re.compile(r"(\d+):(\d\d):(\d\d)[,.](\d{1,3})\s*-->")
_LAT = re.compile(r"latitude\s*[:=]?\s*(-?\d+(?:\.\d+)?)", re.I)
_LON = re.compile(r"longitude\s*[:=]?\s*(-?\d+(?:\.\d+)?)", re.I)
#: Older DJI firmware: ``GPS(lon, lat, alt)`` -- longitude first.
_GPS_TUPLE = re.compile(r"GPS\s*\(\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)", re.I)


def parse_srt(text: str) -> GpsTrack | None:
    """Fixes from a DJI-style subtitle file, each timed by its cue's start."""
    fixes: list[Fix] = []
    for block in re.split(r"\n\s*\n", text.replace("\r\n", "\n")):
        m = _SRT_TIME.search(block)
        if not m:
            continue
        h, mi, s, ms = m.groups()
        t = int(h) * 3600 + int(mi) * 60 + int(s) + int(ms.ljust(3, "0")) / 1000
        lat_m, lon_m = _LAT.search(block), _LON.search(block)
        if lat_m and lon_m:
            lat, lon = float(lat_m.group(1)), float(lon_m.group(1))
        elif g := _GPS_TUPLE.search(block):
            lon, lat = float(g.group(1)), float(g.group(2))
        else:
            continue
        if _valid(lat, lon):
            fixes.append(Fix(t, lat, lon))
    return GpsTrack(_dedupe(fixes), "sidecar subtitle file") if fixes else None


def sidecar_srt(video: Path) -> Path | None:
    for suffix in (".SRT", ".srt"):
        p = video.with_suffix(suffix)
        if p.is_file():
            return p
    return None


def read_embedded_gps(video: str | Path) -> GpsTrack | None:
    """The best GPS record available for `video`, or None.

    A timed track inside the file first, then a sidecar subtitle file, then a
    single location for the clip.
    """
    video = Path(video)
    found = read_with_exiftool(video)
    if found and not found.static:
        return found
    srt = sidecar_srt(video)
    if srt:
        from_srt = parse_srt(srt.read_text(errors="replace"))
        if from_srt:
            return GpsTrack(from_srt.fixes, f"sidecar subtitle file {srt.name}")
    return found
