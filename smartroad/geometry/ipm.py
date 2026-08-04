"""Inverse perspective mapping: image pixels to metres on the road plane.

PCI is a density -- square metres of distress over square metres of pavement --
so every measurement has to leave pixel space. This module does that for a
forward-facing camera by intersecting each pixel's viewing ray with a flat road.

Geometry
--------
Camera frame is X right, Y down, Z along the optical axis. World frame is X
right, Y down (gravity), Z forward and horizontal. The camera sits `height_m`
above the road and is pitched down by `pitch_rad`, so the rotation from camera
to world is about X:

    R = [[1,      0,       0     ],
         [0,  cos t,   sin t     ],
         [0, -sin t,   cos t     ]]

A pixel (u, v) has camera-frame ray direction ((u-cx)/f, (v-cy)/f, 1). Writing
a = (v - cy) / f, the rotated ray is

    dy = cos t * a + sin t          (downward component)
    dz = -sin t * a + cos t         (forward component)

and it meets the road where `scale = height_m / dy`, giving

    Z = scale * dz        X = scale * (u - cx) / f

Rays with dy <= 0 point at or above the horizon and never reach the ground.

Scale varies down the image, so a single "metres per pixel" is wrong. The exact
Jacobian is worth stating because it explains the accuracy limit:

    dX/du = scale / f
    dZ/dv = -scale^2 / (height_m * f)
    pixel area = scale^3 / (height_m * f^2)

Substituting scale = height_m / dy leaves `pixel area = height_m^2 / (dy^3 f^2)`,
so measured area goes with the *square* of the assumed camera height: a 10 %
error in the tape measurement is a 21 % error in every square metre reported.

That error does not simply cancel when the area becomes a density. The inspected
surface grows with height as well, but not in step: it is a fixed *ground* band
(`near_m` to `far_m`) whose width scales with height while its depth is held
constant, so the ratio still moves. Measured on a fixed detection box, raising
the assumed height from 1.95 m to 2.60 m took an area density from 7.6 % to
13.3 %. Height deserves a tape measure, not an estimate.

Area grows with the *cube* of the distance coefficient. Doubling how far away a
pixel lies multiplies the ground area it stands for by eight, so far-field
pixels are worthless for measurement even when the detector sees them clearly --
hence `usable_row_range`.

Assumptions, all of which fail somewhere
----------------------------------------
* The road is planar. Crown, superelevation and the pothole itself are not.
* Pitch and height are constant. True for a rigid mount, false for a handheld
  phone, which is why the Tashkent stills need per-image calibration.
* No lens distortion. Phone main cameras are mild; an ultra-wide is not, and
  its barrel distortion would corrupt this badly.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np

#: Full-frame sensor width. EXIF reports a 35 mm-equivalent focal length, and
#: `f_px = f_35mm / 36 mm * image_width_px` converts it to pixels.
FULL_FRAME_WIDTH_MM = 36.0


@dataclass(frozen=True)
class Camera:
    """A calibrated forward-facing camera above a flat road."""

    width: int
    height: int
    focal_px: float
    height_m: float
    pitch_rad: float
    cx: float
    cy: float

    def __post_init__(self) -> None:
        if self.focal_px <= 0:
            raise ValueError(f"focal length must be positive, got {self.focal_px}")
        if self.height_m <= 0:
            raise ValueError(f"camera height must be positive, got {self.height_m}")
        if not -math.pi / 2 < self.pitch_rad < math.pi / 2:
            raise ValueError(f"pitch must be within +-90 deg, got {self.pitch_rad}")

    # ---------------------------------------------------------------- builders

    @classmethod
    def create(
        cls,
        width: int,
        height: int,
        height_m: float,
        focal_px: float | None = None,
        focal_35mm: float | None = None,
        pitch_rad: float | None = None,
        pitch_deg: float | None = None,
        horizon_row: float | None = None,
        cx: float | None = None,
        cy: float | None = None,
    ) -> "Camera":
        """Build a camera from whichever of the equivalent inputs are known.

        Focal length comes from pixels or from a 35 mm equivalent; pitch from
        radians, degrees, or the image row the horizon falls on -- that last one
        is usually the only one recoverable from a photo nobody measured.
        """
        if focal_px is None:
            if focal_35mm is None:
                raise ValueError("give focal_px or focal_35mm")
            focal_px = focal_35mm / FULL_FRAME_WIDTH_MM * width
        cx = width / 2 if cx is None else cx
        cy = height / 2 if cy is None else cy

        given = [p for p in (pitch_rad, pitch_deg, horizon_row) if p is not None]
        if len(given) != 1:
            raise ValueError("give exactly one of pitch_rad, pitch_deg, horizon_row")
        if pitch_deg is not None:
            pitch_rad = math.radians(pitch_deg)
        elif horizon_row is not None:
            # v_horizon = cy - f * tan(pitch)
            pitch_rad = math.atan((cy - horizon_row) / focal_px)

        return cls(width, height, float(focal_px), float(height_m),
                   float(pitch_rad), float(cx), float(cy))

    @classmethod
    def from_exif(cls, image_path: Path, height_m: float, **kwargs) -> "Camera":
        """Read focal length and image size from a photo's EXIF.

        Rejects digitally zoomed frames: the stored focal length no longer
        describes the crop that was actually saved.
        """
        from PIL import ExifTags, Image

        with Image.open(image_path) as im:
            width, height = im.size
            exif = im._getexif() or {}
        tags = {ExifTags.TAGS.get(k, k): v for k, v in exif.items()}

        zoom = tags.get("DigitalZoomRatio")
        if zoom is not None and abs(float(zoom) - 1.0) > 1e-3:
            raise ValueError(f"{image_path.name}: digital zoom {zoom} invalidates the focal length")

        f35 = tags.get("FocalLengthIn35mmFilm")
        if f35 is None:
            raise ValueError(f"{image_path.name}: no FocalLengthIn35mmFilm in EXIF")

        return cls.create(width=width, height=height, height_m=height_m,
                          focal_35mm=float(f35), **kwargs)

    # ------------------------------------------------------------- projection

    @property
    def horizon_row(self) -> float:
        """Image row where the road plane vanishes. Rows above it never hit it."""
        return self.cy - self.focal_px * math.tan(self.pitch_rad)

    def _downward(self, v):
        """Downward component of the ray through row v (>0 means it meets the road)."""
        a = (np.asarray(v, dtype=float) - self.cy) / self.focal_px
        return math.cos(self.pitch_rad) * a + math.sin(self.pitch_rad)

    #: Rays flatter than this never usefully reach the road. At the horizon the
    #: downward component is exactly zero; just above it, floating-point noise
    #: gives a tiny positive value and a distance of kilometres.
    _MIN_DOWNWARD = 1e-9

    def _scale(self, v):
        """height / downward-component: the ray parameter at the road."""
        dy = self._downward(v)
        with np.errstate(divide="ignore", invalid="ignore"):
            return np.where(dy > self._MIN_DOWNWARD, self.height_m / dy, np.nan)

    def ground_from_pixel(self, u, v):
        """Ground coordinates (X right, Z forward) in metres for pixel (u, v).

        NaN where the pixel is at or above the horizon.
        """
        u = np.asarray(u, dtype=float)
        v = np.asarray(v, dtype=float)
        a = (v - self.cy) / self.focal_px
        scale = self._scale(v)
        dz = -math.sin(self.pitch_rad) * a + math.cos(self.pitch_rad)
        return scale * (u - self.cx) / self.focal_px, scale * dz

    def pixel_from_ground(self, x, z):
        """Inverse of :meth:`ground_from_pixel`, for tests and for drawing."""
        x = np.asarray(x, dtype=float)
        z = np.asarray(z, dtype=float)
        ct, st = math.cos(self.pitch_rad), math.sin(self.pitch_rad)
        # world -> camera is R transposed
        yc = self.height_m * ct - z * st
        zc = self.height_m * st + z * ct
        with np.errstate(divide="ignore", invalid="ignore"):
            return (np.where(zc > 0, self.cx + self.focal_px * x / zc, np.nan),
                    np.where(zc > 0, self.cy + self.focal_px * yc / zc, np.nan))

    def distance_at_row(self, v):
        """Forward distance in metres to the road point on the optical column."""
        return self.ground_from_pixel(self.cx, v)[1]

    def row_at_distance(self, z):
        """Image row showing road at forward distance `z`."""
        return self.pixel_from_ground(0.0, z)[1]

    # ----------------------------------------------------------- measurement

    def pixel_area_m2(self, v):
        """Ground area of one pixel at row v: scale^3 / (height * focal^2)."""
        scale = self._scale(v)
        return scale**3 / (self.height_m * self.focal_px**2)

    def usable_row_range(self, near_m: float = 3.0, far_m: float = 15.0) -> tuple[float, float]:
        """Rows bounding the band where measurement is trustworthy.

        Returns ``(row_far, row_near)`` -- the far limit is the smaller row
        number, since distance grows upward in the image.
        """
        if not 0 < near_m < far_m:
            raise ValueError(f"need 0 < near < far, got {near_m}, {far_m}")
        return float(self.row_at_distance(far_m)), float(self.row_at_distance(near_m))

    def mask_area_m2(self, mask: np.ndarray, near_m: float = 3.0, far_m: float = 15.0) -> float:
        """Ground area of an image mask, in square metres.

        `mask` may be boolean or a float coverage in [0, 1]; segmentation models
        emit the latter, and a hard threshold on a thin crack throws away most
        of its width. Coverage is used as a per-pixel weight.

        Pixels outside the usable distance band are ignored rather than
        extrapolated: near the horizon a single pixel stands for square metres
        of road, so one stray detection there would dominate the density.
        """
        if mask.shape[:2] != (self.height, self.width):
            raise ValueError(f"mask is {mask.shape[:2]}, camera expects {(self.height, self.width)}")
        coverage = mask.astype(float)
        if coverage.min() < 0 or coverage.max() > 1:
            raise ValueError("mask must be boolean or a coverage fraction in [0, 1]")
        rows = np.arange(self.height, dtype=float)
        per_row = self.pixel_area_m2(rows)
        row_far, row_near = self.usable_row_range(near_m, far_m)
        per_row = np.where((rows >= row_far) & (rows <= row_near), per_row, 0.0)
        per_row = np.nan_to_num(per_row, nan=0.0, posinf=0.0)
        return float((coverage.sum(axis=1) * per_row).sum())

    def polyline_length_m(self, points, near_m: float = 3.0, far_m: float = 15.0) -> float:
        """Ground length of a pixel polyline (a crack skeleton), in metres.

        Segments with either end outside the usable band are dropped whole; a
        partially-visible crack is better under-reported than guessed at.
        """
        pts = np.asarray(points, dtype=float)
        if pts.ndim != 2 or pts.shape[1] != 2 or len(pts) < 2:
            raise ValueError("points must be an (N, 2) array of at least two pixels")
        row_far, row_near = self.usable_row_range(near_m, far_m)
        x, z = self.ground_from_pixel(pts[:, 0], pts[:, 1])
        ok = np.isfinite(x) & np.isfinite(z) & (pts[:, 1] >= row_far) & (pts[:, 1] <= row_near)
        seg = ok[:-1] & ok[1:]
        if not seg.any():
            return 0.0
        d = np.hypot(np.diff(x), np.diff(z))
        return float(d[seg].sum())
