"""Pull training metrics out of an Ultralytics run directory.

Two sources, because neither alone is enough:

* `results.csv` gives the per-epoch curve but only aggregate metrics.
* the job log holds the final per-class validation table, which is the part
  that actually matters here -- an overall mAP hides that block_crack has
  61 training boxes and cannot possibly work yet.
"""
from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from pathlib import Path

#: Ultralytics prints the final table as
#:     Class  Images  Instances  Box(P  R  mAP50  mAP50-95)
#: with the class name possibly containing underscores but never spaces.
_ROW = re.compile(
    r"^\s*(?P<name>[A-Za-z_][\w/]*)\s+"
    r"(?P<images>\d+)\s+(?P<instances>\d+)\s+"
    r"(?P<p>[\d.]+)\s+(?P<r>[\d.]+)\s+"
    r"(?P<map50>[\d.]+)\s+(?P<map>[\d.]+)\s*$"
)
_ANSI = re.compile(r"\x1b\[[0-9;]*m")


@dataclass
class ClassMetrics:
    name: str
    images: int
    instances: int
    precision: float
    recall: float
    map50: float
    map50_95: float


@dataclass
class RunMetrics:
    name: str
    epochs: int = 0
    classes: list[ClassMetrics] = field(default_factory=list)
    curve: list[dict] = field(default_factory=list)

    @property
    def overall(self) -> ClassMetrics | None:
        return next((c for c in self.classes if c.name == "all"), None)

    @property
    def per_class(self) -> list[ClassMetrics]:
        return [c for c in self.classes if c.name != "all"]


def parse_log(path: Path) -> list[ClassMetrics]:
    """Final per-class validation table from a training log.

    Ultralytics prints a table after every validation pass; the last complete
    block is the one describing the best weights, so later blocks win.
    """
    found: dict[str, ClassMetrics] = {}
    for raw in path.read_text(errors="replace").splitlines():
        line = _ANSI.sub("", raw)
        m = _ROW.match(line)
        if not m:
            continue
        g = m.groupdict()
        # `all` restarting a block means a fresh table; drop the previous one.
        if g["name"] == "all" and found:
            found = {}
        found[g["name"]] = ClassMetrics(
            name=g["name"],
            images=int(g["images"]),
            instances=int(g["instances"]),
            precision=float(g["p"]),
            recall=float(g["r"]),
            map50=float(g["map50"]),
            map50_95=float(g["map"]),
        )
    return list(found.values())


def parse_curve(path: Path) -> list[dict]:
    """Per-epoch metrics from results.csv, keys normalised."""
    rows: list[dict] = []
    with path.open() as fh:
        for row in csv.DictReader(fh):
            clean = {k.strip(): v.strip() for k, v in row.items() if k}
            def num(*names, default=0.0):
                for n in names:
                    if n in clean and clean[n] not in ("", "nan"):
                        try:
                            return float(clean[n])
                        except ValueError:
                            pass
                return default
            rows.append({
                "epoch": int(num("epoch")),
                "map50": num("metrics/mAP50(B)"),
                "map50_95": num("metrics/mAP50-95(B)"),
                "precision": num("metrics/precision(B)"),
                "recall": num("metrics/recall(B)"),
                "box_loss": num("train/box_loss"),
                "cls_loss": num("train/cls_loss"),
            })
    return rows


def load_run(run_dir: Path, log: Path | None = None) -> RunMetrics:
    metrics = RunMetrics(name=run_dir.name)
    csv_path = run_dir / "results.csv"
    if csv_path.exists():
        metrics.curve = parse_curve(csv_path)
        metrics.epochs = len(metrics.curve)
    if log and log.exists():
        metrics.classes = parse_log(log)
    return metrics


def load_all(output_dir: Path) -> list[RunMetrics]:
    """Every run under a downloaded Kaggle kernel output directory."""
    runs = []
    for run_dir in sorted((output_dir / "runs").glob("*")):
        if not run_dir.is_dir():
            continue
        log = output_dir / f"{run_dir.name}.log"
        runs.append(load_run(run_dir, log if log.exists() else None))
    return runs
