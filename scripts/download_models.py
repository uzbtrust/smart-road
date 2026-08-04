"""Fetch the trained weights from Hugging Face into models/.

    python scripts/download_models.py            # the recommended checkpoint
    python scripts/download_models.py --all      # every checkpoint

app.py downloads on first use anyway; this is for running offline afterwards,
or for pulling the `last` checkpoints to fine-tune from.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

REPO = "uzbtrust/smart-road-pci-yolo11"
MODELS = Path(__file__).resolve().parents[1] / "models"

RECOMMENDED = "yolo11l_640_best.pt"
ALL_FILES = (
    "yolo11l_640_best.pt",     # best epoch (113) -- use this
    "yolo11l_640_last.pt",     # final epoch (143) -- resume or fine-tune
    "yolo11m_1024_best.pt",
    "yolo11m_1024_last.pt",
)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--all", action="store_true", help="all four checkpoints, not just one")
    args = ap.parse_args()

    try:
        from huggingface_hub import hf_hub_download
    except ImportError:
        sys.exit("huggingface_hub is missing: pip install -r requirements.txt")

    MODELS.mkdir(parents=True, exist_ok=True)
    for name in (ALL_FILES if args.all else (RECOMMENDED,)):
        target = MODELS / name
        if target.exists():
            print(f"  have {name}")
            continue
        print(f"  fetching {name} …")
        cached = hf_hub_download(REPO, name)
        # Copy out of the cache so the tree survives a `huggingface-cli delete-cache`.
        shutil.copy(cached, target)
        print(f"  saved {target.relative_to(MODELS.parent)}  "
              f"{target.stat().st_size / 1e6:.0f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
