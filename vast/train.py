#!/usr/bin/env python3
"""Train the Smart Road detectors on a single large-VRAM GPU.

Different shape from the Kaggle script. There the constraint was two 16 GB
cards, so two jobs ran side by side with batch sizes squeezed to fit -- and the
1024 job ended up at batch 6, which meant 6,833 iterations per epoch and about
four epochs inside the session limit. Useless.

With 32 GB the batch is the thing that changes: 1024 at batch 24 is 1,708
iterations per epoch, a quarter of the work for the same data. So the jobs run
sequentially, each with the whole card, and the high-resolution model goes first
because it is the one that matters -- thin distant cracks survive a 1024 resize
and vanish at 640.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

WORK = Path("/workspace")
RUNS = WORK / "runs"

#: Ordered by value: if the budget runs out, the first one is the keeper.
JOBS = [
    {"name": "yolo11m_1024", "model": "yolo11m.pt", "imgsz": 1024, "batch": 24, "hours": 5.0},
    {"name": "yolo11s_640", "model": "yolo11s.pt", "imgsz": 640, "batch": 64, "hours": 2.0},
]


def find_data() -> Path:
    matches = sorted(WORK.rglob("data.yaml"))
    if not matches:
        sys.exit("no data.yaml under /workspace -- run setup.sh first")
    return matches[0]


def run(job: dict, data: Path, workers: int, seed: int) -> int:
    cmd = [
        sys.executable, "-c",
        "from ultralytics import YOLO;"
        f"YOLO({job['model']!r}).train("
        f"data={str(data)!r},"
        "epochs=300,"
        f"time={job['hours']},"
        f"imgsz={job['imgsz']},"
        f"batch={job['batch']},"
        "device=0,"
        "amp=True,"
        f"workers={workers},"
        "cache=False,"
        "optimizer='AdamW',"
        "lr0=0.001,"
        "cos_lr=True,"
        "patience=30,"
        f"seed={seed},"
        "close_mosaic=10,"
        "copy_paste=0.3,"
        "mixup=0.1,"
        f"project={str(RUNS)!r},"
        f"name={job['name']!r},"
        "exist_ok=True,plots=True,val=True)"
    ]
    log = WORK / f"{job['name']}.log"
    print(f"\n=== {job['name']}: {job['model']} @ {job['imgsz']}, "
          f"batch {job['batch']}, {job['hours']}h -> {log}", flush=True)
    t0 = time.time()
    with log.open("w") as fh:
        proc = subprocess.Popen(cmd, stdout=fh, stderr=subprocess.STDOUT)
        while proc.poll() is None:
            time.sleep(120)
            tail = log.read_text(errors="replace").strip().splitlines()[-1:] or [""]
            print(f"[{(time.time()-t0)/60:6.1f} min] {tail[0][:150]}", flush=True)
    print(f"{job['name']} finished with {proc.returncode} "
          f"after {(time.time()-t0)/60:.1f} min", flush=True)
    return proc.returncode


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--workers", type=int, default=16,
                    help="dataloader workers; this box has 32 cores")
    ap.add_argument("--seed", type=int, default=1337)
    ap.add_argument("--only", choices=[j["name"] for j in JOBS])
    args = ap.parse_args()

    data = find_data()
    print(f"data.yaml: {data}", flush=True)
    results = {}
    for job in JOBS:
        if args.only and job["name"] != args.only:
            continue
        code = run(job, data, args.workers, args.seed)
        best = RUNS / job["name"] / "weights" / "best.pt"
        results[job["name"]] = {
            "returncode": code,
            "weights": str(best) if best.exists() else None,
            "imgsz": job["imgsz"],
            "batch": job["batch"],
        }
        (WORK / "train_results.json").write_text(json.dumps(results, indent=2))
    print(json.dumps(results, indent=2), flush=True)


if __name__ == "__main__":
    main()
