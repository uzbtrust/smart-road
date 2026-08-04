"""Resumable download of a Kaggle dataset archive.

The official client has no resume: a stalled transfer restarts from zero, which
on a multi-gigabyte archive over an unreliable link can mean never finishing.
This uses the legacy REST endpoint directly with HTTP range requests, so an
interrupted run picks up where it stopped.

A stall is treated as a failure rather than waited on -- the observed symptom is
a connection that stays open while no bytes arrive, which no timeout on the
overall request would catch. Progress is checked continuously and the connection
is dropped and reopened if it goes quiet.

    .venv/bin/python tools/kaggle_fetch.py uzbtrust/smartroad-yolo -o DATA/kaggle_restore
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import socket
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = "https://www.kaggle.com/api/v1"
CHUNK = 1 << 20          # 1 MiB
STALL_SECONDS = 45       # no bytes for this long -> reconnect
CONNECT_TIMEOUT = 60


def credentials() -> tuple[str, str]:
    path = Path(os.path.expanduser("~/.kaggle/kaggle.json"))
    if not path.is_file():
        raise SystemExit(f"{path} topilmadi")
    cfg = json.loads(path.read_text())
    return cfg["username"], cfg["key"]


def opener(user: str, key: str):
    token = base64.b64encode(f"{user}:{key}".encode()).decode()
    return {"Authorization": f"Basic {token}", "User-Agent": "Kaggle/1.6.17"}


def human(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if abs(n) < 1024:
            return f"{n:.1f}{unit}"
        n /= 1024
    return f"{n:.1f}TB"


def fetch(dataset: str, out_dir: Path, tries: int = 40) -> Path:
    user, key = credentials()
    headers = opener(user, key)
    url = f"{BASE}/datasets/download/{dataset}"
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"{dataset.split('/')[-1]}.zip"
    part = target.with_suffix(".zip.part")

    total: int | None = None
    for attempt in range(1, tries + 1):
        have = part.stat().st_size if part.exists() else 0
        if total is not None and have >= total:
            break

        req = urllib.request.Request(url, headers={**headers, "Range": f"bytes={have}-"})
        try:
            resp = urllib.request.urlopen(req, timeout=CONNECT_TIMEOUT)
        except urllib.error.HTTPError as exc:
            if exc.code == 416 and total is not None and have >= total:
                break
            print(f"  [{attempt}] HTTP {exc.code}, 5 s dan keyin qayta", flush=True)
            time.sleep(5)
            continue
        except (urllib.error.URLError, socket.timeout, OSError) as exc:
            print(f"  [{attempt}] ulanmadi ({exc}), 5 s dan keyin qayta", flush=True)
            time.sleep(5)
            continue

        with resp:
            if total is None:
                rng = resp.headers.get("Content-Range")
                if rng and "/" in rng:
                    total = int(rng.rsplit("/", 1)[1])
                elif resp.headers.get("Content-Length"):
                    total = have + int(resp.headers["Content-Length"])
                print(f"  jami hajm: {human(total) if total else '?'}", flush=True)

            # A 200 to a range request means the server ignored it: start over.
            mode = "ab" if resp.status == 206 and have else "wb"
            if mode == "wb":
                have = 0

            last_data = time.time()
            last_report = 0.0
            start_bytes = have
            t0 = time.time()
            with open(part, mode) as fh:
                while True:
                    try:
                        resp.fp.raw._sock.settimeout(STALL_SECONDS)
                    except AttributeError:
                        pass
                    try:
                        chunk = resp.read(CHUNK)
                    except (socket.timeout, TimeoutError, OSError):
                        print(f"  [{attempt}] oqim to'xtadi ({human(have)}), qayta ulanaman",
                              flush=True)
                        break
                    if not chunk:
                        break
                    fh.write(chunk)
                    have += len(chunk)
                    last_data = time.time()
                    now = time.time()
                    if now - last_report > 10:
                        last_report = now
                        rate = (have - start_bytes) / max(now - t0, 1e-9)
                        pct = f"{100 * have / total:5.1f}%" if total else "  ?  "
                        eta = ((total - have) / rate) if total and rate > 0 else 0
                        print(f"  {pct}  {human(have)}"
                              + (f" / {human(total)}" if total else "")
                              + f"  {human(rate)}/s  qoldi ~{eta/60:.0f} daq", flush=True)

        if total is not None and part.stat().st_size >= total:
            break
        time.sleep(2)

    size = part.stat().st_size if part.exists() else 0
    if total is not None and size < total:
        raise SystemExit(f"tugallanmadi: {human(size)} / {human(total)}")
    part.rename(target)
    print(f"yuklandi: {target}  {human(target.stat().st_size)}")
    return target


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("dataset", help="owner/slug")
    ap.add_argument("-o", "--out", type=Path, default=Path("."))
    args = ap.parse_args()
    fetch(args.dataset, args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
