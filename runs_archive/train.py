#!/usr/bin/env python3
"""Sequential training on one 32 GB card.

Kaggle forced batch 6 at 1024 to fit a 16 GB T4, which meant 6,833 iterations
an epoch and about four epochs inside the session limit. With 32 GB the batch is
what changes: 1024 at batch 24 is 1,708 iterations over the same data.

Bounded by convergence rather than a clock -- `patience` stops training when the
metric stops moving, so a generous epoch budget costs nothing if the model
plateaus early. The high-resolution job runs first: thin distant cracks survive
a 1024 resize and vanish at 640, so if anything goes wrong partway, that is the
model worth having.

The dataset declares ten classes but only eight carry labels; `edge_crack` and
`bumps_and_sags` are reserved so that boxes drawn later drop in without resizing
the detection head and forfeiting its trained weights.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

WORK = Path("/workspace")
RUNS = WORK / "runs"
DATA = WORK / "data" / "data.yaml"

JOBS = [
    {"name": "yolo11m_1024", "model": "yolo11m.pt", "imgsz": 1024, "batch": 24},
    {"name": "yolo11l_640", "model": "yolo11l.pt", "imgsz": 640, "batch": 32},
]

TRAIN_ARGS = dict(
    epochs=150,
    device=0,
    amp=True,          # fp16
    workers=12,        # 24 cores allocated; leave headroom for the main process
    cache=False,
    optimizer="AdamW",
    lr0=0.001,
    cos_lr=True,
    patience=30,       # stop when the metric stops improving
    seed=1337,
    close_mosaic=10,   # final epochs on undistorted images
    copy_paste=0.3,    # helps the rare classes
    mixup=0.1,
    exist_ok=True,
    plots=True,
    val=True,
)


def build(job: dict) -> list[str]:
    args = dict(TRAIN_ARGS, data=str(DATA), imgsz=job["imgsz"], batch=job["batch"],
                project=str(RUNS), name=job["name"])
    kwargs = ", ".join(f"{k}={v!r}" for k, v in args.items())
    return [sys.executable, "-c",
            f"from ultralytics import YOLO; YOLO({job['model']!r}).train({kwargs})"]


def run(job: dict) -> int:
    log = WORK / f"{job['name']}.log"
    print(f"START {job['name']}  {job['model']} @ {job['imgsz']} batch {job['batch']} -> {log}",
          flush=True)
    t0 = time.time()
    with log.open("w") as fh:
        proc = subprocess.Popen(build(job), stdout=fh, stderr=subprocess.STDOUT)
        proc.wait()
    print(f"END   {job['name']}  rc={proc.returncode}  {(time.time()-t0)/60:.1f} min", flush=True)
    return proc.returncode


def main() -> None:
    results: dict[str, dict] = {}
    for job in JOBS:
        rc = run(job)
        best = RUNS / job["name"] / "weights" / "best.pt"
        results[job["name"]] = {
            "returncode": rc,
            "weights": str(best) if best.exists() else None,
            "imgsz": job["imgsz"],
            "batch": job["batch"],
        }
        (WORK / "train_results.json").write_text(json.dumps(results, indent=2))
    print(json.dumps(results, indent=2), flush=True)


if __name__ == "__main__":
    main()
