"""Read GPS coordinates that a dashcam burned into the picture.

    python -m smartroad.survey.overlay_gps drive.mp4            # one fix per second
    python -m smartroad.survey.overlay_gps frame1.jpg frame2.png
    python -m smartroad.survey.overlay_gps drive.mp4 --every-s 0.5 --csv out.csv

Many dashcams -- Viofo, and most Novatek-based cameras -- stamp a strip of text
across the bottom or top of every frame::

    84 KM/H S12.035136 E13.955326   ROBOREDO   VIOFO A129 Plus   15-03-2025 10:56:44

The same camera usually records the track inside the file as well, and
`embedded_gps` reads that; it is the better source. But that track is lost the
moment a clip is trimmed, re-encoded or sent through a messaging app, and the
text in the picture survives all of it. So this is the fallback: OCR on the
strip, then a pattern for the coordinates.

OCR. RapidOCR, which installs with pip alone (``pip install
rapidocr_onnxruntime``) and runs on the CPU. On a Viofo A129 frame it reads the
strip exactly at 2560 px and at the 1280 px the batch grades at, in about half a
second. It is optional: without it this module reports that it cannot read.

WHAT CAN GO WRONG, AND WHAT IS DONE ABOUT IT.

* A misread digit moves a fix kilometres. Fixes that would need the vehicle to
  travel faster than `MAX_SPEED_MS` to reach both of their neighbours are
  dropped; the frame is then placed by interpolating between the fixes either
  side, like any frame whose text could not be read at all.
* The text is refreshed once a second, so a position can be up to a second old:
  23 m at 84 km/h. That is the camera's resolution, not this module's.
* Hemisphere letters matter. ``S12.03`` is ``-12.03``; a pattern that ignored
  the letter would put Angola in the Sahara.
"""
from __future__ import annotations

import argparse
import math
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

from smartroad.survey.embedded_gps import Fix, GpsTrack

#: Fraction of the frame height searched for the text strip, at each edge.
STRIP_FRACTION = 0.10

#: Faster than this between two fixes is a misread, not a vehicle (250 km/h).
MAX_SPEED_MS = 70.0

#: A coordinate needs this many decimals: fewer is a speed, a time, or noise.
_DEC = r"\d{4,}"

_NUM_LAT = rf"\d{{1,2}}\.{_DEC}"
_NUM_LON = rf"\d{{1,3}}\.{_DEC}"
_SEP = r"[\s.,;:/|_]*"

#: The patterns cameras use, most specific first. Each yields
#: (lat hemisphere, lat, lon hemisphere, lon) by group name.
_PATTERNS = [
    # S12.035136 E13.955326   N:41.3111 E:69.2797
    re.compile(rf"(?P<ns>[NS]){_SEP}(?P<lat>{_NUM_LAT}){_SEP}"
               rf"(?P<ew>[EW]){_SEP}(?P<lon>{_NUM_LON})"),
    # E13.955326 S12.035136 (longitude first)
    re.compile(rf"(?P<ew>[EW]){_SEP}(?P<lon>{_NUM_LON}){_SEP}"
               rf"(?P<ns>[NS]){_SEP}(?P<lat>{_NUM_LAT})"),
    # 12.035136S 13.955326E   12.035136°S, 13.955326°E
    re.compile(rf"(?P<lat>{_NUM_LAT})\s*°?\s*(?P<ns>[NS]){_SEP}"
               rf"(?P<lon>{_NUM_LON})\s*°?\s*(?P<ew>[EW])"),
    # LAT: -12.035136 LON: 13.955326
    re.compile(rf"LAT\w*{_SEP}(?P<lat>-?{_NUM_LAT}){_SEP}"
               rf"LON\w*{_SEP}(?P<lon>-?{_NUM_LON})", re.I),
    # -12.035136, 13.955326 (signed decimals; five places, so a pair of
    # readings that happen to sit together is not mistaken for one)
    re.compile(r"(?<![\d.])(?P<lat>-?\d{1,2}\.\d{5,})\s*,\s*(?P<lon>-?\d{1,3}\.\d{5,})"),
]


def parse_overlay_text(text: str) -> tuple[float, float] | None:
    """(lat, lon) in signed degrees from a line of overlay text, or None."""
    for pattern in _PATTERNS:
        m = pattern.search(text)
        if not m:
            continue
        g = m.groupdict()
        lat, lon = float(g["lat"]), float(g["lon"])
        if g.get("ns") == "S":
            lat = -abs(lat)
        if g.get("ew") == "W":
            lon = -abs(lon)
        if -90 <= lat <= 90 and -180 <= lon <= 180 and (lat, lon) != (0.0, 0.0):
            return lat, lon
    return None


def available() -> bool:
    try:
        import rapidocr_onnxruntime  # noqa: F401
    except ImportError:
        return False
    return True


INSTALL_HINT = "pip install rapidocr_onnxruntime"


class OverlayReader:
    """OCR for the coordinate strip, remembering which edge the text is on.

    The first frame is searched at both edges; once one has given a fix, only
    that edge is read, which halves the cost. Five failures there in a row --
    the text moved, or the camera was changed -- and both are searched again.
    """

    def __init__(self) -> None:
        if not available():
            raise RuntimeError(f"reading GPS from the picture needs OCR: {INSTALL_HINT}")
        from rapidocr_onnxruntime import RapidOCR

        self._engine = RapidOCR()
        self._edge: str | None = None
        self._misses = 0

    def _text(self, image, edge: str) -> str:
        import numpy as np

        w, h = image.size
        strip = round(h * STRIP_FRACTION)
        box = (0, h - strip, w, h) if edge == "bottom" else (0, 0, w, strip)
        result, _ = self._engine(np.asarray(image.crop(box).convert("RGB")))
        return " ".join(r[1] for r in (result or []))

    def read(self, image) -> tuple[float, float] | None:
        """(lat, lon) from one PIL image, or None if no coordinates are legible."""
        edges = [self._edge] if self._edge else ["bottom", "top"]
        for edge in edges:
            found = parse_overlay_text(self._text(image, edge))
            if found:
                self._edge, self._misses = edge, 0
                return found
        if self._edge:
            self._misses += 1
            if self._misses >= 5:
                self._edge, self._misses = None, 0
        return None


def _distance_m(a: Fix, b: Fix) -> float:
    p1, p2 = math.radians(a.lat), math.radians(b.lat)
    dl = math.radians(b.lon - a.lon)
    h = (math.sin((p2 - p1) / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2)
    return 2 * 6_371_000.0 * math.asin(math.sqrt(min(1.0, h)))


def _too_fast(a: Fix, b: Fix) -> bool:
    dt = abs(b.t_s - a.t_s)
    # Two fixes in the same displayed second can differ by one refresh.
    return _distance_m(a, b) > MAX_SPEED_MS * max(dt, 1.0)


def drop_misreads(fixes: Sequence[Fix]) -> list[Fix]:
    """Drop fixes the vehicle could not have reached from their neighbours.

    A fix is a misread when it is too far from *every* neighbour it has; one
    good neighbour is enough to keep it, so a real fast stretch survives.
    """
    fixes = sorted(fixes, key=lambda f: f.t_s)
    kept = []
    for i, f in enumerate(fixes):
        neighbours = [fixes[j] for j in (i - 1, i + 1) if 0 <= j < len(fixes)]
        if neighbours and all(_too_fast(f, n) for n in neighbours):
            continue
        kept.append(f)
    return kept


def track_from_overlay(fixes: Iterable[Fix], frames_read: int) -> GpsTrack | None:
    """A track from per-frame OCR fixes, misreads removed."""
    raw = list(fixes)
    good = drop_misreads(raw)
    if not good:
        return None
    dropped = len(raw) - len(good)
    source = (f"read from the picture by OCR, {len(good)} of {frames_read} frames"
              + (f" ({dropped} misread{'s' if dropped != 1 else ''} dropped)"
                 if dropped else ""))
    return GpsTrack(tuple(good), source)


# ───────────────────────────────────────────── the script

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}


@dataclass
class _Row:
    source: str
    t_s: float | None
    lat: float | None
    lon: float | None


def _rows(paths: Sequence[Path], every_s: float, reader: OverlayReader):
    from PIL import Image

    from smartroad.survey.video import iter_frames

    for path in paths:
        if path.suffix.lower() in IMAGE_SUFFIXES:
            with Image.open(path) as im:
                found = reader.read(im.convert("RGB"))
            yield _Row(path.name, None, *(found or (None, None)))
            continue
        for t, image in iter_frames(path, every_s=every_s):
            found = reader.read(image)
            yield _Row(path.name, t, *(found or (None, None)))


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="python -m smartroad.survey.overlay_gps",
        description="Read the GPS coordinates a dashcam printed on its frames.")
    ap.add_argument("inputs", nargs="+", type=Path, help="videos and/or images")
    ap.add_argument("--every-s", type=float, default=1.0,
                    help="seconds between frames read from a video (default 1)")
    ap.add_argument("--csv", type=Path, help="also write the fixes to this CSV file")
    args = ap.parse_args(argv)

    if not available():
        print(f"OCR is not installed: {INSTALL_HINT}", file=sys.stderr)
        return 2
    missing = [p for p in args.inputs if not p.is_file()]
    if missing:
        ap.error("no such file: " + ", ".join(map(str, missing)))

    reader = OverlayReader()
    rows = []
    print(f"{'file':<32} {'t (s)':>7} {'latitude':>12} {'longitude':>12}")
    for row in _rows(args.inputs, args.every_s, reader):
        rows.append(row)
        t = f"{row.t_s:7.1f}" if row.t_s is not None else " " * 7
        where = (f"{row.lat:12.6f} {row.lon:12.6f}" if row.lat is not None
                 else f"{'not legible':>25}")
        print(f"{row.source[:32]:<32} {t} {where}", flush=True)

    if args.csv:
        import csv

        with args.csv.open("w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["file", "t_s", "latitude", "longitude"])
            for r in rows:
                w.writerow([r.source, r.t_s, r.lat, r.lon])
        print(f"wrote {args.csv}")
    read = sum(1 for r in rows if r.lat is not None)
    print(f"{read} of {len(rows)} frames had legible coordinates")
    return 0 if read else 1


if __name__ == "__main__":
    raise SystemExit(main())
