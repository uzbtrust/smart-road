#!/usr/bin/env python3
"""Print how well the collected datasets cover the 19 ASTM D6433 asphalt distresses.

PCI needs three things per distress: the type, an L/M/H severity, and a physical
quantity. A dataset only contributes a quantity if it carries masks/polygons --
a bounding box gives an extent, not an area -- so those axes are reported apart.
"""
import csv, os, collections

ROOT = os.path.dirname(os.path.abspath(__file__))
MAN = os.path.join(ROOT, "manifests")

ASTM_ORDER = [
    ("alligator_cracking", 1, "m2"), ("bleeding", 2, "m2"),
    ("block_cracking", 3, "m2"), ("bumps_and_sags", 4, "m"),
    ("corrugation", 5, "m2"), ("depression", 6, "m2"),
    ("edge_cracking", 7, "m"), ("joint_reflection_cracking", 8, "m"),
    ("lane_shoulder_drop_off", 9, "m"),
    ("longitudinal_transverse_cracking", 10, "m"),
    ("patching", 11, "m2"), ("polished_aggregate", 12, "m2"),
    ("potholes", 13, "count"), ("railroad_crossing", 14, "m2"),
    ("rutting", 15, "m2"), ("shoving", 16, "m2"),
    ("slippage_cracking", 17, "m2"), ("swell", 18, "m2"),
    ("weathering_raveling", 19, "m2"),
]

# manifest -> (short label, does it carry severity?, annotation granularity)
SOURCES = [
    ("qoplama_tashkent.csv", "QOPLAMA", False, "image-class"),
    ("rdd2018_japan.csv",    "RDD2018", False, "bbox"),
    ("rdd2022.csv",          "RDD2022", False, "bbox"),
    ("attain_tehran.csv",    "Attain",  True,  "bbox+poly"),
    ("svrdd_streetview.csv", "SVRDD",   False, "bbox"),
]


def load(fn):
    p = os.path.join(MAN, fn)
    if not os.path.exists(p):
        return []
    with open(p) as fh:
        return list(csv.DictReader(fh))


counts = collections.defaultdict(dict)   # astm_class -> source -> n instances
sev = collections.defaultdict(collections.Counter)
present = []

for fn, label, has_sev, gran in SOURCES:
    rows = load(fn)
    if not rows:
        continue
    present.append((label, len(rows), gran, has_sev))
    for r in rows:
        c = r.get("astm_class", "")
        if not c or c in ("unknown", "unmapped", "not_a_pci_distress"):
            continue
        counts[c][label] = counts[c].get(label, 0) + 1
        if has_sev and r.get("severity"):
            sev[c][r["severity"]] += 1

print("=" * 92)
print("SOURCES")
print("=" * 92)
for label, n, gran, hs in present:
    print(f"  {label:10s} {n:7d} annotated instances   granularity={gran:11s} severity={'YES' if hs else 'no'}")

labels = [p[0] for p in present]
print()
print("=" * 92)
print("ASTM D6433 ASPHALT DISTRESS COVERAGE")
print("=" * 92)
hdr = f"{'#':>3} {'distress':34s} {'unit':>5s} " + " ".join(f"{l:>8s}" for l in labels) + f"  {'severity L/H':>14s}"
print(hdr)
print("-" * len(hdr))

covered = 0
for name, num, unit in ASTM_ORDER:
    row = counts.get(name, {})
    if row:
        covered += 1
    cells = " ".join(f"{row.get(l, 0):8d}" for l in labels)
    s = sev.get(name)
    sv = f"{s.get('low',0)}/{s.get('high',0)}" if s else "-"
    mark = " " if row else "*"
    print(f"{num:3d} {name:34s} {unit:>5s} {cells}  {sv:>14s} {mark}")

print("-" * len(hdr))
print(f"Covered by at least one dataset: {covered}/19   (* = no data at all)")
print()
print("Severity note: Attain labels only Low and High -- no Medium anywhere in the")
print("collection, so the M band has to be derived (crack width) or hand-labelled.")
print()
print("Quantity note: only Attain OS_v1 polygons and CrackSeg9k/Pothole-600 masks give")
print("pixel areas. Everything else is boxes, which cannot yield ASTM m2/m directly.")
