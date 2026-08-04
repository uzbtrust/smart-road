# Smart Road — automated Pavement Condition Index from road imagery

Most road-condition tools *count* defects. This one grades a road the way an
engineer is required to: through **ASTM D6433**, the standard that turns a list
of distresses into a single Pavement Condition Index between 0 and 100.

The pipeline is: detect distresses in imagery → convert pixels to square metres
and metres on the road plane → derive severity → run the ASTM deduct-value
mathematics → PCI per road section.

Built for the National Transport Hackathon 2026 (Tashkent). The event did not go
ahead for our team, so what is here is the engineering, finished and verified,
rather than a competition entry.

---

## Results

**Detector** — YOLO11-L, 640 px, 8 ASTM distress classes, trained on 103,968
boxes drawn from four public datasets unified into one taxonomy.

| | mAP50 | mAP50-95 | Precision | Recall |
|---|---:|---:|---:|---:|
| Reported by the training run (RTX 5090, CUDA) | 0.657 | 0.401 | 0.682 | 0.604 |
| **Reproduced locally** (Apple M-series, MPS) | **0.649** | **0.387** | 0.694 | 0.581 |

The 1.2 % gap is device and framework version, not a different model — the
per-class numbers track to within 0.01 (patching 0.780 vs 0.783, marking 0.777
vs 0.781).

Per class, on 3,550 validation images:

| # | Class | ASTM № | Train boxes | mAP50 | mAP50-95 |
|---|---|---|---:|---:|---:|
| 3 | patching | 11 | 7,719 | 0.780 | 0.555 |
| 7 | marking / manhole | — | 17,334 | 0.777 | 0.492 |
| 6 | lane / shoulder drop-off | 9 | 308 | 0.703 | 0.309 |
| 1 | alligator crack | 1 | 16,056 | 0.663 | 0.377 |
| 0 | longitudinal & transverse crack | 10 | 53,293 | 0.630 | 0.358 |
| 5 | weathering / raveling | 19 | 1,805 | 0.601 | 0.313 |
| 4 | pothole | 13 | 7,394 | 0.547 | 0.245 |
| 2 | block crack | 3 | **59** | 0.495 | 0.446 |

Two of these numbers should not be trusted, and the reason is data, not the
model: **block cracking has 59 training boxes and 2 in validation**, and
lane/shoulder drop-off has 4 validation images. Any metric computed from two
examples is noise. That matters here more than usual — in the field survey this
project was built around, block cracking is the *dominant* distress.

**Pothole is the weakest class that does have data (0.245)**, and it is the one
to fix first: ASTM's deduct curve for potholes is by far the steepest, so a
detection error there moves the final PCI more than an error anywhere else.

**PCI engine** — validated against the worked example printed in ASTM D6433-07
(Fig. 4 → Fig. 6):

| | Published in the standard | This implementation |
|---|---:|---:|
| max CDV | 51 | 51.4 |
| PCI | 49 | 48.6 |

---

## What is actually hard here

**Unit conversion is not a detail.** ASTM's deduct-value curves were drawn in
inch-pound units. Area density is dimensionless, so it passes through unchanged
— but linear density does not (× 0.3048) and neither does a pothole count
(× 0.0929). Skipping that conversion on a real survey section moved its PCI from
26.6 to **0.0**. Errors of up to 26 PCI points, silently.

**Camera height dominates the error budget.** Ground area per pixel goes as
`height² / (dy³ · f²)`, so a 10 % error in the tape measurement is a 21 % error
in every square metre reported, and therefore in the density ASTM turns into a
deduct value. See [`smartroad/geometry/ipm.py`](smartroad/geometry/ipm.py).

**Severity can only be measured close to the camera.** Measured on our own
1080p survey footage, ASTM's low/medium threshold for crack width (10 mm) is
about 4 px at 3.5 m and under 2 px at 9 m. Cracks stay *visible* much further
out than they stay *measurable*.

**A 4K frame cannot be fed to a 640 px model.** Downscaling 3840 px to 640 is a
6× reduction; a crack four pixels wide in training becomes less than one and
disappears. On our survey frames, whole-frame inference found 0 and 2 detections
where tiled inference found 2 and 4.
[`smartroad/detect/tiled.py`](smartroad/detect/tiled.py) tiles the road region
with 20 % overlap and merges the results, flagging any box that touches a tile
seam — because a crack split across two tiles is two fragments, and for a
*length* measurement that distinction changes the answer.

![tiled detection on a 4K survey frame](reports/demo/tiled_4k_fwd_160s.jpg)

*Green: the road region searched. Red: detections. The three stacked boxes are
one crack, fragmented at tile seams — flagged rather than silently merged.*

---

## Validating against a real engineering survey

A civil engineer surveyed 1,810 m of Yangizamon street in Tashkent by hand:
12 sections, 9 distress types, L/M/H severity. His paper states plainly that a
PCI was never calculated, because the deduct-value curves were not applied. He
used a simpler cumulative metric (CDL) instead, and noted himself that it has
"no calibrated scale, deduct-value weighting, or condition rating comparable to
standardized PCI."

Running his densities through the ASTM curves gives the 12 PCI values he stopped
short of — and shows why the shortcut is not equivalent:

| | S1 | S2 | S3 | S4 | S5 | S6 | S7 | S8 | S9 | S10 | S11 | S12 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **PCI** | 52.3 | 64.6 | 61.1 | 33.1 | 64.8 | 62.7 | **26.6** | 32.4 | 45.6 | 58.3 | 45.6 | 69.9 |

Whole street: **51.4 (Poor)**. CDL ranks section 11 as the worst; PCI ranks
section 7 as the worst. The reason is a single comparison: in S7, potholes at
**0.7 %** density produce a deduct of **62.6**, while in S11 block cracking at
**35.2 %** produces **16.9**. Fifty times the density, a quarter of the damage.
Allocate repair budget by CDL and the crew goes to the wrong section.

Details, including six corrupted cells found in the survey spreadsheet and
reconciled against the published figures:
[`DATA/docs/YANGIZAMON_PCI.md`](DATA/docs/YANGIZAMON_PCI.md).

---

## Layout

```
smartroad/
  pci/            ASTM D6433 engine — deduct values, CDV iteration, PCI
    engine.py       Distress, SampleUnit, section_pci
    curves.py       digitised deduct curves (generated, see tools/)
    astm.py         distress catalogue and unit conversion
    from_survey.py  reads a manual field survey out of a spreadsheet
  geometry/
    ipm.py          inverse perspective mapping: pixels → metres on the road
  detect/
    tiled.py        tiled inference for imagery larger than the training size
  data/
    build_yolo.py   merges four source datasets into one 8-class YOLO set
  report/           self-contained HTML training report with inline SVG charts
tools/
  gen_curves.py     regenerates curves.py from the upstream MIT-licensed source
  kaggle_fetch.py   resumable dataset download
tests/              146 tests
```

## Running it

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest tests -q
```

Detect on a large frame:

```python
import numpy as np, PIL.Image
from ultralytics import YOLO
from smartroad.detect.tiled import detect_tiled, road_roi

model = YOLO("yolo11l_640_best.pt")
frame = np.array(PIL.Image.open("frame.jpg").convert("RGB"))
h, w = frame.shape[:2]
dets = detect_tiled(model, frame, roi=road_roi(w, h),
                    classes=range(8), device="mps")
```

⚠️ `classes=range(8)` is not optional. The checkpoint was trained against a
ten-class configuration whose last two classes have no examples at all, so those
two heads are untrained and will fire on anything.

PCI from distress quantities:

```python
from smartroad.pci.engine import Distress, SampleUnit

unit = SampleUnit(area=2500, units="imperial", distresses=[
    Distress("alligator_cracking", "high", 14),
    Distress("potholes", "low", 1),
])
print(unit.evaluate().summary())
```

## Data

| Source | Images | Licence |
|---|---:|---|
| RDD2022 | 26,661 | CC BY-SA 4.0 |
| RDD2018 (Japan) | 9,052 | CC BY-SA 4.0 |
| SVRDD (street view) | 8,000 | CC BY-SA 4.0 |
| Attain (Tehran) | 840 | CC BY-SA 4.0 |

Merged, deduplicated and mapped onto the ASTM taxonomy by
[`smartroad/data/build_yolo.py`](smartroad/data/build_yolo.py): 40,994 training
and 3,550 validation images, 113,648 boxes.

## Credits

Deduct-value curve coefficients are digitised from
[brandnewbox/pavement_condition_index](https://github.com/brandnewbox/pavement_condition_index)
(MIT). `tools/gen_curves.py` regenerates them from that source.
