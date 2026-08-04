#!/usr/bin/env python3
"""Live training dashboard for the vast.ai run.

Serves a single page showing where the training has got to -- epoch, metrics,
GPU, time left -- for glancing at from a phone. Deliberately not a log viewer:
Ultralytics rewrites its progress bar with carriage returns, so a raw tail is
unreadable on a small screen and says less than four parsed numbers.

Each poll asks for the last few kB of the log over a shared SSH connection
rather than following it as a stream. Streaming looked cheaper but could fall
behind the writer without any sign of it; reading the tail is stateless and
therefore always current.

    python bin/dashboard.py            # http://localhost:8899
    python bin/dashboard.py --port 9000 --interval 30
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

# The training box is rented per run, so its address is configuration, not a
# constant: export SMARTROAD_HOST / SMARTROAD_PORT before starting.
HOST = os.environ.get("SMARTROAD_HOST", "root@127.0.0.1")
PORT = int(os.environ.get("SMARTROAD_PORT", "22"))
KEY = os.environ.get("SMARTROAD_SSH_KEY", str(Path.home() / ".ssh" / "id_ed25519_vast"))
REPORT = Path(__file__).resolve().parents[1] / "reports" / "training.html"

SSH = ["ssh", "-p", str(PORT), "-i", KEY, "-o", "BatchMode=yes",
       "-o", "ServerAliveInterval=30", "-o", "StrictHostKeyChecking=accept-new", HOST]
CONTROL_PATH = "/tmp/.smartroad-ssh-%r@%h:%p"

# "   30/150   29.3G   1.493  1.536  1.57   56   1024:  40%|##| 681/1709 [06:12<09:19, 1.84it/s]"
PROGRESS = re.compile(
    r"^\s*(?P<epoch>\d+)/(?P<epochs>\d+)\s+(?P<mem>[\d.]+)G\s+"
    r"(?P<box>[\d.]+)\s+(?P<cls>[\d.]+)\s+(?P<dfl>[\d.]+)\s+\d+\s+\d+:\s*"
    r"(?P<pct>\d+)%\|[^|]*\|\s*(?P<i>\d+)/(?P<n>\d+)\s*"
    r"\[(?P<elapsed>[\d:]+)<(?P<eta>[\d:?]+),\s*(?P<rate>[\d.]+)(?P<unit>it/s|s/it)"
)
# "                   all       3550       9679      0.584       0.53      0.544      0.316"
VALIDATION = re.compile(
    r"^\s*all\s+(?P<images>\d+)\s+(?P<inst>\d+)\s+"
    r"(?P<p>[\d.]+)\s+(?P<r>[\d.]+)\s+(?P<map50>[\d.]+)\s+(?P<map>[\d.]+)\s*$"
)
ANSI = re.compile(r"\x1b\[[0-9;]*m")

STATE: dict = {"snapshot": None, "error": None, "updated": 0.0}
LOCK = threading.Lock()


def _ssh(cmd: str, timeout: int = 30) -> str:
    """One command over a shared connection.

    ControlMaster keeps a single TCP session open, so a poll every few seconds
    costs a round trip rather than a full SSH handshake.
    """
    ctl = ["-o", "ControlMaster=auto", "-o", f"ControlPath={CONTROL_PATH}",
           "-o", "ControlPersist=120"]
    r = subprocess.run(SSH[:1] + ctl + SSH[1:] + [cmd],
                       capture_output=True, text=True, timeout=timeout)
    return r.stdout


def poll_once() -> dict:
    """Read the *tail* of the current log rather than following it.

    An earlier version streamed `tail -f` and parsed line by line. Ultralytics
    redraws its progress bar with carriage returns, so a single "line" can hold
    thousands of updates, and any per-line work makes the reader fall behind the
    writer -- it drifted hours out of date while still reporting fresh data,
    because it was parsing a backlog. Asking for the last few kB each time
    cannot lag: whatever comes back is the current state of the file.
    """
    out = _ssh(
        "L=$(ls -t /workspace/yolo11*_*.log 2>/dev/null | head -1); "
        "echo \"JOB:$(basename ${L:-none} .log)\"; "
        "echo GPU:$(nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total,"
        "temperature.gpu --format=csv,noheader,nounits | head -1); "
        "[ -n \"$L\" ] && { echo ---PROGRESS---; tail -c 4000 \"$L\"; "
        "echo; echo ---VALIDATION---; tr '\\r' '\\n' < \"$L\" | grep -E '^ +all ' | tail -1; }"
    )
    if not out.strip():
        raise RuntimeError("no response from the training host")

    job = gpu = None
    progress = validation = None
    body = out
    for line in out.splitlines():
        if line.startswith("JOB:"):
            job = line[4:].strip() or None
        elif line.startswith("GPU:"):
            parts = [x.strip() for x in line[4:].split(",")]
            if len(parts) >= 4 and parts[0].isdigit():
                gpu = {"util": int(parts[0]), "used_gb": round(int(parts[1]) / 1024, 1),
                       "total_gb": round(int(parts[2]) / 1024, 1), "temp": int(parts[3])}

    if "---PROGRESS---" in body:
        chunk = body.split("---PROGRESS---", 1)[1]
        val_part = ""
        if "---VALIDATION---" in chunk:
            chunk, val_part = chunk.split("---VALIDATION---", 1)
        # last progress update in the tail wins
        for piece in ANSI.sub("", chunk).replace("\r", "\n").splitlines():
            if m := PROGRESS.match(piece):
                progress = m.groupdict()
        for piece in ANSI.sub("", val_part).splitlines():
            if m := VALIDATION.match(piece):
                validation = m.groupdict()

    return {"job": job, "gpu": gpu, "progress": progress, "metrics": validation}


def poller(interval: int) -> None:
    while True:
        try:
            snap = poll_once()
            with LOCK:
                STATE.update(snapshot=snap, error=None, updated=time.time())
        except Exception as exc:
            with LOCK:
                STATE["error"] = f"{type(exc).__name__}: {exc}"[:160]
        time.sleep(interval)


def snapshot() -> dict:
    with LOCK:
        snap = STATE.get("snapshot") or {}
        err = STATE.get("error")
        updated = STATE.get("updated") or 0.0

    p, m = snap.get("progress"), snap.get("metrics")
    out = {
        "job": snap.get("job"),
        "error": err,
        "stale_s": round(time.time() - updated) if updated else None,
        "gpu": snap.get("gpu"),
        "now": datetime.now(timezone.utc).astimezone().strftime("%H:%M:%S"),
    }
    if p:
        epoch, epochs = int(p["epoch"]), int(p["epochs"])
        rate = float(p["rate"])
        per_iter = 1 / rate if p["unit"] == "it/s" else rate
        left_epoch = (int(p["n"]) - int(p["i"])) * per_iter
        out["progress"] = {
            "epoch": epoch, "epochs": epochs,
            "pct_epoch": int(p["pct"]),
            "pct_run": round(100 * (epoch - 1 + int(p["i"]) / int(p["n"])) / epochs, 1),
            "iter": f'{p["i"]}/{p["n"]}',
            "eta_epoch": p["eta"],
            "rate": f'{rate:.2f} {p["unit"]}',
            "mem_gb": float(p["mem"]),
            "loss": {"box": float(p["box"]), "cls": float(p["cls"]), "dfl": float(p["dfl"])},
            # remaining epochs at the current pace; patience usually cuts it short
            "eta_run_h": round((left_epoch + (epochs - epoch) * int(p["n"]) * per_iter) / 3600, 1),
        }
    if m:
        out["metrics"] = {k: float(v) for k, v in m.items()}
    return out


PAGE = """<!doctype html><html lang="uz"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Smart Road — trening</title><style>
:root{color-scheme:light;--surface:#fff;--plane:#f4f4f1;--ink:#0b0b0b;--ink2:#52514e;
--muted:#8a8880;--line:rgba(11,11,11,.09);--accent:#2a78d6;--ok:#0ca30c;--warn:#ec835a;
--track:#edece7;--shadow:0 1px 2px rgba(11,11,11,.04),0 8px 24px rgba(11,11,11,.05)}
@media(prefers-color-scheme:dark){:root{color-scheme:dark;--surface:#1a1a19;--plane:#0d0d0d;
--ink:#f7f7f4;--ink2:#c3c2b7;--muted:#8a8880;--line:rgba(255,255,255,.10);--accent:#3987e5;
--ok:#0ca30c;--warn:#ec835a;--track:#262625;--shadow:none}}
*{box-sizing:border-box}
body{margin:0;background:var(--plane);color:var(--ink);-webkit-font-smoothing:antialiased;
font:15px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif}
.wrap{max-width:620px;margin:0 auto;padding:28px 16px 56px}
header{display:flex;align-items:baseline;justify-content:space-between;gap:12px;margin-bottom:18px}
h1{font-size:20px;margin:0;letter-spacing:-.02em;font-weight:640}
.clock{color:var(--muted);font-size:13px;font-variant-numeric:tabular-nums}
.card{background:var(--surface);border:1px solid var(--line);border-radius:16px;
padding:20px;margin-bottom:14px;box-shadow:var(--shadow)}
.job{color:var(--ink2);font-size:13px;margin-bottom:14px}
.dot{display:inline-block;width:8px;height:8px;border-radius:50%;background:var(--ok);
margin-right:7px;vertical-align:1px}
.dot.stale{background:var(--warn)}
.big{font-size:32px;letter-spacing:-.025em;font-weight:600;line-height:1.1}
.sub{color:var(--muted);font-size:12.5px;margin-top:3px}
.bar{height:8px;background:var(--track);border-radius:99px;overflow:hidden;margin:14px 0 6px}
.bar i{display:block;height:100%;background:var(--accent);border-radius:99px;
transition:width .6s ease}
.row{display:flex;justify-content:space-between;font-size:13px;color:var(--ink2);
font-variant-numeric:tabular-nums}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:14px}
.k{color:var(--muted);font-size:12px;letter-spacing:.02em}
.v{font-size:21px;letter-spacing:-.02em;margin-top:2px;font-variant-numeric:tabular-nums}
a.report{display:block;text-align:center;padding:13px;border:1px solid var(--line);
border-radius:12px;color:var(--accent);text-decoration:none;background:var(--surface);
font-size:14px}
.err{color:var(--warn);font-size:13.5px}
</style></head><body><div class="wrap">
<header><h1>Trening</h1><span class="clock" id="clock">—</span></header>
<div id="main"></div>
<a class="report" href="/report">To'liq hisobotni ochish →</a>
</div>
<script>
const REFRESH = REFRESH_MS;
const esc = s => String(s).replace(/[<>&]/g, c => ({'<':'&lt;','>':'&gt;','&':'&amp;'}[c]));
function card(inner){ return '<div class="card">'+inner+'</div>'; }
function render(d){
  document.getElementById('clock').textContent = d.now;
  let h = '';
  if (d.error) h += card('<div class="err">⚠ '+esc(d.error)+'</div>');
  const stale = d.stale_s !== null && d.stale_s > 180;
  if (d.progress){
    const p = d.progress;
    h += card(
      '<div class="job"><span class="dot'+(stale?' stale':'')+'"></span>'+esc(d.job||'')+
        (stale?' · '+d.stale_s+'s jim':'')+'</div>'+
      '<div class="big">'+p.epoch+' <span style="font-size:18px;color:var(--muted)">/ '+p.epochs+'</span></div>'+
      '<div class="sub">epoch · '+p.pct_run+'% umumiy</div>'+
      '<div class="bar"><i style="width:'+p.pct_epoch+'%"></i></div>'+
      '<div class="row"><span>'+esc(p.iter)+'</span><span>'+esc(p.eta_epoch)+' qoldi</span></div>'+
      '<div class="row" style="margin-top:4px"><span>'+esc(p.rate)+'</span>'+
        '<span>~'+p.eta_run_h+' soat to\\'liq</span></div>');
  }
  if (d.metrics){
    const m = d.metrics;
    h += card('<div class="grid">'+
      '<div><div class="k">mAP<sub>50</sub></div><div class="v">'+m.map50.toFixed(3)+'</div></div>'+
      '<div><div class="k">mAP<sub>50-95</sub></div><div class="v">'+m.map.toFixed(3)+'</div></div>'+
      '<div><div class="k">Aniqlik</div><div class="v">'+m.p.toFixed(3)+'</div></div>'+
      '<div><div class="k">To\\'liqlik</div><div class="v">'+m.r.toFixed(3)+'</div></div>'+
      '</div>');
  }
  if (d.gpu){
    const g = d.gpu;
    h += card('<div class="grid">'+
      '<div><div class="k">GPU</div><div class="v">'+g.util+'%</div></div>'+
      '<div><div class="k">Xotira</div><div class="v">'+g.used_gb+'<span style="font-size:13px;color:var(--muted)"> / '+g.total_gb+' GB</span></div></div>'+
      '<div><div class="k">Harorat</div><div class="v">'+g.temp+'°</div></div>'+
      '</div>');
  }
  if (!h) h = card('<div class="sub">Ma\\'lumot kutilmoqda…</div>');
  document.getElementById('main').innerHTML = h;
}
async function tick(){
  try { render(await (await fetch('/api/status',{cache:'no-store'})).json()); }
  catch(e){ /* keep the last good view rather than blanking the page */ }
}
tick(); setInterval(tick, REFRESH);
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    interval_ms = 15000

    def _send(self, body: bytes, ctype: str, code: int = 200) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path.startswith("/api/status"):
            self._send(json.dumps(snapshot()).encode(), "application/json")
        elif self.path.startswith("/report"):
            if REPORT.exists():
                self._send(REPORT.read_bytes(), "text/html; charset=utf-8")
            else:
                self._send(b"report not generated yet", "text/plain; charset=utf-8", 404)
        elif self.path in ("/", "/index.html"):
            page = PAGE.replace("REFRESH_MS", str(self.interval_ms))
            self._send(page.encode(), "text/html; charset=utf-8")
        else:
            self._send(b"not found", "text/plain; charset=utf-8", 404)

    def log_message(self, *_args) -> None:
        pass  # keep the console clear for the tunnel URL


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--port", type=int, default=8899)
    ap.add_argument("--interval", type=int, default=15,
                    help="seconds between refreshes; an epoch takes minutes, "
                         "so anything under ~10 s only costs SSH round trips")
    args = ap.parse_args()

    Handler.interval_ms = args.interval * 1000
    threading.Thread(target=poller, args=(args.interval,), daemon=True).start()

    print(f"dashboard on http://localhost:{args.port}  (refresh {args.interval}s)")
    ThreadingHTTPServer(("0.0.0.0", args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
