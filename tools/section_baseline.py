"""Grade a survey pass section by section and compare it to the hand survey.

    .venv/bin/python tools/section_baseline.py                      # measure
    .venv/bin/python tools/section_baseline.py --against before.json

The point is the second form. Block cracking is 46 % of the professor's total
deduct and the detector currently finds none of it, so the automatic PCI reads
optimistic by a knowable amount. Run this before retraining and again after,
and the difference is the answer to "did it help", in the units the project is
judged in rather than in mAP.

Results are written as JSON so two runs months apart can be subtracted.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SURVEY = ROOT / "SURVEY" / "2026-08-03_yangizamon"
DEFAULT_VIDEO = SURVEY / "yangizamon_2026-08-03_fwd_pass2_iphone.mov"
DEFAULT_GPX = SURVEY / "yangizamon_2026-08-03_fwd_pass2.gpx"

#: The professor's hand-computed PCI, direction A, from DATA/docs/YANGIZAMON_PCI.md.
#: Six sections of 300 m; the forward pass covers the same carriageway.
HAND_PCI_A = {1: 52.3, 2: 64.6, 3: 61.1, 4: 33.1, 5: 64.8, 6: 62.7}


def measure(video: Path, gpx: Path, *, every_s: float, section_m: float,
            severity: str, sky: float) -> dict:
    from ultralytics import YOLO
    from huggingface_hub import hf_hub_download
    from smartroad.detect.tiled import detect_tiled, road_roi
    from smartroad.geometry.ipm import Camera
    from smartroad.survey.frames import locate_frames
    from smartroad.survey.sections import (assess_sections, coverage_report,
                                           disjoint_windows, effective_band,
                                           split_into_sections)
    from smartroad.survey.video import iter_frames

    model = YOLO(hf_hub_download("uzbtrust/smart-road-pci-yolo11",
                                 "yolo11l_640_best.pt"))
    names = dict(model.names)
    geo = locate_frames(video, gpx, every_s=every_s)

    started = time.time()
    by_frame, camera, roi = {}, None, None
    for t_s, pil in iter_frames(video, every_s=every_s, long_side=1280):
        frame = np.asarray(pil.convert("RGB"))
        h, w = frame.shape[:2]
        if camera is None:
            camera = Camera.create(width=w, height=h, height_m=1.70,
                                   focal_35mm=25.0, horizon_row=0.139 * h)
            roi = road_roi(w, h, top_fraction=sky)
        by_frame[t_s] = detect_tiled(model, frame, tile=640, overlap=0.2, roi=roi,
                                     conf=0.25, classes=tuple(range(8)),
                                     device=_device())
    elapsed = time.time() - started

    near, far = effective_band(camera, roi, 3.0, 15.0)
    windows = disjoint_windows(geo, near_m=near, far_m=far)
    sections = split_into_sections(windows, section_m=section_m)
    graded = assess_sections(sections, by_frame, camera, severity=severity,
                             class_names=names, roi=roi)

    found: dict[str, int] = {}
    for dets in by_frame.values():
        for d in dets:
            n = names[d.class_id]
            found[n] = found.get(n, 0) + 1

    return {
        "video": video.name,
        "measured_at": time.strftime("%Y-%m-%d %H:%M"),
        "settings": {"every_s": every_s, "section_m": section_m,
                     "severity": severity, "sky_cut_off": sky,
                     "effective_band_m": [round(near, 2), round(far, 2)]},
        "frames": len(geo),
        "detections": sum(len(v) for v in by_frame.values()),
        "by_class": dict(sorted(found.items(), key=lambda kv: -kv[1])),
        "seconds": round(elapsed, 1),
        "coverage": {k: round(v, 3) for k, v in
                     coverage_report(windows).items()},
        "sections": [{"index": a.section.index + 1,
                      "start_m": round(a.section.start_m, 1),
                      "end_m": round(a.section.end_m, 1),
                      "frames": len(a.section),
                      "area_m2": round(a.inspected_area_m2, 1),
                      "coverage": round(a.section.coverage_fraction, 3),
                      "pci": round(a.pci, 1),
                      "rating": a.rating}
                     for a in graded],
    }


def _device() -> str:
    import torch
    if torch.cuda.is_available():
        return "cuda"
    return "mps" if torch.backends.mps.is_available() else "cpu"


def report(run: dict, previous: dict | None = None) -> None:
    s = run["settings"]
    band = s["effective_band_m"]
    print(f"{run['video']}  ·  {run['measured_at']}")
    print(f"  {run['frames']} frames every {s['every_s']} s, "
          f"{run['detections']} detections in {run['seconds']} s")
    print(f"  sky cut-off {s['sky_cut_off']} gives a real band of "
          f"{band[0]}-{band[1]} m, covering "
          f"{run['coverage']['coverage_fraction'] * 100:.1f}% of "
          f"{run['coverage']['span_m']:.0f} m")
    if run["by_class"]:
        print("  found: " + ", ".join(f"{k} {v}" for k, v in
                                      list(run["by_class"].items())[:6]))
    if "block_crack" not in run["by_class"]:
        print("  block cracking: none — 46 % of the hand survey's deduct total")

    print(f"\n  {'sec':<5}{'range':<16}{'frames':>7}{'m2':>8}{'cov':>6}"
          f"{'PCI':>8}{'hand':>7}{'gap':>7}", end="")
    print(f"{'was':>7}{'moved':>8}" if previous else "")
    was = {x["index"]: x["pci"] for x in previous["sections"]} if previous else {}

    gaps, moves = [], []
    for row in run["sections"]:
        i = row["index"]
        hand = HAND_PCI_A.get(i)
        line = (f"  S{i:<4}{row['start_m']:>5.0f}-{row['end_m']:<10.0f}"
                f"{row['frames']:>7}{row['area_m2']:>8.0f}"
                f"{row['coverage'] * 100:>5.0f}%{row['pci']:>8.1f}")
        if hand is not None:
            gaps.append(row["pci"] - hand)
            line += f"{hand:>7.1f}{row['pci'] - hand:>+7.1f}"
        else:
            line += f"{'-':>7}{'':>7}"
        if previous and i in was:
            moves.append(row["pci"] - was[i])
            line += f"{was[i]:>7.1f}{row['pci'] - was[i]:>+8.1f}"
        print(line)

    if gaps:
        print(f"\n  mean against the hand survey: {statistics.fmean(gaps):+.1f} "
              f"points over {len(gaps)} sections")
    if moves:
        shift = statistics.fmean(moves)
        closer = statistics.fmean(abs(g) for g in gaps) if gaps else None
        print(f"  mean shift since the previous run: {shift:+.1f} points")
        if closer is not None:
            print(f"  mean distance from the hand survey now: {closer:.1f} points")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--video", type=Path, default=DEFAULT_VIDEO)
    ap.add_argument("--gpx", type=Path, default=DEFAULT_GPX)
    ap.add_argument("--every-s", type=float, default=1.0)
    ap.add_argument("--section-m", type=float, default=300.0,
                    help="300 m matches the professor's sections")
    ap.add_argument("--severity", default="medium",
                    choices=("low", "medium", "high"))
    ap.add_argument("--sky", type=float, default=0.45,
                    help="sky cut-off; 0.25 reaches the full 15 m, see COVERAGE.md")
    ap.add_argument("-o", "--out", type=Path,
                    help="write the run as JSON for a later comparison")
    ap.add_argument("--against", type=Path,
                    help="an earlier JSON run to compare against")
    args = ap.parse_args()

    for path in (args.video, args.gpx):
        if not path.exists():
            sys.exit(f"missing: {path}")

    run = measure(args.video, args.gpx, every_s=args.every_s,
                  section_m=args.section_m, severity=args.severity, sky=args.sky)
    previous = json.loads(args.against.read_text()) if args.against else None
    report(run, previous)

    if args.out:
        args.out.write_text(json.dumps(run, indent=2))
        print(f"\n  written to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
