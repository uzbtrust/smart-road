"""Detect on imagery far larger than the size the model was trained at.

The detector was trained on 640 px crops of images whose long side was at most
1024 px. A 3840x2160 survey frame fed to it whole is first resized to 640, a
6x reduction: a 10 mm crack that occupied four pixels in training occupies less
than one here, and simply disappears. Measured on our own survey frames, whole-
frame inference found a single detection where the tiled path below finds
dozens.

The fix is to keep the pixels and move the window instead. The frame is cut into
overlapping tiles at roughly the scale the model saw during training, each tile
is detected on independently, and the boxes are mapped back to frame coordinates
and merged.

Two details matter more than the tiling itself:

*Overlap.* A crack lying on a tile seam is seen twice, each time as a fragment.
Without overlap it is seen twice as two *different* short cracks and never as
one. The default 20 % overlap means any distress shorter than the overlap band
is wholly inside at least one tile.

*Merging.* Overlap guarantees duplicates, so the union has to be reduced. Plain
per-class NMS handles the easy case -- the same crack found twice at nearly the
same place. It cannot join two halves of a crack that genuinely spans a seam,
and this module does not pretend to: fragments are kept separate and the caller
is told how many boxes touch a seam, because for a *length* measurement that
distinction changes the answer and should not be hidden.

Restricting to a region of interest is not an optimisation. Above the horizon
there is no road, and near it one pixel stands for square metres of ground
(see :mod:`smartroad.geometry.ipm`), so a detection there contributes noise to
any density that ASTM would turn into a deduct value.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

import numpy as np

#: Tile side in pixels. The model's training resolution; tiling at the size the
#: network expects avoids a second rescale inside the predictor.
DEFAULT_TILE = 640

#: Fraction of a tile shared with its neighbour.
DEFAULT_OVERLAP = 0.2

#: A box within this distance of a tile edge may be a fragment of a larger one.
SEAM_MARGIN_PX = 4


@dataclass(frozen=True)
class Detection:
    """One detection in full-frame pixel coordinates."""

    x1: float
    y1: float
    x2: float
    y2: float
    confidence: float
    class_id: int
    on_seam: bool = False

    @property
    def width(self) -> float:
        return self.x2 - self.x1

    @property
    def height(self) -> float:
        return self.y2 - self.y1

    @property
    def area(self) -> float:
        return max(0.0, self.width) * max(0.0, self.height)

    def as_xyxy(self) -> tuple[float, float, float, float]:
        return (self.x1, self.y1, self.x2, self.y2)


def tile_grid(width: int, height: int, tile: int = DEFAULT_TILE,
              overlap: float = DEFAULT_OVERLAP,
              roi: tuple[int, int, int, int] | None = None) -> list[tuple[int, int, int, int]]:
    """Overlapping tile boxes ``(x0, y0, x1, y1)`` covering the region.

    The last tile in each direction is pushed back against the far edge rather
    than allowed to hang over it, so no padding is ever fed to the model. That
    makes the final overlap larger than requested, which is harmless -- more
    overlap only costs time. A region smaller than one tile yields a single
    tile of that region, smaller than `tile`.
    """
    if tile <= 0:
        raise ValueError(f"tile must be positive, got {tile}")
    if not 0 <= overlap < 1:
        raise ValueError(f"overlap must be in [0, 1), got {overlap}")

    rx0, ry0, rx1, ry1 = roi if roi else (0, 0, width, height)
    rx0, ry0 = max(0, rx0), max(0, ry0)
    rx1, ry1 = min(width, rx1), min(height, ry1)
    if rx1 <= rx0 or ry1 <= ry0:
        raise ValueError(f"empty region of interest {(rx0, ry0, rx1, ry1)}")

    def starts(lo: int, hi: int) -> list[int]:
        if hi - lo <= tile:
            return [lo]
        stride = max(1, int(round(tile * (1 - overlap))))
        out = list(range(lo, hi - tile + 1, stride))
        if out[-1] != hi - tile:
            out.append(hi - tile)
        return out

    return [(x, y, min(x + tile, rx1), min(y + tile, ry1))
            for y in starts(ry0, ry1) for x in starts(rx0, rx1)]


def _iou(a: Detection, b: Detection) -> float:
    ix1, iy1 = max(a.x1, b.x1), max(a.y1, b.y1)
    ix2, iy2 = min(a.x2, b.x2), min(a.y2, b.y2)
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    union = a.area + b.area - inter
    return inter / union if union > 0 else 0.0


def merge_detections(dets: Sequence[Detection], iou_threshold: float = 0.5) -> list[Detection]:
    """Class-wise non-maximum suppression over detections from all tiles.

    Suppression is per class on purpose: a pothole inside a patch is two true
    detections at the same place, and a class-agnostic pass would delete one of
    them. `on_seam` is carried over from whichever box survives, so a merged
    detection is still flagged if any of its sources touched a tile edge.
    """
    if not 0 < iou_threshold <= 1:
        raise ValueError(f"iou_threshold must be in (0, 1], got {iou_threshold}")

    kept: list[Detection] = []
    for cls in sorted({d.class_id for d in dets}):
        pool = sorted((d for d in dets if d.class_id == cls),
                      key=lambda d: d.confidence, reverse=True)
        survivors: list[Detection] = []
        for cand in pool:
            hit = next((i for i, s in enumerate(survivors)
                        if _iou(cand, s) > iou_threshold), None)
            if hit is None:
                survivors.append(cand)
            elif cand.on_seam and not survivors[hit].on_seam:
                s = survivors[hit]
                survivors[hit] = Detection(s.x1, s.y1, s.x2, s.y2, s.confidence,
                                           s.class_id, on_seam=True)
        kept.extend(survivors)
    return sorted(kept, key=lambda d: d.confidence, reverse=True)


def _touches_seam(x1: float, y1: float, x2: float, y2: float,
                  tile_box: tuple[int, int, int, int],
                  frame: tuple[int, int]) -> bool:
    """True if a tile-local box sits against a tile edge that is not a frame edge."""
    tx0, ty0, tx1, ty1 = tile_box
    w, h = frame
    return (
        (x1 <= SEAM_MARGIN_PX and tx0 > 0)
        or (y1 <= SEAM_MARGIN_PX and ty0 > 0)
        or (x2 >= (tx1 - tx0) - SEAM_MARGIN_PX and tx1 < w)
        or (y2 >= (ty1 - ty0) - SEAM_MARGIN_PX and ty1 < h)
    )


def detect_tiled(model, image: np.ndarray, *, tile: int = DEFAULT_TILE,
                 overlap: float = DEFAULT_OVERLAP,
                 roi: tuple[int, int, int, int] | None = None,
                 conf: float = 0.25, iou_threshold: float = 0.5,
                 classes: Iterable[int] | None = None,
                 device: str | None = None, batch: int = 8) -> list[Detection]:
    """Run an Ultralytics model over `image` tile by tile.

    `classes` restricts which class ids are kept. This is not cosmetic for our
    checkpoint: it was trained against a ten-class `data.yaml` whose last two
    classes have no examples at all, so those two heads are untrained and can
    fire on anything. Pass ``range(8)`` to drop them.
    """
    if image.ndim != 3:
        raise ValueError(f"expected an HxWx3 image, got shape {image.shape}")
    height, width = image.shape[:2]
    boxes = tile_grid(width, height, tile=tile, overlap=overlap, roi=roi)

    wanted = set(classes) if classes is not None else None
    out: list[Detection] = []

    for start in range(0, len(boxes), batch):
        chunk = boxes[start:start + batch]
        crops = [image[y0:y1, x0:x1] for x0, y0, x1, y1 in chunk]
        results = model.predict(crops, imgsz=tile, conf=conf, device=device,
                                verbose=False)
        for (x0, y0, x1, y1), res in zip(chunk, results):
            if res.boxes is None or len(res.boxes) == 0:
                continue
            xyxy = res.boxes.xyxy.cpu().numpy()
            confs = res.boxes.conf.cpu().numpy()
            clss = res.boxes.cls.cpu().numpy().astype(int)
            for (bx1, by1, bx2, by2), c, k in zip(xyxy, confs, clss):
                if wanted is not None and int(k) not in wanted:
                    continue
                out.append(Detection(
                    x1=float(bx1) + x0, y1=float(by1) + y0,
                    x2=float(bx2) + x0, y2=float(by2) + y0,
                    confidence=float(c), class_id=int(k),
                    on_seam=_touches_seam(bx1, by1, bx2, by2, (x0, y0, x1, y1),
                                          (width, height)),
                ))

    return merge_detections(out, iou_threshold=iou_threshold)


def road_roi(width: int, height: int, top_fraction: float = 0.45) -> tuple[int, int, int, int]:
    """A crude road region: everything below `top_fraction` of the frame.

    A stand-in for :meth:`smartroad.geometry.ipm.Camera.usable_row_range`, for
    frames whose camera height and pitch have not been calibrated. It assumes a
    roughly level, forward-facing camera, which the survey footage is.
    """
    if not 0 <= top_fraction < 1:
        raise ValueError(f"top_fraction must be in [0, 1), got {top_fraction}")
    return (0, int(height * top_fraction), width, height)
