#!/usr/bin/env python3
"""Render a training report from a downloaded Kaggle kernel output.

Self-contained HTML with inline SVG -- no CDN, no build step -- so it can be
opened straight from disk, attached to an email, or published as-is.

Usage:
    python -m smartroad.report.build_report /tmp/kout5 -o reports/training.html
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
from pathlib import Path

from .parse_results import ClassMetrics, RunMetrics, load_all

# Validated against scripts/validate_palette.js in both modes (all checks pass).
SERIES = ["#2a78d6", "#eb6834"]
SERIES_DARK = ["#3987e5", "#d95926"]

#: Uzbek labels for the pavement engineer reading this.
CLASS_UZ = {
    "longitudinal_transverse_crack": "Bo'ylama va ko'ndalang yoriq",
    "alligator_crack": "To'rsimon (charchoq) yoriq",
    "block_crack": "Bloksimon yoriq",
    "patching": "Yamoq va quduq kesimi",
    "pothole": "Chuqurcha",
    "weathering_raveling": "Yemirilish / tishlashish",
    "lane_shoulder_drop_off": "Chekka pasayishi",
    "marking_manhole": "Yo'l belgisi / quduq",
}
ASTM_NO = {
    "longitudinal_transverse_crack": 10,
    "alligator_crack": 1,
    "block_crack": 3,
    "patching": 11,
    "pothole": 13,
    "weathering_raveling": 19,
    "lane_shoulder_drop_off": 9,
}


def esc(s) -> str:
    return html.escape(str(s), quote=True)


def bar_chart(classes: list[ClassMetrics], train_counts: dict[str, int]) -> str:
    """Horizontal bars: one measure across categories, so length carries
    magnitude and every bar keeps the same hue. Identity lives on the axis."""
    rows = sorted(classes, key=lambda c: c.map50, reverse=True)
    row_h, gap, label_w, pad = 34, 10, 250, 8
    width, plot_w = 860, 860 - 250 - 70
    height = len(rows) * (row_h + gap) + 30

    parts = [f'<svg viewBox="0 0 {width} {height}" role="img" '
             f'aria-label="Har bir nuqson turi uchun mAP50" class="chart">']
    for i, c in enumerate(rows):
        y = i * (row_h + gap)
        w = max(2.0, c.map50 * plot_w)
        n_train = train_counts.get(c.name, 0)
        weak = n_train < 500
        uz = CLASS_UZ.get(c.name, c.name)
        astm = ASTM_NO.get(c.name)
        tag = f"ASTM {astm}" if astm else "PCI'ga kirmaydi"
        parts.append(
            f'<g class="row" tabindex="0">'
            f'<title>{esc(uz)} — mAP50 {c.map50:.3f}, mAP50-95 {c.map50_95:.3f}, '
            f'aniqlik {c.precision:.3f}, to\'liqlik {c.recall:.3f}; '
            f'{n_train} ta o\'quv annotatsiyasi</title>'
            f'<text x="{label_w - 12}" y="{y + row_h/2 + 1}" class="cat" '
            f'text-anchor="end" dominant-baseline="middle">{esc(uz)}</text>'
            f'<text x="{label_w - 12}" y="{y + row_h/2 + 14}" class="sub" '
            f'text-anchor="end" dominant-baseline="middle">{esc(tag)} · {n_train:,} annotatsiya</text>'
            f'<rect x="{label_w}" y="{y + 6}" width="{plot_w}" height="{row_h - 12}" '
            f'class="track" rx="4"/>'
            f'<rect x="{label_w}" y="{y + 6}" width="{w:.1f}" height="{row_h - 12}" '
            f'class="bar{" weak" if weak else ""}" rx="4"/>'
            f'<text x="{label_w + w + 10:.1f}" y="{y + row_h/2}" class="val" '
            f'dominant-baseline="middle">{c.map50:.3f}</text>'
            f'</g>'
        )
    parts.append("</svg>")
    return "".join(parts)


def line_chart(runs: list[RunMetrics], key: str, title: str) -> str:
    """mAP over epochs for both models. Two series, so legend plus a direct
    label at each line's end -- identity is never colour alone."""
    series = [r for r in runs if r.curve]
    if not series:
        return '<p class="empty">Epoch bo\'yicha ma\'lumot yo\'q.</p>'

    width, height = 860, 300
    left, right, top, bottom = 52, 130, 18, 34
    pw, ph = width - left - right, height - top - bottom
    max_ep = max(len(r.curve) for r in series)
    top_v = max(max((p[key] for p in r.curve), default=0.0) for r in series)
    top_v = max(0.1, top_v * 1.15)

    def x(e):
        return left + (pw * (e - 1) / max(1, max_ep - 1))

    def y(v):
        return top + ph - (ph * v / top_v)

    parts = [f'<svg viewBox="0 0 {width} {height}" role="img" '
             f'aria-label="{esc(title)}" class="chart">']
    for frac in (0, 0.25, 0.5, 0.75, 1.0):
        gy = top + ph - ph * frac
        parts.append(f'<line x1="{left}" x2="{left+pw}" y1="{gy:.1f}" y2="{gy:.1f}" class="grid"/>')
        parts.append(f'<text x="{left-10}" y="{gy:.1f}" class="tick" text-anchor="end" '
                     f'dominant-baseline="middle">{top_v*frac:.2f}</text>')
    for e in range(1, max_ep + 1, max(1, max_ep // 8)):
        parts.append(f'<text x="{x(e):.1f}" y="{top+ph+20}" class="tick" '
                     f'text-anchor="middle">{e}</text>')
    parts.append(f'<text x="{left+pw/2}" y="{height-2}" class="axis-title" '
                 f'text-anchor="middle">epoch</text>')

    for i, run in enumerate(series):
        pts = " ".join(f"{x(p['epoch']):.1f},{y(p[key]):.1f}" for p in run.curve)
        parts.append(f'<polyline points="{pts}" class="line s{i}" fill="none"/>')
        last = run.curve[-1]
        parts.append(f'<circle cx="{x(last["epoch"]):.1f}" cy="{y(last[key]):.1f}" '
                     f'r="5" class="dot s{i}"/>')
        parts.append(f'<text x="{x(last["epoch"])+12:.1f}" y="{y(last[key]):.1f}" '
                     f'class="endlabel s{i}" dominant-baseline="middle">'
                     f'{esc(run.name)} · {last[key]:.3f}</text>')
    parts.append("</svg>")
    return "".join(parts)


def stat_tiles(runs: list[RunMetrics], n_train: int, n_val: int) -> str:
    best = max((r for r in runs if r.overall), key=lambda r: r.overall.map50, default=None)
    if not best:
        return ""
    o = best.overall
    tiles = [
        ("mAP<sub>50</sub>", f"{o.map50:.3f}", f"eng yaxshi model: {best.name}"),
        ("mAP<sub>50-95</sub>", f"{o.map50_95:.3f}", "qat'iyroq mezon"),
        ("Aniqlik / To'liqlik", f"{o.precision:.2f} / {o.recall:.2f}", "precision / recall"),
        ("Annotatsiyalar", f"{n_train:,}", f"{n_val:,} ta tekshiruv rasmi"),
    ]
    return "".join(
        f'<div class="tile"><div class="tile-label">{lab}</div>'
        f'<div class="tile-value">{esc(val)}</div>'
        f'<div class="tile-sub">{esc(sub)}</div></div>'
        for lab, val, sub in tiles
    )


def table(classes: list[ClassMetrics], train_counts: dict[str, int]) -> str:
    head = ("<tr><th>Nuqson</th><th>ASTM</th><th class='n'>Annotatsiya</th>"
            "<th class='n'>mAP50</th><th class='n'>mAP50-95</th>"
            "<th class='n'>Aniqlik</th><th class='n'>To'liqlik</th></tr>")
    rows = []
    for c in sorted(classes, key=lambda c: c.map50, reverse=True):
        astm = ASTM_NO.get(c.name)
        rows.append(
            f"<tr><td>{esc(CLASS_UZ.get(c.name, c.name))}</td>"
            f"<td>{astm if astm else '—'}</td>"
            f"<td class='n'>{train_counts.get(c.name, 0):,}</td>"
            f"<td class='n'>{c.map50:.3f}</td><td class='n'>{c.map50_95:.3f}</td>"
            f"<td class='n'>{c.precision:.3f}</td><td class='n'>{c.recall:.3f}</td></tr>"
        )
    return f"<table>{head}{''.join(rows)}</table>"


CSS = """
/* Declared on :root, not on .viz-root. body sits *above* .viz-root, and custom
   properties only inherit downwards -- scoping them to the wrapper left
   body{color:var(--text-primary)} resolving to nothing, so every heading that
   inherited from body came out near-black on the dark surface. */
:root{color-scheme:light;--surface-1:#ffffff;--plane:#f4f4f1;--text-primary:#0b0b0b;
--text-secondary:#52514e;--muted:#8a8880;--grid:#e6e5df;--baseline:#c3c2b7;
--border:rgba(11,11,11,.09);--s0:#2a78d6;--s1:#eb6834;--track:#edece7;--warn:#ec835a;
--shadow:0 1px 2px rgba(11,11,11,.04),0 8px 24px rgba(11,11,11,.05)}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){
color-scheme:dark;--surface-1:#1a1a19;--plane:#0d0d0d;--text-primary:#f7f7f4;
--text-secondary:#c3c2b7;--muted:#8a8880;--grid:#2c2c2a;--baseline:#383835;
--border:rgba(255,255,255,.10);--s0:#3987e5;--s1:#d95926;--track:#262625;--warn:#ec835a;
--shadow:none}}
:root[data-theme=dark]{color-scheme:dark;--surface-1:#1a1a19;--plane:#0d0d0d;
--text-primary:#f7f7f4;--text-secondary:#c3c2b7;--muted:#8a8880;--grid:#2c2c2a;
--baseline:#383835;--border:rgba(255,255,255,.10);--s0:#3987e5;--s1:#d95926;
--track:#262625;--warn:#ec835a;--shadow:none}
*{box-sizing:border-box}
body{margin:0;background:var(--plane);color:var(--text-primary);
-webkit-font-smoothing:antialiased;
font:15px/1.6 system-ui,-apple-system,"Segoe UI",sans-serif}
.viz-root{max-width:940px;margin:0 auto;padding:56px 20px 80px;color:var(--text-primary)}
header{margin-bottom:36px}
h1{font-size:32px;line-height:1.15;margin:0 0 10px;letter-spacing:-.025em;
color:var(--text-primary);font-weight:640}
.lede{color:var(--text-secondary);margin:0;font-size:16px;max-width:64ch}
.meta{color:var(--muted);font-size:13px;margin-top:10px}
section{background:var(--surface-1);border:1px solid var(--border);border-radius:16px;
padding:26px 28px;margin:18px 0;box-shadow:var(--shadow)}
h2{font-size:17px;margin:0 0 4px;letter-spacing:-.012em;color:var(--text-primary);
font-weight:620}
.note{color:var(--text-secondary);font-size:14px;margin:0 0 18px;max-width:70ch}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin:0}
.tile{background:var(--surface-1);border:1px solid var(--border);border-radius:14px;
padding:18px 20px;box-shadow:var(--shadow)}
.tile-label{color:var(--text-secondary);font-size:12.5px;letter-spacing:.02em}
.tile-value{font-size:32px;line-height:1.1;margin:8px 0 3px;letter-spacing:-.025em;
color:var(--text-primary);font-weight:600}
.tile-sub{color:var(--muted);font-size:12px}
.chart{width:100%;height:auto;display:block;overflow:visible}
.cat{fill:var(--text-primary);font-size:13.5px}
.sub{fill:var(--muted);font-size:11px}
.val{fill:var(--text-secondary);font-size:12.5px;font-variant-numeric:tabular-nums}
.track{fill:var(--track)}
.bar{fill:var(--s0)}
.bar.weak{fill:var(--warn)}
.row:hover .bar,.row:focus .bar{opacity:.82}
.row:focus{outline:none}
.row:focus .cat{text-decoration:underline}
.grid{stroke:var(--grid);stroke-width:1}
.tick{fill:var(--muted);font-size:11px;font-variant-numeric:tabular-nums}
.axis-title{fill:var(--muted);font-size:11.5px}
.line{stroke-width:2;stroke-linecap:round;stroke-linejoin:round}
.line.s0,.dot.s0{stroke:var(--s0)}.dot.s0{fill:var(--s0)}
.line.s1,.dot.s1{stroke:var(--s1)}.dot.s1{fill:var(--s1)}
.dot{stroke-width:2;stroke:var(--surface-1)}
.endlabel{font-size:12px;fill:var(--text-secondary)}
.legend{display:flex;gap:18px;flex-wrap:wrap;margin:0 0 14px;font-size:13px;
color:var(--text-secondary)}
.legend span{display:inline-flex;align-items:center;gap:7px}
.swatch{width:11px;height:11px;border-radius:3px;display:inline-block}
.wrap{overflow-x:auto}
table{border-collapse:collapse;width:100%;font-size:13.5px;min-width:620px}
th,td{text-align:left;padding:9px 12px;border-bottom:1px solid var(--border)}
th{color:var(--text-secondary);font-weight:600;font-size:12.5px}
td.n,th.n{text-align:right;font-variant-numeric:tabular-nums}
.callout{border-left:3px solid var(--warn);padding:14px 18px;background:var(--surface-1);
border-radius:0 10px 10px 0;margin:18px 0 0}
.callout h3{margin:0 0 6px;font-size:14.5px}
.callout p{margin:8px 0 0;color:var(--text-secondary);font-size:14px}
.callout ul{margin:0;padding-left:20px;color:var(--text-secondary);font-size:14px}
.callout li{margin:4px 0}
.empty{color:var(--muted)}
footer{color:var(--muted);font-size:12.5px;margin-top:28px;text-align:center}
"""


def render(runs: list[RunMetrics], train_counts: dict[str, int],
           n_train: int, n_val: int, hardware: str = "") -> str:
    best = max((r for r in runs if r.overall), key=lambda r: r.overall.map50, default=None)
    classes = best.per_class if best else []
    # Flag anything a reader would query: too little data to judge, or plenty
    # of data and still poor. Each gets its own reason rather than one blanket
    # caveat, because the causes are different and the fixes are different.
    def _concern(c):
        n = train_counts.get(c.name, 0)
        if n < 500:
            return f"atigi {n} ta o'quv annotatsiyasi — natija ishonchli emas"
        if c.recall < 0.25:
            return (f"ma'lumot yetarli ({n:,}), lekin model ularning "
                    f"{c.recall*100:.0f}% ini topmoqda — yuza bo'ylab tarqalgan "
                    f"naqsh 640-1024 px ga siqilganda yo'qoladi")
        if c.map50 < 0.40:
            return f"aniqlik past (mAP50 {c.map50:.2f}) — qo'shimcha ma'lumot kerak"
        return None

    concerns = [(c, r) for c in classes if (r := _concern(c))]
    weak = [c for c in classes if train_counts.get(c.name, 0) < 500]
    today = dt.date.today().isoformat()

    legend = "".join(
        f'<span><i class="swatch" style="background:var(--s{i})"></i>{esc(r.name)}</span>'
        for i, r in enumerate(r for r in runs if r.curve)
    )
    weak_note = ""
    if concerns:
        items = "".join(
            f"<li><b>{esc(CLASS_UZ.get(c.name, c.name))}</b> — {esc(reason)}</li>"
            for c, reason in concerns
        )
        weak_note = (
            '<div class="callout"><h3>⚠ Ishonch bilan ishlatib bo\'lmaydigan klasslar</h3>'
            f'<ul>{items}</ul>'
            '<p>Bularning hammasi ma\'lumot cheklovi, model kamchiligi emas. '
            'Diagrammada kam ma\'lumotlilari boshqa rangda.</p></div>'
        )

    return f"""<div class="viz-root">
<header>
  <h1>Yo'l qoplamasi nuqsonlarini aniqlash — o'qitish natijalari</h1>
  <p class="lede">ASTM D6433 taksonomiyasiga keltirilgan 4 mamlakat ma'lumotlari asosida
  o'qitilgan detektor. Aniqlangan nuqsonlar keyingi bosqichda Pavement Condition Index (PCI)
  hisobiga kirish sifatida ishlatiladi.</p>
  <p class="meta">{esc(today)}{" · " + esc(hardware) if hardware else ""} · {n_train:,} o'quv annotatsiyasi · {n_val:,} tekshiruv rasmi</p>
</header>

<div class="tiles">{stat_tiles(runs, n_train, n_val)}</div>

<section>
  <h2>Nuqson turlari bo'yicha aniqlik</h2>
  <p class="note">mAP<sub>50</sub> — modelning har bir nuqson turini qanchalik ishonchli
  topishi. Har bir qator yonida ASTM D6433 dagi nuqson raqami va o'quv annotatsiyalari soni
  ko'rsatilgan.</p>
  {bar_chart(classes, train_counts) if classes else '<p class="empty">Ma\'lumot yo\'q.</p>'}
  {weak_note}
</section>

<section>
  <h2>O'qitish jarayoni</h2>
  <p class="note">Ikkala model bitta RTX 5090 da ketma-ket o'qitildi. Har ikkalasi ham
  150 epochga qo'yilgan edi, lekin <code>patience=30</code> bo'yicha erta to'xtadi:
  yolo11l_640 — 143 epoch (eng yaxshisi 113), yolo11m_1024 — 61 epoch (eng yaxshisi 31).</p>
  <div class="legend">{legend}</div>
  {line_chart(runs, "map50", "mAP50 epoch bo'yicha")}
</section>

<section>
  <h2>To'liq jadval</h2>
  <div class="wrap">{table(classes, train_counts) if classes else ''}</div>
</section>

<footer>Smart Road · ASTM D6433 Pavement Condition Index</footer>
</div>"""


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("output_dir", type=Path, help="downloaded Kaggle kernel output")
    ap.add_argument("-o", "--out", type=Path, default=Path("reports/training.html"))
    ap.add_argument("--counts", type=Path, help="JSON of {class: train box count}")
    ap.add_argument("--hardware", default="",
                    help="e.g. 'vast.ai, RTX 5090' -- shown in the header")
    ap.add_argument("--fragment", action="store_true",
                    help="emit body only, for embedding (e.g. an Artifact)")
    args = ap.parse_args()

    runs = load_all(args.output_dir)
    if not runs:
        raise SystemExit(f"no runs found under {args.output_dir}/runs")
    counts = json.loads(args.counts.read_text()) if args.counts else {}

    best = max((r for r in runs if r.overall), key=lambda r: r.overall.map50, default=None)
    n_val = best.overall.images if best else 0

    args.out.parent.mkdir(parents=True, exist_ok=True)
    body = render(runs, counts, sum(counts.values()) if counts else 0, n_val, args.hardware)
    inner = f"<style>{CSS}</style>\n{body}\n"
    if args.fragment:
        # For publishing as an Artifact, which supplies its own <head>.
        args.out.write_text(inner, encoding="utf-8")
    else:
        args.out.write_text(
            '<!doctype html>\n<html lang="uz">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
            "<title>Smart Road - o'qitish natijalari</title>\n</head>\n<body>\n"
            + inner + "</body>\n</html>\n",
            encoding="utf-8",
        )
    print(f"wrote {args.out}")
    for r in runs:
        o = r.overall
        print(f"  {r.name}: {r.epochs} epochs" + (f", mAP50 {o.map50:.3f}" if o else ""))


if __name__ == "__main__":
    main()
