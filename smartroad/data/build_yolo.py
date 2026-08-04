#!/usr/bin/env python3
"""Merge every annotated source into one YOLO detection dataset.

The sources disagree about almost everything -- Japanese D-codes, Persian
free text, bare Chinese class indices -- so the ASTM class taxonomy in
`smartroad.pci.astm` is the common ground. Each source's labels are translated
into that vocabulary via DATA/manifests/*.csv, which `DATA/build_manifests.py`
produces.

Two classes need explaining:

* `marking_manhole` is not an ASTM distress and never earns a deduct. It is
  trained anyway because faded paint and manhole covers are the things most
  easily mistaken for patches and potholes; giving the model a name for them
  is cheaper than filtering false positives later.
* `edge_crack` is absent. No source ships bounding boxes for it, and a class
  with no instances produces NaN metrics rather than an honest zero.

Images are symlinked by default so a rebuild costs no disk. Pass --copy to
materialise them (re-encoded and size-capped) for upload to Kaggle.
"""
from __future__ import annotations

import argparse
import collections
import csv
import os
import random
import shutil
from concurrent.futures import ProcessPoolExecutor, as_completed
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "DATA"
MANIFESTS = DATA / "manifests"
#: manifest `relpath` values are relative to DATA/, not the repository root.
IMAGE_BASE = DATA

#: YOLO class index -> (name, ASTM distress key or None)
CLASSES: list[tuple[str, str | None]] = [
    ("longitudinal_transverse_crack", "longitudinal_transverse_cracking"),
    ("alligator_crack", "alligator_cracking"),
    ("block_crack", "block_cracking"),
    ("patching", "patching_and_utility_cut_patching"),
    ("pothole", "potholes"),
    ("weathering_raveling", "weathering"),
    ("lane_shoulder_drop_off", "lane_shoulder_drop_off"),
    ("marking_manhole", None),
]
NAME_TO_ID = {name: i for i, (name, _) in enumerate(CLASSES)}

#: manifest `astm_class` -> YOLO class name
ASTM_TO_CLASS = {
    "longitudinal_transverse_cracking": "longitudinal_transverse_crack",
    "alligator_cracking": "alligator_crack",
    "block_cracking": "block_crack",
    "patching": "patching",
    "potholes": "pothole",
    "weathering_raveling": "weathering_raveling",
    "lane_shoulder_drop_off": "lane_shoulder_drop_off",
    "not_a_pci_distress": "marking_manhole",
}

#: RDD2018 is a predecessor of the RDD2022 Japan subset. No image is
#: byte-identical between them, but the scenes may overlap, so it is pinned to
#: train: a near-duplicate landing in val would quietly inflate the numbers we
#: use to decide whether the hackathon-day model beats the frozen backup.
TRAIN_ONLY_SOURCES = {"rdd2018_japan"}

SOURCES = ["rdd2022", "rdd2018_japan", "attain_tehran", "svrdd_streetview"]


def _image_size(path: Path, cache: dict[Path, tuple[int, int]]) -> tuple[int, int] | None:
    """Width/height, reading only the header. None if the image is unreadable."""
    if path in cache:
        return cache[path]
    try:
        with Image.open(path) as im:
            cache[path] = im.size
    except Exception:
        cache[path] = None  # type: ignore[assignment]
    return cache[path]


def _to_yolo(xmin, ymin, xmax, ymax, w, h):
    """Pixel corners -> normalised centre/size, clipped to the frame."""
    xmin, xmax = sorted((max(0.0, xmin), min(float(w), xmax)))
    ymin, ymax = sorted((max(0.0, ymin), min(float(h), ymax)))
    bw, bh = xmax - xmin, ymax - ymin
    if bw <= 1 or bh <= 1:  # degenerate after clipping
        return None
    return ((xmin + bw / 2) / w, (ymin + bh / 2) / h, bw / w, bh / h)


def collect() -> tuple[dict[str, list[tuple[int, float, float, float, float]]], dict[str, str], dict]:
    """Read every manifest into {image_path: [(cls, cx, cy, w, h), ...]}."""
    boxes: dict[str, list] = collections.defaultdict(list)
    origin: dict[str, str] = {}
    sizes: dict[Path, tuple[int, int]] = {}
    stats = collections.Counter()

    for source in SOURCES:
        path = MANIFESTS / f"{source}.csv"
        if not path.exists():
            print(f"  ! {source}.csv missing, skipping", file=sys.stderr)
            continue
        with path.open() as fh:
            for row in csv.DictReader(fh):
                cls_name = ASTM_TO_CLASS.get(row.get("astm_class", ""))
                if cls_name is None:
                    stats[f"{source}:unmapped"] += 1
                    continue
                img = IMAGE_BASE / row["relpath"]
                if not img.exists():
                    stats[f"{source}:missing_image"] += 1
                    continue
                if "cx" in row and row.get("cx"):
                    # SVRDD ships YOLO-normalised boxes already.
                    cx, cy, bw, bh = (float(row[k]) for k in ("cx", "cy", "w", "h"))
                    if not (0 < bw <= 1 and 0 < bh <= 1):
                        stats[f"{source}:bad_box"] += 1
                        continue
                    box = (cx, cy, bw, bh)
                else:
                    size = _image_size(img, sizes)
                    if size is None:
                        stats[f"{source}:missing_image"] += 1
                        continue
                    box = _to_yolo(
                        float(row["xmin"]), float(row["ymin"]),
                        float(row["xmax"]), float(row["ymax"]), *size,
                    )
                    if box is None:
                        stats[f"{source}:degenerate_box"] += 1
                        continue
                key = str(img)
                boxes[key].append((NAME_TO_ID[cls_name], *box))
                origin[key] = source
                stats[f"{source}:boxes"] += 1
    return boxes, origin, stats


def split(images: list[str], origin: dict[str, str], val_fraction: float, seed: int):
    """Per-source random split so every source is represented in val."""
    rng = random.Random(seed)
    by_source: dict[str, list[str]] = collections.defaultdict(list)
    for img in images:
        by_source[origin[img]].append(img)

    train, val = [], []
    for source, imgs in sorted(by_source.items()):
        imgs = sorted(imgs)
        rng.shuffle(imgs)
        if source in TRAIN_ONLY_SOURCES:
            train.extend(imgs)
            continue
        cut = int(len(imgs) * val_fraction)
        val.extend(imgs[:cut])
        train.extend(imgs[cut:])
    return sorted(train), sorted(val)


def materialise(src: Path, dst: Path, copy: bool, max_side: int, quality: int) -> None:
    if dst.exists() or dst.is_symlink():
        dst.unlink()
    if not copy:
        dst.symlink_to(src)
        return
    try:
        with Image.open(src) as im:
            im = im.convert("RGB")
            if max(im.size) > max_side:
                scale = max_side / max(im.size)
                im = im.resize((round(im.width * scale), round(im.height * scale)), Image.LANCZOS)
            im.save(dst, "JPEG", quality=quality, optimize=True)
    except Exception:
        shutil.copy2(src, dst)


def build(out: Path, val_fraction: float, seed: int, copy: bool, max_side: int, quality: int):
    print("reading manifests ...")
    boxes, origin, stats = collect()
    print(f"  {len(boxes)} images with at least one usable box")
    for key in sorted(stats):
        print(f"    {key}: {stats[key]}")

    train, val = split(list(boxes), origin, val_fraction, seed)
    print(f"\nsplit: {len(train)} train / {len(val)} val")

    for name, subset in (("train", train), ("val", val)):
        (out / "images" / name).mkdir(parents=True, exist_ok=True)
        (out / "labels" / name).mkdir(parents=True, exist_ok=True)
        seen: set[str] = set()
        jobs: list[tuple[Path, Path]] = []
        for i, img in enumerate(subset, 1):
            src = Path(img)
            # Sources reuse filenames (Japan_000001.jpg exists twice), so the
            # stem is prefixed with its source to keep the flat folder unique.
            stem = f"{origin[img]}__{src.stem}"
            if stem in seen:
                stem = f"{stem}_{i}"
            seen.add(stem)
            jobs.append((src, out / "images" / name / f"{stem}.jpg"))
            lines = [f"{c} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}" for c, cx, cy, w, h in boxes[img]]
            (out / "labels" / name / f"{stem}.txt").write_text("\n".join(lines) + "\n")

        if copy:
            # Re-encoding tens of thousands of JPEGs is the slow part; spread it
            # over the cores rather than waiting half an hour on one.
            with ProcessPoolExecutor() as pool:
                futures = [pool.submit(materialise, s, d, True, max_side, quality)
                           for s, d in jobs]
                for i, fut in enumerate(as_completed(futures), 1):
                    fut.result()
                    if i % 5000 == 0:
                        print(f"  {name}: {i}/{len(jobs)}")
        else:
            for i, (s, d) in enumerate(jobs, 1):
                materialise(s, d, False, max_side, quality)
                if i % 10000 == 0:
                    print(f"  {name}: {i}/{len(jobs)}")

    yaml = out / "data.yaml"
    yaml.write_text(
        "# Smart Road unified road-distress dataset\n"
        "# Generated by smartroad/data/build_yolo.py -- do not edit by hand.\n"
        f"path: {out.resolve()}\n"
        "train: images/train\n"
        "val: images/val\n"
        f"nc: {len(CLASSES)}\n"
        "names:\n" + "".join(f"  {i}: {n}\n" for i, (n, _) in enumerate(CLASSES))
    )
    print(f"\nwrote {yaml}")
    return train, val, boxes


def report(out: Path, train, val, boxes):
    print("\nclass distribution")
    print(f"  {'class':32s} {'train':>8s} {'val':>8s}")
    counts = {"train": collections.Counter(), "val": collections.Counter()}
    for name, subset in (("train", train), ("val", val)):
        for img in subset:
            for c, *_ in boxes[img]:
                counts[name][c] += 1
    for i, (name, _) in enumerate(CLASSES):
        print(f"  {name:32s} {counts['train'][i]:8d} {counts['val'][i]:8d}")
    print(f"  {'TOTAL':32s} {sum(counts['train'].values()):8d} {sum(counts['val'].values()):8d}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=ROOT / "DATA" / "yolo")
    ap.add_argument("--val-fraction", type=float, default=0.10)
    ap.add_argument("--seed", type=int, default=1337)
    ap.add_argument("--copy", action="store_true",
                    help="re-encode images instead of symlinking (for Kaggle upload)")
    ap.add_argument("--max-side", type=int, default=1024)
    ap.add_argument("--quality", type=int, default=88)
    args = ap.parse_args()

    if args.out.exists():
        shutil.rmtree(args.out)
    train, val, boxes = build(args.out, args.val_fraction, args.seed,
                              args.copy, args.max_side, args.quality)
    report(args.out, train, val, boxes)


if __name__ == "__main__":
    main()
