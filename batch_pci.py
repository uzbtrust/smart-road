"""Grade a batch of drive videos through ASTM D6433 and write the scores to Excel.

    python batch_pci.py videos/                        # every video in a folder
    python batch_pci.py videos/ -r -o survey.xlsx      # ... and its subfolders
    python batch_pci.py a.mp4 b.MOV "drives/*.mp4"     # files and patterns
    python batch_pci.py --help                         # every setting

This is the app's *Drive video* mode without the app. Each clip is sampled
every `--every-s` seconds, each sample is detected and graded exactly as the
app does it -- same frame decoding, same detector call, same camera, same ASTM
arithmetic -- and the scores go into one workbook instead of onto the screen.

The defaults are the app's sidebar defaults with one exception. The app stops
at 15 frames a clip (its *Max frames* slider) because it is interactive; a
batch grades the whole clip unless told otherwise. `--max-frames 15` gives the
app's numbers frame for frame, which is how to check this tool against the app
on a clip of your own.

The workbook
------------
Summary     one row per video: mean, median, worst and best PCI, the mean if
            every distress were low or high severity, the share of frames in
            each ASTM band, and the error for any clip that could not be read
Per second  one row per second of footage (only with --per-second)
Frames      one row per sampled frame: PCI at the chosen severity and at all
            three, the main distress, the deduct chain, boxes, surface measured
Distresses  one row per distress per frame: boxes, quantity, density, deduct
Detections  one row per detected box (only with --detections)
Settings    every setting the scores depend on, and what the numbers are not

The workbook is saved as the batch goes -- after every video while it is
small -- so an interrupted batch keeps what it finished; Ctrl+C stops after
saving. A clip that cannot be read gets an error row and the batch moves on.
"""
from __future__ import annotations

import argparse
import glob
import importlib.metadata
import io
import os
import platform
import re
import shlex
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterable, Iterator, Sequence

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:                     # runnable from any directory
    sys.path.insert(0, str(ROOT))

from smartroad.detect.tiled import (Detection, detect_tiled,  # noqa: E402
                                    rgb_to_bgr, road_roi)
from smartroad.geometry.ipm import Camera  # noqa: E402
from smartroad.pci.astm import number_of  # noqa: E402
from smartroad.pci.engine import RATING_SCALE, deduct_value  # noqa: E402
from smartroad.pci.from_detections import (CLASS_TO_DISTRESS,  # noqa: E402
                                           FrameAssessment, Quantity,
                                           inspected_area_m2,
                                           pci_from_detections)
from smartroad.pci.from_survey import imperial_density  # noqa: E402
from smartroad.survey.sections import effective_band  # noqa: E402
from smartroad.survey.video import (VideoInfo, frame_times,  # noqa: E402
                                    iter_frames, probe_video)

# ───────────────────────────────────────────────────── what the app fixes
# Every constant here is a value app.py uses. They are restated rather than
# imported because app.py is a Streamlit script: importing it runs the page.

HF_REPO = "uzbtrust/smart-road-pci-yolo11"
WEIGHTS = "yolo11l_640_best.pt"

#: Only the first eight heads were trained; see the model card.
TRAINED_CLASSES = tuple(range(8))

#: The app grades every frame from 3 m out (`near_m=3.0` in its `grade`).
NEAR_M = 3.0

#: The app samples a clip at this long side (`extract_frames(long_side=1280)`).
APP_LONG_SIDE = 1280

#: `extract_frames` writes each sample as a JPEG at this quality, and the app
#: detects on the JPEG it reads back rather than on the decoded video frame.
APP_JPEG_QUALITY = 92

SEVERITIES = ("low", "medium", "high")

COLOURS = {
    "longitudinal_transverse_crack": "#ff6b6b",
    "alligator_crack": "#4dabf7",
    "block_crack": "#ffd43b",
    "patching": "#69db7c",
    "pothole": "#f783ac",
    "weathering_raveling": "#ffa94d",
    "lane_shoulder_drop_off": "#b197fc",
    "marking_manhole": "#868e96",
}
PRETTY = {
    "longitudinal_transverse_crack": "Longitudinal / transverse crack",
    "alligator_crack": "Alligator crack",
    "block_crack": "Block crack",
    "patching": "Patching",
    "pothole": "Pothole",
    "weathering_raveling": "Weathering / raveling",
    "lane_shoulder_drop_off": "Lane / shoulder drop-off",
    "marking_manhole": "Marking / manhole",
}

# ───────────────────────────────────────────────────── batch-only constants

VIDEO_SUFFIXES = frozenset({".mp4", ".mov", ".m4v", ".avi", ".mkv", ".mts",
                            ".m2ts", ".3gp", ".webm"})

#: ASTM distress key -> the app's name for it.
DISTRESS_PRETTY = {astm: PRETTY[cls] for cls, astm in CLASS_TO_DISTRESS.items()}

UNIT_LABEL = {"area": "m²", "linear": "m", "count": "count"}

#: ASTM bands, best first, as the engine's rating scale lists them.
BANDS = tuple(label for _, label, _ in RATING_SCALE)


@dataclass(frozen=True)
class Settings:
    """Everything a score depends on. Defaults are the app's sidebar defaults."""

    every_s: float = 1.0
    max_frames: int = 0               # 0: the whole clip
    long_side: int = APP_LONG_SIDE    # 0: the clip's own resolution
    severity: str = "medium"
    conf: float = 0.25
    tiled: bool = True
    overlap: float = 0.20
    sky: float = 0.45
    height_m: float = 1.70
    focal_35mm: float = 25.0
    horizon: float = 0.139
    far_m: float = 15.0

    def problems(self) -> list[str]:
        """What is wrong with these settings, in the words of their options."""
        out = []
        if self.every_s <= 0:
            out.append("--every-s must be positive")
        if self.max_frames < 0:
            out.append("--max-frames must be 0 (whole clip) or more")
        if self.long_side and self.long_side < 64:
            out.append("--long-side must be 0 (native) or at least 64 px")
        if self.severity not in SEVERITIES:
            out.append(f"--severity must be one of {', '.join(SEVERITIES)}")
        if not 0 < self.conf < 1:
            out.append("--conf must be between 0 and 1")
        if not 0 <= self.overlap < 1:
            out.append("--overlap must be at least 0 and below 1")
        if not 0 <= self.sky < 1:
            out.append("--sky must be at least 0 and below 1")
        if self.height_m <= 0:
            out.append("--height-m must be positive")
        if self.focal_35mm <= 0:
            out.append("--focal-35mm must be positive")
        if not 0 <= self.horizon < 1:
            out.append("--horizon must be a fraction of the frame height, 0 to 1")
        if self.far_m <= NEAR_M:
            out.append(f"--far-m must be beyond the {NEAR_M:g} m the app measures from")
        return out


# ───────────────────────────────────────────────────── the app's pipeline

def load_model(weights: Path | None = None):
    """The app's `load_model`: models/ first, then the Hugging Face cache."""
    from ultralytics import YOLO

    if weights is None:
        local = ROOT / "models" / WEIGHTS
        if local.exists():
            weights = local
        else:
            from huggingface_hub import hf_hub_download
            weights = Path(hf_hub_download(HF_REPO, WEIGHTS))
    return YOLO(str(weights)), Path(weights)


def pick_device() -> str:
    """The app's `pick_device`."""
    import torch

    if torch.cuda.is_available():
        return "cuda"
    return "mps" if torch.backends.mps.is_available() else "cpu"


def detect(model, frame: np.ndarray, s: Settings, device: str | None) -> list[Detection]:
    """The app's `_detect`, taking its settings as arguments instead of sliders."""
    h, w = frame.shape[:2]
    roi = road_roi(w, h, top_fraction=s.sky)
    if s.tiled:
        return detect_tiled(model, frame, tile=640, overlap=s.overlap, roi=roi,
                            conf=s.conf, classes=TRAINED_CLASSES, device=device)
    # frame is RGB; Ultralytics reads a numpy array as BGR.
    res = model.predict(rgb_to_bgr(frame), imgsz=640, conf=s.conf, device=device,
                        classes=list(TRAINED_CLASSES), verbose=False)[0]
    out = [Detection(*map(float, b.xyxy[0].tolist()), float(b.conf), int(b.cls))
           for b in res.boxes]
    return [d for d in out if d.y2 >= roi[1]]


def make_camera(width: int, height: int, s: Settings) -> Camera:
    """The camera the app's `grade` builds for a frame of this size."""
    return Camera.create(width=width, height=height, height_m=s.height_m,
                         focal_35mm=s.focal_35mm, horizon_row=s.horizon * height)


def frame_geometry(width: int, height: int, s: Settings):
    """Camera and searched region for a frame size, refusing one with no road.

    `pci_from_detections` would refuse too, but only after the detector had
    run; checking first means a wrong horizon fails a clip in a second rather
    than after an hour of inference.
    """
    camera = make_camera(width, height, s)
    roi = road_roi(width, height, top_fraction=s.sky)
    if inspected_area_m2(camera, roi, NEAR_M, s.far_m) <= 0:
        raise ValueError(
            f"at {width}x{height} the camera settings leave no road to measure "
            f"(height {s.height_m:g} m, focal {s.focal_35mm:g} mm, horizon "
            f"{s.horizon:g}, sky cut-off {s.sky:g}); check --horizon and --sky")
    return camera, roi


def grade_frame(dets: Sequence[Detection], camera: Camera, roi, names: dict[int, str],
                s: Settings) -> dict[str, FrameAssessment]:
    """The app's `grade`, at all three severities; `s.severity` is the score.

    The detector has no severity head, so the other two are the range the
    answer really occupies -- the app shows the same three on a photograph.
    Only the ASTM arithmetic runs three times, never the detector.
    """
    return {sev: pci_from_detections(dets, camera, severity=sev, class_names=names,
                                     roi=roi, near_m=NEAR_M, far_m=s.far_m)
            for sev in SEVERITIES}


def sampled_frames(path: Path, s: Settings) -> Iterator[tuple[float, Image.Image]]:
    """The frames the app grades, decoded the way the app decodes them.

    The app has `extract_frames` write each sample to a quality-92 JPEG and
    detects on the JPEG it reads back. The same round trip is made here, in
    memory: skipping it would move a borderline box across the confidence
    threshold now and then, and the two tools would disagree about one clip
    for no reason anyone could see.
    """
    for t, image in iter_frames(path, every_s=s.every_s,
                                max_frames=s.max_frames or None,
                                long_side=s.long_side or None):
        buf = io.BytesIO()
        image.save(buf, format="JPEG", quality=APP_JPEG_QUALITY)
        yield t, Image.open(io.BytesIO(buf.getvalue())).convert("RGB")


def deducts_by_distress(a: FrameAssessment) -> list[tuple[Quantity, float]]:
    """Each distress with the deduct value it produced, largest first.

    `pci_from_quantities` keeps the deduct values but not which distress each
    came from; this recomputes the pairing with the same two calls it makes.
    """
    # Pothole amounts are already equivalent counts (quantify() converted them),
    # so the density must not be divided by 0.5 m2 a second time.
    pairs = [(q, deduct_value(q.distress, q.severity,
                              imperial_density(q.density_pct, q.distress,
                                               potholes_as_area=False)))
             for q in a.quantities if q.density_pct > 0]
    return sorted(pairs, key=lambda p: p[1], reverse=True)


def rating_of(pci: float) -> tuple[str, str]:
    """ASTM band and colour for a score; the app's `band`."""
    return next((label, colour) for lo, label, colour in RATING_SCALE if pci >= lo)


def ink_for(colour: str) -> str:
    """The app's `ink_for`: dark text on the pale bands, white on the dark."""
    r, g, b = (int(colour[i:i + 2], 16) / 255 for i in (1, 3, 5))
    return "#0b0b0c" if 0.2126 * r + 0.7152 * g + 0.0722 * b > 0.45 else "#ffffff"


# ───────────────────────────────────────────────────── results

@dataclass
class FrameResult:
    index: int                                   # 1-based, in sampling order
    t_s: float
    size: tuple[int, int]                        # (width, height) as graded
    detections: list[Detection]
    graded: dict[str, FrameAssessment]           # by severity
    image: Path | None = None                    # annotated JPEG, if saved


@dataclass
class VideoResult:
    path: Path
    label: str
    status: str = "Not started"
    info: VideoInfo | None = None
    frames: list[FrameResult] = field(default_factory=list)
    band_m: tuple[float, float] | None = None    # what the frames really measure
    seconds: float = 0.0

    @property
    def ok(self) -> bool:
        return self.status == "OK"


@dataclass(frozen=True)
class VideoStats:
    frames: int
    mean: float
    median: float
    worst: FrameResult
    best: float
    mean_at: dict[str, float]                    # mean PCI by severity
    band_share: dict[str, float]                 # fraction of frames per band
    boxes: int


def video_stats(v: VideoResult, severity: str) -> VideoStats | None:
    """The app's three video figures -- frames, mean, worst -- and a few more.

    The mean is the plain mean of the frame scores, which is what the app
    reports. It is not a section PCI: frames overlap or leave gaps between
    them, and PCI is not linear in density. See the Settings sheet.
    """
    if not v.frames:
        return None
    scores = [f.graded[severity].pci for f in v.frames]
    n = len(scores)
    counts = dict.fromkeys(BANDS, 0)
    for f in v.frames:
        counts[f.graded[severity].rating] += 1
    ordered = sorted(scores)
    median = (ordered[n // 2] if n % 2 else (ordered[n // 2 - 1] + ordered[n // 2]) / 2)
    return VideoStats(
        frames=n,
        mean=sum(scores) / n,                    # as the app computes it
        median=median,
        # min() keeps the first of equal scores, as the app's own min() does.
        worst=min(v.frames, key=lambda f: f.graded[severity].pci),
        best=max(scores),
        mean_at={sev: sum(f.graded[sev].pci for f in v.frames) / n for sev in SEVERITIES},
        band_share={b: counts[b] / n for b in BANDS},
        boxes=sum(len(f.detections) for f in v.frames),
    )


# ───────────────────────────────────────────────────── annotated frames

def _font(size: int):
    try:
        return ImageFont.load_default(size=size)
    except TypeError:                                    # Pillow < 10.1
        return ImageFont.load_default()


def annotate(image: Image.Image, dets: Sequence[Detection], names: dict[int, str],
             roi, caption: str) -> Image.Image:
    """The app's `draw`, plus a label per box and a caption.

    The app has a legend beside the picture; a JPEG on its own does not, so
    each box carries its class and confidence instead.
    """
    canvas = image.copy()
    d = ImageDraw.Draw(canvas, "RGBA")
    w = max(2, canvas.width // 480)
    d.rectangle(roi, outline=(0, 210, 106, 190), width=w)
    size = max(12, canvas.width // 90)
    font = _font(size)
    for det in dets:
        name = names.get(det.class_id, "")
        colour = COLOURS.get(name, "#ffffff")
        d.rectangle(det.as_xyxy(), outline=colour, width=w + 1)
        at = (det.x1 + 2, max(0.0, det.y1 - size - 4))
        label = f"{PRETTY.get(name, name)} {det.confidence:.2f}"
        d.rectangle(d.textbbox(at, label, font=font), fill=(0, 0, 0, 150))
        d.text(at, label, fill=colour, font=font)
    big = _font(max(14, canvas.width // 55))
    box = d.textbbox((0, 0), caption, font=big)
    d.rectangle((0, 0, box[2] + 16, box[3] + 12), fill=(0, 0, 0, 170))
    d.text((8, 6), caption, fill="#ffffff", font=big)
    return canvas


def _safe(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", text).strip("._") or "video"


def save_annotated(frames_dir: Path, video_no: int, v: VideoResult, fr: FrameResult,
                   image: Image.Image, names: dict[int, str], s: Settings) -> Path:
    a = fr.graded[s.severity]
    folder = frames_dir / f"{video_no:03d}_{_safe(Path(v.label).stem)}"
    folder.mkdir(parents=True, exist_ok=True)
    dst = folder / f"t{fr.t_s:07.1f}s_pci{a.pci:03.0f}.jpg"
    roi = road_roi(*fr.size, top_fraction=s.sky)
    caption = f"{v.label}  {fr.t_s:.1f} s  PCI {a.pci:.0f} {a.rating}"
    annotate(image, fr.detections, names, roi, caption).save(dst, quality=90)
    return dst


# ───────────────────────────────────────────────────── grading a clip

def grade_video(v: VideoResult, model, names: dict[int, str], s: Settings,
                device: str | None, *, video_no: int = 1, save_frames: str = "none",
                frames_dir: Path | None = None,
                progress: Callable[[int], None] | None = None) -> VideoResult:
    """Sample, detect and grade one clip, filling in `v` as it goes.

    Filled in place rather than returned at the end, so that a Ctrl+C half way
    through still leaves the frames already graded where the caller can save
    them. Any other failure becomes the clip's status and the batch goes on.
    """
    started = time.perf_counter()
    worst: tuple[float, FrameResult, Image.Image] | None = None
    geometry: dict[tuple[int, int], tuple] = {}
    try:
        v.info = probe_video(v.path)
        for t, image in sampled_frames(v.path, s):
            frame = np.array(image)
            h, w = frame.shape[:2]
            if (w, h) not in geometry:
                geometry[(w, h)] = frame_geometry(w, h, s)
            camera, roi = geometry[(w, h)]
            if v.band_m is None:
                v.band_m = effective_band(camera, roi, NEAR_M, s.far_m)

            dets = detect(model, frame, s, device)
            fr = FrameResult(len(v.frames) + 1, t, (w, h), dets,
                             grade_frame(dets, camera, roi, names, s))
            pci = fr.graded[s.severity].pci
            if save_frames == "all" and frames_dir:
                fr.image = save_annotated(frames_dir, video_no, v, fr, image, names, s)
            elif save_frames == "worst" and (worst is None or pci < worst[0]):
                worst = (pci, fr, image)
            v.frames.append(fr)
            if progress:
                progress(len(v.frames))

        if not v.frames:
            raise ValueError("no frames could be sampled from this clip")
        if worst is not None and frames_dir:
            worst[1].image = save_annotated(frames_dir, video_no, v, worst[1],
                                            worst[2], names, s)
        v.status = "OK"
    except Exception as exc:          # noqa: BLE001 -- one bad clip must not end a batch
        v.status = f"Error: {type(exc).__name__}: {exc}"[:500]
    finally:
        v.seconds = time.perf_counter() - started
    return v


# ───────────────────────────────────────────────────── finding the videos

def _natural(text: str) -> list:
    """Sort key putting clip2 before clip10."""
    return [int(p) if p.isdigit() else p for p in re.split(r"(\d+)", text.lower())]


def _is_video(p: Path) -> bool:
    # "._clip.mp4" is the resource fork macOS leaves on exFAT cards: a video
    # by name only.
    return p.is_file() and p.suffix.lower() in VIDEO_SUFFIXES and not p.name.startswith("._")


def collect_videos(inputs: Iterable[str], recursive: bool = False
                   ) -> tuple[list[tuple[Path, str]], list[str]]:
    """Expand files, folders and glob patterns into ``(path, label)`` pairs.

    Order is the order given, and natural order inside each folder or pattern;
    a file reached twice is graded once. Labels are what the workbook calls
    each video: the name, or the path within a folder that was searched
    recursively, or the path from here when two videos would share a name.
    Returns the videos and the inputs that matched nothing.
    """
    found: list[tuple[Path, str]] = []
    unmatched: list[str] = []
    seen: set[Path] = set()

    def add(path: Path, label: str) -> None:
        key = path.resolve()
        if key not in seen:
            seen.add(key)
            found.append((path, label))

    for raw in inputs:
        p = Path(raw).expanduser()
        if p.is_dir():
            hits = [q for q in (p.rglob("*") if recursive else p.glob("*")) if _is_video(q)]
            hits.sort(key=lambda q: _natural(q.relative_to(p).as_posix()))
            for q in hits:
                add(q, q.relative_to(p).as_posix())
            if not hits:
                unmatched.append(raw)
        elif p.is_file():
            add(p, p.name)
        else:
            hits = [Path(x) for x in glob.glob(str(p), recursive=True)]
            hits = sorted((q for q in hits if _is_video(q)), key=lambda q: _natural(str(q)))
            for q in hits:
                add(q, q.name)
            if not hits:
                unmatched.append(raw)

    labels = [label for _, label in found]
    if len(set(labels)) < len(labels):
        clash = {x for x in labels if labels.count(x) > 1}
        found = [(path, _relative(path) if label in clash else label)
                 for path, label in found]
    return found, unmatched


def _relative(path: Path) -> str:
    try:
        return Path(os.path.relpath(path)).as_posix()
    except ValueError:                          # another drive, on Windows
        return str(path)


# ───────────────────────────────────────────────────── the workbook
# Written in openpyxl's write-only mode: rows stream to disk instead of being
# held as cell objects, so a batch of many long drives does not run the
# machine out of memory while saving. The price is that every cell has to be
# finished as it is written, so styling travels with the value (`Styled`).

#: Excel stops at this many rows; a longer sheet is cut and says so.
EXCEL_ROWS = 1_048_576

_ILLEGAL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def _clean(value):
    """Text Excel will take: no control characters, never read as a formula."""
    if isinstance(value, str):
        value = _ILLEGAL.sub("", value)
        if value.startswith("="):
            value = " " + value
    return value


def _r(x, digits: int):
    """Round for the sheet. A PCI to a tenth is already finer than its error."""
    return None if x is None else round(float(x), digits)


@dataclass(frozen=True)
class Col:
    header: str
    width: float
    band: str | None = None           # head the column in this ASTM band's colour


@dataclass(frozen=True)
class Styled:
    """A value that needs more than a plain cell."""

    value: object
    band: str | None = None           # fill in this ASTM band's colour
    fmt: str | None = None
    link: str | None = None
    error: bool = False
    bold: bool = False
    wrap: bool = False


class _Styles:
    """Made once per workbook rather than once per cell."""

    def __init__(self):
        from openpyxl.styles import Alignment, Font, PatternFill

        self.head_font = Font(bold=True, color="F7F7F4")
        self.head_fill = PatternFill("solid", fgColor="1A1A19")
        self.head_align = Alignment(wrap_text=True, vertical="center")
        self.bold = Font(bold=True)
        self.error = Font(color="C00000")
        self.link = Font(color="0563C1", underline="single")
        self.wrap = Alignment(wrap_text=True, vertical="top")
        self.band = {label: (PatternFill("solid", fgColor=colour[1:].upper()),
                             Font(color=ink_for(colour)[1:].upper(), bold=True))
                     for _, label, colour in RATING_SCALE}


def _cell(ws, x, row: int, col: int, st: _Styles):
    from openpyxl.cell import WriteOnlyCell

    if not isinstance(x, Styled):
        return _clean(x)
    c = WriteOnlyCell(ws, value=_clean(x.value))
    # A hyperlink records its cell's address when it is set, and a write-only
    # cell has no address until it is written: place it first.
    c.row, c.column = row, col
    if x.band:
        c.fill, c.font = st.band[x.band]
    if x.fmt:
        c.number_format = x.fmt
    if x.link:
        c.hyperlink, c.font = x.link, st.link
    if x.error:
        c.font = st.error
    if x.bold:
        c.font = st.bold
    if x.wrap:
        c.alignment = st.wrap
    return c


def _sheet(wb, title: str, cols: Sequence[Col], rows: Iterable[Sequence], st: _Styles, *,
           freeze: str, filters: bool = True) -> int:
    """Stream one table into a new sheet. Returns how many rows did not fit."""
    from openpyxl.cell import WriteOnlyCell
    from openpyxl.utils import get_column_letter

    ws = wb.create_sheet(title)
    for i, c in enumerate(cols, 1):
        ws.column_dimensions[get_column_letter(i)].width = c.width
    ws.row_dimensions[1].height = 46
    ws.freeze_panes = freeze

    head = []
    for c in cols:
        h = WriteOnlyCell(ws, value=c.header)
        h.fill, h.font = st.band[c.band] if c.band else (st.head_fill, st.head_font)
        h.alignment = st.head_align
        head.append(h)
    ws.append(head)

    written, dropped = 0, 0
    rows = iter(rows)
    for row in rows:
        if written == EXCEL_ROWS - 2:
            dropped = 1 + sum(1 for _ in rows)
            ws.append([_cell(ws, Styled(f"{dropped:,} more rows not written: Excel stops "
                                        f"at {EXCEL_ROWS:,} rows", error=True),
                             written + 2, 1, st)])
            break
        r = written + 2
        ws.append([_cell(ws, x, r, i, st) for i, x in enumerate(row, 1)])
        written += 1
    if filters and written:
        ws.auto_filter.ref = f"A1:{get_column_letter(len(cols))}{written + 1}"
    return dropped


def _link(target: Path | None, book: Path) -> Styled | None:
    if target is None:
        return None
    try:
        rel = Path(os.path.relpath(target, book.parent)).as_posix()
    except ValueError:                          # another drive, on Windows
        rel = target.as_posix()
    return Styled("open", link=rel)


def _coloured(pci: float, rating: str) -> Styled:
    return Styled(_r(pci, 1), band=rating, fmt="0.0")


SUMMARY = [
    Col("Video", 34), Col("Status", 12), Col("Mean PCI", 9), Col("Rating", 13),
    Col("Median PCI", 9), Col("Worst PCI", 9), Col("Worst at (s)", 9), Col("Best PCI", 9),
    Col("Mean PCI if all low", 11), Col("Mean PCI if all high", 11),
    Col("Frames graded", 9),
    *[Col(f"% {b}", 12, band=b) for b in BANDS],
    Col("Boxes", 8), Col("Measured band (m)", 11), Col("Duration (s)", 10),
    Col("Source", 17), Col("Graded at", 11), Col("Processing (s)", 11),
    Col("Worst frame image", 12), Col("Path", 60),
]
_S = {c.header: i for i, c in enumerate(SUMMARY, 1)}

FRAMES = [
    Col("Video", 34), Col("Frame", 7), Col("t (s)", 8), Col("PCI", 7), Col("Rating", 13),
    Col("PCI if low", 8), Col("PCI if medium", 9), Col("PCI if high", 8),
    Col("Main distress", 28), Col("Max CDV", 8), Col("q", 5), Col("Deduct values", 30),
    Col("Boxes", 7), Col("Boxes graded", 8), Col("On tile seams", 8),
    Col("Surface measured (m²)", 12), Col("Not graded", 46), Col("Image", 8),
]
_F = {c.header: i for i, c in enumerate(FRAMES, 1)}

DISTRESSES = [
    Col("Video", 34), Col("Frame", 7), Col("t (s)", 8), Col("Distress", 28),
    Col("ASTM no.", 7), Col("Severity", 9), Col("Boxes", 7), Col("Quantity", 10),
    Col("Unit", 7), Col("Density (%)", 10), Col("Deduct value", 9),
]

DETECTIONS = [
    Col("Video", 34), Col("Frame", 7), Col("t (s)", 8), Col("Class", 28),
    Col("Graded as", 30), Col("Confidence", 10), Col("x1", 7), Col("y1", 7),
    Col("x2", 7), Col("y2", 7), Col("On tile seam", 8),
]

PER_SECOND = [
    Col("Video", 34), Col("Second", 8), Col("Covers (s)", 10), Col("Sampled at (s)", 9),
    Col("PCI", 7), Col("Rating", 13), Col("PCI if low", 8), Col("PCI if medium", 9),
    Col("PCI if high", 8), Col("Main distress", 28), Col("Boxes", 7), Col("Note", 40),
]

SETTINGS = [Col("Setting", 36), Col("Value", 30), Col("Option", 14), Col("Note", 90)]


def _not_graded(excluded: dict[str, int]) -> str:
    return "; ".join(f"{PRETTY.get(k, k)} ×{n}" for k, n in excluded.items())


def _summary_rows(results: Sequence[VideoResult], s: Settings, book: Path):
    for v in results:
        st = video_stats(v, s.severity)
        info = v.info
        if st:
            mean_band = rating_of(st.mean)[0]
            worst = st.worst.graded[s.severity]
            scores = [_coloured(st.mean, mean_band), Styled(mean_band, band=mean_band),
                      _r(st.median, 1), _coloured(worst.pci, worst.rating), st.worst.t_s,
                      _r(st.best, 1), _r(st.mean_at["low"], 1), _r(st.mean_at["high"], 1),
                      st.frames, *[_r(100 * st.band_share[b], 1) for b in BANDS], st.boxes]
        else:
            scores = [None] * (9 + len(BANDS) + 1)
        yield [v.label,
               Styled(v.status, error=True) if v.status.startswith("Error") else v.status,
               *scores,
               f"{v.band_m[0]:.1f}–{v.band_m[1]:.1f}" if v.band_m else None,
               _r(info.duration_s, 1) if info else None,
               f"{info.width}x{info.height}, {info.fps:.0f} fps" if info else None,
               f"{v.frames[0].size[0]}x{v.frames[0].size[1]}" if v.frames else None,
               _r(v.seconds, 0),
               _link(st.worst.image, book) if st else None,
               str(v.path.resolve())]


def _frame_rows(results: Sequence[VideoResult], s: Settings, book: Path):
    for v in results:
        for f in v.frames:
            a = f.graded[s.severity]
            pairs = deducts_by_distress(a)
            yield [v.label, f.index, f.t_s, _coloured(a.pci, a.rating),
                   Styled(a.rating, band=a.rating),
                   _r(f.graded["low"].pci, 1), _r(f.graded["medium"].pci, 1),
                   _r(f.graded["high"].pci, 1),
                   DISTRESS_PRETTY.get(pairs[0][0].distress, pairs[0][0].distress)
                   if pairs else None,
                   _r(a.max_cdv, 1), a.q,
                   ", ".join(f"{d:.1f}" for d in a.deduct_values) or None,
                   len(f.detections), sum(q.detections for q in a.quantities),
                   sum(1 for d in f.detections if d.on_seam), _r(a.inspected_area_m2, 2),
                   _not_graded(a.excluded) or None, _link(f.image, book)]


def _per_second_rows(results: Sequence[VideoResult], s: Settings):
    """One row per whole second of footage, scored by the frame sampled in it.

    Sampling starts half an interval in, so at one frame a second the frame for
    second k is taken at k + 0.5 s and every second has exactly one score. At a
    coarser interval the seconds without a sample are listed and left empty
    rather than filled in: nobody measured them. The list ends at the last
    second sampled, so a clip's short tail -- or the rest of a clip cut off by
    --max-frames -- is not listed as a gap.
    """
    for v in results:
        if not v.frames:
            continue
        by_second: dict[int, FrameResult] = {}
        for f in v.frames:
            by_second.setdefault(int(f.t_s), f)
        for sec in range(max(by_second) + 1):
            f = by_second.get(sec)
            covers = f"{sec}–{sec + 1}"
            if f is None:
                yield [v.label, sec, covers, None, None, None, None, None, None, None,
                       None, "not sampled at this interval"]
                continue
            a = f.graded[s.severity]
            pairs = deducts_by_distress(a)
            yield [v.label, sec, covers, f.t_s, _coloured(a.pci, a.rating),
                   Styled(a.rating, band=a.rating),
                   _r(f.graded["low"].pci, 1), _r(f.graded["medium"].pci, 1),
                   _r(f.graded["high"].pci, 1),
                   DISTRESS_PRETTY.get(pairs[0][0].distress, pairs[0][0].distress)
                   if pairs else None,
                   len(f.detections), None]


def _distress_rows(results: Sequence[VideoResult], s: Settings):
    for v in results:
        for f in v.frames:
            for q, dv in deducts_by_distress(f.graded[s.severity]):
                yield [v.label, f.index, f.t_s, DISTRESS_PRETTY.get(q.distress, q.distress),
                       number_of(q.distress), q.severity, q.detections, _r(q.amount, 3),
                       UNIT_LABEL[q.unit], _r(q.density_pct, 4), _r(dv, 1)]


def _detection_rows(results: Sequence[VideoResult], names: dict[int, str]):
    for v in results:
        for f in v.frames:
            for d in f.detections:
                name = names.get(d.class_id, str(d.class_id))
                astm = CLASS_TO_DISTRESS.get(name)
                yield [v.label, f.index, f.t_s, PRETTY.get(name, name),
                       f"{DISTRESS_PRETTY[astm]} (ASTM {number_of(astm)})" if astm
                       else "not graded: not a pavement distress",
                       _r(d.confidence, 3), _r(d.x1, 1), _r(d.y1, 1), _r(d.x2, 1),
                       _r(d.y2, 1), "yes" if d.on_seam else None]


def _settings_rows(s: Settings, meta: dict, results: Sequence[VideoResult]):
    ok = sum(1 for v in results if v.ok)
    failed = sum(1 for v in results if v.status.startswith("Error"))
    other = len(results) - ok - failed
    videos = f"{len(results)}: {ok} graded" + (f", {failed} failed" if failed else "") \
        + (f", {other} not finished" if other else "")
    return [
        ("RUN", None, None, None),
        ("Date", meta.get("date"), None, None),
        ("Videos", videos, None, None),
        ("Command", meta.get("command"), None, "Run it again to repeat this batch."),
        ("smart-road", meta.get("commit"), None, "Commit of the checkout that graded it."),
        ("Weights", meta.get("weights"), "--weights", None),
        ("Device", meta.get("device"), "--device", None),
        ("Python · ultralytics · torch", meta.get("versions"), None, None),
        (None, None, None, None),
        ("SAMPLING", None, None, None),
        ("Sample every (s)", s.every_s, "--every-s", "App: 'Sample every (s)'."),
        ("Max frames per video", s.max_frames or "all", "--max-frames",
         "The app stops at 15 by default; 15 here reproduces its numbers."),
        ("Frame long side (px)", s.long_side or "native", "--long-side",
         "The app samples clips at 1280 px."),
        ("Frame decoding", f"JPEG round trip at quality {APP_JPEG_QUALITY}", None,
         "As the app: each sample is encoded and read back as a JPEG before "
         "detection, so both see identical pixels."),
        (None, None, None, None),
        ("DETECTION", None, None, None),
        ("Detection confidence", s.conf, "--conf", "App: 'Detection confidence'."),
        ("Tiled inference", "on" if s.tiled else "off", "--no-tiled", "App: 'Tiled inference'."),
        ("Tile overlap", s.overlap, "--overlap", "App: 'Tile overlap'."),
        ("Sky cut-off", s.sky, "--sky", "App: 'Sky cut-off'. Fraction of frame height ignored."),
        ("Classes", "0–7", None, "Heads 8 and 9 of the checkpoint are untrained and dropped."),
        (None, None, None, None),
        ("CAMERA GEOMETRY", None, None, None),
        ("Camera height above road (m)", s.height_m, "--height-m",
         "Area goes with height²: 10 % wrong here is 21 % wrong in every m²."),
        ("Focal length, 35 mm equivalent (mm)", s.focal_35mm, "--focal-35mm",
         "From the camera's EXIF."),
        ("Horizon row (fraction of height)", s.horizon, "--horizon", "Sets the pitch."),
        ("Measure from (m)", NEAR_M, None, "Fixed in the app."),
        ("Measure out to (m)", s.far_m, "--far-m",
         "A request: the sky cut-off usually stops the search sooner. "
         "'Measured band' on the Summary sheet is what each clip really measured."),
        (None, None, None, None),
        ("GRADING", None, None, None),
        ("Severity", s.severity, "--severity",
         "Applied to every detection: the model does not predict severity. "
         "The 'if low' and 'if high' columns are the same detections graded at the "
         "other severities -- the range the answer really occupies."),
        (None, None, None, None),
        ("ASTM D6433 RATING SCALE", None, None, None),
        *[(label, f"{lo:g}–{hi:g}", None, None) for lo, hi, label in _band_ranges()],
        (None, None, None, None),
        ("WHAT THESE NUMBERS ARE NOT", None, None, None),
        ("Not a sample-unit PCI", None, None,
         "ASTM's asphalt sample unit is 232 ± 93 m²; one frame measures far less "
         "(see 'Surface measured' on the Frames sheet). Each frame PCI is a reading "
         "of the road in view, for comparing frames and clips."),
        ("Mean PCI is a plain mean", None, None,
         "It is the mean of the frame scores, exactly as the app reports it. Frames "
         "can overlap or leave road between them unmeasured, and PCI is not linear "
         "in density, so it is not a section PCI. Section grading needs a GPS track "
         "(smartroad/survey/sections.py)."),
        ("Not graded", None, None,
         "Marking / manhole is detected but never graded: it is not a pavement "
         "distress. Boxes outside the measurable band are dropped too."),
        ("Density units", None, None,
         "For cracks (m) and potholes (count) 'Density (%)' is per 100 m² of "
         "surface, as the app shows it; the ASTM curves receive it converted to feet."),
        ("Rounding", None, None,
         "Scores are written to a tenth, densities to 0.0001; the means on the "
         "Summary sheet are taken before rounding."),
    ]


def _settings_sheet_rows(s: Settings, meta: dict, results: Sequence[VideoResult]):
    for name, value, option, note in _settings_rows(s, meta, results):
        heading = bool(name and value is None and option is None and name.isupper())
        band = name if name in BANDS and value is not None else None
        yield [Styled(name, bold=heading, band=band, wrap=True) if name else None,
               *(Styled(x, wrap=True) if x is not None else None
                 for x in (value, option, note))]


def _band_ranges():
    hi = 100.0
    for lo, label, _ in sorted(RATING_SCALE, key=lambda b: b[0], reverse=True):
        yield lo, hi, label
        hi = lo


def write_workbook(path: Path, results: Sequence[VideoResult], s: Settings, meta: dict,
                   names: dict[int, str], *, with_detections: bool = False,
                   per_second: bool = False,
                   warn: Callable[[str], None] | None = None) -> Path:
    """Write the whole workbook to `path`, replacing it only once it is complete."""
    from openpyxl import Workbook

    st = _Styles()
    wb = Workbook(write_only=True)
    sheets = [("Summary", SUMMARY, _summary_rows(results, s, path), "B2"),
              *([("Per second", PER_SECOND, _per_second_rows(results, s), "C2")]
                if per_second else []),
              ("Frames", FRAMES, _frame_rows(results, s, path), "D2"),
              ("Distresses", DISTRESSES, _distress_rows(results, s), "E2")]
    if with_detections:
        sheets.append(("Detections", DETECTIONS, _detection_rows(results, names), "E2"))
    for title, cols, rows, freeze in sheets:
        dropped = _sheet(wb, title, cols, rows, st, freeze=freeze)
        if dropped and warn:
            warn(f"      ! {title}: {dropped:,} rows did not fit in Excel's "
                 f"{EXCEL_ROWS:,}; grade fewer videos per workbook")
    _sheet(wb, "Settings", SETTINGS, _settings_sheet_rows(s, meta, results), st,
           freeze="A2", filters=False)

    tmp = path.with_name(f"~{path.stem}.partial.xlsx")
    try:
        wb.save(tmp)
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    return path


# ───────────────────────────────────────────────────── the batch

def _clock(seconds: float) -> str:
    seconds = int(max(0, seconds))
    h, rest = divmod(seconds, 3600)
    m, s = divmod(rest, 60)
    return f"{h}h{m:02d}m" if h else f"{m}m{s:02d}s"


def _planned_frames(path: Path, s: Settings) -> int:
    try:
        return len(frame_times(probe_video(path), s.every_s, s.max_frames or None))
    except Exception:                 # noqa: BLE001 -- reported when it is graded
        return 0


def run_batch(videos: Sequence[tuple[Path, str]], model, names: dict[int, str],
              s: Settings, device: str | None, out: Path, *, meta: dict,
              save_frames: str = "none", with_detections: bool = False,
              per_second: bool = False,
              stream=None) -> tuple[list[VideoResult], Path, bool]:
    """Grade every video, saving the workbook as it goes.

    It is saved after the first video, the last, an interruption, and in
    between whenever the time since the last save is at least four times what
    that save took. A small workbook is therefore saved after every video,
    while a large one -- tens of thousands of frames take a minute to write --
    never spends more than a fifth of the run saving itself.

    Returns the results, the path actually written (it changes if the
    workbook is held open by another program), and whether Ctrl+C stopped it.
    """
    stream = stream or sys.stdout
    tty = getattr(stream, "isatty", lambda: False)()

    def say(text: str = "") -> None:
        print(text, file=stream, flush=True)

    frames_dir = out.with_name(f"{out.stem}_frames") if save_frames != "none" else None
    planned = [_planned_frames(p, s) for p, _ in videos]
    total = sum(planned)
    results: list[VideoResult] = []
    done_before = 0
    started = time.perf_counter()
    interrupted = False
    saved_at, save_cost = -float("inf"), 0.0

    def save(final: bool) -> None:
        nonlocal out, saved_at, save_cost
        t = time.perf_counter()
        warn = say if final else None
        try:
            write_workbook(out, results, s, meta, names, with_detections=with_detections,
                           per_second=per_second, warn=warn)
        except PermissionError:
            alt = out.with_name(f"{out.stem}_{datetime.now():%H%M%S}{out.suffix}")
            say(f"      ! {out.name} is open in another program; saving to {alt.name}")
            out = alt
            write_workbook(out, results, s, meta, names, with_detections=with_detections,
                           per_second=per_second, warn=warn)
        saved_at = time.perf_counter()
        save_cost = saved_at - t

    for k, ((path, label), n) in enumerate(zip(videos, planned), 1):
        v = VideoResult(path=path, label=label)
        results.append(v)
        say(f"[{k}/{len(videos)}] {label}" + (f"  ({n} frames)" if n else ""))

        def tick(i: int, n=n) -> None:
            spent = time.perf_counter() - started
            rate = spent / max(1, done_before + i)
            left = max(0, total - done_before - i) * rate
            line = (f"      frame {i}/{n or '?'}  {rate:.2f} s/frame  "
                    f"batch ETA {_clock(left)}")
            if tty:
                print("\r" + line.ljust(70), end="", file=stream, flush=True)
            elif i % 50 == 0:
                say(line)

        try:
            grade_video(v, model, names, s, device, video_no=k, save_frames=save_frames,
                        frames_dir=frames_dir, progress=tick)
        except KeyboardInterrupt:
            v.status = f"Interrupted after {len(v.frames)} frames"
            interrupted = True
        if tty and v.frames:                       # end the line the ticks redrew
            print(file=stream)
        done_before += len(v.frames)

        st = video_stats(v, s.severity)
        if v.ok and st:
            worst = st.worst.graded[s.severity].pci
            say(f"      mean PCI {st.mean:.1f} {rating_of(st.mean)[0]} | worst {worst:.1f} "
                f"at {st.worst.t_s:.1f} s | {st.frames} frames in {_clock(v.seconds)}")
        else:
            say(f"      {v.status}")
        final = interrupted or k == len(videos)
        if final or k == 1 or time.perf_counter() - saved_at >= 4 * save_cost:
            save(final)
        if interrupted:
            break
    return results, out, interrupted


def _versions() -> str:
    def version(name: str) -> str:
        try:
            return importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            return "?"
    return f"{platform.python_version()} · {version('ultralytics')} · {version('torch')}"


def git_commit(root: Path = ROOT) -> str:
    """The checkout's commit, read from .git without running git."""
    try:
        head = (root / ".git" / "HEAD").read_text().strip()
        if not head.startswith("ref: "):
            return head[:7]
        ref = head[5:]
        loose = root / ".git" / ref
        if loose.exists():
            return loose.read_text().strip()[:7]
        for line in (root / ".git" / "packed-refs").read_text().splitlines():
            if line.endswith(" " + ref):
                return line.split()[0][:7]
    except OSError:
        pass
    return "unknown"


def _command(argv: Sequence[str]) -> str:
    args = ["python", "batch_pci.py", *argv]
    return subprocess.list2cmdline(args) if os.name == "nt" else shlex.join(args)


# ───────────────────────────────────────────────────── command line

def build_parser() -> argparse.ArgumentParser:
    d = Settings()
    ap = argparse.ArgumentParser(
        prog="batch_pci.py",
        description="Grade a batch of drive videos through ASTM D6433 and write "
                    "the scores to an Excel workbook. Defaults are the app's.",
        epilog="examples:\n"
               "  python batch_pci.py videos/\n"
               "  python batch_pci.py videos/ -r -o survey.xlsx --save-frames worst\n"
               "  python batch_pci.py a.mp4 b.MOV --height-m 1.45 --focal-35mm 26\n"
               "  python batch_pci.py samples --max-frames 15     # the app's numbers",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("inputs", nargs="+", metavar="VIDEO_OR_FOLDER",
                    help="video files, folders of videos, or patterns like 'drives/*.mp4'")
    ap.add_argument("-o", "--out", type=Path,
                    help="workbook to write (default: smartroad_batch_<date>_<time>.xlsx "
                         "in the current folder)")
    ap.add_argument("-r", "--recursive", action="store_true",
                    help="also take videos from subfolders of a folder given")

    g = ap.add_argument_group("sampling")
    g.add_argument("--every-s", type=float, default=d.every_s,
                   help="seconds between sampled frames (default %(default)s)")
    g.add_argument("--max-frames", type=int, default=d.max_frames,
                   help="frames per video, 0 for the whole clip (default 0; the app uses 15)")
    g.add_argument("--long-side", type=int, default=d.long_side,
                   help="resize frames to this long side, 0 for the clip's own "
                        "resolution (default %(default)s, as the app)")

    g = ap.add_argument_group("detection")
    g.add_argument("--conf", type=float, default=d.conf,
                   help="detection confidence (default %(default)s)")
    g.add_argument("--no-tiled", dest="tiled", action="store_false",
                   help="resize the whole frame to 640 px instead of tiling")
    g.add_argument("--overlap", type=float, default=d.overlap,
                   help="tile overlap (default %(default)s)")
    g.add_argument("--sky", type=float, default=d.sky,
                   help="sky cut-off, fraction of frame height ignored (default %(default)s)")
    g.add_argument("--weights", type=Path,
                   help=f"checkpoint (default models/{WEIGHTS}, else the Hugging Face copy)")
    g.add_argument("--device", help="cuda, cuda:1, mps or cpu (default: the best available)")

    g = ap.add_argument_group("camera geometry")
    g.add_argument("--height-m", type=float, default=d.height_m,
                   help="camera height above the road, m (default %(default)s)")
    g.add_argument("--focal-35mm", type=float, default=d.focal_35mm,
                   help="focal length, 35 mm equivalent (default %(default)s)")
    g.add_argument("--horizon", type=float, default=d.horizon,
                   help="horizon row as a fraction of frame height (default %(default)s)")
    g.add_argument("--far-m", type=float, default=d.far_m,
                   help="measure out to this distance, m (default %(default)s)")

    g = ap.add_argument_group("grading")
    g.add_argument("--severity", choices=SEVERITIES, default=d.severity,
                   help="ASTM severity applied to every detection (default %(default)s); "
                        "the other two are reported alongside")

    g = ap.add_argument_group("output")
    g.add_argument("--per-second", action="store_true",
                   help="add a sheet with one PCI per second of footage "
                        "(exact at the default --every-s 1)")
    g.add_argument("--detections", action="store_true",
                   help="add a sheet listing every detected box")
    g.add_argument("--save-frames", choices=("none", "worst", "all"), default="none",
                   help="also save annotated frames as JPEGs beside the workbook, "
                        "linked from it (default none)")
    return ap


def main(argv: Sequence[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    for stream in (sys.stdout, sys.stderr):
        # A file name the console's code page cannot show must not stop a
        # batch that has been running for an hour.
        try:
            stream.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass
    ap = build_parser()
    args = ap.parse_args(argv)
    s = Settings(every_s=args.every_s, max_frames=args.max_frames, long_side=args.long_side,
                 severity=args.severity, conf=args.conf, tiled=args.tiled,
                 overlap=args.overlap, sky=args.sky, height_m=args.height_m,
                 focal_35mm=args.focal_35mm, horizon=args.horizon, far_m=args.far_m)
    if problems := s.problems():
        ap.error("; ".join(problems))
    if args.weights and not args.weights.is_file():
        ap.error(f"--weights: no such file: {args.weights}")

    videos, unmatched = collect_videos(args.inputs, recursive=args.recursive)
    for raw in unmatched:
        print(f"  no videos in or matching: {raw}")
    if not videos:
        ap.error("no videos found (looked for " + ", ".join(sorted(VIDEO_SUFFIXES)) + ")")

    out = (args.out or Path(f"smartroad_batch_{datetime.now():%Y-%m-%d_%H%M}.xlsx"))
    out = out.expanduser().resolve()
    if out.suffix.lower() != ".xlsx":
        out = out.with_name(out.name + ".xlsx")
    out.parent.mkdir(parents=True, exist_ok=True)

    print(f"smart-road batch: {len(videos)} video(s) -> {out}")
    print(f"  severity {s.severity} | every {s.every_s:g} s | "
          f"{s.max_frames or 'all'} frames | {'tiled' if s.tiled else 'whole frame'} | "
          f"conf {s.conf:g} | sky {s.sky:g} | camera {s.height_m:g} m, "
          f"{s.focal_35mm:g} mm, horizon {s.horizon:g}")
    model, weights = load_model(args.weights)
    names = dict(model.names)
    device = args.device or pick_device()
    print(f"  weights {weights} on {device}\n")

    meta = {"date": datetime.now().strftime("%Y-%m-%d %H:%M"), "command": _command(argv),
            "commit": git_commit(), "weights": str(weights), "device": device,
            "versions": _versions()}
    try:
        results, out, interrupted = run_batch(videos, model, names, s, device, out,
                                              meta=meta, save_frames=args.save_frames,
                                              with_detections=args.detections,
                                              per_second=args.per_second)
    except KeyboardInterrupt:
        # Only reachable while the workbook itself is being written; the
        # previous save is untouched, because it is replaced only when whole.
        print(f"\nStopped while saving; {out} still holds the previous save.")
        return 130
    ok = sum(1 for v in results if v.ok)
    failed = sum(1 for v in results if v.status.startswith("Error"))
    print(f"\n{'Stopped' if interrupted else 'Done'}: {ok} of {len(videos)} video(s) graded"
          + (f", {failed} failed" if failed else "") + f" -> {out}")
    if interrupted:
        return 130
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
