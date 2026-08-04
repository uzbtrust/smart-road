#!/usr/bin/env python3
"""Train the Smart Road distress detector on Kaggle's 2x Tesla T4.

Runs two *independent* single-GPU jobs rather than one DDP job. Ultralytics DDP
is known to hang on Kaggle (ultralytics#3904, #7843, #24675) and debugging a
hang burns the weekly GPU quota. Two processes, one per card, cannot deadlock on
NCCL and hand us two heterogeneous models -- which is what we want anyway, since
ensembling different architectures is what separated first place from tenth in
CRDDC'2022.

Each job is pinned by passing Ultralytics an explicit physical `device` index.
CUDA_VISIBLE_DEVICES does not work here: select_device() rewrites it from the
`device` argument, so setting it in the child's environment is silently undone.

T4 has no bf16, so AMP means fp16.

Usage on Kaggle (GPU T4 x2, internet on):
    !pip install -q ultralytics
    !python train_detector.py --hours 5
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

# Kaggle mounts attached datasets read-only under /kaggle/input.
KAGGLE_INPUT = Path("/kaggle/input")
WORKING = Path("/kaggle/working")

#: Two jobs, one per card. Different sizes and input resolutions so the
#: ensemble sees different failure modes: the 1024 job exists to catch the thin
#: distant cracks that get lost when a frame is squeezed to 640.
#:
#: Both are bounded by wall-clock rather than epoch count. Kaggle kills a
#: session at 12 hours, and 41k images through YOLO11-l at 640 is roughly ten
#: minutes an epoch on one T4 -- an epoch budget that looked reasonable would
#: have been cut off mid-run with nothing saved. `time` lets Ultralytics scale
#: the schedule to fit and still finish cleanly.
JOBS = [
    {"name": "yolo11s_640", "model": "yolo11s.pt", "imgsz": 640, "batch": 24, "gpu": 0},
    {"name": "yolo11m_1024", "model": "yolo11m.pt", "imgsz": 1024, "batch": 6, "gpu": 1},
]


def find_data_yaml(explicit: str | None) -> Path:
    if explicit:
        p = Path(explicit)
        if not p.exists():
            sys.exit(f"data.yaml not found at {p}")
        return p
    # Kaggle nests dataset mounts as /kaggle/input/datasets/<owner>/<slug>/,
    # so search the whole tree rather than guessing a depth.
    candidates = sorted(KAGGLE_INPUT.rglob("data.yaml"))
    if not candidates:
        sys.exit(f"no data.yaml under {KAGGLE_INPUT}; attach the dataset to the notebook")
    return candidates[0]


def rewrite_paths(data_yaml: Path) -> Path:
    """Point data.yaml at wherever Kaggle actually mounted the dataset.

    The file is generated locally with an absolute `path:` that does not exist
    on Kaggle, and /kaggle/input is read-only, so write a corrected copy.
    """
    text = data_yaml.read_text()
    out_lines = []
    for line in text.splitlines():
        if line.startswith("path:"):
            out_lines.append(f"path: {data_yaml.parent}")
        else:
            out_lines.append(line)
    fixed = WORKING / "data.yaml"
    fixed.write_text("\n".join(out_lines) + "\n")
    return fixed


def available_gpus() -> list[str]:
    """Names of the visible CUDA devices, empty if none or torch is missing."""
    try:
        import torch
    except ImportError:
        return []
    if not torch.cuda.is_available():
        return []
    return [torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())]


def assign_gpus(jobs: list[dict]) -> list[dict]:
    """Bind jobs to the cards that actually exist.

    Kaggle hands out whatever accelerator is free unless `machine_shape` pins
    it, and a run once landed on a single Tesla P100 -- whose sm_60 the stock
    PyTorch no longer builds for. Both jobs then died on `no kernel image is
    available`. Checking up front turns that into one clear message instead of
    two stack traces, and drops surplus jobs rather than pointing them at a
    device index that is not there.
    """
    gpus = available_gpus()
    print(f"visible GPUs ({len(gpus)}): {gpus or 'none'}", flush=True)
    if not gpus:
        sys.exit("no CUDA device visible -- enable a GPU accelerator on the notebook")

    unsupported = [g for g in gpus if "P100" in g or "K80" in g]
    if unsupported:
        sys.exit(
            f"accelerator {unsupported[0]} is too old for the installed PyTorch "
            "(needs compute capability >= 7.0). Set machine_shape=NvidiaTeslaT4 "
            "in kernel-metadata.json and re-push."
        )

    if len(jobs) > len(gpus):
        dropped = [j["name"] for j in jobs[len(gpus):]]
        print(f"only {len(gpus)} GPU(s); dropping {dropped}", flush=True)
        jobs = jobs[: len(gpus)]
    for i, job in enumerate(jobs):
        job["gpu"] = i
    return jobs


def build_command(job: dict, data_yaml: Path, hours: float, epochs: int, patience: int, seed: int) -> list[str]:
    return [
        sys.executable, "-c",
        (
            "from ultralytics import YOLO;"
            f"m=YOLO({job['model']!r});"
            "m.train("
            f"data={str(data_yaml)!r},"
            f"epochs={epochs},"
            f"time={hours},"
            f"imgsz={job['imgsz']},"
            f"batch={job['batch']},"
            # Physical index, not 0. Ultralytics' select_device() rewrites
            # CUDA_VISIBLE_DEVICES from this argument, so pinning the card
            # through the environment does not survive -- an earlier run put
            # both jobs on GPU 0 and they OOMed against each other.
            f"device={job['gpu']},"
            "amp=True,"              # fp16: T4 has no bf16
            "cache=False,"
            "workers=2,"
            "optimizer='AdamW',"
            "lr0=0.001,"
            "cos_lr=True,"
            f"patience={patience},"
            f"seed={seed},"
            "close_mosaic=10,"       # last epochs on undistorted images
            "copy_paste=0.3,"        # helps the rare classes (block_crack, pothole)
            "mixup=0.1,"
            "project='/kaggle/working/runs',"
            f"name={job['name']!r},"
            "exist_ok=True,"
            "plots=True,"
            "val=True"
            ")"
        ),
    ]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--hours", type=float, default=5.0,
                    help="wall-clock budget per job; both run in parallel")
    ap.add_argument("--epochs", type=int, default=200,
                    help="upper bound; --hours normally stops it first")
    ap.add_argument("--patience", type=int, default=15)
    ap.add_argument("--seed", type=int, default=1337)
    ap.add_argument("--data", default=None, help="path to data.yaml (auto-detected on Kaggle)")
    ap.add_argument("--only", choices=[j["name"] for j in JOBS], help="run a single job")
    args = ap.parse_args()

    data_yaml = rewrite_paths(find_data_yaml(args.data))
    print(f"data.yaml -> {data_yaml}\n{data_yaml.read_text()}", flush=True)

    jobs = [j for j in JOBS if args.only is None or j["name"] == args.only]
    jobs = assign_gpus(jobs)
    procs = []
    for job in jobs:
        log = WORKING / f"{job['name']}.log"
        print(f"launching {job['name']} on GPU {job['gpu']} -> {log}", flush=True)
        procs.append((
            job,
            subprocess.Popen(
                build_command(job, data_yaml, args.hours, args.epochs, args.patience, args.seed),
                stdout=log.open("w"), stderr=subprocess.STDOUT,
            ),
            log,
        ))

    # Stream a heartbeat so a silent Kaggle session is distinguishable from a hang.
    start = time.time()
    while any(p.poll() is None for _, p, _ in procs):
        time.sleep(120)
        elapsed = (time.time() - start) / 60
        states = " ".join(
            f"{j['name']}={'running' if p.poll() is None else f'exit {p.returncode}'}"
            for j, p, _ in procs
        )
        print(f"[{elapsed:6.1f} min] {states}", flush=True)
        for _, _, log in procs:
            tail = log.read_text().strip().splitlines()[-1:] or [""]
            print(f"    {log.stem}: {tail[0][:140]}", flush=True)

    results = {}
    for job, proc, log in procs:
        ok = proc.returncode == 0
        print(f"\n=== {job['name']}: {'OK' if ok else f'FAILED ({proc.returncode})'} ===", flush=True)
        print("\n".join(log.read_text().splitlines()[-25:]), flush=True)
        best = WORKING / "runs" / job["name"] / "weights" / "best.pt"
        results[job["name"]] = {
            "returncode": proc.returncode,
            "weights": str(best) if best.exists() else None,
            "imgsz": job["imgsz"],
            "model": job["model"],
        }
    (WORKING / "train_results.json").write_text(json.dumps(results, indent=2))
    print("\nwrote /kaggle/working/train_results.json", flush=True)

    if any(r["returncode"] != 0 for r in results.values()):
        sys.exit("at least one training job failed")


if __name__ == "__main__":
    main()
