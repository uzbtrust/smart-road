#!/usr/bin/env python3
"""Kaggle entry point: install ultralytics, train both detectors, archive weights.

`kaggle kernels push` uploads a single code file, so the training logic travels
with the dataset (train_detector.py sits next to data.yaml) and is copied out
here. The search is recursive and prints what it actually found: the first run
failed with "not found" and no way to tell whether the dataset was mounted
somewhere unexpected or the file had simply not been uploaded.
"""
import shutil
import subprocess
import sys
from pathlib import Path

WORKING = Path("/kaggle/working")
INPUT = Path("/kaggle/input")

print("=== /kaggle/input tree (depth 2) ===", flush=True)
for entry in sorted(INPUT.glob("*")):
    print(f"  {entry}", flush=True)
    if entry.is_dir():
        for child in sorted(entry.glob("*"))[:20]:
            marker = "/" if child.is_dir() else ""
            print(f"      {child.name}{marker}", flush=True)

subprocess.run([sys.executable, "-m", "pip", "install", "-q", "ultralytics==8.3.155"], check=True)

subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv"], check=False)

# The trainer lives in its own few-KB dataset so it can be re-versioned without
# re-uploading 4.4 GB of imagery. An older copy also sits inside the image
# dataset; prefer smartroad-code so the two cannot drift apart.
trainers = sorted(INPUT.rglob("train_detector.py"))
trainers.sort(key=lambda p: "smartroad-code" not in str(p))
print(f"\nfound {len(trainers)} trainer(s): {trainers}", flush=True)
if not trainers:
    sys.exit("train_detector.py not present in any attached dataset -- see tree above")

trainer = WORKING / "train_detector.py"
shutil.copy(trainers[0], trainer)
print(f"using {trainers[0]}", flush=True)

# data.yaml is located here and passed explicitly rather than left to the
# trainer to find. Kaggle mounts datasets at /kaggle/input/datasets/<owner>/<slug>/,
# and the trainer copy shipped inside the dataset predates that discovery --
# re-uploading 4.4 GB just to fix its glob would be absurd.
yamls = sorted(INPUT.rglob("data.yaml"))
print(f"found {len(yamls)} data.yaml: {yamls}", flush=True)
if not yamls:
    sys.exit("no data.yaml in any attached dataset -- see tree above")

subprocess.run(
    [sys.executable, str(trainer), "--hours", "5", "--data", str(yamls[0])], check=True
)

# Surface the best checkpoints at the top of /kaggle/working so the run output
# can be saved straight into a Kaggle Dataset as the frozen backup.
for run in sorted((WORKING / "runs").glob("*/weights/best.pt")):
    target = WORKING / f"{run.parent.parent.name}_best.pt"
    shutil.copy(run, target)
    print("archived", target, target.stat().st_size // 1024 // 1024, "MB", flush=True)
