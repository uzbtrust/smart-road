"""Measure how wide a crack is, in millimetres, so ASTM can grade it.

The detector has no severity head: the training data carried no consistent
L/M/H labels, so the app grades every detection at one chosen severity and
shows the three answers side by side. ASTM does not accept that -- severity is
half of what selects a deduct curve. For cracks, the standard's own criterion
is width, and width is measurable from the same frame the box came from.

HOW. A crack is darker than the asphalt around it and thin. Black-hat
morphology isolates exactly that: dark structures narrower than the kernel,
with the slow background shading removed, which matters because a shadowed
frame otherwise thresholds into nonsense. Otsu then splits the response, the
largest connected component is taken as the crack, and its mean width is its
area divided by its length -- the honest estimator for a thin ribbon, and far
steadier than the widest point, which is usually where two cracks cross.

Pixels become millimetres through `Camera.lateral_m_per_px`, evaluated at the
crack's own row. Width is measured across the road, and a pixel on the road is
foreshortened, so the lateral scale is the right one and the square root of
the pixel area is not.

WHAT THIS CANNOT DO, and it is most of the honesty here. Width in pixels runs
out before the road does. At 1080p a 10 mm crack -- the L/M boundary -- is 3.5
pixels wide at 3.5 m, 1.9 at 7 m and 1.5 at 9 m. Below about three pixels
across, the measurement is a guess dressed as a number, so `CrackWidth` carries
`reliable` and the classifier refuses rather than returning a severity it
cannot support. On 4K the same crack is 7.0 pixels at 3.5 m and 2.9 at 9 m,
which is why the survey was reshot at 4K.

And width is not how ASTM grades everything. Alligator cracking is graded by
pattern -- hairline, then interconnected, then spalled and loose -- and
potholes by depth and diameter. Handing those a width would be inventing a
criterion the standard does not use, so `WIDTH_GRADED` names the distresses
this applies to and `severity_from_width` refuses the rest.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

#: Distresses ASTM D6433 grades by crack width. Alligator cracking is graded by
#: pattern and potholes by depth, so neither belongs here.
WIDTH_GRADED = frozenset({
    "longitudinal_transverse_cracking",
    "block_cracking",
    "edge_cracking",
    "joint_reflection_cracking",
})

#: ASTM's width boundaries in millimetres: low below the first, high above the
#: second. Roughly 3/8 inch and 3 inches, the units the standard is drawn in.
LOW_MEDIUM_MM = 10.0
MEDIUM_HIGH_MM = 75.0

#: Below this many pixels across, a width is noise with a decimal point on it.
MIN_PX_ACROSS = 3.0

#: A crack is long against its width. This is deliberately permissive: it
#: rejects a round blob and nothing more. A stricter value separated the three
#: real cracks (8.1, 11.4, 9.4) from bare noise (4.2 to 4.5), but it also threw
#: out a 40 px crack drawn in a 200 px patch, whose ratio is 5.0 -- because
#: elongation depends on the shape of the box as much as on the crack. Deciding
#: whether a crack is present is the detector's job, not this module's.
MIN_ELONGATION = 3.0

#: Two independent width estimators have to agree before a component is called
#: a crack: area over length, which is only meaningful for a ribbon, and twice
#: the largest distance-transform value, which is a true local half-width
#: wherever it is taken. Their ratio is the gate.
#:
#: Measured. Synthetic cracks from 3 to 40 px: 0.99 to 1.33. The three cracks
#: on the Yangizamon frame: 0.77, 1.16, 1.02. Otsu's split of bare asphalt
#: across three seeds: 0.05, 0.05, 0.04 -- because a sprawl has no length in
#: the sense area/length assumes, so that estimator returns a nonsense 88 px
#: against a distance transform that still says 4.4.
#:
#: Grey-level contrast was the obvious gate and is useless here: real cracks
#: stand 5.4 to 13.6 levels below their surroundings and bare noise gives 6.2
#: to 24.9, ranges that sit on top of each other.
RIBBON_RATIO_MIN = 0.35

#: The black-hat kernel must enclose the widest crack worth resolving, because
#: a structure wider than the kernel is removed along with the background --
#: measured: a 20 px crack under a 15 px kernel vanishes entirely, responding
#: no more strongly than bare asphalt. Sized from the geometry at twice ASTM's
#: high-severity boundary, so the whole graded range survives.
KERNEL_MM = 2.0 * MEDIUM_HIGH_MM

#: Bounds on that kernel: small enough to stay selective, odd for symmetry.
MIN_KERNEL_PX, MAX_KERNEL_PX = 9, 121


@dataclass(frozen=True)
class CrackWidth:
    """A width measurement and the grounds for believing it."""

    mean_mm: float
    max_mm: float
    length_px: float
    px_across: float
    mm_per_px: float
    distance_m: float

    @property
    def reliable(self) -> bool:
        """Whether the crack is wide enough in pixels to have been measured."""
        return self.px_across >= MIN_PX_ACROSS

    def __str__(self) -> str:
        flag = "" if self.reliable else "  (unreliable: too few pixels across)"
        return (f"{self.mean_mm:.1f} mm mean, {self.max_mm:.1f} mm max, "
                f"{self.px_across:.1f} px across at {self.distance_m:.1f} m{flag}")


def _cv2():
    import cv2
    return cv2


def _length_px(mask: np.ndarray) -> float:
    """Extent of the mask along its own principal axis.

    A crack is not axis-aligned, so its length is not the box diagonal and not
    the row count: it is how far the ink runs in the direction it actually
    runs, which is the first principal component of the lit pixels.
    """
    ys, xs = np.nonzero(mask)
    if ys.size < 2:
        return float(ys.size)
    pts = np.stack([xs.astype(float), ys.astype(float)])
    centred = pts - pts.mean(axis=1, keepdims=True)
    # Principal direction from the 2x2 covariance; no SVD needed for two dims.
    cov = centred @ centred.T / centred.shape[1]
    values, vectors = np.linalg.eigh(cov)
    axis = vectors[:, int(np.argmax(values))]
    projection = axis @ centred
    return float(projection.max() - projection.min())


def segment_crack(patch: np.ndarray, kernel_px: int = 31) -> np.ndarray:
    """Boolean mask of the crack in a patch, or an empty mask if there is none.

    Black-hat removes the background shading before thresholding, so a patch
    lying half in shadow does not threshold along the shadow line instead of
    along the crack. `kernel_px` must exceed the widest crack to be resolved;
    see KERNEL_MM.

    Otsu splits noise as happily as it splits asphalt from a fissure, so what it
    finds is gated twice: on elongation, which rejects a round stain, and on
    the two width estimators agreeing, which rejects a sprawl of grain. See
    RIBBON_RATIO_MIN for the measurements behind the second.

    This is called on a box the detector has already decided contains a crack.
    It is not a second opinion on whether one is there; it locates the crack in
    order to measure it.
    """
    cv2 = _cv2()
    gray = (cv2.cvtColor(patch, cv2.COLOR_RGB2GRAY) if patch.ndim == 3
            else patch.astype(np.uint8))
    if gray.size == 0:
        return np.zeros((0, 0), dtype=bool)

    kernel_px = int(np.clip(kernel_px | 1, MIN_KERNEL_PX, MAX_KERNEL_PX))
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_px, kernel_px))
    hat = cv2.morphologyEx(gray, cv2.MORPH_BLACKHAT, k)
    empty = np.zeros_like(gray, dtype=bool)
    if int(hat.max()) == 0:
        return empty

    _, binary = cv2.threshold(hat, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(binary, 8)
    if count <= 1:
        return empty
    largest = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    mask = labels == largest

    area = float(mask.sum())
    if area <= 0 or mask.all():
        return empty
    length = _length_px(mask)
    if length <= 0 or length / (area / length) < MIN_ELONGATION:
        return empty
    mean_px = area / length
    max_px = float(cv2.distanceTransform(mask.astype(np.uint8),
                                         cv2.DIST_L2, 5).max()) * 2.0
    if mean_px <= 0 or max_px / mean_px < RIBBON_RATIO_MIN:
        return empty                      # not a ribbon; see RIBBON_RATIO_MIN
    return mask


def measure_width(image: np.ndarray, box: tuple[float, float, float, float],
                  camera, *, pad_px: int = 4) -> CrackWidth | None:
    """Width of the crack inside `box`, in millimetres on the road.

    `box` is (x1, y1, x2, y2) in full-frame pixels. Returns None when nothing
    crack-like is found, which is a real answer: a box can be a false positive,
    or a shadow, or a joint the detector mistook for a crack.

    The scale is taken at the crack's own centre row rather than the box's,
    because a box tall enough to matter spans a real change in distance.
    """
    cv2 = _cv2()
    h, w = image.shape[:2]
    x1 = max(0, int(box[0]) - pad_px)
    y1 = max(0, int(box[1]) - pad_px)
    x2 = min(w, int(box[2]) + pad_px)
    y2 = min(h, int(box[3]) + pad_px)
    if x2 - x1 < 2 or y2 - y1 < 2:
        return None

    # Size the black-hat kernel from the geometry: a crack wider than the
    # kernel is erased by the operator, and the widest ASTM grades is 75 mm.
    mid_row = (y1 + y2) / 2.0
    mm_at_mid = float(camera.lateral_m_per_px(mid_row)) * 1000.0
    if not np.isfinite(mm_at_mid) or mm_at_mid <= 0:
        return None                       # at or above the horizon
    kernel_px = int(round(KERNEL_MM / mm_at_mid))

    mask = segment_crack(np.ascontiguousarray(image[y1:y2, x1:x2]), kernel_px)
    area_px = float(mask.sum())
    if area_px <= 0:
        return None

    length_px = _length_px(mask)
    if length_px <= 0:
        return None
    mean_px = area_px / length_px

    # Half-width at the thickest point, from the distance transform: every lit
    # pixel is labelled with its distance to the nearest edge, so the largest
    # value is the medial axis at its widest.
    dist = cv2.distanceTransform(mask.astype(np.uint8), cv2.DIST_L2, 5)
    max_px = float(dist.max()) * 2.0

    ys, _ = np.nonzero(mask)
    centre_row = float(ys.mean()) + y1
    mm_per_px = float(camera.lateral_m_per_px(centre_row)) * 1000.0
    if not np.isfinite(mm_per_px) or mm_per_px <= 0:
        return None                       # at or above the horizon

    return CrackWidth(mean_mm=mean_px * mm_per_px,
                      max_mm=max_px * mm_per_px,
                      length_px=length_px,
                      px_across=mean_px,
                      mm_per_px=mm_per_px,
                      distance_m=float(camera.distance_at_row(centre_row)))


def severity_from_width(distress: str, width: CrackWidth) -> str | None:
    """ASTM's L/M/H for a width-graded crack, or None where it does not apply.

    None means the question was wrong, not that the answer is low: alligator
    cracking is graded by pattern and potholes by depth, and a measurement too
    coarse to resolve the 10 mm boundary cannot decide it either. The caller
    should keep reporting the severity range in both cases rather than commit
    to a grade the evidence does not carry.
    """
    if distress not in WIDTH_GRADED or not width.reliable:
        return None
    if width.mean_mm < LOW_MEDIUM_MM:
        return "low"
    return "medium" if width.mean_mm <= MEDIUM_HIGH_MM else "high"


def reliable_distance_m(camera, *, threshold_mm: float = LOW_MEDIUM_MM,
                        min_px: float = MIN_PX_ACROSS) -> float:
    """How far out a crack of `threshold_mm` still spans `min_px` pixels.

    The honest edge of severity measurement for a given camera: beyond this,
    `measure_width` still returns numbers but `reliable` is False. Reported so a
    survey can be driven, or a resolution chosen, against a figure rather than
    against a hope.
    """
    lo, hi = 0.5, 200.0
    for _ in range(60):                   # bisection; the scale is monotonic
        mid = (lo + hi) / 2
        row = camera.row_at_distance(mid)
        mm_per_px = float(camera.lateral_m_per_px(row)) * 1000.0
        if not np.isfinite(mm_per_px) or threshold_mm / mm_per_px < min_px:
            hi = mid
        else:
            lo = mid
    return lo
