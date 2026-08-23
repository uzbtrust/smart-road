"""Put a sampled frame somewhere on the road.

`video.py` turns a drive into frames and grades each one, and its own docstring
names what it cannot do: consecutive samples overlap, so a long crack is counted
twice and densities can never be summed into a section total. Fixing that needs
to know where each frame *is*, not merely when it was taken. That is what this
module supplies -- a chainage in metres along the driven track, from which
`sections.py` can bin frames into ASTM sample units and drop the overlap.

The pieces are a GPS track, a wall-clock start for the video, and the assumption
that the camera and the phone recording the track were in the same vehicle.

TIME. The GPX carries UTC. The video carries a creation time in its `mvhd` atom,
counted in seconds from 1904-01-01 UTC. On the Yangizamon survey the two agree
without adjustment: the recorder wrote 11:38:01 for a 288-second clip against a
track running 11:37:50 to 11:42:42, so the stamp is the moment recording began
and the clip ends seven seconds inside the track. That is not universal -- some
cameras stamp the moment recording stopped, and some write local time into a
field the specification reserves for UTC -- so `offset_s` exists to correct it
and `locate_frames` refuses to guess when the two do not overlap.

Reading `mvhd` directly rather than shelling out to ffprobe is deliberate, for
the reason `video.py` gives at length: a subprocess spawned from a worker thread
after Metal has initialised segfaults on macOS, and Streamlit runs the script on
a worker thread. Parsing sixteen bytes of container header has no fork in it.

DISTANCE. Haversine on a sphere, which is good to about half a percent at these
latitudes -- ten centimetres over a twenty-metre gap between fixes, well inside
the noise of the fixes themselves. Steps shorter than `MIN_STEP_M` are treated
as jitter and contribute nothing, because a stationary vehicle otherwise
accumulates phantom metres from GPS wander and every chainage after the stop is
wrong by that much.
"""
from __future__ import annotations

import datetime as _dt
import math
import struct
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

#: Seconds between the QuickTime epoch and the Unix one.
QUICKTIME_EPOCH = _dt.datetime(1904, 1, 1, tzinfo=_dt.timezone.utc)

#: Mean Earth radius, metres. Haversine's usual constant.
EARTH_RADIUS_M = 6_371_000.0

#: Consecutive fixes closer than this are GPS wander rather than travel.
MIN_STEP_M = 1.0

#: How far outside the track a frame may fall before it is an error rather than
#: an edge effect. One fix interval is generous; ten seconds covers the gap
#: between pressing record and the tracker's next sample.
EDGE_TOLERANCE_S = 10.0

_GPX_NS = {"gpx": "http://www.topografix.com/GPX/1/1"}


@dataclass(frozen=True)
class TrackPoint:
    """One GPS fix, with distance travelled to reach it."""

    time: _dt.datetime
    lat: float
    lon: float
    ele: float | None
    chainage_m: float


@dataclass(frozen=True)
class GeoFrame:
    """A sampled frame, placed on the track."""

    t_s: float                 #: seconds into the video
    time: _dt.datetime         #: wall clock, UTC
    lat: float
    lon: float
    chainage_m: float          #: metres along the track from its start
    speed_ms: float | None     #: instantaneous speed at this point


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in metres."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


def _parse_time(text: str) -> _dt.datetime:
    """GPX times are ISO 8601; Python before 3.11 will not take a bare Z."""
    cleaned = text.strip().replace("Z", "+00:00")
    stamp = _dt.datetime.fromisoformat(cleaned)
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=_dt.timezone.utc)
    return stamp.astimezone(_dt.timezone.utc)


def read_gpx(path: str | Path) -> list[TrackPoint]:
    """Read a GPX track and accumulate chainage along it.

    Points without a time are dropped rather than guessed at: the whole point of
    the track is to be indexed by time, and a fix that cannot be is not useful.
    """
    root = ET.parse(Path(path)).getroot()
    raw: list[tuple[_dt.datetime, float, float, float | None]] = []
    for pt in root.iterfind(".//gpx:trkpt", _GPX_NS):
        when = pt.find("gpx:time", _GPX_NS)
        if when is None or not (when.text or "").strip():
            continue
        ele = pt.find("gpx:ele", _GPX_NS)
        raw.append((_parse_time(when.text),
                    float(pt.get("lat")), float(pt.get("lon")),
                    float(ele.text) if ele is not None and ele.text else None))

    if not raw:
        raise ValueError(f"{path}: no timed track points")

    raw.sort(key=lambda r: r[0])
    points: list[TrackPoint] = []
    travelled = 0.0
    for i, (when, lat, lon, ele) in enumerate(raw):
        if i:
            step = haversine_m(raw[i - 1][1], raw[i - 1][2], lat, lon)
            if step >= MIN_STEP_M:
                travelled += step
        points.append(TrackPoint(when, lat, lon, ele, travelled))
    return points


def video_start_time(path: str | Path) -> _dt.datetime:
    """Wall-clock start of an MP4/MOV, read from its `mvhd` atom.

    Raises if the atom is absent or the time is zero, which is what a container
    written without a clock looks like -- better to fail than to place every
    frame at the start of 1904.
    """
    path = Path(path)
    size = path.stat().st_size
    with path.open("rb") as fh:
        body = _find_atom(fh, size, b"mvhd")
    if body is None:
        raise ValueError(f"{path}: no mvhd atom; not an MP4/MOV container?")

    version = body[0]
    seconds = (struct.unpack(">Q", body[4:12])[0] if version == 1
               else struct.unpack(">I", body[4:8])[0])
    if seconds == 0:
        raise ValueError(f"{path}: mvhd carries no creation time")
    return QUICKTIME_EPOCH + _dt.timedelta(seconds=seconds)


def _find_atom(fh, end: int, want: bytes) -> bytes | None:
    """Walk the atom tree for `want`, descending only through containers."""
    containers = {b"moov", b"trak", b"mdia", b"udta"}
    while fh.tell() < end - 8:
        start = fh.tell()
        header = fh.read(8)
        if len(header) < 8:
            return None
        size, kind = struct.unpack(">I4s", header)
        if size == 1:                       # 64-bit extended size
            size = struct.unpack(">Q", fh.read(8))[0]
        elif size == 0:                     # runs to end of file
            size = end - start
        if size < 8:
            return None
        if kind == want:
            return fh.read(min(size - 8, end - fh.tell()))
        if kind in containers:
            found = _find_atom(fh, min(start + size, end), want)
            if found is not None:
                return found
        fh.seek(start + size)
    return None


class Track:
    """A GPS track, queryable by time."""

    def __init__(self, points: list[TrackPoint]) -> None:
        if len(points) < 2:
            raise ValueError("a track needs at least two fixes")
        self.points = points

    # ------------------------------------------------------------- properties
    @property
    def start(self) -> _dt.datetime:
        return self.points[0].time

    @property
    def end(self) -> _dt.datetime:
        return self.points[-1].time

    @property
    def length_m(self) -> float:
        return self.points[-1].chainage_m

    @property
    def duration_s(self) -> float:
        return (self.end - self.start).total_seconds()

    # ---------------------------------------------------------------- queries
    def at(self, when: _dt.datetime) -> tuple[float, float, float, float | None]:
        """Interpolate (lat, lon, chainage_m, speed_ms) at `when`.

        Linear between the bracketing fixes. Times just outside the track are
        clamped to its ends -- a recording usually starts a moment before or
        after the tracker does -- but anything further out raises, because a
        frame that far outside is a synchronisation error, not an edge effect,
        and silently clamping it would place real distress at the wrong end of
        the street.
        """
        if when < self.start - _dt.timedelta(seconds=EDGE_TOLERANCE_S):
            raise ValueError(f"{when.isoformat()} is before the track "
                             f"({self.start.isoformat()})")
        if when > self.end + _dt.timedelta(seconds=EDGE_TOLERANCE_S):
            raise ValueError(f"{when.isoformat()} is after the track "
                             f"({self.end.isoformat()})")

        if when <= self.start:
            first = self.points[0]
            return first.lat, first.lon, first.chainage_m, self._speed(0)
        if when >= self.end:
            last = self.points[-1]
            return last.lat, last.lon, last.chainage_m, self._speed(len(self.points) - 1)

        hi = self._bracket(when)
        lo = hi - 1
        a, b = self.points[lo], self.points[hi]
        span = (b.time - a.time).total_seconds()
        f = 0.0 if span <= 0 else (when - a.time).total_seconds() / span
        return (a.lat + (b.lat - a.lat) * f,
                a.lon + (b.lon - a.lon) * f,
                a.chainage_m + (b.chainage_m - a.chainage_m) * f,
                self._speed(hi))

    def _bracket(self, when: _dt.datetime) -> int:
        """Index of the first fix at or after `when`. Binary search."""
        lo, hi = 0, len(self.points) - 1
        while lo < hi:
            mid = (lo + hi) // 2
            if self.points[mid].time < when:
                lo = mid + 1
            else:
                hi = mid
        return max(lo, 1)

    def _speed(self, i: int) -> float | None:
        """Speed over the segment ending at `i`, m/s."""
        if i <= 0:
            i = 1
        a, b = self.points[i - 1], self.points[i]
        span = (b.time - a.time).total_seconds()
        if span <= 0:
            return None
        return (b.chainage_m - a.chainage_m) / span


def locate_frames(video: str | Path, gpx: str | Path, *,
                  every_s: float = 1.0, max_frames: int | None = None,
                  offset_s: float = 0.0) -> list[GeoFrame]:
    """Place each sampled frame of `video` on the track in `gpx`.

    Sampling times come from `video.frame_times`, so this and the grading path
    agree on which frames exist rather than each deciding separately.

    `offset_s` is added to the video's start before the lookup, for containers
    whose creation time is the end of the recording or is written in local time.
    Where the two clocks disagree by more than the clip's own length, the
    overlap check below refuses rather than producing a chainage that looks
    plausible and is not.
    """
    from smartroad.survey.video import frame_times, probe_video

    track = Track(read_gpx(gpx))
    started = video_start_time(video) + _dt.timedelta(seconds=offset_s)
    info = probe_video(video)
    finished = started + _dt.timedelta(seconds=info.duration_s)

    if finished < track.start - _dt.timedelta(seconds=EDGE_TOLERANCE_S) or \
            started > track.end + _dt.timedelta(seconds=EDGE_TOLERANCE_S):
        raise ValueError(
            f"video runs {started.isoformat()}..{finished.isoformat()} but the "
            f"track runs {track.start.isoformat()}..{track.end.isoformat()}; "
            "they do not overlap. Pass offset_s if the clocks differ.")

    out: list[GeoFrame] = []
    for t_s in frame_times(info, every_s=every_s, max_frames=max_frames):
        when = started + _dt.timedelta(seconds=t_s)
        lat, lon, chainage, speed = track.at(when)
        out.append(GeoFrame(t_s, when, lat, lon, chainage, speed))
    return out


def frame_spacing_m(frames: list[GeoFrame]) -> list[float]:
    """Distance between consecutive frames.

    `sections.py` needs this to know whether two samples overlap: a frame
    measures a band roughly three to twelve metres deep, so anything closer than
    that band is looking at asphalt its neighbour already counted.
    """
    return [b.chainage_m - a.chainage_m for a, b in zip(frames, frames[1:])]
