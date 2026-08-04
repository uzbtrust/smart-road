"""Sample a driven survey video into frames and grade each one.

A single photograph gives one PCI for one patch of road. A drive gives a profile
along it, which is what a pavement management system actually wants: not "this
road is 46" but "it is 70 here and 25 three hundred metres later".

Sampling is by time rather than by every frame, for two reasons. At 60 fps a
vehicle moving at 35 km/h advances 16 cm per frame, so consecutive frames show
almost the same asphalt and would count the same crack dozens of times. And the
cost is linear in frames: one second apart turns a 15-second clip into 15
detections instead of 900.

Decoding is in-process through OpenCV rather than by shelling out to ffmpeg.
That is not a preference. Streamlit runs the script on a worker thread, and on
macOS a subprocess spawned from a non-main thread after Metal has initialised —
which it has, the detector runs on MPS — segfaults on startup. It reproduced
every time as ffprobe dying with SIGSEGV inside a session while working from a
plain shell. Reading frames in-process has no fork in it to be unsafe.

What this does *not* do is deduplicate across frames. At one sample per second
and 35 km/h the frames are about 10 m apart while the measured band is roughly
3-12 m deep, so consecutive samples still overlap and a long crack can be
counted twice. Densities are therefore reported per frame, never summed into a
section total -- summing them would inflate the result, and the honest fix is
frame-to-frame matching against a georeferenced chainage, which belongs with the
survey geometry rather than here.
"""
from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator


@dataclass(frozen=True)
class VideoInfo:
    path: Path
    width: int
    height: int
    fps: float
    duration_s: float
    n_frames: int

    @property
    def label(self) -> str:
        return (f"{self.width}x{self.height} · {self.fps:.0f} fps · "
                f"{self.duration_s:.1f} s")


def _cv2():
    try:
        import cv2
    except ImportError as exc:                                  # pragma: no cover
        raise RuntimeError(
            "OpenCV is required to read video: pip install opencv-python") from exc
    return cv2


def _open(path: Path):
    cv2 = _cv2()
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        cap.release()
        raise ValueError(f"{path.name}: could not be opened as video")
    return cap


def probe_video(path: str | Path) -> VideoInfo:
    """Dimensions, frame rate and duration of a video file."""
    cv2 = _cv2()
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(path)

    cap = _open(path)
    try:
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = float(cap.get(cv2.CAP_PROP_FPS)) or 0.0
        n_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    finally:
        cap.release()

    if width <= 0 or height <= 0:
        raise ValueError(f"{path.name}: no readable video stream")
    duration = n_frames / fps if fps > 0 and n_frames > 0 else 0.0
    return VideoInfo(path=path, width=width, height=height, fps=fps,
                     duration_s=duration, n_frames=max(n_frames, 0))


def frame_times(info: VideoInfo, every_s: float, max_frames: int | None = None) -> list[float]:
    """Timestamps to sample, starting half an interval in.

    Offsetting by half an interval keeps the first sample off frame zero, which
    on dashcam footage is often still auto-exposing.
    """
    if every_s <= 0:
        raise ValueError(f"every_s must be positive, got {every_s}")
    if info.duration_s <= 0:
        raise ValueError(f"{info.path.name}: zero duration")

    times: list[float] = []
    t = min(every_s / 2, info.duration_s / 2)
    while t < info.duration_s:
        times.append(round(t, 3))
        t += every_s
    return times[:max_frames] if max_frames else times


def _resize(image, long_side: int | None):
    if not long_side:
        return image
    cv2 = _cv2()
    h, w = image.shape[:2]
    if max(h, w) <= long_side:
        return image
    scale = long_side / max(h, w)
    return cv2.resize(image, (round(w * scale), round(h * scale)),
                      interpolation=cv2.INTER_AREA)


def iter_frames(path: str | Path, every_s: float = 1.0,
                max_frames: int | None = None,
                long_side: int | None = None) -> Iterator[tuple[float, "object"]]:
    """Yield ``(seconds, PIL.Image)`` for each sampled frame.

    Frames are reached by seeking rather than by decoding the whole clip: at one
    sample a second, decoding every frame throws away 59 out of 60 of the work.
    """
    from PIL import Image

    cv2 = _cv2()
    info = probe_video(path)
    cap = _open(info.path)
    try:
        for t in frame_times(info, every_s, max_frames):
            cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000.0)
            ok, bgr = cap.read()
            if not ok or bgr is None:
                continue
            rgb = cv2.cvtColor(_resize(bgr, long_side), cv2.COLOR_BGR2RGB)
            yield t, Image.fromarray(rgb)
    finally:
        cap.release()


def extract_frames(path: str | Path, every_s: float = 1.0,
                   max_frames: int | None = None,
                   long_side: int | None = None,
                   out_dir: str | Path | None = None) -> list[tuple[float, Path]]:
    """Write one JPEG per sample time; return ``(seconds, path)`` pairs."""
    out_dir = Path(out_dir) if out_dir else Path(
        tempfile.mkdtemp(prefix="smartroad_frames_"))
    out_dir.mkdir(parents=True, exist_ok=True)

    out: list[tuple[float, Path]] = []
    for i, (t, image) in enumerate(iter_frames(path, every_s, max_frames, long_side), 1):
        dst = out_dir / f"frame_{i:05d}.jpg"
        image.save(dst, quality=92)
        out.append((t, dst))
    return out
